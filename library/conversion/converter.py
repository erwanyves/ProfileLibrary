# Chemin : library/conversion/converter.py
# -*- coding: utf-8 -*-
# Path: Library/conversion/converter.py
"""
Convertisseur de draft en template
Orchestre le processus complet de conversion
"""
import FreeCAD as App
import FreeCADGui as Gui
import os
import time
import traceback

class ConversionResult:
    """Résultat d'une conversion."""
    def __init__(self):
        self.success = False
        self.message = ""
        self.part = None
        self.spreadsheet = None
        self.warnings = []

    def add_warning(self, warning):
        self.warnings.append(warning)

def convert_draft_to_template(body, variant_name="Variante_1", part_name=None):
    """
    Convertit un Body draft en template complet.
    """
    # Lazy imports (évite soucis de chargement)
    from ..core.detection import get_named_constraints
    from .spreadsheet_creator import (
        create_profile_spreadsheet,
        setup_dynamic_binding,
        link_sketch_to_spreadsheet
    )
    from .part_creator import (
        create_profile_part,
        setup_part_expressions,
        move_lcs_to_part,
        create_pad_if_missing,
        create_lcs_if_missing
    )

    result = ConversionResult()
    doc = body.Document

    print(f"\nLibrary- ⚙️ Début conversion: {body.Label}")
    print("=" * 50)

    try:
        #===[1/7] Prérequis===
        print("Library-[1/7] Vérification des prérequis...")

        sketch = next((o for o in body.Group if o.TypeId == "Sketcher::SketchObject"), None)
        if not sketch:
            result.message = "Aucun Sketch trouvé dans le Body"
            return result

        constraints = get_named_constraints(sketch)
        if not constraints:
            result.message = "Aucune contrainte nommée dans le Sketch"
            return result

        print(f"Library- ✅ Sketch: {sketch.Label}")
        print(f"Library- ✅ {len(constraints)} contraintes nommées")

        #===[2/7] Pad===
        print("Library-[2/7] Vérification du Pad...")

        pad = next((o for o in body.Group if o.TypeId == "PartDesign::Pad"), None)
        if not pad:
            pad = create_pad_if_missing(doc, body, sketch)
            if not pad:
                result.message = "Impossible de créer le Pad"
                return result
            result.add_warning("Pad créé automatiquement (100mm)")

        print(f"Library- ✅ Pad: {pad.Label}")

        #===[3/7] Nettoyage LCS du Body===
        print("Library-[3/7] Nettoyage des LCS existants du Body...")
        try:
            create_lcs_if_missing(doc, body, pad)
        except Exception:
            # non bloquant
            pass

        #===[4/7] Spreadsheet===
        print("Library-[4/7] Création de la Spreadsheet...")
        spreadsheet, config_info = create_profile_spreadsheet(doc, constraints, variant_name)
        if not spreadsheet:
            result.message = "Erreur création Spreadsheet"
            return result

        result.spreadsheet = spreadsheet
        print(f"Library- ✅ Spreadsheet: {spreadsheet.Label}")

        #===[5/7] Part===
        print("Library-[5/7] Création du Part...")
        part, ok = create_profile_part(doc, body, spreadsheet, [variant_name], part_name)
        if not ok or not part:
            result.message = "Erreur création Part"
            return result

        result.part = part
        print(f"Library- ✅ Part: {part.Label} (Name={part.Name})")

        #=== VÉRIFICATION CRITIQUE CopyOnChange ===
        for prop in ['Section', 'Longueur', 'Angle']:
            if hasattr(part, prop):
                status = part.getPropertyStatus(prop)
                if "CopyOnChange" not in status:
                    part.setPropertyStatus(prop, "CopyOnChange")
                    print(f"Library- ⚠️  CopyOnChange activé manuellement sur {prop}")
                else:
                    print(f"Library- ✅ CopyOnChange activé sur {prop}")

        #===[6/7] Liaisons===
        print("Library-[6/7] Configuration des liaisons...")

        # 6.1 Anti-cycle + Pad.Length -> RefLongueur
        if not setup_part_expressions(part, spreadsheet, pad, config_num=1):
            result.add_warning("Anti-cycle RefLongueur/RefAngle non configuré")

        # 6.2 Binding dynamique des variantes (ligne 2)
        if not setup_dynamic_binding(spreadsheet, part.Name, config_info, config_num=1):
            result.add_warning("Binding dynamique des variantes non configuré")

        # 6.3 Contraintes sketch -> alias ligne 2
        link_sketch_to_spreadsheet(sketch, spreadsheet, constraints)

        doc.recompute()

        #===[7/7] LCS dans le Part===
        print("Library-[7/7] Finalisation (LCS)...")
        lcs_base, lcs_top, lcs_ok = move_lcs_to_part(doc, body, part, pad, spreadsheet)
        if not lcs_ok:
            result.add_warning("LCS non créés / non liés correctement")

        # Final
        sketch.Visibility = False
        doc.recompute()
        Gui.updateGui()

        print("=" * 50)
        print("Library- ✅ Conversion terminée avec succès")

        result.success = True
        result.message = f"Profil '{part.Label}' créé avec {len(constraints)} paramètres"
        if result.warnings:
            result.message += "\n\nAvertissements:\n-" + "\n-".join(result.warnings)

        return result

    except Exception as e:
        print(f"Library- ❌ Erreur conversion: {e}")
        traceback.print_exc()
        result.message = f"Erreur: {str(e)}"
        return result

def save_template_to_library(doc, part, dest_path):
    """
    Sauvegarde le template dans la bibliothèque (avec retry en cas de lock).
    """
    try:
        if hasattr(part, "profile_source"):
            part.profile_source = dest_path

        if not dest_path.lower().endswith(".fcstd"):
            dest_path += ".FCStd"

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        max_retries = 3
        retry_delay = 1
        for attempt in range(max_retries):
            try:
                doc.saveAs(dest_path)
                print(f"Library- ✅ Template sauvegardé: {dest_path}")
                return True, f"Template sauvegardé: {os.path.basename(dest_path)}"
            except OSError:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

    except Exception as e:
        print(f"Library- ❌ Erreur sauvegarde: {e}")
        traceback.print_exc()
        return False, f"Erreur sauvegarde: {str(e)}"

def get_conversion_summary(result):
    """
    Génère un résumé de la conversion.
    """
    if not result or not result.success:
        msg = result.message if result else "Résultat vide"
        return f"❌ Échec de la conversion\n\n{msg}"

    summary = [
        "✅ Conversion réussie!",
        "",
        f"Part: {result.part.Label if result.part else '?'}",
        f"Spreadsheet: {result.spreadsheet.Label if result.spreadsheet else '?'}",
    ]

    if result.warnings:
        summary.append("")
        summary.append("⚠ Avertissements:")
        for w in result.warnings:
            summary.append(f"- {w}")

    return "\n".join(summary)

#=== OBSERVER CONFIG 5 ===
# NOTE: Désormais géré par l'observer unifié dans variant_editor.py
# On garde la fonction d'installation pour compatibilité d'import mais elle
# délègue à ensure_observer().

_config5_observer = None

def _install_config5_observer():
    """Installe l'observer unifié (délègue à variant_editor.ensure_observer)."""
    global _config5_observer
    if _config5_observer is None:
        try:
            from ..interface.variant_editor import ensure_observer
            ensure_observer()
            _config5_observer = True  # marqueur, pas un vrai observer
            print("Library- Observer profil unifié installé via converter")
        except Exception as e:
            print(f"Library- Observer init différée: {e}")
