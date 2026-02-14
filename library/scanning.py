# Chemin : library/scanning.py
# -*- coding: utf-8 -*-
# Path: Library/library/scanning.py
"""Scan de la bibliothèque de composants"""
import os

def scan_folder(folder_path):
    if not os.path.exists(folder_path):
        return None
    result = {
        'name': os.path.basename(folder_path) or folder_path,
        'path': folder_path,
        'type': 'folder',
        'children': []
    }
    try:
        items = sorted(
            os.listdir(folder_path),
            key=lambda x: (not os.path.isdir(os.path.join(folder_path, x)), x.lower())
        )
        for item in items:
            if item.startswith('.') or item.endswith('.FCBak'):
                continue
            item_path = os.path.join(folder_path, item)
            if os.path.isdir(item_path):
                child = scan_folder(item_path)
                if child:
                    result['children'].append(child)
            elif item.lower().endswith('.fcstd'):
                result['children'].append({
                    'name': item,
                    'path': item_path,
                    'type': 'file',
                    'size': os.path.getsize(item_path)
                })
    except PermissionError:
        result['error'] = "Accès refusé"
    except Exception as e:
        result['error'] = str(e)
    return result

def scan_library(library_path):
    if not library_path or not os.path.exists(library_path):
        return None
    return scan_folder(library_path)

def count_items(tree_data):
    if not tree_data:
        return 0, 0
    folders = 0
    files = 0
    for child in tree_data.get('children', []):
        if child['type'] == 'folder':
            folders += 1
            sub_folders, sub_files = count_items(child)
            folders += sub_folders
            files += sub_files
        else:
            files += 1
    return folders, files
