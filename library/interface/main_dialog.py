# Chemin : library/interface/main_dialog.py
# -*- coding: utf-8 -*-
# Path: Library/interface/main_dialog.py
"""Dialogue principal de Library avec gestion intelligente des vignettes"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import os
import time
import traceback
import zipfile
import base64
from io import BytesIO

from ..config import load_config, save_config
from ..library import (
    scan_library, create_folder, rename_item, delete_item, cleanup_temp_files
)
from ..core.detection import (
    CONTEXT_NONE, CONTEXT_DRAFT, CONTEXT_BODY, CONTEXT_PROFILE, CONTEXT_LINK,
    analyze_selection, get_available_actions,
    is_draft_body, is_profile_part, analyze_body
)
from ..templates import create_new_profile_from_template

def safe_save(doc, path=None):
    """Tente de sauvegarder le document avec retry en cas de lock."""
    filepath = path or doc.FileName
    if not filepath:
        return False, "Aucun chemin de fichier défini"
    for i in range(3):
        try:
            doc.save()
            return True, "Sauvegardé"
        except Exception as e:
            err_msg = str(e)
            if "rename temporary file" in err_msg or "Permission denied" in err_msg:
                if i < 2:
                    time.sleep(0.5)
                    continue
            return False, "Erreur sauvegarde: " + err_msg
    return False, "Echec sauvegarde"

def get_open_document_by_path(file_path):
    """Retourne un document FreeCAD déjà ouvert correspondant au chemin donné."""
    if not file_path or not os.path.exists(file_path):
        return None

    abs_path = os.path.abspath(os.path.normpath(file_path))

    for doc_name, doc in App.listDocuments().items():
        if doc.FileName:
            doc_path = os.path.abspath(os.path.normpath(doc.FileName))
            if doc_path == abs_path:
                return doc
    return None

class ThumbnailCache:
    def __init__(self, max_size=50):
        self.cache = {}
        self.max_size = max_size

    def get(self, file_path):
        return self.cache.get(file_path)

    def set(self, file_path, pixmap):
        if len(self.cache) >= self.max_size:
            del self.cache[next(iter(self.cache))]
        self.cache[file_path] = pixmap

class LibraryDialog(QtGui.QDialog):
    def __init__(self, parent=None, active_doc=None):
        super(LibraryDialog, self).__init__(parent or Gui.getMainWindow())
        self.setWindowTitle("Library - Gestionnaire de composants")
        self.setMinimumSize(900, 650)
        self.config = load_config()
        self.thumbnail_cache = ThumbnailCache()
        self.file_kind_cache = {}
        self._info_panel_locked = False
        self.locked_item_data = None
        self.selected_file_analysis = None
        self.active_doc_at_start = active_doc or App.ActiveDocument

        lp = self.config.get('user_library_path', '')
        if lp and os.path.exists(lp):
            cleanup_temp_files(lp)

        self.setup_ui()
        self.load_library()

        self.context_timer = QtCore.QTimer(self)
        self.context_timer.timeout.connect(self.update_context)
        self.context_timer.start(1000)

        # Désactiver la mise à jour de la vignette principale au survol
        self.tree.itemEntered.disconnect()
        self.tree.itemEntered.connect(self.on_item_hovered_tooltip)

    def setup_ui(self):
        main_layout = QtGui.QVBoxLayout(self)
        path_layout = QtGui.QHBoxLayout()
        self.label_library_path = QtGui.QLabel(self.config.get('user_library_path', '') or "<non définie>")
        self.label_library_path.setStyleSheet("color:#0066cc; font-weight: bold;")
        path_layout.addWidget(QtGui.QLabel("Bibliothèque:"))
        path_layout.addWidget(self.label_library_path, 1)
        btn_change = QtGui.QPushButton("Modifier...")
        btn_change.setMaximumWidth(100)
        btn_change.clicked.connect(self.browse_library_path)
        path_layout.addWidget(btn_change)
        main_layout.addLayout(path_layout)

        splitter = QtGui.QSplitter(QtCore.Qt.Horizontal)

        left_widget = QtGui.QWidget()
        left_layout = QtGui.QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        toolbar = QtGui.QHBoxLayout()
        self.btn_new_folder = QtGui.QPushButton("Nouveau dossier")
        self.btn_new_folder.clicked.connect(self.on_new_folder)
        toolbar.addWidget(self.btn_new_folder)

        self.btn_rename = QtGui.QPushButton("Renommer")
        self.btn_rename.clicked.connect(self.on_rename)
        toolbar.addWidget(self.btn_rename)

        self.btn_delete = QtGui.QPushButton("Supprimer")
        self.btn_delete.clicked.connect(self.on_delete)
        toolbar.addWidget(self.btn_delete)

        toolbar.addStretch()

        self.btn_migrate = QtGui.QPushButton("Migrer les profils")
        self.btn_migrate.setToolTip("Met à jour tous les templates de la bibliothèque\n"
                                     "(masquage propriétés, CopyOnChange, nettoyage)")
        self.btn_migrate.clicked.connect(self.on_migrate_all)
        toolbar.addWidget(self.btn_migrate)

        self.btn_refresh = QtGui.QPushButton("Actualiser")
        self.btn_refresh.clicked.connect(self.load_library)
        toolbar.addWidget(self.btn_refresh)

        left_layout.addLayout(toolbar)

        self.tree = QtGui.QTreeWidget()
        self.tree.setHeaderLabels(["Nom"])
        self.tree.setColumnWidth(0, 450)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemClicked.connect(self.on_item_clicked)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.currentItemChanged.connect(self.on_current_item_changed)
        self.tree.setMouseTracking(True)
        self.tree.itemEntered.connect(self.on_item_hovered_tooltip)

        left_layout.addWidget(self.tree)
        splitter.addWidget(left_widget)

        right_widget = QtGui.QWidget()
        right_layout = QtGui.QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        preview_group = QtGui.QGroupBox("Aperçu")
        preview_layout = QtGui.QVBoxLayout(preview_group)
        self.label_preview = QtGui.QLabel("Sélectionnez un profil dans la bibliothèque")
        self.label_preview.setMinimumSize(200, 150)
        self.label_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.label_preview.setStyleSheet("color:#666; font-style: italic;")
        preview_layout.addWidget(self.label_preview)
        right_layout.addWidget(preview_group)

        context_group = QtGui.QGroupBox("Contexte")
        context_layout = QtGui.QVBoxLayout(context_group)
        self.label_context = QtGui.QLabel("Aucune sélection dans la bibliothèque")
        self.label_context.setWordWrap(True)
        context_layout.addWidget(self.label_context)
        self.context_buttons_layout = QtGui.QVBoxLayout()
        context_layout.addLayout(self.context_buttons_layout)
        right_layout.addWidget(context_group)

        right_layout.addStretch()
        splitter.addWidget(right_widget)

        splitter.setSizes([600, 300])
        main_layout.addWidget(splitter)

        status_layout = QtGui.QHBoxLayout()
        status_layout.addStretch()
        btn_close = QtGui.QPushButton("Fermer")
        btn_close.clicked.connect(self.close)
        status_layout.addWidget(btn_close)
        main_layout.addLayout(status_layout)

        self.update_buttons_state()

    def analyze_file_type(self, file_path):
        """Analyse un fichier .FCStd pour déterminer son type (draft/template)."""
        if file_path in self.file_kind_cache:
            return self.file_kind_cache[file_path]

        if not file_path or not file_path.lower().endswith('.fcstd'):
            result = {'is_draft': False, 'is_template': False, 'part': None, 'path': file_path}
            self.file_kind_cache[file_path] = result
            return result

        try:
            doc = get_open_document_by_path(file_path)
            was_already_open = doc is not None

            if not doc:
                doc = App.openDocument(file_path, hidden=True)

            if not doc:
                result = {'is_draft': False, 'is_template': False, 'part': None, 'path': file_path}
                self.file_kind_cache[file_path] = result
                return result

            result = {'is_draft': False, 'is_template': False, 'part': None, 'path': file_path, 'doc': doc}

            for obj in doc.Objects:
                if obj.TypeId == "PartDesign::Body":
                    if (hasattr(obj, 'profile_draft') and obj.profile_draft) or \
                       (hasattr(obj, 'draft') and obj.draft):
                        result['is_draft'] = True
                        break

            for obj in doc.Objects:
                if obj.TypeId == "App::Part" and hasattr(obj, 'profile') and obj.profile:
                    result['is_template'] = True
                    result['part'] = obj
                    break

            if not was_already_open:
                App.closeDocument(doc.Name)

            self.file_kind_cache[file_path] = result
            return result
        except Exception as e:
            print(f"Library- Erreur analyse fichier {file_path}: {e}")
            traceback.print_exc()
            result = {'is_draft': False, 'is_template': False, 'part': None, 'path': file_path}
            self.file_kind_cache[file_path] = result
            return result

    def update_context_buttons_for_selection(self):
        """Met à jour les boutons de contexte selon le fichier sélectionné dans l'arbre."""
        while self.context_buttons_layout.count():
            it = self.context_buttons_layout.takeAt(0)
            if it.widget():
                it.widget().deleteLater()

        if not self.selected_file_analysis:
            self.update_context()
            return

        analysis = self.selected_file_analysis
        actions = []

        if analysis['is_draft']:
            actions.append(('convert', "⚙️ Transformer en template", "Convertir ce draft en template de bibliothèque"))
        elif analysis['is_template']:
            actions.append(('edit_variants', "✏️ Éditer les variantes", "Modifier les variantes du profil"))

        actions.append(('insert', "📁 Insérer un profil", "Insérer ce profil dans le document actif"))
        actions.append(('create', "➕ Nouveau profil", "Créer un nouveau profil"))

        for aid, lbl, desc in actions:
            b = QtGui.QPushButton(lbl)
            b.setToolTip(desc)
            b.clicked.connect(lambda checked=False, a=aid: self.on_context_action_for_selection(a))
            self.context_buttons_layout.addWidget(b)

        if analysis['is_draft']:
            self.label_context.setText("✅ Draft de profil sélectionné\n(profile_draft = true)")
        elif analysis['is_template']:
            self.label_context.setText("✅ Template de profil sélectionné\n(profile = true)")
        else:
            self.label_context.setText("📄 Fichier sélectionné (non reconnu comme profil)")

    def on_context_action_for_selection(self, action_id):
        sel = self.tree.currentItem()
        if not sel: return
        data = sel.data(0, QtCore.Qt.UserRole)
        if not data or data['type'] != 'file': return

        path = data['path']

        if action_id == 'convert':
            try:
                doc = get_open_document_by_path(path)
                was_already_open = doc is not None

                if not doc:
                    doc = App.openDocument(path)

                if doc:
                    body = None
                    for obj in doc.Objects:
                        if obj.TypeId == "PartDesign::Body":
                            if (hasattr(obj, 'profile_draft') and obj.profile_draft) or \
                               (hasattr(obj, 'draft') and obj.draft):
                                body = obj
                                break

                    if body:
                        analysis = analyze_body(body)
                        from ..conversion.conversion_dialog import show_conversion_dialog
                        res, saved_path = show_conversion_dialog(body, analysis, self.config.get('user_library_path', ''), self)
                        if res and res.success and saved_path:
                            if path in self.file_kind_cache:
                                del self.file_kind_cache[path]
                            self.load_library()
                            self._open_post_conversion_dialogs(saved_path)
                        else:
                            # Fermer seulement si la conversion a échoué/annulée
                            if not was_already_open:
                                App.closeDocument(doc.Name)
            except Exception as e:
                print(f"Library- Erreur conversion: {e}")
                traceback.print_exc()
                QtGui.QMessageBox.critical(self, "Erreur", f"Impossible de convertir le draft:\n{str(e)}")

        elif action_id == 'edit_variants':
            from .variant_editor import show_variant_editor
            try:
                doc = get_open_document_by_path(path)
                was_already_open = doc is not None

                if not doc:
                    doc = App.openDocument(path)

                if doc:
                    part = None
                    for obj in doc.Objects:
                        if obj.TypeId == "App::Part" and hasattr(obj, 'profile') and obj.profile:
                            part = obj
                            break

                    if part and show_variant_editor(part, self):
                        doc.recompute()
                        ok, msg = safe_save(doc)
                        if ok:
                            if path in self.file_kind_cache:
                                del self.file_kind_cache[path]
                            self.load_library()

                        App.setActiveDocument(doc.Name)
                        Gui.ActiveDocument = Gui.getDocument(doc.Name)
                        Gui.updateGui()
            except Exception as e:
                print(f"Library- Erreur édition variantes: {e}")
                traceback.print_exc()
                QtGui.QMessageBox.critical(self, "Erreur", f"Impossible d'éditer les variantes:\n{str(e)}")

        elif action_id == 'insert':
            self.on_insert_profile()

        elif action_id == 'create':
            self.on_new_profile()

    def _open_post_conversion_dialogs(self, template_path):
        try:
            doc = get_open_document_by_path(template_path)
            was_already_open = doc is not None

            if not doc:
                doc = App.openDocument(template_path)

            if not doc:
                return

            part = next((o for o in doc.Objects if o.TypeId == "App::Part" and hasattr(o, 'profile') and o.profile), None)
            if not part:
                QtGui.QMessageBox.warning(self, "Erreur", "Part profil non trouvé dans le template")
                if not was_already_open:
                    App.closeDocument(doc.Name)
                return

            spreadsheet = next((o for o in part.Group if o.TypeId == "Spreadsheet::Sheet"), None)
            if not spreadsheet:
                QtGui.QMessageBox.warning(self, "Erreur", "Spreadsheet non trouvée dans le template")
                if not was_already_open:
                    App.closeDocument(doc.Name)
                return

            from .variant_editor import ProfileConfigDialog, show_variant_editor

            config_dlg = ProfileConfigDialog(part, spreadsheet, self)
            if config_dlg.exec_() == QtGui.QDialog.Accepted:
                if show_variant_editor(part, self):
                    doc.recompute()
                    doc.save()
                    print(f"Library- ✅ Configuration et variantes terminées pour {part.Label}")
                else:
                    doc.recompute()
                    doc.save()
            else:
                if not was_already_open:
                    App.closeDocument(doc.Name)
                return

            App.setActiveDocument(doc.Name)
            Gui.ActiveDocument = Gui.getDocument(doc.Name)
            Gui.updateGui()

            doc_name = doc.Name  # capture pour le closure
            def _apply_view():
                try:
                    App.setActiveDocument(doc_name)
                    gd = Gui.getDocument(doc_name)
                    if gd:
                        Gui.ActiveDocument = gd
                        Gui.updateGui()
                        Gui.runCommand('Std_ViewIsometric', 0)
                        Gui.runCommand('Std_ViewFitAll', 0)
                        print("Library- Vue isométrique et FitAll appliqués.")
                except Exception as e:
                    print(f"Library- Erreur apply_view: {e}")
            QtCore.QTimer.singleShot(800, _apply_view)

        except Exception as e:
            print(f"Library- Erreur dialogues post-conversion: {e}")
            traceback.print_exc()
            QtGui.QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir les dialogues de configuration:\n{str(e)}")

    def on_new_folder(self, parent_path=None):
        if not isinstance(parent_path, str):
            selected = self.tree.currentItem()
            if selected:
                data = selected.data(0, QtCore.Qt.UserRole)
                parent_path = data['path'] if data['type'] == 'folder' else os.path.dirname(data['path'])
            else:
                parent_path = self.config.get('user_library_path', '')

        name, ok = QtGui.QInputDialog.getText(self, "Nouveau dossier", "Nom:")
        if ok and name:
            ok, msg, p = create_folder(parent_path, name)
            if ok:
                self.load_library()
            else:
                QtGui.QMessageBox.warning(self, "Erreur", msg)

    def on_rename(self):
        sel = self.tree.currentItem()
        if not sel: return
        data = sel.data(0, QtCore.Qt.UserRole)
        name, ok = QtGui.QInputDialog.getText(self, "Renommer", "Nouveau nom:", text=data['name'])
        if ok and name and name != data['name']:
            ok, msg, p = rename_item(data['path'], name)
            if ok:
                if data['path'] in self.file_kind_cache:
                    del self.file_kind_cache[data['path']]
                self.load_library()
            else:
                QtGui.QMessageBox.warning(self, "Erreur", msg)

    def on_delete(self):
        sel = self.tree.currentItem()
        if not sel: return
        data = sel.data(0, QtCore.Qt.UserRole)
        reply = QtGui.QMessageBox.question(self, "Supprimer", f"Supprimer '{data['name']}'?",
                                          QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
        if reply == QtGui.QMessageBox.Yes:
            ok, msg = delete_item(data['path'], force=True)
            if ok:
                if data['path'] in self.file_kind_cache:
                    del self.file_kind_cache[data['path']]
                self.load_library()
            else:
                QtGui.QMessageBox.warning(self, "Erreur", msg)

    def open_file(self, path):
        try:
            doc = get_open_document_by_path(path)
            if doc:
                App.setActiveDocument(doc.Name)
                Gui.ActiveDocument = Gui.getDocument(doc.Name)
                Gui.updateGui()
                print(f"Library- ✅ Document déjà ouvert: {doc.Label}")
            else:
                App.openDocument(path)
        except Exception as e:
            QtGui.QMessageBox.critical(self, "Erreur", f"Impossible d'ouvrir le fichier:\n{str(e)}")

    def show_context_menu(self, position):
        item = self.tree.itemAt(position)
        menu = QtGui.QMenu()
        if item:
            data = item.data(0, QtCore.Qt.UserRole)
            if data['type'] == 'file':
                menu.addAction("Insérer", self.on_insert_profile)
                menu.addAction("Ouvrir", lambda: self.open_file(data['path']))
                menu.addSeparator()
                analysis = self.analyze_file_type(data['path'])
                if analysis['is_draft']:
                    menu.addAction("Transformer en template",
                                  lambda: self.on_context_action_for_selection('convert'))
                elif analysis['is_template']:
                    menu.addAction("Éditer les variantes",
                                  lambda: self.on_context_action_for_selection('edit_variants'))
            elif data['type'] == 'folder':
                menu.addAction("Nouveau profil ici", lambda: self.on_new_profile_in_folder(data['path']))
                menu.addAction("Nouveau dossier ici", lambda: self.on_new_folder(data['path']))
                menu.addSeparator()

            menu.addAction("Renommer", self.on_rename)
            menu.addAction("Supprimer", self.on_delete)
        else:
            menu.addAction("Nouveau profil", self.on_new_profile)
            menu.addAction("Nouveau dossier", self.on_new_folder)

        menu.exec_(self.tree.viewport().mapToGlobal(position))

    def on_new_profile_in_folder(self, folder_path):
        name, ok = QtGui.QInputDialog.getText(self, "Nouveau profil", "Nom:")
        if ok and name:
            dest_path = os.path.join(folder_path, name if name.lower().endswith('.fcstd') else name + '.FCStd')
            ok, msg, doc = create_new_profile_from_template(dest_path)
            if ok:
                self.load_library()
            else:
                QtGui.QMessageBox.critical(self, "Erreur", msg)

    def update_context(self):
        if self.selected_file_analysis is not None:
            return

        try:
            self.current_context = analyze_selection()
            self.label_context.setText(self.current_context['message'])

            while self.context_buttons_layout.count():
                it = self.context_buttons_layout.takeAt(0)
                if it.widget():
                    it.widget().deleteLater()

            actions = get_available_actions(self.current_context['context'])
            for aid, lbl, desc in actions:
                b = QtGui.QPushButton(lbl)
                b.setToolTip(desc)
                b.clicked.connect(lambda checked=False, a=aid: self.on_context_action(a))
                self.context_buttons_layout.addWidget(b)
        except Exception as e:
            traceback.print_exc()

    def on_context_action(self, action_id):
        actions = {
            'insert': self.on_insert_profile,
            'create': self.on_new_profile,
            'convert': self.on_convert_draft,
            'edit': self.on_edit_variants,
            'change_variant': self.on_change_variant
        }
        if action_id in actions:
            actions[action_id]()

    def on_edit_variants(self):
        if self.current_context and self.current_context['context'] == CONTEXT_PROFILE:
            part = self.current_context.get('object')
            if part:
                self._action_edit_file_variants(part.Document.FileName)

    def on_change_variant(self):
        if self.current_context and self.current_context['context'] == CONTEXT_LINK:
            link = self.current_context['object']
            if link and hasattr(link, 'LinkedObject'):
                part = link.LinkedObject
                if hasattr(part, 'Section'):
                    variants = list(part.getEnumerationsOfProperty('Section'))
                    current = link.Section if hasattr(link, 'Section') else part.Section[0]
                    v, ok = QtGui.QInputDialog.getItem(self, "Changer variante", f"Variante pour {link.Label}:",
                                                      variants, variants.index(current) if current in variants else 0, False)
                    if ok and v:
                        link.Section = v
                        App.ActiveDocument.recompute()

    def on_insert_profile(self):
        sel = self.tree.currentItem()
        if not sel: return
        data = sel.data(0, QtCore.Qt.UserRole)
        if not data or data['type'] != 'file': return

        from .insertion_dialog import show_insertion_dialog, insert_profile
        
        target_doc = self.active_doc_at_start
        if not target_doc:
            docs = sorted(
                [d for d in App.listDocuments().values() if d.FileName],
                key=lambda d: d.LastModifiedTime,
                reverse=True
            )
            target_doc = docs[0] if docs else None
        
        if not target_doc:
            QtGui.QMessageBox.critical(
                self, "Erreur", 
                "Aucun document actif détecté.\n\n"
                "1. Fermez cette fenêtre Library\n"
                "2. Cliquez dans la fenêtre 3D de votre document\n"
                "3. Réouvrez Library et réessayez"
            )
            return
        
        App.setActiveDocument(target_doc.Name)
        Gui.activateWorkbench('PartDesignWorkbench')
        Gui.updateGui()
        QtGui.QApplication.processEvents()
        
        # CORRECTION: Appel avec for_insertion=True pour simplifier l'interface
        params = show_insertion_dialog(data['path'], self, for_insertion=True)
        if params:
            ok, res = insert_profile(params, target_doc=target_doc)
            if not ok:
                QtGui.QMessageBox.critical(self, "Erreur", str(res))
            else:
                App.setActiveDocument(target_doc.Name)
                Gui.ActiveDocument = Gui.getDocument(target_doc.Name)
                Gui.updateGui()
                QtGui.QApplication.processEvents()

    def on_new_profile(self):
        lp = self.config.get('user_library_path', '')
        if not lp or not os.path.exists(lp):
            QtGui.QMessageBox.warning(self, "Action impossible", "Veuillez d'abord définir un dossier de bibliothèque valide.")
            return

        dlg = NewProfileDialog(lp, self)
        if dlg.exec_() == QtGui.QDialog.Accepted:
            dp = dlg.get_full_path()
            if os.path.exists(dp) and QtGui.QMessageBox.question(self, "Fichier existant", f"Le fichier '{os.path.basename(dp)}' existe déjà. Remplacer?", QtGui.QMessageBox.Yes | QtGui.QMessageBox.No) != QtGui.QMessageBox.Yes:
                return

            ok, msg, doc = create_new_profile_from_template(dp)
            if ok and doc:
                def apply_view():
                    try:
                        App.setActiveDocument(doc.Name)
                        Gui.ActiveDocument = Gui.getDocument(doc.Name)
                        Gui.updateGui()
                        if Gui.ActiveDocument:
                            Gui.runCommand('Std_ViewIsometric', 0)
                            Gui.runCommand('Std_ViewFitAll', 0)
                    except Exception as e:
                        print(f"Library- Erreur dans apply_view: {e}")

                QtCore.QTimer.singleShot(500, apply_view)
                self.load_library()
            else:
                QtGui.QMessageBox.critical(self, "Erreur", msg)

    def on_convert_draft(self):
        if self.current_context and self.current_context['context'] == CONTEXT_DRAFT:
            an = self.current_context.get('analysis')
            if an and an.get('ready_for_conversion'):
                from ..conversion.conversion_dialog import show_conversion_dialog
                res, saved_path = show_conversion_dialog(an['body'], an, self.config.get('user_library_path', ''), self)
                if res and res.success and saved_path:
                    if an['body'].Document.FileName in self.file_kind_cache:
                        del self.file_kind_cache[an['body'].Document.FileName]
                    self.load_library()
                    self.update_context()
                    self._open_post_conversion_dialogs(saved_path)

    def on_migrate_all(self):
        """Migre tous les templates de la bibliothèque."""
        lp = self.config.get('user_library_path', '')
        if not lp or not os.path.exists(lp):
            QtGui.QMessageBox.warning(
                self, "Action impossible",
                "Veuillez d'abord définir un dossier de bibliothèque valide."
            )
            return

        # Dry-run d'abord pour montrer ce qui sera fait
        from ..validation.migrator import batch_migrate
        dry_summary = batch_migrate(lp, dry_run=True)

        total = dry_summary['total']
        to_migrate = dry_summary['migrated']

        if to_migrate == 0:
            QtGui.QMessageBox.information(
                self, "Migration",
                f"{total} template(s) analysé(s).\n\n"
                "Tous les profils sont déjà à jour."
            )
            return

        reply = QtGui.QMessageBox.question(
            self, "Migration des profils",
            f"{total} template(s) analysé(s).\n"
            f"{to_migrate} nécessite(nt) une mise à jour.\n\n"
            "Modifications appliquées :\n"
            "  • Masquage des propriétés internes\n"
            "  • Vérification CopyOnChange\n"
            "  • Suppression de profile_id (obsolète)\n"
            "  • Ajout des propriétés manquantes\n\n"
            "Lancer la migration ?",
            QtGui.QMessageBox.Yes | QtGui.QMessageBox.No
        )
        if reply != QtGui.QMessageBox.Yes:
            return

        # Migration réelle
        self.btn_migrate.setEnabled(False)
        self.btn_migrate.setText("Migration en cours...")
        QtGui.QApplication.processEvents()

        try:
            summary = batch_migrate(lp, dry_run=False)
            migrated = summary['migrated']
            errors = summary['errors']
            skipped = summary['skipped']

            msg = (
                f"Migration terminée.\n\n"
                f"  • {migrated} template(s) mis à jour\n"
                f"  • {skipped} déjà à jour\n"
            )
            if errors:
                msg += f"  • {errors} erreur(s)\n"
                for d in summary.get('details', []):
                    msg += f"\n    ⚠ {d.get('file','?')}: {d.get('error','?')}"

            QtGui.QMessageBox.information(self, "Migration", msg)
            self.load_library()

        except Exception as e:
            print(f"Library- Erreur migration: {e}")
            traceback.print_exc()
            QtGui.QMessageBox.critical(
                self, "Erreur",
                f"Erreur pendant la migration:\n{str(e)}"
            )
        finally:
            self.btn_migrate.setEnabled(True)
            self.btn_migrate.setText("Migrer les profils")

    def browse_library_path(self):
        cur = self.config.get('user_library_path', '') or os.path.expanduser("~")
        path = QtGui.QFileDialog.getExistingDirectory(self, "Choisir dossier", cur)
        if path:
            self.config['user_library_path'] = path
            save_config(self.config)
            self.label_library_path.setText(path)
            self.load_library()

    def load_library(self):
        self.tree.clear()
        self.file_kind_cache.clear()
        lp = self.config.get('user_library_path', '')
        if not lp or not os.path.exists(lp):
            self.label_library_path.setText("<non définie>")
            self.label_preview.setText("Sélectionnez un profil dans la bibliothèque")
            self.label_preview.setStyleSheet("color:#666; font-style: italic;")
            self.selected_file_analysis = None
            self.update_context()
            return

        self.library_data = scan_library(lp)
        if self.library_data:
            self.populate_tree(self.library_data, None)
            self.update_buttons_state()
            self.selected_file_analysis = None
            self.update_context()

    def populate_tree(self, data, parent):
        for child in data.get('children', []):
            item = QtGui.QTreeWidgetItem(parent or self.tree)
            icon = "📁" if child['type'] == 'folder' else "📄"
            item.setText(0, icon + " " + child['name'])
            item.setData(0, QtCore.Qt.UserRole, child)
            
            # Précharger les tooltips avec vignettes pour les fichiers
            if child['type'] == 'file':
                self._set_item_thumbnail_tooltip(item, child['path'])
            
            if child['type'] == 'folder':
                self.populate_tree(child, item)
                item.setExpanded(True)

    def _set_item_thumbnail_tooltip(self, item, file_path):
        """Configure un tooltip avec vignette pour l'élément d'arbre."""
        try:
            # Extraire la vignette une seule fois et la mettre en cache
            pixmap = self._load_thumbnail_pixmap(file_path)
            if pixmap and not pixmap.isNull():
                # Convertir en base64 pour l'embed dans le HTML du tooltip
                buffer = BytesIO()
                pixmap.save(buffer, "PNG")
                b64_image = base64.b64encode(buffer.getvalue()).decode()
                
                # Tooltip HTML avec image centrée et dimensions fixes
                tooltip_html = f"""
                <div style="text-align: center; padding: 4px;">
                    <img src="image/png;base64,{b64_image}" 
                         width="120" height="90" 
                         style="border: 1px solid #ccc; background: #fff;"/>
                    <div style="margin-top: 4px; font-weight: bold; color: #333;">
                        {os.path.basename(file_path)}
                    </div>
                </div>
                """
                item.setToolTip(0, tooltip_html)
        except Exception as e:
            print(f"Library- Erreur tooltip vignette: {e}")

    def _load_thumbnail_pixmap(self, path):
        """Charge la vignette depuis le cache ou le fichier FCStd."""
        cached = self.thumbnail_cache.get(path)
        if cached:
            return cached

        try:
            with zipfile.ZipFile(path, 'r') as z:
                thumb_name = 'thumbnails/Thumbnail.png'
                if thumb_name in z.namelist():
                    p = QtGui.QPixmap()
                    p.loadFromData(z.read(thumb_name))
                    if not p.isNull():
                        self.thumbnail_cache.set(path, p)
                        return p
        except Exception as e:
            print(f"Library- Erreur chargement vignette {path}: {e}")
        return None

    def on_item_clicked(self, item, column):
        if self._info_panel_locked: return
        data = item.data(0, QtCore.Qt.UserRole)
        self.update_info_panel_from_data(data)

        if data and data['type'] == 'file':
            self.selected_file_analysis = self.analyze_file_type(data['path'])
            self.update_context_buttons_for_selection()
        else:
            self.selected_file_analysis = None
            self.update_context()

    def on_item_hovered_tooltip(self, item, column):
        """Gère le survol avec tooltip personnalisé (sans modifier la vignette principale)."""
        # Rien à faire ici - le tooltip est déjà configuré via setToolTip()
        # La vignette principale reste inchangée (seulement mise à jour au clic)
        pass

    def on_current_item_changed(self, current, previous):
        if not self._info_panel_locked:
            if current:
                data = current.data(0, QtCore.Qt.UserRole)
                self.update_info_panel_from_data(data)
            else:
                # Aucune sélection → vignette par défaut
                self.label_preview.setText("Sélectionnez un profil dans la bibliothèque")
                self.label_preview.setStyleSheet("color:#666; font-style: italic;")
                self.selected_file_analysis = None
                self.update_context()

    def on_item_double_clicked(self, item, column):
        data = item.data(0, QtCore.Qt.UserRole)
        if data and data['type'] == 'file':
            self.on_insert_profile()

    def update_info_panel_from_data(self, data):
        """Met à jour la vignette principale UNIQUEMENT pour les sélections (pas le survol)."""
        if not data or data['type'] != 'file':
            self.label_preview.setText("Sélectionnez un profil dans la bibliothèque")
            self.label_preview.setStyleSheet("color:#666; font-style: italic;")
            return

        path = data['path']
        pixmap = self._load_thumbnail_pixmap(path)
        if pixmap and not pixmap.isNull():
            self.label_preview.setPixmap(pixmap.scaled(200, 150, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            self.label_preview.setStyleSheet("")  # Retirer le style italique
        else:
            self.label_preview.setText("Pas d'aperçu disponible")
            self.label_preview.setStyleSheet("color:#999; font-style: italic;")

    def _action_edit_file_variants(self, path):
        from .variant_editor import show_variant_editor
        doc = get_open_document_by_path(path)
        was_already_open = doc is not None

        if not doc:
            doc = App.openDocument(path)

        if not doc:
            return

        part = next((o for o in doc.Objects if is_profile_part(o)), None)
        if part and show_variant_editor(part, self):
            doc.recompute()
            ok, msg = safe_save(doc)
            if ok:
                if path in self.file_kind_cache:
                    del self.file_kind_cache[path]
                self.load_library()

            App.setActiveDocument(doc.Name)
            Gui.ActiveDocument = Gui.getDocument(doc.Name)

    def update_buttons_state(self):
        ok = bool(self.config.get('user_library_path'))
        self.btn_new_folder.setEnabled(ok)
        sel = self.tree.currentItem()
        self.btn_rename.setEnabled(sel is not None)
        self.btn_delete.setEnabled(sel is not None)

    def closeEvent(self, ev):
        self.context_timer.stop()
        if self.active_doc_at_start:
            try:
                App.setActiveDocument(self.active_doc_at_start.Name)
                Gui.ActiveDocument = Gui.getDocument(self.active_doc_at_start.Name)
                Gui.updateGui()
                Gui.getMainWindow().setFocus()
                QtGui.QApplication.processEvents()
            except Exception as e:
                print(f"Library- ⚠ Erreur restauration document à la fermeture: {e}")
        super(LibraryDialog, self).closeEvent(ev)

class NewProfileDialog(QtGui.QDialog):
    def __init__(self, lp, parent=None):
        super(NewProfileDialog, self).__init__(parent)
        self.lp = lp
        self.selected_folder = lp
        self.setWindowTitle("Nouveau profil")
        self.setup_ui()

    def setup_ui(self):
        layout = QtGui.QVBoxLayout(self)
        name_layout = QtGui.QHBoxLayout()
        name_layout.addWidget(QtGui.QLabel("Nom:"))
        self.edit_name = QtGui.QLineEdit("mon_profil")
        name_layout.addWidget(self.edit_name)
        layout.addLayout(name_layout)

        folder_group = QtGui.QGroupBox("Emplacement")
        folder_layout = QtGui.QVBoxLayout(folder_group)
        self.tree_folders = QtGui.QTreeWidget()
        self.tree_folders.setHeaderHidden(True)
        self.tree_folders.itemClicked.connect(self.on_folder_selected)
        self.populate_folders(self.lp)
        folder_layout.addWidget(self.tree_folders)
        self.label_dest = QtGui.QLabel(f"Destination: {self.lp}")
        folder_layout.addWidget(self.label_dest)
        layout.addWidget(folder_group)

        bb = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def populate_folders(self, path, parent=None):
        item = QtGui.QTreeWidgetItem(parent or self.tree_folders)
        item.setText(0, os.path.basename(path) or path)
        item.setData(0, QtCore.Qt.UserRole, path)
        item.setExpanded(True)
        try:
            for entry in sorted(os.listdir(path)):
                if os.path.isdir(os.path.join(path, entry)) and not entry.startswith('.'):
                    self.populate_folders(os.path.join(path, entry), item)
        except:
            pass

    def on_folder_selected(self, item, column):
        self.selected_folder = item.data(0, QtCore.Qt.UserRole)
        self.label_dest.setText(f"Destination: {self.selected_folder}")

    def get_full_path(self):
        name = self.edit_name.text()
        return os.path.join(self.selected_folder, name if name.lower().endswith('.fcstd') else name + '.FCStd')
