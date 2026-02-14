# Chemin : library/conversion/part_creator.py
# -*- coding: utf-8 -*-
# Path: Library/conversion/part_creator.py
"""
Création du Part pour encapsuler le profil.

Architecture validée:
- Variantes pilotées via Spreadsheet ligne 2 (binding dynamique géré ailleurs)
- Anti-cycle obligatoire:
  Spreadsheet.RefLongueur (E2) = hiddenref(<<PartLabel>>.Longueur) SAUF config 5
  Spreadsheet.RefAngle  (F2) = hiddenref(<<PartLabel>>.Angle)
  Pad.Length -> <<Section datas>>.RefLongueur
  LCS rotation -> <<Section datas>>.RefAngle
  LCS_Top.Z   -> <<Section datas>>.RefLongueur

IMPORTANT:
- CopyOnChange activé sur Section/Longueur/Angle → chaque Link garde ses propres valeurs
- Config 5: Part.Longueur lié PAR EXPRESSION à Spreadsheet.Longueur → standalone 100%
"""
import FreeCAD as App
import traceback

def _ensure_alias(ss, cell, alias):
    try:
        ss.setAlias(cell, alias)
        return True
    except Exception as e:
        print(f"Library- ⚠ Alias '{alias}' sur {cell} impossible: {e}")
        return False

def create_profile_part(doc, body, spreadsheet, variant_names, part_name=None):
    try:
        part = doc.addObject("App::Part", "Part")

        if part_name:
            part.Label = part_name
        else:
            part.Label = body.Label.replace("Body", "Part") if "Body" in body.Label else f"Part_{body.Label}"

        #--- PROPRIÉTÉS INTERNES (masquées, groupe "profile") ---
        part.addProperty("App::PropertyBool", "profile", "profile",
                         "Indique que ce Part est un profil de la bibliothèque")
        part.profile = True
        part.setEditorMode("profile", 2)  # Masqué

        part.addProperty("App::PropertyFile", "profile_source", "profile",
                         "Chemin du fichier source dans la bibliothèque")
        part.profile_source = ""
        part.setEditorMode("profile_source", 2)  # Masqué

        part.addProperty("App::PropertyInteger", "Config", "profile",
                         "Mode de configuration (1-5)")
        part.Config = 1
        part.setEditorMode("Config", 2)  # Masqué

        #=== CopyOnChange sur Update (masqué, nécessaire au mécanisme Link) ===
        part.addProperty("App::PropertyBool", "Update", "profile",
                         "Déclencheur CopyOnChange pour les Links")
        part.Update = True
        part.setPropertyStatus("Update", "CopyOnChange")
        part.setEditorMode("Update", 2)  # Masqué

        #--- PROPRIÉTÉS UTILISATEUR ---
        # Groupe "Profil" : Angle (A) puis Section (S) → tri alphabétique correct
        part.addProperty("App::PropertyAngle", "Angle", "Profil", "Angle utilisateur")
        part.Angle = 0.0
        part.setPropertyStatus("Angle", "CopyOnChange")

        part.addProperty("App::PropertyEnumeration", "Section", "Profil", "Variante")
        part.Section = variant_names
        part.setPropertyStatus("Section", "CopyOnChange")

        # Groupe "Profil longueur" : apparaît après "Profil" alphabétiquement
        part.addProperty("App::PropertyLength", "Longueur", "Profil longueur",
                         "Longueur utilisateur")
        part.Longueur = 100.0
        part.setPropertyStatus("Longueur", "CopyOnChange")

        #--- ENCAPSULATION ---
        part.addObject(body)
        part.addObject(spreadsheet)

        # Supprimer flags draft du body
        for prop_name in ("profile_draft", "profile_profile_draft", "draft"):
            if hasattr(body, prop_name):
                try:
                    body.removeProperty(prop_name)
                except Exception:
                    try:
                        setattr(body, prop_name, False)
                    except Exception:
                        pass

        print(f"Library- ✅ Part créé: Label='{part.Label}', Name='{part.Name}'")
        
        #=== VÉRIFICATION CRITIQUE CopyOnChange ===
        for prop in ['Section', 'Longueur', 'Angle', 'Update']:
            if hasattr(part, prop):
                status = part.getPropertyStatus(prop)
                if "CopyOnChange" not in status:
                    part.setPropertyStatus(prop, "CopyOnChange")
                    print(f"Library- ⚠️  CopyOnChange FORCÉ sur {prop}")
                else:
                    print(f"Library- ✅ CopyOnChange activé sur {prop}")

        return part, True

    except Exception as e:
        print(f"Library- ❌ Erreur création Part: {e}")
        traceback.print_exc()
        return None, False

def setup_part_expressions(part, spreadsheet, pad, config_num=1):
    """
    Configure l'anti-cycle et lie Pad.Length à RefLongueur.
    
    COMPORTEMENT PAR CONFIGURATION:
    - Configs 1-4: RefLongueur = hiddenref(Part.Longueur) → utilisateur contrôle la longueur
                   Part.Longueur éditable → suit l'utilisateur
    - Config 5:    RefLongueur = B2 → longueur fixe par variante
                   Part.Longueur LIÉ PAR EXPRESSION à Spreadsheet.Longueur → standalone 100%
    """
    try:
        ss_label = spreadsheet.Label
        part_ref = f"<<{part.Label}>>"  # référence par Label (FreeCAD met à jour au renommage)

        # Garantir cellules et alias (E2/F2 doivent exister et ne pas être bindées)
        spreadsheet.set("E2", "=0 mm")
        spreadsheet.set("F2", "=0 deg")
        _ensure_alias(spreadsheet, "E2", "RefLongueur")
        _ensure_alias(spreadsheet, "F2", "RefAngle")

        #=== CONFIG 5: Longueur LIÉE PAR EXPRESSION à la Spreadsheet (standalone) ===
        if config_num == 5:
            # Part.Longueur suit AUTOMATIQUEMENT B2 via le DAG FreeCAD
            # → Aucun observer Python requis pour la synchronisation de la valeur
            part.setExpression("Longueur", f"<<{ss_label}>>.Longueur")
            part.setEditorMode("Longueur", 1)  # Lecture seule
            
            # Pad.Length suit directement RefLongueur
            if pad:
                pad.setExpression("Length", f"<<{ss_label}>>.RefLongueur")
            
            print("Library- ✅ Config 5: Part.Longueur lié à Spreadsheet.Longueur (standalone)")
        
        #=== CONFIGS 1-4: Longueur contrôlée PAR L'UTILISATEUR ===
        else:
            # Anti-cycle via hiddenref (le Part n'entre pas dans le DAG)
            spreadsheet.set("E2", f"=hiddenref({part_ref}.Longueur)")
            part.setEditorMode("Longueur", 0)  # Éditable par l'utilisateur
            
            # Pad.Length suit RefLongueur
            if pad:
                pad.setExpression("Length", f"<<{ss_label}>>.RefLongueur")
            
            print(f"Library- ✅ Config {config_num}: RefLongueur = hiddenref(Part.Longueur)")

        # RefAngle toujours en anti-cycle (indépendant de la config)
        spreadsheet.set("F2", f"=hiddenref({part_ref}.Angle)")

        return True

    except Exception as e:
        print(f"Library- ❌ Erreur setup_part_expressions: {e}")
        traceback.print_exc()
        return False

def move_lcs_to_part(doc, body, part, pad, spreadsheet=None):
    """
    Crée LCS_Base et LCS_Top dans le Part et les lie via RefLongueur/RefAngle.
    """
    try:
        part_origin = part.Origin if hasattr(part, "Origin") else None
        if not part_origin:
            doc.recompute()
            part_origin = part.Origin

        xy_plane = None
        if hasattr(part_origin, "OriginFeatures"):
            for f in part_origin.OriginFeatures:
                if "XY" in f.Label or (hasattr(f, "Role") and f.Role == "XY_Plane"):
                    xy_plane = f
                    break

        if not xy_plane:
            print("Library- ⚠ XY_Plane introuvable")
            return None, None, False

        # Supprimer anciens LCS du Body
        for obj in list(body.Group):
            if obj.TypeId == "PartDesign::CoordinateSystem":
                try:
                    body.removeObject(obj)
                    doc.removeObject(obj.Name)
                except Exception:
                    pass

        lcs_base = doc.addObject("PartDesign::CoordinateSystem", "LCS_Base")
        lcs_base.Label = "LCS_Base"
        lcs_base.AttachmentSupport = [(xy_plane, "")]
        lcs_base.MapMode = "FlatFace"
        part.addObject(lcs_base)

        lcs_top = doc.addObject("PartDesign::CoordinateSystem", "LCS_Top")
        lcs_top.Label = "LCS_Top"
        lcs_top.AttachmentSupport = [(xy_plane, "")]
        lcs_top.MapMode = "FlatFace"
        part.addObject(lcs_top)

        doc.recompute()

        if spreadsheet:
            ss_label = spreadsheet.Label
            # IMPORTANT: dépendre de Spreadsheet.Ref*, jamais de Part.*
            lcs_top.setExpression("AttachmentOffset.Base.z", f"<<{ss_label}>>.RefLongueur")
            lcs_base.setExpression("AttachmentOffset.Rotation.Angle", f"<<{ss_label}>>.RefAngle")
            lcs_top.setExpression("AttachmentOffset.Rotation.Angle", f"<<{ss_label}>>.RefAngle")
            print("Library- ✅ LCS liés à RefLongueur/RefAngle")

        return lcs_base, lcs_top, True

    except Exception as e:
        print(f"Library- ❌ Erreur déplacement LCS: {e}")
        traceback.print_exc()
        return None, None, False

def create_pad_if_missing(doc, body, sketch):
    for obj in body.Group:
        if obj.TypeId == "PartDesign::Pad":
            return obj

    try:
        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Label = "Pad"
        pad.Profile = sketch
        pad.Length = 100.0
        doc.recompute()
        return pad
    except Exception as e:
        print(f"Library- ❌ Erreur création Pad: {e}")
        traceback.print_exc()
        return None

def create_lcs_if_missing(doc, body, pad):
    return None, None
