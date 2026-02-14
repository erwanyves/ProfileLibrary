# Chemin : library/templates/__init__.py
# Library/templates/__init__.py
# -*- coding: utf-8 -*-
"""Module templates - Gestion des templates de profils"""
from .template_creator import (
    get_template_path,
    template_exists,
    create_template_file,
    ensure_template_exists,
    create_new_profile_from_template
)

__all__ = [
    'get_template_path',
    'template_exists',
    'create_template_file',
    'ensure_template_exists',
    'create_new_profile_from_template'
]
