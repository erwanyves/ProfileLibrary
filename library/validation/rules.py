# Chemin : library/validation/rules.py
# Library/validation/rules.py
# -*- coding: utf-8 -*-
"""
Règles de validation des templates - versionnées pour permettre les migrations
"""

# Version actuelle des templates
CURRENT_VERSION = 1

# === RÈGLES VERSION 1 ===
TEMPLATE_RULES_V1 = {
    'version': 1,
    'description': "Structure initiale avec Part, Body, Spreadsheet, LCS",
    
    # Règles pour le Part
    'part': {
        'required_properties': [
            {
                'name': 'profile',
                'type': 'App::PropertyBool',
                'group': 'profile',
                'default': True,
                'readonly': True,
                'description': "Identifie le Part comme un profil Library"
            },
            {
                'name': 'Section',
                'type': 'App::PropertyEnumeration',
                'group': 'Profil',
                'default': ['Variante_1'],
                'copy_on_change': True,
                'description': "Sélection de la variante"
            },
            {
                'name': 'Longueur',
                'type': 'App::PropertyLength',
                'group': 'Profil longueur',
                'default': 100.0,
                'copy_on_change': True,
                'description': "Longueur du profilé"
            },
        ],
        'optional_properties': [
            {
                'name': 'Angle',
                'type': 'App::PropertyAngle',
                'group': 'Profil',
                'default': 0.0,
                'copy_on_change': True,
                'description': "Angle de rotation des LCS"
            },
            {
                'name': 'Update',
                'type': 'App::PropertyBool',
                'group': 'profile',
                'default': True,
                'copy_on_change': True,
                'description': "Déclencheur CopyOnChange pour les Links"
            },
        ],
    },
    
    # Règles pour le Body
    'body': {
        'required_objects': [
            {
                'type': 'Sketcher::SketchObject',
                'min_count': 1,
                'description': "Au moins un Sketch"
            },
            {
                'type': 'PartDesign::Pad',
                'min_count': 1,
                'description': "Au moins un Pad"
            },
        ],
        'pad_binding': {
            'property': 'Length',
            'expression': '<<Section datas>>.RefLongueur',
            'description': "Pad.Length lié à la Spreadsheet"
        },
    },
    
    # Règles pour la Spreadsheet
    'spreadsheet': {
        'label': 'Section datas',
        'required_aliases': [
            {
                'name': 'Prefered',
                'row': 2,
                'description': "Alias pour le champ Prefered"
            },
        ],
        'optional_aliases': [
            {
                'name': 'RefLongueur',
                'row': 2,
                'expression': 'hiddenref(<<{part_label}>>.Longueur)',
                'description': "Référence à Part.Longueur (évite cycles)"
            },
            {
                'name': 'RefAngle',
                'row': 2,
                'expression': 'hiddenref(<<{part_label}>>.Angle)',
                'description': "Référence à Part.Angle (évite cycles)"
            },
        ],
        'structure': {
            'header_row': 1,
            'ref_row': 2,
            'data_start_row': 3,
            'section_column': 'A',
        },
    },
    
    # Règles pour les LCS
    'lcs': {
        'required': [
            {
                'label': 'LCS_Base',
                'attachment_support': 'XY_Plane',
                'map_mode': 'FlatFace',
                'bindings': {
                    'AttachmentOffset.Rotation.Angle': '<<Section datas>>.RefAngle',
                },
                'description': "LCS à l'origine du profil"
            },
            {
                'label': 'LCS_Top',
                'attachment_support': 'XY_Plane',
                'map_mode': 'FlatFace',
                'bindings': {
                    'AttachmentOffset.Base.z': '<<Section datas>>.RefLongueur',
                    'AttachmentOffset.Rotation.Angle': '<<Section datas>>.RefAngle',
                },
                'description': "LCS à l'extrémité du profil"
            },
        ],
        'location': 'part',  # Les LCS doivent être dans le Part, pas le Body
    },
}

# Dictionnaire des versions disponibles
TEMPLATE_RULES = {
    1: TEMPLATE_RULES_V1,
}


def get_rules(version=None):
    """
    Récupère les règles pour une version donnée.
    
    Args:
        version: Version des règles (None = version actuelle)
    
    Returns:
        dict: Règles de validation
    """
    if version is None:
        version = CURRENT_VERSION
    
    if version not in TEMPLATE_RULES:
        raise ValueError(f"Version {version} non supportée. Versions disponibles: {list(TEMPLATE_RULES.keys())}")
    
    return TEMPLATE_RULES[version]


def get_current_version():
    """Retourne la version actuelle des règles."""
    return CURRENT_VERSION
