# Chemin : library/config/__init__.py
# -*- coding: utf-8 -*-
# Path: Library/config/__init__.py
"""Module config - Gestion des chemins et paramètres"""
from .paths import get_macro_dir, get_library_dir, ensure_directories
from .settings import load_config, save_config

__all__ = ['get_macro_dir', 'get_library_dir', 'ensure_directories', 'load_config', 'save_config']
