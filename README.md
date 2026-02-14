Cette macro est un gestionnaire de bibliothèque de profils pour FreeCAD, avec conversion
automatique de bodies « draft » en profils paramétriques réutilisables et insertion facilitée dans
les projets.
Ajoute une entrée « Library » dans le menu Macro de FreeCAD pour ouvrir un gestionnaire
de composants/profils.
Gère un dossier de bibliothèque de fichiers .FCStd (profils) avec arborescence,
création/déplacement/renommage/suppression de dossiers et fichiers, et nettoyage des
fichiers temporaires (.FCBak, noms UUID.
Stocke sa configuration (chemins, langue, dernier dossier, fichiers récents) dans des fichiers
JSON dédiés (config/config.json, library/config/config.json).
Analyse récursivement un dossier de bibliothèque pour construire un arbre «
dossiers/fichiers », en filtrant les fichiers cachés et les sauvegardes, et en comptant le
nombre de dossiers/fichiers.
Opérations de base sur le système de fichiers de la bibliothèque : créer un dossier,
renommer, supprimer (avec gestion des dossiers non vides), déplacer, copier des fichiers ou
dossiers, avec messages dʼerreur explicites.
Fonction de nettoyage qui supprime automatiquement les fichiers temporaires de type
sauvegarde ou nommés par UUID dans toute la bibliothèque.
Analyse ce qui est sélectionné pour déterminer le contexte :
aucun objet,
Body « draft » de profil (CONTEXTDRAFT),
Body standard (CONTEXTBODY),
Part profil déjà converti (CONTEXTPROFILE),
Link vers un profil (CONTEXTLINK).
Fournit des fonctions de détection : isdraftbody, isprofilepart, isprofilelink, détection de
pourrais-tu me faire une synthèse des fonctionnalités de cette macro?
Rôle général
Gestion de la bibliothèque de fichiers
Détection de contexte dans FreeCAD dʼun Sketch.
Analyse un Body de type « draft de profil » : recherche du Sketch, du Pad, des LCS, des
contraintes nommées et signale les problèmes éventuels (pas de Sketch, pas de contraintes
nommées, etc.).
Ouvre un dialogue de conversion qui :
affiche les éléments détectés Sketch, Pad, contraintes nommées, LCS,
demande le nom de la première variante, le nom de fichier,
permet de choisir le dossier de destination dans la bibliothèque.
Enregistre le résultat comme template de profil dans la bibliothèque, en utilisant un modèle
.FCStd dédié (templates/templateprofile.FCStd) et des scripts de création de Part,
Spreadsheet, LCS, etc. (templatecreator, partcreator, spreadsheetcreator, converter).
Définit des règles pour structurer un profil :
Part marqué profile = True avec propriétés Section, Longueur, Angle, Update, etc.,
présence dʼune Spreadsheet dans le Part avec colonnes Section, Longueur, liste de
longueurs, autres contraintes nommées,
LCS LCSBase et LCSTop avec liaisons AttachmentOffset) sur la longueur et lʼangle.
Lit la Spreadsheet pour :
extraire la liste des variantes,
associer à chaque variante des valeurs de contraintes nommées,
gérer soit une longueur libre, soit une longueur standard, soit une liste de longueurs.
Fournit un éditeur de variantes VariantEditorDialog) pour modifier, ajouter ou supprimer des
variantes, leurs paramètres et les listes de longueurs.
Dialogue principal « LibraryDialog » : navigation dans lʼarborescence de la bibliothèque,
affichage dʼinfos fichiers (taille, date, etc.) et actions disponibles selon le contexte (insertion,
conversion, édition de variantes).
Dialogue dʼinsertion dʼun profil :
choix de la variante, de la longueur (valeur libre ou liste prédéfinie), de lʼangle,
insertion du profil dans le document courant, en créant les LCS et en paramétrant la
longueur et lʼangle.
Dialogue de validation pour vérifier quʼun fichier de profil respecte les règles (présence du
Part, Spreadsheet, LCS, propriétés profil, etc.) et outil de migration si les règles évoluent
(module validation avec checker, migrator, rules).
Conversion dʼun Body en profil
Profils paramétriques et variantes
Insertion et mise à jour des profils
Installe, au premier lancement, un module LibraryStartup dans Mod/LibraryStartup qui :
ajoute automatiquement le menu Macro « Library » au démarrage de FreeCAD,
installe un observer unifié pour toutes les configurations de profils 1 à 5, qui surveille
les changements des propriétés Section, Longueur, Angle, etc., et déclenche les mises
à jour nécessaires.
Le code gère la mise à jour de LibraryStartup par comparaison de hash SHA‑256 des
fichiers, et demande un redémarrage de FreeCAD si une installation ou une mise à jour est
effectuée.
Si tu veux, je peux zoomer sur une partie précise (par exemple le workflow de conversion ou la
structure exacte de la Spreadsheet de variantes) et la détailler.
Library-py.txt
Library-tree.txt
Library-json.txt
Library-txt.txt
Library-img.txt
Observateur et intégration au démarrage
