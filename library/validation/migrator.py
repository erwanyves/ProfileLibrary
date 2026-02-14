# Chemin : library/validation/migrator.py
# -*- coding: utf-8 -*-
# Library/validation/migrator.py
"""
Migrateur de templates pour assurer la conformité.
"""
import FreeCAD as App
import traceback
import os

class MigrationResult:
    def __init__(self):
        self.success = True
        self.changes = []
        self.errors = []

    def add_change(self, action, element):
        self.changes.append({'action': action, 'element': element})

    def add_error(self, message):
        self.errors.append(message)
        self.success = False

    def get_summary(self):
        return "Migration réussie" if self.success else f"Échec: {self.errors}"

def migrate_template(doc, dry_run=False):
    """
    Migre un template vers la version actuelle.
    """
    result = MigrationResult()
    try:
        part = next((obj for obj in doc.Objects if obj.TypeId == "App::Part" and hasattr(obj, 'profile')), None)
        if not part:
            result.add_error("Part principal non trouvé")
            return result

        body = next((o for o in part.Group if o.TypeId == "PartDesign::Body"), None)
        spreadsheet = next((o for o in part.Group if o.TypeId == "Spreadsheet::Sheet"), None)
        
        if not body:
            # Récupérer un body orphelin si nécessaire
            for obj in doc.Objects:
                if obj.TypeId == "PartDesign::Body" and obj not in part.Group:
                    body = obj
                    if not dry_run:
                        part.addObject(body)
                        result.add_change("Déplacement", "Body")
                    break

        if not spreadsheet:
            result.add_error("Spreadsheet non trouvée")
            return result

        _migrate_part_properties(part, result, dry_run)
        _migrate_lcs(doc, part, body, result, dry_run)
        _migrate_spreadsheet_aliases(spreadsheet, part, result, dry_run)
        _migrate_bindings(body, spreadsheet, result, dry_run)

        if not dry_run:
            doc.recompute()
            
    except Exception as e:
        traceback.print_exc()
        result.add_error(str(e))
    
    return result

def _migrate_part_properties(part, result, dry_run):
    """Migration complète des propriétés du Part.

    - Ajoute les propriétés manquantes (Config, Angle, Update)
    - Supprime profile_id (obsolète)
    - Masque les propriétés internes (profile, profile_source, Config, Update)
    - Garantit CopyOnChange sur Section/Longueur/Angle/Update
    """
    # 1. Ajouter les propriétés manquantes
    # (nom, type, default, groupe)
    missing_props = {
        'Config': ('App::PropertyInteger', 1, 'profile'),
        'Angle': ('App::PropertyAngle', 0.0, 'Profil'),
        'Update': ('App::PropertyBool', True, 'profile'),
    }
    for name, (ptype, default, group) in missing_props.items():
        if not hasattr(part, name):
            if not dry_run:
                part.addProperty(ptype, name, group, f"Propriété {name}")
                if default is not None:
                    setattr(part, name, default)
                if name == 'Update':
                    part.setPropertyStatus(name, "CopyOnChange")
            result.add_change("Ajout", name)

    # 2. Supprimer profile_id (obsolète, jamais lu)
    if hasattr(part, 'profile_id'):
        if not dry_run:
            try:
                part.removeProperty('profile_id')
            except Exception:
                pass
        result.add_change("Suppression", "profile_id")

    # 3. Masquer les propriétés internes (mode 2 = invisible)
    hidden_props = ('profile', 'profile_source', 'Config', 'Update')
    for prop in hidden_props:
        if hasattr(part, prop):
            if not dry_run:
                current_mode = part.getEditorMode(prop)
                if current_mode != [2]:
                    part.setEditorMode(prop, 2)
                    result.add_change("Masquage", prop)

    # 4. Garantir CopyOnChange sur les propriétés utilisateur
    coc_props = ('Section', 'Longueur', 'Angle', 'Update')
    for prop in coc_props:
        if hasattr(part, prop):
            if not dry_run:
                status = part.getPropertyStatus(prop)
                if "CopyOnChange" not in status:
                    part.setPropertyStatus(prop, "CopyOnChange")
                    result.add_change("CopyOnChange", prop)

def _migrate_lcs(doc, part, body, result, dry_run):
    for lcs_name in ["LCS_Base", "LCS_Top"]:
        lcs = doc.getObject(lcs_name)
        if body and not lcs:
            lcs = next((o for o in body.Group if o.Label == lcs_name), None)
            if lcs and not dry_run:
                body.removeObject(lcs)
                part.addObject(lcs)
                result.add_change("Déplacement", lcs_name)

        if not lcs:
            if not dry_run:
                lcs = doc.addObject("PartDesign::CoordinateSystem", lcs_name)
                lcs.Label = lcs_name
                part.addObject(lcs)
                lcs.MapMode = "Deactivated"
            result.add_change("Création", lcs_name)
        elif lcs not in part.Group:
            if not dry_run:
                part.addObject(lcs)
                result.add_change("Ré-assignation", lcs_name)

def _migrate_spreadsheet_aliases(ss, part, result, dry_run):
    # FIX: Utiliser part.Label au lieu de part.Name pour les expressions
    aliases_to_create = {
        "RefLongueur": f"=hiddenref(<<{part.Label}>>.Longueur)",
        "RefAngle": f"=hiddenref(<<{part.Label}>>.Angle)"
    }

    # Récupérer les noms d'alias existants
    # getAliases() retourne [('E2', 'RefLongueur'), ('F2', 'RefAngle'), ...]
    existing_alias_names = set()
    try:
        for cell, alias_name in ss.getAliases():
            existing_alias_names.add(alias_name)
    except Exception:
        pass

    for alias, formula in aliases_to_create.items():
        if alias in existing_alias_names:
            continue  # Alias déjà défini, rien à faire
        if not dry_run:
            col_letter = _find_free_column(ss)
            if not col_letter:
                result.add_error(f"Pas de colonne libre pour {alias}")
                continue

            ss.set(f"{col_letter}1", f"'{alias}")
            ss.set(f"{col_letter}2", formula)
            try:
                ss.setAlias(f"{col_letter}2", alias)
                result.add_change("Création Alias", alias)
            except Exception as e:
                # Double sécurité : si l'alias existe malgré tout, ce n'est pas une erreur
                if "already" in str(e).lower() or "existe" in str(e).lower():
                    pass  # L'alias existe, OK
                else:
                    result.add_error(f"Alias '{alias}': {e}")
        else:
             result.add_change("Création Alias (simulée)", alias)


def _find_free_column(ss):
    """Trouve la première colonne vide dans la spreadsheet."""
    for col in "ZYXWVUTSRQPONMLKJIHGFEDC": # Parcours inversé
        try:
            if not ss.getContents(f"{col}1"):
                return col
        except:
            continue
    return None

def _migrate_bindings(body, ss, result, dry_run):
    pad = next((o for o in body.Group if o.TypeId == "PartDesign::Pad"), None)
    if pad and not dry_run:
        # Vérifier si binding existe déjà
        bound = False
        if hasattr(pad, "ExpressionEngine"):
            for expr in pad.ExpressionEngine:
                if "Length" in expr[0] and "RefLongueur" in expr[1]:
                    bound = True
                    break
        
        if not bound:
            try:
                pad.setExpression("Length", f"<<{ss.Label}>>.RefLongueur")
                result.add_change("Binding", "Pad.Length")
            except: pass

def batch_migrate(library_path, dry_run=False):
    """Migre tous les templates d'une bibliothèque."""
    summary = {'total': 0, 'migrated': 0, 'skipped': 0, 'errors': 0, 'details': []}
    if not library_path or not os.path.exists(library_path): return summary

    for root, _, files in os.walk(library_path):
        for file in files:
            if file.lower().endswith('.fcstd'):
                file_path = os.path.join(root, file)
                summary['total'] += 1
                doc = None
                try:
                    doc = App.openDocument(file_path, hidden=True)
                    if not doc:
                        continue

                    # Vérifier si c'est un template (Part avec profile=True)
                    part = next((obj for obj in doc.Objects
                                 if obj.TypeId == "App::Part"
                                 and hasattr(obj, 'profile')), None)
                    if not part:
                        # Draft ou fichier non-template → ignorer silencieusement
                        summary['skipped'] += 1
                        continue

                    res = migrate_template(doc, dry_run=dry_run)
                    if res.success:
                        if res.changes and not dry_run:
                            doc.recompute()
                            doc.save()
                        if res.changes:
                            summary['migrated'] += 1
                        else:
                            summary['skipped'] += 1
                    else:
                        summary['errors'] += 1
                        summary['details'].append({'file': file, 'error': res.errors})
                except Exception as e:
                    summary['errors'] += 1
                    summary['details'].append({'file': file, 'error': str(e)})
                finally:
                    if doc:
                        try:
                            App.closeDocument(doc.Name)
                        except Exception:
                            pass
    return summary
