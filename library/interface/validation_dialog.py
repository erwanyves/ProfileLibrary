# Chemin : library/interface/validation_dialog.py
# -*- coding: utf-8 -*-
# Library/interface/validation_dialog.py
"""
Dialogue de validation et migration des templates
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import os
import traceback

from ..validation import (
    check_template,
    migrate_template,
    batch_migrate  # Assurez-vous que batch_migrate est bien exporté dans validation/__init__.py
)

class ValidationDialog(QtGui.QDialog):
    """Dialogue pour valider et migrer les templates."""
    def __init__(self, parent=None, library_path=None):
        super().__init__(parent)
        self.library_path = library_path
        self.current_doc = None
        self.validation_result = None
        self.setWindowTitle("Validation des templates")
        self.setMinimumSize(600, 500)
        self.setup_ui()

    def setup_ui(self):
        layout = QtGui.QVBoxLayout(self)

        # === SECTION: Document actuel ===
        group_current = QtGui.QGroupBox("Document actuel")
        layout_current = QtGui.QVBoxLayout(group_current)
        
        self.label_doc = QtGui.QLabel("Aucun document ouvert")
        layout_current.addWidget(self.label_doc)
        
        btn_layout = QtGui.QHBoxLayout()
        self.btn_check = QtGui.QPushButton("Vérifier")
        self.btn_check.clicked.connect(self.check_current)
        btn_layout.addWidget(self.btn_check)
        
        self.btn_migrate = QtGui.QPushButton("Corriger")
        self.btn_migrate.clicked.connect(self.migrate_current)
        self.btn_migrate.setEnabled(False)
        btn_layout.addWidget(self.btn_migrate)
        
        layout_current.addLayout(btn_layout)
        layout.addWidget(group_current)

        # === SECTION: Résultat ===
        group_result = QtGui.QGroupBox("Résultat")
        layout_result = QtGui.QVBoxLayout(group_result)
        self.text_result = QtGui.QTextEdit()
        self.text_result.setReadOnly(True)
        layout_result.addWidget(self.text_result)
        layout.addWidget(group_result)

        # === SECTION: Migration batch ===
        group_batch = QtGui.QGroupBox("Migration bibliothèque")
        layout_batch = QtGui.QVBoxLayout(group_batch)
        self.label_path = QtGui.QLabel(f"Chemin: {self.library_path or 'Non défini'}")
        layout_batch.addWidget(self.label_path)
        
        self.check_dry_run = QtGui.QCheckBox("Simulation (ne rien modifier)")
        self.check_dry_run.setChecked(True)
        layout_batch.addWidget(self.check_dry_run)
        
        self.btn_batch = QtGui.QPushButton("Migrer toute la bibliothèque")
        self.btn_batch.clicked.connect(self.migrate_batch)
        if not self.library_path: self.btn_batch.setEnabled(False)
        layout_batch.addWidget(self.btn_batch)
        
        layout.addWidget(group_batch)

        # === Boutons ===
        btn_close = QtGui.QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

        self.update_doc_info()

    def update_doc_info(self):
        doc = App.ActiveDocument
        if doc:
            self.current_doc = doc
            self.label_doc.setText(f"{doc.Label}")
            self.btn_check.setEnabled(True)
        else:
            self.current_doc = None
            self.label_doc.setText("Aucun document")
            self.btn_check.setEnabled(False)
            self.btn_migrate.setEnabled(False)

    def check_current(self):
        if not self.current_doc: return
        self.text_result.clear()
        self.text_result.append("Vérification...")
        try:
            res = check_template(self.current_doc)
            self.text_result.append(res.get_summary())
            if res.needs_migration():
                self.btn_migrate.setEnabled(True)
                self.btn_migrate.setText("Corriger")
            else:
                self.btn_migrate.setEnabled(False)
        except Exception as e:
            self.text_result.append(f"Erreur: {str(e)}")

    def migrate_current(self):
        if not self.current_doc: return
        try:
            res = migrate_template(self.current_doc, dry_run=False)
            self.text_result.append(res.get_summary())
            if res.success:
                self.btn_migrate.setEnabled(False)
                self.current_doc.recompute()
                self.text_result.append("Migration terminée. Pensez à sauvegarder.")
        except Exception as e:
            self.text_result.append(f"Erreur: {str(e)}")

    def migrate_batch(self):
        if not self.library_path: return
        dry = self.check_dry_run.isChecked()
        mode = "SIMULATION" if dry else "RÉELLE"
        
        if QtGui.QMessageBox.question(self, "Confirmer", f"Lancer la migration {mode} ?", QtGui.QMessageBox.Yes | QtGui.QMessageBox.No) != QtGui.QMessageBox.Yes:
            return

        self.text_result.clear()
        self.text_result.append(f"Début migration {mode}...")
        QtGui.QApplication.processEvents()
        
        try:
            summary = batch_migrate(self.library_path, dry_run=dry)
            self.text_result.append("\n=== RÉSUMÉ ===")
            self.text_result.append(f"Total: {summary['total']}")
            self.text_result.append(f"Migrés: {summary['migrated']}")
            self.text_result.append(f"Ignorés: {summary['skipped']}")
            self.text_result.append(f"Erreurs: {summary['errors']}")
            
            if summary['errors'] > 0:
                self.text_result.append("\nDétails erreurs:")
                for d in summary['details']:
                    self.text_result.append(f"{d['file']}: {d['error']}")
                    
        except Exception as e:
            self.text_result.append(f"Erreur batch: {str(e)}")

def show_validation_dialog(parent=None, library_path=None):
    dlg = ValidationDialog(parent, library_path)
    dlg.exec_()
