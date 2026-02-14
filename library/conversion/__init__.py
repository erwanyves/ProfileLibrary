# Chemin : library/conversion/__init__.py
# -*- coding: utf-8 -*-
# Path: Library/conversion/__init__.py
"""
Module de conversion draft -> template
"""

# Le contenu de ce fichier a été intentionnellement simplifié pour résoudre 
# un problème de dépendance circulaire lors de l'importation des sous-modules
# (converter, part_creator, etc.).

# Les autres modules doivent maintenant importer directement depuis les sous-modules.
# Par exemple : from .converter import convert_draft_to_template
# Au lieu de : from ..conversion import convert_draft_to_template

# La liste __all__ est conservée pour déclarer l'API publique du package,
# mais elle ne déclenche pas d'importation.
__all__ = [
    # from .converter
    'convert_draft_to_template',
    'save_template_to_library',
    'get_conversion_summary',
    'ConversionResult',
    
    # from .spreadsheet_creator
    'create_profile_spreadsheet',
    'setup_dynamic_binding',
    'link_sketch_to_spreadsheet',
    
    # from .part_creator
    'create_profile_part',
    'setup_part_expressions',
    'move_lcs_to_part',
    'create_pad_if_missing',
    'create_lcs_if_missing',
    
    # from .conversion_dialog
    'ConversionDialog',
    'show_conversion_dialog',
]
