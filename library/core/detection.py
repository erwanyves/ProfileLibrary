# Chemin : library/core/detection.py
# -*- coding: utf-8 -*-
# Path: Library/core/detection.py
"""
Détection du contexte de sélection FreeCAD
Analyse ce qui est sélectionné pour déterminer l'action appropriée
"""
import FreeCAD as App
import FreeCADGui as Gui

# Types de contexte
CONTEXT_NONE = "none"           # Rien sélectionné → proposer insertion/création
CONTEXT_DRAFT = "draft"         # Body avec profile_draft=true → proposer conversion
CONTEXT_BODY = "body"           # Body standard → proposer création draft
CONTEXT_PROFILE = "profile"     # Part avec profile=true → proposer édition variantes
CONTEXT_LINK = "link"           # Link vers profil → proposer mise à jour/changement


def is_draft_body(obj):
    """Vérifie si un objet est un Body draft (propriété draft=true dans le groupe profile)."""
    if obj is None:
        return False
    if obj.TypeId != "PartDesign::Body":
        return False
    
    draft_props = ['profile_draft', 'profile_profile_draft', 'draft']
    
    for prop in draft_props:
        if hasattr(obj, prop):
            try:
                if getattr(obj, prop) == True:
                    return True
            except:
                pass
    
    return False


def is_profile_part(obj):
    """Vérifie si un objet est un Part profil converti (profile=true)."""
    if obj is None:
        return False
    if obj.TypeId != "App::Part":
        return False
    
    profile_props = ['profile', 'profile_profile']
    
    for prop in profile_props:
        if hasattr(obj, prop):
            try:
                if getattr(obj, prop) == True:
                    return True
            except:
                pass
    
    return False


def is_profile_link(obj):
    """Vérifie si un objet est un Link vers un profil."""
    if obj is None:
        return False
    if obj.TypeId != "App::Link":
        return False
    
    if hasattr(obj, 'LinkedObject') and obj.LinkedObject:
        return is_profile_part(obj.LinkedObject)
    return False


def get_named_constraints(sketch):
    """
    Récupère les contraintes nommées d'un sketch.
    
    Returns:
        list: [{'name': str, 'index': int, 'value': float, 'type': str}, ...]
    """
    constraints = []
    
    if sketch is None or sketch.TypeId != "Sketcher::SketchObject":
        return constraints
    
    try:
        for i, c in enumerate(sketch.Constraints):
            name = c.Name if hasattr(c, 'Name') else ''
            if name and not name.startswith('Constraint'):
                constraints.append({
                    'name': name,
                    'index': i,
                    'value': c.Value if hasattr(c, 'Value') else None,
                    'type': c.Type if hasattr(c, 'Type') else 'Unknown'
                })
    except Exception as e:
        print(f"Library - ⚠️ Erreur lecture contraintes: {e}")
    
    return constraints


def find_sketch_in_body(body):
    """Trouve le premier Sketch dans un Body."""
    if body is None or body.TypeId != "PartDesign::Body":
        return None
    
    for obj in body.Group:
        if obj.TypeId == "Sketcher::SketchObject":
            return obj
    return None


def find_pad_in_body(body):
    """Trouve le premier Pad dans un Body."""
    if body is None or body.TypeId != "PartDesign::Body":
        return None
    
    for obj in body.Group:
        if obj.TypeId == "PartDesign::Pad":
            return obj
    return None


def find_lcs_in_body(body):
    """
    Trouve les LCS dans un Body.
    
    Returns:
        dict: {'base': LCS_Base or None, 'top': LCS_Top or None}
    """
    result = {'base': None, 'top': None}
    
    if body is None or body.TypeId != "PartDesign::Body":
        return result
    
    for obj in body.Group:
        if obj.TypeId == "PartDesign::CoordinateSystem":
            if obj.Label == "LCS_Base":
                result['base'] = obj
            elif obj.Label == "LCS_Top":
                result['top'] = obj
    
    return result


def analyze_body(body):
    """
    Analyse un Body pour vérifier sa structure.
    
    Returns:
        dict: Informations sur le Body
    """
    result = {
        'body': body,
        'is_draft': is_draft_body(body),
        'sketch': find_sketch_in_body(body),
        'pad': find_pad_in_body(body),
        'lcs': find_lcs_in_body(body),
        'constraints': [],
        'issues': [],
        'ready_for_conversion': False
    }
    
    if result['sketch']:
        result['constraints'] = get_named_constraints(result['sketch'])
    
    if not result['sketch']:
        result['issues'].append("Aucun Sketch trouvé")
    elif not result['constraints']:
        result['issues'].append("Aucune contrainte nommée dans le Sketch")
    
    if not result['pad']:
        result['issues'].append("Aucun Pad trouvé (sera créé automatiquement)")
    
    if result['is_draft'] and result['sketch'] and result['constraints']:
        result['ready_for_conversion'] = True
    
    return result


def analyze_selection():
    """
    Analyse la sélection actuelle dans FreeCAD.
    
    Returns:
        dict: {
            'context': str,
            'object': FreeCAD object or None,
            'analysis': dict (pour les Bodies),
            'message': str
        }
    """
    result = {
        'context': CONTEXT_NONE,
        'object': None,
        'analysis': None,
        'message': "Aucune sélection"
    }
    
    if App.ActiveDocument is None:
        result['message'] = "Aucun document ouvert"
        return result
    
    selection = Gui.Selection.getSelection()
    
    if not selection:
        result['context'] = CONTEXT_NONE
        result['message'] = "Aucun objet sélectionné"
        return result
    
    obj = selection[0]
    result['object'] = obj
    
    if is_draft_body(obj):
        result['context'] = CONTEXT_DRAFT
        result['analysis'] = analyze_body(obj)
        n = len(result['analysis']['constraints'])
        result['message'] = f"✅ Draft de profil ({n} contraintes nommées)"
        return result
    
    if obj.TypeId == "PartDesign::Body":
        result['context'] = CONTEXT_BODY
        result['analysis'] = analyze_body(obj)
        result['message'] = "Body standard (non marqué comme draft)"
        return result
    
    if is_profile_part(obj):
        result['context'] = CONTEXT_PROFILE
        result['message'] = "📦 Profil (template converti)"
        return result
    
    if is_profile_link(obj):
        result['context'] = CONTEXT_LINK
        result['message'] = "🔗 Link vers un profil"
        return result
    
    result['context'] = CONTEXT_NONE
    result['message'] = f"Objet {obj.TypeId}"
    return result


def get_available_actions(context):
    """
    Retourne les actions disponibles selon le contexte.
    
    Args:
        context: str (CONTEXT_*)
    
    Returns:
        list of tuples: [(action_id, label, description), ...]
    """
    actions = []
    
    if context == CONTEXT_NONE:
        actions = [
            ('insert', "📥 Insérer un profil", "Insérer un profil depuis la bibliothèque"),
            ('create', "📝 Nouveau profil", "Créer un nouveau draft de profil")
        ]
    
    elif context == CONTEXT_DRAFT:
        actions = [
            ('convert', "⚙️ Convertir en template", "Finaliser le profil et l'ajouter à la bibliothèque")
        ]
    
    elif context == CONTEXT_BODY:
        actions = [
            ('insert', "📥 Insérer un profil", "Insérer un profil depuis la bibliothèque"),
            ('create', "📝 Nouveau profil", "Créer un nouveau draft de profil")
        ]
    
    elif context == CONTEXT_PROFILE:
        actions = [
            ('edit', "✏️ Éditer les variantes", "Modifier les variantes du profil")
        ]
    
    elif context == CONTEXT_LINK:
        actions = [
            ('update', "🔄 Mettre à jour", "Synchroniser avec le template source"),
            ('change_variant', "📋 Changer de variante", "Sélectionner une autre variante"),
            ('change_template', "🔀 Changer de template", "Remplacer par un autre profil")
        ]
    
    return actions
