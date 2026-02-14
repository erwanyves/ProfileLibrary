# Chemin : library/validation/checker.py
# -*- coding: utf-8 -*-
# Library/validation/checker.py
"""
Vérificateur de structure des templates
"""
import FreeCAD as App
import traceback

class ValidationResult:
    def __init__(self):
        self.is_valid = True
        self.missing = []
        self.errors = []

    def add_missing(self, name, type_):
        self.missing.append({'name': name, 'type': type_})
        self.is_valid = False

    def add_error(self, msg):
        self.errors.append(msg)
        self.is_valid = False

    def needs_migration(self):
        return len(self.missing) > 0

    def get_summary(self):
        lines = []
        if self.missing:
            lines.append("Éléments manquants :")
            for m in self.missing:
                lines.append(f" - {m['name']} ({m['type']})")
        if self.errors:
            lines.append("Erreurs critiques :")
            for e in self.errors:
                lines.append(f" - {e}")
        return "\n".join(lines) if lines else "Template valide."

def check_template(doc):
    """Vérifie si le document est un template valide."""
    result = ValidationResult()
    if not doc:
        result.add_error("Document non valide fourni.")
        return result

    try:
        part = next((obj for obj in doc.Objects if obj.TypeId == "App::Part" and hasattr(obj, 'profile')), None)
        if not part:
            result.add_missing("Part container avec prop 'profile'", "App::Part")
            return result # Arrêt si pas de Part principal

        props = ['Section', 'Longueur', 'Angle', 'Config']
        for p in props:
            if not hasattr(part, p):
                result.add_missing(f"Propriété Part.{p}", "Property")

        ss = next((obj for obj in part.Group if obj.TypeId == "Spreadsheet::Sheet"), None)
        if not ss:
            result.add_missing("Spreadsheet", "Object")
        else:
            aliases_to_check = ["RefLongueur", "RefAngle"]
            for alias in aliases_to_check:
                try:
                    ss.getAlias(alias)
                except Exception:
                    result.add_missing(f"Alias {alias} dans Spreadsheet", "Alias")

        # FIX: Vérifier que l'objet LCS est bien DANS le groupe du Part
        if not any(o.Label == "LCS_Base" for o in part.Group):
            result.add_missing("LCS_Base dans Part", "Object")
        if not any(o.Label == "LCS_Top" for o in part.Group):
            result.add_missing("LCS_Top dans Part", "Object")

    except Exception as e:
        result.add_error(f"Erreur inattendue: {str(e)}")
        traceback.print_exc()

    return result

def check_document(doc):
    return check_template(doc)
