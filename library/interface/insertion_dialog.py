# Chemin : library/interface/insertion_dialog.py
# -*- coding: utf-8 -*-
# Path: Library/library/interface/insertion_dialog.py
"""
Dialogue d'insertion de profils - version simplifiée pour l'insertion
N'affiche PAS la section "Configuration du dialogue" lors de l'insertion

CORRECTIONS APPLIQUÉES:
- ProfileData.from_document() extrait config_num depuis Part.Config
- _apply_initial_state() lit Config du template en mode insertion
- _get_configuration_mode() corrige l'inversion modes 4/5
- insert_profile() copie l'énumération Section AVANT l'affectation
- Config 1/2: masque complètement le champ Variante (profil unique)
- Config 5: longueur en lecture seule (label readonly)
- strip("'") au lieu de lstrip("'") pour supprimer les apostrophes
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import os
import traceback

# ── Correspondance Config ↔ (is_single, length_mode) ──────────────────────
CONFIG_MAP_INV = {
    1: (True,  "user"),
    2: (True,  "list"),
    3: (False, "user"),
    4: (False, "list"),
    5: (False, "variant"),
}

class ProfileData:
    def __init__(self):
        self.part = None
        self.spreadsheet = None
        self.variants = []
        self.constraints = {}
        self.lengths = {}
        self.length_lists = {}
        self.has_length_column = False
        self.has_length_list_column = False
        self.default_angle = 0.0
        self.is_single_profile = False
        self.config_num = 0              # ← AJOUT: numéro de configuration

    @classmethod
    def from_document(cls, doc):
        data = cls()
        try:
            for obj in doc.Objects:
                if obj.TypeId == "App::Part" and hasattr(obj, 'profile') and obj.profile:
                    data.part = obj
                    break
            if not data.part:
                return None
            if hasattr(data.part, 'Angle'):
                data.default_angle = float(data.part.Angle)

            # ── CORRECTION: lire Config depuis le Part ──
            if hasattr(data.part, 'Config'):
                try:
                    data.config_num = int(data.part.Config)
                except (ValueError, TypeError):
                    data.config_num = 0
            # ────────────────────────────────────────────

            for obj in data.part.Group:
                if obj.TypeId == "Spreadsheet::Sheet":
                    data.spreadsheet = obj
                    break
            if not data.spreadsheet:
                return None
            data._parse_spreadsheet()
            data.is_single_profile = len(data.variants) <= 1
            return data
        except Exception as e:
            print(f"Library- Erreur extraction données profil: {e}")
            traceback.print_exc()
            return None

    def _parse_spreadsheet(self):
        ss = self.spreadsheet
        col_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        headers = {}
        constraint_cols = []
        longueur_col = None
        longueur_liste_col = None
        for col_idx, col in enumerate(col_letters[:20]):
            try:
                content = ss.getContents(f"{col}1")
                if content:
                    # ── CORRECTION: strip("'") des DEUX côtés ──
                    header = content.strip().strip("'")
                    headers[col] = header
                    if header == "Longueur":
                        longueur_col = col
                        self.has_length_column = True
                    elif header.lower() in ["longueur_liste", "longueurliste"]:
                        longueur_liste_col = col
                        self.has_length_list_column = True
                    elif header not in ["Section", "Preferred", "RefLongueur", "RefAngle"]:
                        constraint_cols.append((col, header))
            except:
                pass
        row = 3
        while row < 100:
            try:
                variant_name = ss.getContents(f"A{row}")
                if not variant_name or not variant_name.strip():
                    break
                # ── CORRECTION: strip("'") des DEUX côtés ──
                variant_name = variant_name.strip().strip("'")
                self.variants.append(variant_name)
                self.constraints[variant_name] = {}
                for col, constraint_name in constraint_cols:
                    try:
                        value = ss.get(f"{col}{row}")
                        if hasattr(value, 'Value'):
                            self.constraints[variant_name][constraint_name] = value.Value
                        else:
                            self.constraints[variant_name][constraint_name] = 0.0
                    except:
                        self.constraints[variant_name][constraint_name] = 0.0
                if longueur_col:
                    try:
                        value = ss.get(f"{longueur_col}{row}")
                        if hasattr(value, 'Value'):
                            self.lengths[variant_name] = value.Value
                        else:
                            self.lengths[variant_name] = 100.0
                    except:
                        self.lengths[variant_name] = 100.0
                if longueur_liste_col:
                    try:
                        content = ss.getContents(f"{longueur_liste_col}{row}")
                        if content:
                            # ── CORRECTION: strip("'") des DEUX côtés ──
                            content = content.strip().strip("'")
                            parts = content.split(';') if ';' in content else content.split(',')
                            lengths = []
                            for p in parts:
                                try:
                                    lengths.append(float(p.strip().replace('mm', '').strip()))
                                except:
                                    pass
                            if lengths:
                                self.length_lists[variant_name] = lengths
                    except:
                        pass
                row += 1
            except:
                break

    def get_first_variant(self):
        return self.variants[0] if self.variants else "Variante_1"

    def get_constraints_for_variant(self, variant_name):
        return self.constraints.get(variant_name, {})

    def get_length_for_variant(self, variant_name):
        return self.lengths.get(variant_name, 100.0)

    def get_length_list_for_variant(self, variant_name):
        return self.length_lists.get(variant_name, [100.0])

class InsertionDialog(QtGui.QDialog):
    def __init__(self, profile_data, template_path, parent=None, for_insertion=False):
        super(InsertionDialog, self).__init__(parent)
        self.profile_data = profile_data
        self.template_path = template_path
        self.result = None
        self.for_insertion = for_insertion

        self.setWindowTitle("Insérer un profil")
        self.setMinimumSize(550, 450 if for_insertion else 600)
        self.setup_ui()
        self._apply_initial_state()

    def setup_ui(self):
        layout = QtGui.QVBoxLayout(self)
        layout.setSpacing(10)

        header = QtGui.QLabel("<h3>Insertion de profil</h3>")
        layout.addWidget(header)
        file_label = QtGui.QLabel(f"{os.path.basename(self.template_path)}")
        file_label.setStyleSheet("color:#666;")
        layout.addWidget(file_label)

        #=== SECTION CONFIGURATION (masquée en mode insertion) ===
        self.config_group = QtGui.QGroupBox("Configuration du dialogue")
        config_layout = QtGui.QVBoxLayout(self.config_group)

        self.check_single_profile = QtGui.QCheckBox("Profil unique (première variante éditable)")
        self.check_single_profile.setChecked(self.profile_data.is_single_profile)
        self.check_single_profile.stateChanged.connect(self._on_single_profile_changed)
        config_layout.addWidget(self.check_single_profile)

        line = QtGui.QFrame()
        line.setFrameShape(QtGui.QFrame.HLine)
        line.setFrameShadow(QtGui.QFrame.Sunken)
        config_layout.addWidget(line)

        config_layout.addWidget(QtGui.QLabel("Mode de longueur:"))
        self.radio_length_user = QtGui.QRadioButton("Longueur définie par l'utilisateur")
        self.radio_length_user.setChecked(True)
        self.radio_length_user.toggled.connect(self._on_length_mode_changed)
        config_layout.addWidget(self.radio_length_user)

        self.radio_length_list = QtGui.QRadioButton("Longueur issue d'une liste")
        self.radio_length_list.toggled.connect(self._on_length_mode_changed)
        if not self.profile_data.has_length_list_column:
            self.radio_length_list.setEnabled(False)
        config_layout.addWidget(self.radio_length_list)

        self.radio_length_variant = QtGui.QRadioButton("Longueur liée à la variante")
        self.radio_length_variant.toggled.connect(self._on_length_mode_changed)
        if not self.profile_data.has_length_column:
            self.radio_length_variant.setEnabled(False)
        config_layout.addWidget(self.radio_length_variant)

        # Masquer la section si en mode insertion
        self.config_group.setVisible(not self.for_insertion)
        layout.addWidget(self.config_group)

        params_group = QtGui.QGroupBox("Paramètres")
        params_layout = QtGui.QFormLayout(params_group)

        self.spin_angle = QtGui.QDoubleSpinBox()
        self.spin_angle.setRange(-360.0, 360.0)
        self.spin_angle.setDecimals(2)
        self.spin_angle.setSuffix(" °")
        self.spin_angle.setValue(self.profile_data.default_angle)
        params_layout.addRow("Angle:", self.spin_angle)

        self.combo_variant = QtGui.QComboBox()
        self.combo_variant.addItems(self.profile_data.variants)
        self.combo_variant.currentIndexChanged.connect(self._on_variant_changed)
        self.edit_variant = QtGui.QLineEdit()
        self.edit_variant.setText(self.profile_data.get_first_variant())
        self.edit_variant.textChanged.connect(self._on_variant_text_changed)
        variant_container = QtGui.QWidget()
        variant_hlayout = QtGui.QHBoxLayout(variant_container)
        variant_hlayout.setContentsMargins(0, 0, 0, 0)
        variant_hlayout.addWidget(self.combo_variant)
        variant_hlayout.addWidget(self.edit_variant)
        self.label_variant = QtGui.QLabel("Variante:")
        params_layout.addRow(self.label_variant, variant_container)

        self.spin_length = QtGui.QDoubleSpinBox()
        self.spin_length.setRange(1.0, 100000.0)
        self.spin_length.setDecimals(2)
        self.spin_length.setSuffix(" mm")
        self.spin_length.setValue(100.0)
        self.label_length = QtGui.QLabel("Longueur:")
        params_layout.addRow(self.label_length, self.spin_length)

        self.combo_length_list = QtGui.QComboBox()
        self.label_length_list = QtGui.QLabel("Longueur:")
        params_layout.addRow(self.label_length_list, self.combo_length_list)

        self.label_variant_length_value = QtGui.QLabel("100.0 mm")
        self.label_variant_length_value.setStyleSheet("font-weight: bold; color:#0066cc;")
        self.label_variant_length = QtGui.QLabel("Longueur (variante):")
        params_layout.addRow(self.label_variant_length, self.label_variant_length_value)

        layout.addWidget(params_group)

        constraints_group = QtGui.QGroupBox("Contraintes de la variante")
        constraints_layout = QtGui.QVBoxLayout(constraints_group)
        self.list_constraints = QtGui.QListWidget()
        self.list_constraints.setMaximumHeight(100)
        constraints_layout.addWidget(self.list_constraints)
        layout.addWidget(constraints_group)

        self.label_config_mode = QtGui.QLabel("")
        self.label_config_mode.setStyleSheet(
            "QLabel{background-color: #e8f4e8; color: #2e7d32; padding: 8px; "
            "border: 1px solid #a0c8a0; border-radius: 4px; font-weight: bold;}"
        )
        self.label_config_mode.setWordWrap(True)
        layout.addWidget(self.label_config_mode)

        layout.addStretch()
        btn_layout = QtGui.QHBoxLayout()
        btn_cancel = QtGui.QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        self.btn_insert = QtGui.QPushButton("Insérer")
        self.btn_insert.setStyleSheet("""
            QPushButton{
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover{
                background-color: #1976D2;
            }
        """)
        self.btn_insert.clicked.connect(self._on_insert)
        btn_layout.addWidget(self.btn_insert)
        layout.addLayout(btn_layout)

    # ══════════════════════════════════════════════════════════════════════
    # CORRECTION MAJEURE: lire Config du template au lieu de deviner
    # ══════════════════════════════════════════════════════════════════════
    def _apply_initial_state(self):
        pd = self.profile_data
        config_num = getattr(pd, 'config_num', 0)

        if self.for_insertion and config_num > 0:
            # ── Mode INSERTION: lire Config du template et verrouiller l'UI ──
            is_single, length_mode = CONFIG_MAP_INV.get(config_num, (False, "user"))
            self.check_single_profile.setChecked(is_single)
            if length_mode == "user":
                self.radio_length_user.setChecked(True)
            elif length_mode == "list":
                self.radio_length_list.setChecked(True)
                # Forcer activation même si la colonne semble absente
                self.radio_length_list.setEnabled(True)
            elif length_mode == "variant":
                self.radio_length_variant.setChecked(True)
                # Forcer activation même si la colonne semble absente
                self.radio_length_variant.setEnabled(True)
        else:
            # ── Mode TEST / CONFIGURATION: état par défaut ──
            self.check_single_profile.setChecked(pd.is_single_profile)
            self.radio_length_user.setChecked(True)

        self._on_single_profile_changed()

    def _on_single_profile_changed(self):
        is_single = self.check_single_profile.isChecked()
        can_use_variant_length = (not is_single) and self.profile_data.has_length_column
        self.radio_length_variant.setEnabled(can_use_variant_length)
        if is_single and self.radio_length_variant.isChecked():
            self.radio_length_user.setChecked(True)

        # ── CORRECTION: Config 1/2 → masquer complètement la ligne Variante ──
        if is_single:
            self.label_variant.setVisible(False)
            self.combo_variant.setVisible(False)
            self.edit_variant.setVisible(False)
            # S'assurer que le parent container est aussi masqué
            self.combo_variant.parentWidget().setVisible(False)
        else:
            self.label_variant.setVisible(True)
            self.combo_variant.parentWidget().setVisible(True)
            self.combo_variant.setVisible(True)
            self.edit_variant.setVisible(False)

        self._update_length_mode_display()
        self._update_constraints_display()
        self._update_length_list()
        self._update_variant_length_display()
        self._update_config_summary()

    def _on_length_mode_changed(self):
        self._update_length_mode_display()
        self._update_config_summary()

    def _on_variant_changed(self):
        self._update_constraints_display()
        self._update_length_list()
        self._update_variant_length_display()
        self._update_config_summary()

    def _on_variant_text_changed(self):
        self._update_constraints_display()
        self._update_length_list()
        self._update_variant_length_display()
        self._update_config_summary()

    def _get_length_mode(self):
        if self.radio_length_user.isChecked():
            return "user"
        elif self.radio_length_variant.isChecked():
            return "variant"
        else:
            return "list"

    def _update_length_mode_display(self):
        mode = self._get_length_mode()
        self.spin_length.setVisible(mode == "user")
        self.label_length.setVisible(mode == "user")
        self.combo_length_list.setVisible(mode == "list")
        self.label_length_list.setVisible(mode == "list")
        self.label_variant_length.setVisible(mode == "variant")
        self.label_variant_length_value.setVisible(mode == "variant")

        # ── CORRECTION Config 5: affichage lecture seule ──
        if mode == "variant":
            self.label_variant_length.setText("Longueur (fixe):")
            self.label_variant_length_value.setStyleSheet(
                "font-weight: bold; color:#666; font-style:italic;"
            )
            self._update_variant_length_display()

    def _get_current_variant(self):
        if self.check_single_profile.isChecked():
            # ── CORRECTION: pour profil unique, toujours la première variante ──
            return self.profile_data.get_first_variant()
        else:
            return self.combo_variant.currentText()

    def _get_variant_for_constraints(self):
        if self.check_single_profile.isChecked():
            return self.profile_data.get_first_variant()
        else:
            return self.combo_variant.currentText()

    def _update_constraints_display(self):
        self.list_constraints.clear()
        variant = self._get_variant_for_constraints()
        constraints = self.profile_data.get_constraints_for_variant(variant)
        for name, value in constraints.items():
            self.list_constraints.addItem(f"{name} = {value:.2f} mm")
        if not constraints:
            self.list_constraints.addItem("(aucune contrainte)")

    def _update_length_list(self):
        self.combo_length_list.clear()
        variant = self._get_variant_for_constraints()
        lengths = self.profile_data.get_length_list_for_variant(variant)
        for length in lengths:
            self.combo_length_list.addItem(f"{length:.0f} mm", length)
        if not lengths:
            self.combo_length_list.addItem("100 mm", 100.0)

    def _update_variant_length_display(self):
        variant = self._get_variant_for_constraints()
        length = self.profile_data.get_length_for_variant(variant)
        self.label_variant_length_value.setText(f"{length:.2f} mm")

    # ══════════════════════════════════════════════════════════════════════
    # CORRECTION CRITIQUE: modes 4 et 5 étaient inversés
    # Config 4 = (False, "list")    → Famille, longueur semi standard
    # Config 5 = (False, "variant") → Famille, longueur fixe par variante
    # ══════════════════════════════════════════════════════════════════════
    def _get_configuration_mode(self):
        is_single = self.check_single_profile.isChecked()
        length_mode = self._get_length_mode()
        if is_single:
            if length_mode == "user":
                return (1, "Profil particulier, coupe à longueur")
            else:
                return (2, "Profil particulier, longueur semi standard")
        else:
            if length_mode == "user":
                return (3, "Famille de profilés, coupe à longueur")
            elif length_mode == "list":
                return (4, "Famille de profilés, longueur semi standard")
            else:  # variant
                return (5, "Famille de profilés, longueur fixe par variante")

    def _update_config_summary(self):
        mode_num, mode_desc = self._get_configuration_mode()
        variant = self._get_current_variant()
        params = ["Angle"]
        if not self.check_single_profile.isChecked():
            params.append("Variante")
        length_mode = self._get_length_mode()
        if length_mode == "user":
            params.append("Longueur")
        elif length_mode == "list":
            params.append("Longueur_liste")
        elif length_mode == "variant":
            params.append("Longueur (fixe)")
        self.label_config_mode.setText(
            f"Mode {mode_num}: {mode_desc}\n"
            f"Paramètres: {', '.join(params)}\n"
            f"Variante: {variant}"
        )

    def _get_selected_length(self):
        mode = self._get_length_mode()
        variant = self._get_variant_for_constraints()
        if mode == "user":
            return self.spin_length.value()
        elif mode == "variant":
            return self.profile_data.get_length_for_variant(variant)
        else:
            return self.combo_length_list.currentData() or 100.0

    def _on_insert(self):
        variant = self._get_current_variant()
        if not variant:
            QtGui.QMessageBox.warning(self, "Erreur", "Veuillez entrer un nom de variante")
            return
        mode_num, mode_desc = self._get_configuration_mode()
        self.result = {
            'template_path': self.template_path,
            'variant': variant,
            'length': self._get_selected_length(),
            'angle': self.spin_angle.value(),
            'is_single_profile': self.check_single_profile.isChecked(),
            'length_mode': self._get_length_mode(),
            'configuration_mode': mode_num,
            'configuration_description': mode_desc,
            'constraints': self.profile_data.get_constraints_for_variant(self._get_variant_for_constraints())
        }
        self.accept()

    def get_result(self):
        return self.result

def show_insertion_dialog(template_path, parent=None, for_insertion=False):
    try:
        doc = App.openDocument(template_path, hidden=True)
        if not doc:
            QtGui.QMessageBox.critical(parent, "Erreur", f"Impossible d'ouvrir le template:\n{template_path}")
            return None
        profile_data = ProfileData.from_document(doc)
        if not profile_data:
            App.closeDocument(doc.Name)
            QtGui.QMessageBox.critical(parent, "Erreur", "Le fichier ne contient pas de profil valide.")
            return None
        dialog = InsertionDialog(profile_data, template_path, parent, for_insertion=for_insertion)
        if dialog.exec_() == QtGui.QDialog.Accepted:
            result = dialog.get_result()
            return result
        App.closeDocument(doc.Name)
        return None
    except Exception as e:
        print(f"Library- Erreur dialogue insertion: {e}")
        traceback.print_exc()
        QtGui.QMessageBox.critical(parent, "Erreur", f"Erreur lors de l'ouverture du template:\n{str(e)}")
        return None

def _force_owned_properties(link, source_part):
    try:
        for prop in ['Section', 'Longueur', 'Angle', 'Update']:
            if hasattr(source_part, prop) and hasattr(link, prop):
                status = link.getPropertyStatus(prop)
                if "CopyOnChange" not in status:
                    link.setPropertyStatus(prop, "CopyOnChange")
    except Exception as e:
        print(f"Library- Erreur forçage propriétés 'Owned': {e}")
        traceback.print_exc()

def insert_profile(params, target_doc=None):
    template_doc = None
    was_already_open = False
    try:
        if target_doc is None:
            target_doc = App.ActiveDocument
        if target_doc is None:
            return False, "Aucun document actif"
        if not target_doc.FileName:
            reply = QtGui.QMessageBox.question(
                None, "Document non sauvegardé",
                "Le document doit être sauvegardé avant insertion d'un profil.\n\n"
                "Voulez-vous sauvegarder maintenant ?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No, QtGui.QMessageBox.Yes
            )
            if reply == QtGui.QMessageBox.Yes:
                file_path, _ = QtGui.QFileDialog.getSaveFileName(
                    None, "Sauvegarder le document", "",
                    "FreeCAD Document (*.FCStd)"
                )
                if file_path:
                    if not file_path.lower().endswith('.fcstd'):
                        file_path += '.FCStd'
                    target_doc.saveAs(file_path)
                    if not target_doc.FileName:
                        return False, "Échec de la sauvegarde du document"
                else:
                    return False, "Opération annulée: sauvegarde requise pour insérer un profil"
            else:
                return False, "Opération annulée: sauvegarde requise pour insérer un profil"
        template_path = params['template_path']
        for doc_name, doc in App.listDocuments().items():
            if doc.FileName and os.path.normpath(doc.FileName) == os.path.normpath(template_path):
                template_doc = doc
                was_already_open = True
                break
        if template_doc is None:
            template_doc = App.openDocument(template_path, hidden=True)
            if not template_doc:
                return False, f"Impossible d'ouvrir le template: {template_path}"
        part = None
        for obj in template_doc.Objects:
            if obj.TypeId == "App::Part" and hasattr(obj, 'profile') and obj.profile:
                part = obj
                break
        if not part:
            if not was_already_open:
                App.closeDocument(template_doc.Name)
            return False, "Part profil non trouvé dans le template"
        link = target_doc.addObject("App::Link", "Profile")
        link.setLink(part)
        link.Label = f"{part.Label} (lié)"
        link.LinkCopyOnChange = "Owned"
        _force_owned_properties(link, part)
        if hasattr(link, 'Longueur'):
            link.Longueur = params['length']
        if hasattr(link, 'Angle'):
            link.Angle = params['angle']

        # ══════════════════════════════════════════════════════════════
        # CORRECTION CRITIQUE: copier l'énumération Section AVANT
        # d'affecter la valeur, sinon ValueError "not in enumeration"
        # ══════════════════════════════════════════════════════════════
        if hasattr(link, 'Section'):
            # 1) Copier la liste d'énumération depuis le Part source
            enum_copied = False
            try:
                enum_list = list(part.getEnumerationsOfProperty("Section"))
                if enum_list:
                    link.Section = enum_list   # Initialise l'énumération
                    enum_copied = True
            except Exception:
                pass

            if not enum_copied:
                # Fallback: essayer via getPropertyByName
                try:
                    prop = part.getPropertyByName("Section")
                    if isinstance(prop, (list, tuple)) and len(prop) > 0:
                        link.Section = list(prop)
                        enum_copied = True
                except Exception:
                    pass

            # 2) Maintenant affecter la valeur choisie
            try:
                link.Section = params['variant']
            except Exception as e:
                print(f"Library- Erreur affectation Section='{params['variant']}': {e}")
                # Si l'affectation échoue, essayer avec la première variante
                try:
                    enum_list = list(part.getEnumerationsOfProperty("Section"))
                    if enum_list:
                        link.Section = enum_list[0]
                        print(f"Library- Fallback: Section='{enum_list[0]}'")
                except Exception:
                    pass

        target_doc.recompute()
        Gui.updateGui()

        # Installer l'observer unifié pour recompute auto
        from .variant_editor import ensure_observer
        ensure_observer()

        mode_desc = params.get('configuration_description', 'N/A')
        print(f"Library- Profil inséré: {link.Label}")
        print(f"  Configuration: {mode_desc}")
        print(f"  Variante: {params['variant']}")
        print(f"  Longueur: {params['length']} mm")
        print(f"  Angle: {params['angle']}°")
        return True, link
    except Exception as e:
        print(f"Library- Erreur insertion profil: {e}")
        traceback.print_exc()
        try:
            if not was_already_open and template_doc:
                App.closeDocument(template_doc.Name)
        except:
            pass
        return False, str(e)
