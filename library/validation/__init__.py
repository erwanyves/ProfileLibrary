# Chemin : library/validation/__init__.py
# -*- coding: utf-8 -*-
# Library/validation/__init__.py
"""
Module de validation et migration des templates Library
"""
from .checker import (
    check_template,
    check_document,
    ValidationResult
)

from .migrator import (
    migrate_template,
    batch_migrate,
    MigrationResult
)

all = [
    'check_template',
    'check_document',
    'ValidationResult',
    'migrate_template',
    'batch_migrate',
    'MigrationResult'
]
