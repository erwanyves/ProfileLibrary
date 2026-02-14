# Chemin : library/core/utils.py
# -*- coding: utf-8 -*-
# Path: Library/core/utils.py
"""Utilitaires généraux"""
import os
from datetime import datetime

def format_size(size_bytes):
    """Formate une taille en bytes en format lisible."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def get_file_info(filepath):
    """Récupère les informations d'un fichier."""
    try:
        stat = os.stat(filepath)
        return {
            'name': os.path.basename(filepath),
            'path': filepath,
            'size': stat.st_size,
            'size_formatted': format_size(stat.st_size),
            'modified': datetime.fromtimestamp(stat.st_mtime),
            'is_fcstd': filepath.lower().endswith('.fcstd')
        }
    except Exception as e:
        return {'name': os.path.basename(filepath), 'path': filepath, 'error': str(e)}
