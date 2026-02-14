# Chemin : library/conversion/spreadsheet_creator.py
# -*- coding: utf-8 -*-
# Path: Library/conversion/spreadsheet_creator.py
"""
Spreadsheet stable:
A Section
B Longueur (variant)
C Longueur_liste (variant)
D Preferred (variant)
E RefLongueur (anti-cycle hiddenref Part.Longueur SAUF config 5 où =B2)
F RefAngle (anti-cycle hiddenref Part.Angle)
G.. contraintes nommées (variant)

Binding dynamique:
- Configs 1-4: .cells.Bind pour B..D et contraintes
- Config 5:     RefLongueur = B2 (longueur fixe par variante)
"""
import traceback

_COLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

def create_profile_spreadsheet(doc, constraints, variant_name="Variante_1"):
    try:
        ss = doc.addObject("Spreadsheet::Sheet", "Section_datas")
        ss.Label = "Section datas"

        # En-têtes fixes
        ss.set("A1", "'Section")
        ss.set("B1", "'Longueur")
        ss.set("C1", "'Longueur_liste")
        ss.set("D1", "'Preferred")
        ss.set("E1", "'RefLongueur")
        ss.set("F1", "'RefAngle")

        # Contraintes à partir de G
        constraint_cols = {}
        start_idx = 6  # G
        for i, c in enumerate(constraints):
            col = _COLS[start_idx + i]
            name = c["name"]
            ss.set(f"{col}1", f"'{name}")
            constraint_cols[name] = col

        # Ligne 2 (références + alias)
        ss.set("A2", "=.A3")
        ss.setAlias("A2", "Section_ref")

        ss.set("B2", "=.B3")
        ss.setAlias("B2", "Longueur")

        ss.set("C2", "=.C3")
        ss.setAlias("C2", "Longueur_liste")

        ss.set("D2", "=.D3")
        ss.setAlias("D2", "Preferred")

        # E/F: anti-cycle (valeurs init valides + alias garantis)
        ss.set("E2", "=0 mm")
        ss.set("F2", "=0 deg")
        ss.setAlias("E2", "RefLongueur")
        ss.setAlias("F2", "RefAngle")

        # Contraintes: alias sur ligne 2
        for name, col in constraint_cols.items():
            ss.set(f"{col}2", f"=.{col}3")
            ss.setAlias(f"{col}2", name)

        # Ligne 3: variante 1
        ss.set("A3", f"'{variant_name}")
        ss.set("B3", "=100 mm")
        ss.set("C3", "'100;200;300;500;1000")
        ss.set("D3", "1")

        for name, col in constraint_cols.items():
            v = next((cc.get("value") for cc in constraints if cc["name"] == name), None)
            if v is None:
                ss.set(f"{col}3", "=0 mm")
            else:
                ss.set(f"{col}3", f"={float(v)} mm")

        last_constraint_col = _COLS[start_idx + len(constraints) - 1] if constraints else None

        config_info = {
            "ref_row": 2,
            "start_row": 3,
            "last_constraint_col": last_constraint_col,
            "bind_ranges": [
                ("B", "D"),
                ("G", last_constraint_col) if last_constraint_col else None
            ]
        }
        config_info["bind_ranges"] = [r for r in config_info["bind_ranges"] if r is not None]

        print("Library- ✅ Spreadsheet créée (RefLongueur/RefAngle garantis)")
        return ss, config_info

    except Exception as e:
        print(f"Library- ❌ Erreur création Spreadsheet: {e}")
        traceback.print_exc()
        return None, None

def setup_dynamic_binding(spreadsheet, part_internal_name, config_info, config_num=1):
    """
    Configure les liaisons selon la configuration:
    
    CONFIG 5 (longueur fixe par variante):
    - RefLongueur = B2 → longueur fixe par variante
    - Pad.Length suit directement B2 via RefLongueur
    
    CONFIGS 1-4:
    - .cells.Bind normal pour B..D et contraintes
    - RefLongueur = hiddenref(Part.Longueur)
    """
    try:
        ref_row = config_info["ref_row"]
        start_row = config_info["start_row"]

        # A2: nom de section sélectionnée (lecture seule)
        spreadsheet.set(f"A{ref_row}", f"=hiddenref({part_internal_name}.Section.String)")

        if config_num == 5:
            #=== CONFIG 5: RefLongueur = B2 (longueur fixe par variante) ===
            spreadsheet.set("E2", "=B2")
            print("Library- ✅ Config 5: RefLongueur = B2 (longueur fixe par variante)")
        
        else:
            #=== CONFIGS 1-4: .cells.Bind normal + hiddenref ===
            for first_col, last_col in config_info["bind_ranges"]:
                binding_expr = (
                    f"tuple(.cells;"
                    f"<<{first_col}>>+ str(hiddenref({part_internal_name}.Section)+{start_row}); "
                    f"<<{last_col}>>+ str(hiddenref({part_internal_name}.Section)+{start_row}))"
                )
                spreadsheet.setExpression(
                    f".cells.Bind.{first_col}{ref_row}.{last_col}{ref_row}",
                    binding_expr
                )
            
            # RefLongueur = hiddenref(Part.Longueur)
            part_label = spreadsheet.Document.getObject(part_internal_name).Label
            spreadsheet.set("E2", f"=hiddenref(<<{part_label}>>.Longueur)")
            print(f"Library- ✅ Config {config_num}: .cells.Bind + hiddenref(Part.Longueur)")

        # RefAngle toujours en anti-cycle (indépendant de la config)
        part_label = spreadsheet.Document.getObject(part_internal_name).Label
        spreadsheet.set("F2", f"=hiddenref(<<{part_label}>>.Angle)")

        print("Library- ✅ Liaisons configurées")
        return True

    except Exception as e:
        print(f"Library- ❌ Erreur configuration liaisons: {e}")
        traceback.print_exc()
        return False

def link_sketch_to_spreadsheet(sketch, spreadsheet, constraints):
    linked = 0
    ss_label = spreadsheet.Label

    for c in constraints:
        try:
            sketch.setExpression(
                f"Constraints[{c['index']}]",
                f"<<{ss_label}>>.{c['name']}"
            )
            linked += 1
        except Exception as e:
            print(f"Library- ⚠ Liaison contrainte '{c['name']}' impossible: {e}")

    print(f"Library- ✅ {linked}/{len(constraints)} contraintes liées à la Spreadsheet")
    return linked
