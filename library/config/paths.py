# Chemin : library/config/paths.py
# -*- coding: utf-8 -*-
# Path: Library/config/paths.py
"""Gestion des chemins de Library"""
import os
import sys

def get_macro_dir():
    """Récupère le répertoire des macros FreeCAD."""
    if sys.platform == 'win32':
        appdata = os.getenv('APPDATA')
        if appdata:
            macro_dir = os.path.join(appdata, "FreeCAD", "Macro")
            if os.path.exists(macro_dir):
                return macro_dir
    try:
        import FreeCAD as App
        if hasattr(App, 'ConfigGet'):
            return os.path.join(App.ConfigGet("UserAppData"), "Macro")
    except:
        pass
    return os.path.expanduser("~/FreeCAD/Macro")

def get_library_dir():
    """Retourne le répertoire d'installation de Library."""
    return os.path.join(get_macro_dir(), "Library")

def ensure_directories():
    """Crée les répertoires nécessaires."""
    lib_dir = get_library_dir()
    for subdir in ["config", "templates"]:
        os.makedirs(os.path.join(lib_dir, subdir), exist_ok=True)
    return lib_dir
