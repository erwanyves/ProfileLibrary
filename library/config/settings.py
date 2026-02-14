# Chemin : library/config/settings.py
# -*- coding: utf-8 -*-
# Path: Library/config/settings.py
"""Gestion des paramètres utilisateur"""
import json
import os
from .paths import get_library_dir

def _get_config_path():
    return os.path.join(get_library_dir(), "config", "config.json")

def _default_config():
    return {
        'user_library_path': '',
        'language': 'fr',
        'last_folder': '',
        'recent_files': []
    }

def load_config():
    """Charge la configuration."""
    path = _get_config_path()
    default = _default_config()
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for k, v in default.items():
                    config.setdefault(k, v)
                return config
        except:
            pass
    return default

def save_config(config):
    """Sauvegarde la configuration."""
    path = _get_config_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Library - ❌ Erreur sauvegarde config: {e}")
        return False
