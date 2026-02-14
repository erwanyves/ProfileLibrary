# Chemin : library/templates/template_creator.py
# Library/templates/template_creator.py
# -*- coding: utf-8 -*-
"""
Création et gestion du template de base pour les profils
"""
import FreeCAD as App
import os
import traceback
import shutil

from ..config import get_library_dir

TEMPLATE_FILENAME = "template_profile.FCStd"

def get_template_path():
    """Retourne le chemin du template de base."""
    return os.path.join(get_library_dir(), "templates", TEMPLATE_FILENAME)

def template_exists():
    """Vérifie si le template existe."""
    return os.path.exists(get_template_path())

def create_template_file():
    """
    Crée le fichier template_profile.FCStd avec la structure de base.
    """
    template_path = get_template_path()
    try:
        os.makedirs(os.path.dirname(template_path), exist_ok=True)
        doc = App.newDocument("template_profile", hidden=True)
        
        body = doc.addObject("PartDesign::Body", "Body")
        body.Label = "Body"
        body.addProperty("App::PropertyBool", "draft", "profile", "Indique que c'est un draft de profil à convertir")
        body.draft = True

        sketch = body.newObject("Sketcher::SketchObject", "Sketch")
        sketch.Label = "Sketch"
        sketch.MapMode = "FlatFace"

        xy_plane = next((f for f in body.Origin.OriginFeatures if "XY" in f.Label or (hasattr(f, 'Role') and f.Role == "XY_Plane")), None)
        if xy_plane:
            sketch.AttachmentSupport = [(xy_plane, '')]
        else:
            print("Library - XY_Plane non trouvé.")

        import Part
        import Sketcher
        sketch.addGeometry(Part.LineSegment(App.Vector(-20,-10,0), App.Vector(20,-10,0)), False)
        sketch.addGeometry(Part.LineSegment(App.Vector(20,-10,0), App.Vector(20,10,0)), False)
        sketch.addGeometry(Part.LineSegment(App.Vector(20,10,0), App.Vector(-20,10,0)), False)
        sketch.addGeometry(Part.LineSegment(App.Vector(-20,10,0), App.Vector(-20,-10,0)), False)
        sketch.addConstraint(Sketcher.Constraint('Coincident',0,2,1,1))
        sketch.addConstraint(Sketcher.Constraint('Coincident',1,2,2,1))
        sketch.addConstraint(Sketcher.Constraint('Coincident',2,2,3,1))
        sketch.addConstraint(Sketcher.Constraint('Coincident',3,2,0,1))
        sketch.addConstraint(Sketcher.Constraint('Horizontal',0))
        sketch.addConstraint(Sketcher.Constraint('Horizontal',2))
        sketch.addConstraint(Sketcher.Constraint('Vertical',1))
        sketch.addConstraint(Sketcher.Constraint('Vertical',3))
        sketch.addConstraint(Sketcher.Constraint('Symmetric',0,1,0,2,-1,1))

        c_largeur = sketch.addConstraint(Sketcher.Constraint('DistanceX',0,1,0,2,40.0))
        sketch.renameConstraint(c_largeur, 'Largeur')
        c_hauteur = sketch.addConstraint(Sketcher.Constraint('DistanceY',1,1,1,2,20.0))
        sketch.renameConstraint(c_hauteur, 'Hauteur')

        pad = body.newObject("PartDesign::Pad", "Pad")
        pad.Label = "Pad"
        pad.Profile = sketch
        pad.Length = 100.0
        
        doc.recompute()
        sketch.Visibility = False
        doc.saveAs(template_path)
        App.closeDocument(doc.Name)
        
        print("Library - Template créé: " + template_path)
        return True, "Template créé avec succès", template_path
    except Exception as e:
        print(f"Library - Erreur création template: {e}")
        traceback.print_exc()
        return False, f"Erreur: {e}", None

def ensure_template_exists():
    """Vérifie que le template existe, le crée si nécessaire."""
    template_path = get_template_path()
    if os.path.exists(template_path):
        return True, "Template existant", template_path
    print("Library - Template absent, création en cours...")
    return create_template_file()

def create_new_profile_from_template(dest_path):
    """Crée un nouveau fichier profil basé sur le template."""
    success, msg, template_path = ensure_template_exists()
    if not success:
        return False, f"Template non disponible: {msg}", None
    try:
        if not dest_path.lower().endswith('.fcstd'):
            dest_path += '.FCStd'
        shutil.copy2(template_path, dest_path)
        doc = App.openDocument(dest_path)
        return True, "Nouveau profil créé", doc
    except Exception as e:
        print(f"Library - Erreur création profil: {e}")
        traceback.print_exc()
        return False, f"Erreur: {e}", None
