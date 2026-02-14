# Chemin : library/conversion/conversion_dialog.py
#-*- coding: utf-8 -*-
# Path: Library/conversion/conversion_dialog.py
"""
 Dialogue de conversion draft → template
 Interface utilisateur pour la conversion
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import os
import traceback

class ConversionDialog(QtGui.QDialog):
    """
     Dialogue pour convertir un Body draft en template de profil.
    """

    def __init__(self, body, analysis, library_path, parent=None):
        super().__init__(parent)
        self.body = body
        self.analysis = analysis
        self.library_path = library_path
        self.result = None
        self.saved_path = None  # Stocke le chemin sauvegardé après conversion

        self.setWindowTitle("Convertir en Template")
        self.setMinimumSize(550, 500)
        self.setup_ui()

    def setup_ui(self):
        """Configure l'interface."""
        layout = QtGui.QVBoxLayout(self)
        layout.setSpacing(10)

        #=== EN-TÊTE===
        header = QtGui.QLabel(f"<h3>⚙️ Conversion: {self.body.Label}</h3>")
        layout.addWidget(header)

        #=== INFORMATIONS DÉTECTÉES===
        info_group = QtGui.QGroupBox("🔍 Éléments détectés")
        info_layout = QtGui.QVBoxLayout(info_group)

        sketch_name = self.analysis['sketch'].Label if self.analysis['sketch'] else "Non trouvé"
        sketch_label = QtGui.QLabel(f"• Sketch: <b>{sketch_name}</b>")
        info_layout.addWidget(sketch_label)

        pad_name = self.analysis['pad'].Label if self.analysis['pad'] else "Sera créé automatiquement"
        pad_label = QtGui.QLabel(f"• Pad: <b>{pad_name}</b>")
        info_layout.addWidget(pad_label)

        constraints = self.analysis.get('constraints', [])
        constraints_label = QtGui.QLabel(f"• Contraintes nommées: <b>{len(constraints)}</b>")
        info_layout.addWidget(constraints_label)

        if constraints:
            constraints_list = QtGui.QListWidget()
            constraints_list.setMaximumHeight(100)
            for c in constraints:
                value_str = f"{c['value']:.2f}" if c['value'] is not None else "?"
                constraints_list.addItem(f" {c['name']} = {value_str} mm")
            info_layout.addWidget(constraints_list)

        lcs_list = self.analysis.get('lcs', [])
        lcs_text = f"{len(lcs_list)} trouvé(s)" if lcs_list else "Seront créés automatiquement"
        lcs_label = QtGui.QLabel(f"• LCS: <b>{lcs_text}</b>")
        info_layout.addWidget(lcs_label)

        layout.addWidget(info_group)

        #=== CONFIGURATION===
        config_group = QtGui.QGroupBox("⚙️ Configuration")
        config_layout = QtGui.QFormLayout(config_group)

        self.edit_variant = QtGui.QLineEdit("Variante_1")
        self.edit_variant.setPlaceholderText("Nom de la première variante")
        config_layout.addRow("Variante:", self.edit_variant)

        default_name = self.body.Label.replace("Body", "").replace("_", "").strip()
        if not default_name:
            default_name = "Nouveau_profil"
        self.edit_filename = QtGui.QLineEdit(default_name)
        self.edit_filename.setPlaceholderText("Nom du fichier (sans extension)")
        config_layout.addRow("Nom fichier:", self.edit_filename)

        layout.addWidget(config_group)

        #=== DESTINATION===
        dest_group = QtGui.QGroupBox("📁 Destination dans la bibliothèque")
        dest_layout = QtGui.QVBoxLayout(dest_group)

        self.tree_dest = QtGui.QTreeWidget()
        self.tree_dest.setHeaderLabel("Dossiers")
        self.tree_dest.setMaximumHeight(150)
        self.populate_folder_tree()
        dest_layout.addWidget(self.tree_dest)

        self.label_dest_path = QtGui.QLabel(f"📁 {self.library_path}")
        self.label_dest_path.setStyleSheet("color:#666; font-style: italic;")
        dest_layout.addWidget(self.label_dest_path)

        self.tree_dest.itemClicked.connect(self.on_folder_selected)

        layout.addWidget(dest_group)

        #=== AVERTISSEMENTS===
        issues = self.analysis.get('issues', [])
        if issues:
            warn_group = QtGui.QGroupBox("⚠️ Avertissements")
            warn_layout = QtGui.QVBoxLayout(warn_group)
            for issue in issues:
                warn_label = QtGui.QLabel(f"• {issue}")
                warn_label.setStyleSheet("color:#e65100;")
                warn_layout.addWidget(warn_label)
            layout.addWidget(warn_group)

        #=== BOUTONS===
        layout.addStretch()

        btn_layout = QtGui.QHBoxLayout()

        self.btn_cancel = QtGui.QPushButton("Annuler")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)

        btn_layout.addStretch()

        self.btn_convert = QtGui.QPushButton("⚙️ Convertir et Sauvegarder")
        self.btn_convert.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self.btn_convert.clicked.connect(self.on_convert)
        btn_layout.addWidget(self.btn_convert)

        layout.addLayout(btn_layout)

    def populate_folder_tree(self):
        """Remplit l'arbre avec les dossiers de la bibliothèque."""
        self.tree_dest.clear()
        root_item = QtGui.QTreeWidgetItem(self.tree_dest, ["📁 Bibliothèque"])
        root_item.setData(0, QtCore.Qt.UserRole, self.library_path)
        root_item.setExpanded(True)
        self._populate_folder_tree_recursive(root_item, self.library_path)

    def _populate_folder_tree_recursive(self, parent_item, path):
        try:
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path) and not item.startswith('.'):
                    folder_item = QtGui.QTreeWidgetItem(parent_item, [f"📁 {item}"])
                    folder_item.setData(0, QtCore.Qt.UserRole, item_path)
                    folder_item.setExpanded(True)
                    self._populate_folder_tree_recursive(folder_item, item_path)
        except PermissionError:
            pass

    def on_folder_selected(self, item, column):
        """Gère la sélection d'un dossier."""
        path = item.data(0, QtCore.Qt.UserRole)
        if path:
            self.selected_path = path
            self.label_dest_path.setText(f"📁 {path}")

    def get_destination_path(self):
        """Retourne le chemin de destination complet."""
        selected_items = self.tree_dest.selectedItems()
        if selected_items:
            folder = selected_items[0].data(0, QtCore.Qt.UserRole)
        else:
            folder = self.library_path

        filename = self.edit_filename.text().strip()
        if not filename:
            filename = "profil"

        if not filename.lower().endswith('.fcstd'):
            filename += '.FCStd'

        return os.path.join(folder, filename)

    def on_convert(self):
        """Lance la conversion."""
        variant_name = self.edit_variant.text().strip()
        if not variant_name:
            QtGui.QMessageBox.warning(self, "Erreur", "Entrez un nom de variante")
            return

        filename = self.edit_filename.text().strip()
        if not filename:
            QtGui.QMessageBox.warning(self, "Erreur", "Entrez un nom de fichier")
            return

        dest_path = self.get_destination_path()

        if os.path.exists(dest_path):
            reply = QtGui.QMessageBox.question(
                self, "Fichier existant",
                f"Le fichier existe déjà:\n{os.path.basename(dest_path)}\n\nRemplacer?",
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No
            )
            if reply == QtGui.QMessageBox.No:
                return

        self.btn_convert.setEnabled(False)
        self.btn_convert.setText("⏳ Conversion en cours...")
        QtGui.QApplication.processEvents()

        try:
            from .converter import convert_draft_to_template, save_template_to_library, get_conversion_summary

            part_name = filename
            if part_name.lower().endswith('.fcstd'):
                part_name = part_name[:-6]

            result = convert_draft_to_template(self.body, variant_name, part_name)

            if not result.success:
                QtGui.QMessageBox.critical(self, "Échec", result.message)
                self.btn_convert.setEnabled(True)
                self.btn_convert.setText("⚙️ Convertir et Sauvegarder")
                return

            save_success, save_msg = save_template_to_library(
                self.body.Document, result.part, dest_path
            )

            if not save_success:
                QtGui.QMessageBox.warning(self, "Erreur sauvegarde", save_msg)
                self.btn_convert.setEnabled(True)
                self.btn_convert.setText("⚙️ Convertir et Sauvegarder")
                return

            self.result = result
            self.saved_path = dest_path  # Stocker le chemin sauvegardé

            summary = get_conversion_summary(result)
            summary += f"\n\n📁 Sauvegardé: {os.path.basename(dest_path)}"

            QtGui.QMessageBox.information(self, "Conversion réussie", summary)
            self.accept()

        except Exception as e:
            print(f"Library - ❌ Erreur conversion: {e}")
            traceback.print_exc()
            QtGui.QMessageBox.critical(self, "Erreur", f"Erreur lors de la conversion:\n{str(e)}")
            self.btn_convert.setEnabled(True)
            self.btn_convert.setText("⚙️ Convertir et Sauvegarder")

    def get_saved_path(self):
        """Retourne le chemin du fichier sauvegardé."""
        return self.saved_path

def show_conversion_dialog(body, analysis, library_path, parent=None):
    """
     Affiche le dialogue de conversion.

     Args:
        body: Body à convertir
        analysis: Résultat de analyze_body()
        library_path: Chemin de la bibliothèque
        parent: Widget parent

     Returns:
        tuple: (ConversionResult ou None, chemin_sauvegardé ou None)
    """
    dialog = ConversionDialog(body, analysis, library_path, parent)

    if dialog.exec_() == QtGui.QDialog.Accepted:
        return dialog.result, dialog.get_saved_path()

    return None, None
