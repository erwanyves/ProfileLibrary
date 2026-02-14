# Chemin : library/file_operations.py
# -*- coding: utf-8 -*-
# Path: Library/library/file_operations.py
"""Opérations sur les fichiers et dossiers de la bibliothèque"""
import os
import shutil
import re

def cleanup_temp_files(library_path):
    if not library_path or not os.path.exists(library_path):
        return 0, ["Chemin de bibliothèque invalide"]
    deleted_count = 0
    errors = []
    uuid_pattern = re.compile(r'^.+\.FCStd\.[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    for root, dirs, files in os.walk(library_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            should_delete = False
            if filename.endswith('.FCBak'):
                should_delete = True
            elif uuid_pattern.match(filename):
                should_delete = True
            if should_delete:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except PermissionError:
                    errors.append(f"Permission refusée: {filename}")
                except Exception as e:
                    errors.append(f"Erreur {filename}: {str(e)}")
    if deleted_count > 0:
        print(f"Library- ✅ {deleted_count} fichier(s) temporaire(s) supprimé(s)")
    return deleted_count, errors

def create_folder(parent_path, folder_name):
    if not parent_path or not os.path.exists(parent_path):
        return False, "Dossier parent invalide", None
    if not folder_name or not folder_name.strip():
        return False, "Nom de dossier vide", None
    folder_name = folder_name.strip()
    new_path = os.path.join(parent_path, folder_name)
    if os.path.exists(new_path):
        return False, f"'{folder_name}' existe déjà", None
    try:
        os.makedirs(new_path)
        return True, f"Dossier '{folder_name}' créé", new_path
    except PermissionError:
        return False, "Permission refusée", None
    except Exception as e:
        return False, f"Erreur: {str(e)}", None

def rename_item(old_path, new_name):
    if not old_path or not os.path.exists(old_path):
        return False, "Élément introuvable", None
    if not new_name or not new_name.strip():
        return False, "Nouveau nom vide", None
    new_name = new_name.strip()
    parent_dir = os.path.dirname(old_path)
    new_path = os.path.join(parent_dir, new_name)
    if os.path.exists(new_path):
        return False, f"'{new_name}' existe déjà", None
    try:
        os.rename(old_path, new_path)
        return True, f"'{os.path.basename(old_path)}' renommé en '{new_name}'", new_path
    except PermissionError:
        return False, "Permission refusée", None
    except Exception as e:
        return False, f"Erreur: {str(e)}", None

def delete_item(item_path, force=False):
    if not item_path or not os.path.exists(item_path):
        return False, "Élément introuvable"
    item_name = os.path.basename(item_path)
    try:
        if os.path.isfile(item_path):
            os.remove(item_path)
            return True, f"Fichier '{item_name}' supprimé"
        elif os.path.isdir(item_path):
            if force:
                shutil.rmtree(item_path)
                return True, f"Dossier '{item_name}' et son contenu supprimés"
            else:
                if os.listdir(item_path):
                    return False, f"Le dossier '{item_name}' n'est pas vide"
                os.rmdir(item_path)
                return True, f"Dossier '{item_name}' supprimé"
    except PermissionError:
        return False, "Permission refusée"
    except Exception as e:
        return False, f"Erreur: {str(e)}"

def move_item(source_path, dest_folder):
    if not source_path or not os.path.exists(source_path):
        return False, "Source introuvable", None
    if not dest_folder or not os.path.isdir(dest_folder):
        return False, "Destination invalide", None
    item_name = os.path.basename(source_path)
    new_path = os.path.join(dest_folder, item_name)
    if os.path.exists(new_path):
        return False, f"'{item_name}' existe déjà dans la destination", None
    try:
        shutil.move(source_path, new_path)
        return True, f"'{item_name}' déplacé", new_path
    except PermissionError:
        return False, "Permission refusée", None
    except Exception as e:
        return False, f"Erreur: {str(e)}", None

def copy_item(source_path, dest_folder, new_name=None):
    if not source_path or not os.path.exists(source_path):
        return False, "Source introuvable", None
    if not dest_folder or not os.path.isdir(dest_folder):
        return False, "Destination invalide", None
    item_name = new_name or os.path.basename(source_path)
    new_path = os.path.join(dest_folder, item_name)
    if os.path.exists(new_path):
        return False, f"'{item_name}' existe déjà dans la destination", None
    try:
        if os.path.isfile(source_path):
            shutil.copy2(source_path, new_path)
        else:
            shutil.copytree(source_path, new_path)
        return True, f"'{item_name}' copié", new_path
    except PermissionError:
        return False, "Permission refusée", None
    except Exception as e:
        return False, f"Erreur: {str(e)}", None
