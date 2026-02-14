# Chemin : library/main.py
# -*- coding: utf-8 -*-
# =============================================================================
# INSTALL PATH: {FreeCAD_Macro}/Library/main.py
# =============================================================================
"""Point d'entrée principal de Library"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui
import traceback

def main():
    """Lance l'interface principale de Library."""
    try:
        from .config import ensure_directories
        ensure_directories()
        
        from .interface import LibraryDialog
        dialog = LibraryDialog()
        dialog.exec_()
        
    except Exception as e:
        print(f"Library - ❌ Erreur: {e}")
        traceback.print_exc()
        try:
            QtGui.QMessageBox.critical(None, "Erreur Library", f"Erreur au démarrage:\n{str(e)}")
        except:
            pass
