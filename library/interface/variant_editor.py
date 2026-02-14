# Chemin : library/interface/variant_editor.py
# -*- coding: utf-8 -*-
# Library/library/interface/variant_editor.py
"""
Dialogue d'édition des variantes d'un profil.
Configure les propriétés du Part selon le mode choisi (Config 1-5).

CORRECTIONS APPLIQUÉES:
- HIDDEN_COLUMNS_BY_CONFIG[1] cache 'longueur' ET 'longueurliste'
- strip("'") au lieu de lstrip("'") partout (supprime apostrophes fin de libellé)
- Config 5: cellule Longueur même style que les autres (thème cohérent)
- Boutons Ajouter/Dupliquer/Supprimer masqués pour profil unique (Config 1/2)
- Double-clic Longueur_liste ouvre bien l'éditeur (vérification _is_ll corrigée)
"""
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtGui, QtCore
import traceback

#============================================================================
# Constantes
#============================================================================
TEXT_COLUMNS = {'Section', 'Longueur_liste', 'Longueur liste', 'LongueurListe'}
BOOL_COLUMNS = {'Preferred', 'Prefered'}

# Colonnes "système" (liaisons internes) à ne jamais afficher/éditer
SYSTEM_COLUMNS_NORM = {'reflongueur', 'refangle'}

CONFIG_MAP = {
    (True, "user"): 1,
    (True, "list"): 2,
    (False, "user"): 3,
    (False, "list"): 4,
    (False, "variant"): 5,
}
CONFIG_MAP_INV = {v: k for k, v in CONFIG_MAP.items()}

# ══════════════════════════════════════════════════════════════════════════
# CORRECTION: Config 1 cache AUSSI 'longueur' (pas seulement longueurliste)
# Car en Config 1, la longueur est saisie par l'utilisateur, pas stockée
# dans la spreadsheet de variantes.
# ══════════════════════════════════════════════════════════════════════════
HIDDEN_COLUMNS_BY_CONFIG = {
    1: {'longueur', 'longueurliste'},  # ← CORRIGÉ: cacher les deux
    2: {'longueur'},
    3: {'longueurliste'},
    4: {'longueur'},
    5: {'longueurliste'},  # Longueur VISIBLE mais éditable (fixe par variante)
}

MODE_DESCRIPTIONS = {
    1: {'title': "Configuration 1: Profil unique, coupe à longueur",
        'description': (
            "Il s'agit d'un profil particulier, dont la section "
            "n'est pas déclinable en variantes.\n\n"
            "Exemple:\n"
            " • profil aluminium non standard, coupe à longueur\n\n"
            "Interface:\n"
            " • Le paramètre Longueur est éditable "
            "(saisie manuelle)\n"
            " • Le paramètre Angle est éditable\n\n"
            "Dans tous les cas, le paramètre Angle est éditable "
            "par l'utilisateur (indépendant de la spreadsheet).")},
    2: {'title': "Configuration 2: Profil unique, longueur semi standard",
        'description': (
            "Il s'agit d'un profil particulier, dont la section "
            "n'est pas déclinable en variantes.\n\n"
            "Exemple:\n"
            " • profil aluminium non standard, longueur "
            "à choisir dans une plage\n\n"
            "Interface:\n"
            " • Le paramètre Longueur est éditable "
            "(boîte déroulante)\n"
            " • Le paramètre Angle est éditable\n\n"
            "Dans tous les cas, le paramètre Angle est éditable "
            "par l'utilisateur (indépendant de la spreadsheet).")},
    3: {'title': "Configuration 3: Famille de profils, coupe à longueur",
        'description': (
            "Il s'agit d'un composant à section variable "
            "paramétrique, la longueur est définie par "
            "l'utilisateur (saisie manuelle).\n\n"
            "Exemple:\n"
            " • Famille de cornières standard, de tubes\n\n"
            "Interface:\n"
            " • Le paramètre Variante est éditable "
            "(liste de choix)\n"
            " • Le paramètre Longueur est éditable "
            "(saisie manuelle)\n"
            " • Le paramètre Angle est éditable\n\n"
            "Dans tous les cas, le paramètre Angle est éditable "
            "par l'utilisateur (indépendant de la spreadsheet).")},
    4: {'title': "Configuration 4: Famille de profils, longueur semi standard",
        'description': (
            "Il s'agit d'un composant à section variable "
            "paramétrique, dont la longueur est à choisir dans "
            "une plage (propre à chaque variante).\n\n"
            "Exemple:\n"
            " • Tube de plomberie (longueurs normalisées)\n\n"
            "Interface:\n"
            " • Le paramètre Variante est éditable "
            "(liste de choix)\n"
            " • Le paramètre Longueur est éditable "
            "(boîte déroulante)\n"
            " • Le paramètre Angle est éditable\n\n"
            "Dans tous les cas, le paramètre Angle est éditable "
            "par l'utilisateur (indépendant de la spreadsheet).")},
    5: {'title': "Configuration 5: Famille de profils, longueur fixe par variante",
        'description': (
            "Il s'agit d'un composant à section variable "
            "paramétrique, dont la longueur est propre "
            "à chaque variante.\n\n"
            "Exemple:\n"
            " • Famille de profils à variantes fixes\n\n"
            "Interface:\n"
            " • Le paramètre Variante est éditable "
            "(liste de choix)\n"
            " • Le paramètre Longueur est en lecture seule "
            "(valeur fixe par variante)\n"
            " • Le paramètre Angle est éditable\n\n"
            "Dans tous les cas, le paramètre Angle est éditable "
            "par l'utilisateur (indépendant de la spreadsheet).")},
}

#============================================================================
# Observer unifié pour toutes les configs
#============================================================================
class _ProfileObserver:
    """Observer unique gérant toutes les configs profil.

    Utilise QTimer.singleShot(0) pour différer le traitement après la
    transaction FreeCAD courante. Ceci garantit que :
    - Config 4 : Section → update enum → update Longueur (chaîne complète)
    - Config 5 : Section → recompute → expression Longueur réévaluée
    """
    _PROFILE_PROPS = {"Section", "Longueur", "Longueur_standard", "Angle"}

    def __init__(self):
        self._pending = set()  # (doc_name, obj_name, prop) en attente

    def slotChangedObject(self, obj, prop):
        if prop not in self._PROFILE_PROPS:
            return
        try:
            # Identifier la config : soit directement (Part), soit via LinkedObject (Link)
            config = getattr(obj, 'Config', 0)
            is_profile = hasattr(obj, 'profile') and obj.profile
            if not is_profile and config == 0:
                linked = getattr(obj, 'LinkedObject', None)
                if linked:
                    config = getattr(linked, 'Config', 0)
                    is_profile = hasattr(linked, 'profile') and linked.profile
            if not is_profile or config == 0:
                return

            # Éviter les doublons dans la file d'attente
            key = (obj.Document.Name, obj.Name, prop)
            if key in self._pending:
                return
            self._pending.add(key)

            # Différer le traitement APRÈS la transaction FreeCAD courante
            from PySide import QtCore
            QtCore.QTimer.singleShot(0, lambda: self._process(
                obj.Document.Name, obj.Name, prop, config
            ))
        except Exception:
            pass

    def _process(self, doc_name, obj_name, prop, config):
        """Traitement différé — exécuté hors de slotChangedObject."""
        try:
            doc = App.getDocument(doc_name)
            if not doc:
                return
            obj = doc.getObject(obj_name)
            if not obj:
                return

            # Config 2/4 : Longueur_standard → copier vers Longueur
            if prop == "Longueur_standard" and config in (2, 4):
                if hasattr(obj, 'Longueur'):
                    val_str = obj.Longueur_standard
                    if val_str:
                        try:
                            obj.Longueur = float(
                                _strip_unit(val_str).replace(",", ".")
                            )
                        except ValueError:
                            pass

            # Config 4 : Section → mettre à jour l'enum Longueur_standard
            elif prop == "Section" and config == 4:
                if hasattr(obj, 'Longueur_standard'):
                    # Trouver la spreadsheet (Part direct ou LinkedObject)
                    source = obj
                    if hasattr(obj, 'LinkedObject') and obj.LinkedObject:
                        source = obj.LinkedObject
                    ss = None
                    if hasattr(source, 'Group'):
                        for child in source.Group:
                            if child.TypeId == "Spreadsheet::Sheet":
                                ss = child
                                break
                    update_longueur_liste_enum(obj, ss)

            # Recompute systématique
            doc.recompute()

        except Exception as e:
            print(f"Library- Observer: {e}")
        finally:
            key = (doc_name, obj_name, prop)
            self._pending.discard(key)

_observer_instance = None

def ensure_observer():
    """Installe l'observer unifié (toutes configs) si nécessaire."""
    global _observer_instance
    if _observer_instance is None:
        _observer_instance = _ProfileObserver()
        App.addDocumentObserver(_observer_instance)
        print("Library- Observer profil unifié installé")

#============================================================================
# Configuration Part
#============================================================================
def configure_part_for_config(part, config_num, spreadsheet=None):
    if not hasattr(part, 'Longueur'):
        print("Library- Attention: Part sans propriété Longueur")
        return

    # Configurations 1 et 2 : profil unique → Section en lecture seule
    if config_num in (1, 2):
        if hasattr(part, 'Section'):
            # Garder uniquement la première variante
            if isinstance(part.Section, (list, tuple)) and len(part.Section) > 0:
                first_variant = part.Section[0]
                part.Section = [first_variant]
                part.setEditorMode("Section", 1)  # Lecture seule

    # Configurations 1 et 3 : Longueur éditable par l'utilisateur
    if config_num in (1, 3):
        part.setEditorMode("Longueur", 0)
        if hasattr(part, 'Longueur_standard'):
            part.setEditorMode("Longueur_standard", 2)

    # Configuration 5 : Longueur en lecture seule (valeur fixe par variante)
    elif config_num == 5:
        part.setEditorMode("Longueur", 1)  # Lecture seule
        if spreadsheet:
            part.setExpression("Longueur", f"<<{spreadsheet.Label}>>.Longueur")
        if hasattr(part, 'Longueur_standard'):
            part.setEditorMode("Longueur_standard", 2)

    # Configurations 2 et 4 : Longueur via liste standard
    elif config_num in (2, 4):
        part.setEditorMode("Longueur", 2)
        values = _read_longueur_liste(part, spreadsheet)
        if not values:
            values = ["100", "200", "300", "500", "1000"]
        if not hasattr(part, 'Longueur_standard'):
            part.addProperty(
                "App::PropertyEnumeration", "Longueur_standard",
                "Profil longueur", "Longueur choisie dans la liste standard"
            )
        part.Longueur_standard = values

        cur = float(part.Longueur)
        best = values[0]
        best_diff = abs(float(_strip_unit(best).replace(",", ".")) - cur)
        for v in values[1:]:
            try:
                diff = abs(float(_strip_unit(v).replace(",", ".")) - cur)
                if diff < best_diff:
                    best = v
                    best_diff = diff
            except ValueError:
                pass

        part.Longueur_standard = best
        try:
            part.Longueur = float(_strip_unit(best).replace(",", "."))
        except ValueError:
            pass

        part.setEditorMode("Longueur_standard", 0)
        part.setPropertyStatus("Longueur_standard", "CopyOnChange")

    # --- Masquage systématique des propriétés internes ---
    for prop in ('profile', 'profile_source', 'Config', 'Update'):
        if hasattr(part, prop):
            part.setEditorMode(prop, 2)  # Masqué

    # Observer unifié pour TOUTES les configs
    ensure_observer()

def _strip_unit(s):
    """Extrait la partie numérique d'une chaîne avec unité.
    '100 mm' -> '100', '2,5 m' -> '2,5', '100.5mm' -> '100.5'
    """
    import re
    m = re.match(r'^([0-9]+[.,]?[0-9]*)', s.strip())
    return m.group(1) if m else s.strip()

def _read_longueur_liste(part, spreadsheet=None):
    if spreadsheet is None:
        for obj in part.Group:
            if obj.TypeId == "Spreadsheet::Sheet":
                spreadsheet = obj
                break
    if not spreadsheet:
        return []

    col_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    liste_col = None
    for col in col_letters[:20]:
        try:
            header = spreadsheet.getContents(f"{col}1")
            if header:
                # ── CORRECTION: strip("'") des DEUX côtés ──
                norm = header.strip().strip("'").lower().replace('_', '').replace(' ', '')
                if norm == 'longueurliste':
                    liste_col = col
                    break
        except Exception:
            break

    if not liste_col:
        return []

    row = 3
    if hasattr(part, 'Section'):
        cur_section = part.Section
        if isinstance(cur_section, (list, tuple)):
            cur_section = cur_section[0] if len(cur_section) > 0 else None
        for r in range(3, 100):
            try:
                cell = spreadsheet.getContents(f"A{r}")
                # ── CORRECTION: strip("'") des DEUX côtés ──
                if cell and cell.strip().strip("'") == cur_section:
                    row = r
                    break
                if not cell or not cell.strip():
                    break
            except Exception:
                break

    try:
        content = spreadsheet.getContents(f"{liste_col}{row}")
        if content:
            # ── CORRECTION: strip("'") des DEUX côtés ──
            content = content.strip().strip("'")
            return [_strip_unit(v) for v in content.split(";") if v.strip()]
    except Exception:
        pass
    return []

def update_longueur_liste_enum(part, spreadsheet=None):
    """Met à jour l'enum Longueur_standard après changement de Section."""
    # Déterminer config : directement ou via LinkedObject
    config = getattr(part, 'Config', 0)
    if config == 0:
        linked = getattr(part, 'LinkedObject', None)
        if linked:
            config = getattr(linked, 'Config', 0)
    if config not in (2, 4):
        return
    if not hasattr(part, 'Longueur_standard'):
        return

    values = _read_longueur_liste(part, spreadsheet)
    if values:
        current = part.Longueur_standard
        part.Longueur_standard = values
        if current in values:
            part.Longueur_standard = current
        else:
            part.Longueur_standard = values[0]
        try:
            part.Longueur = float(_strip_unit(values[0]).replace(",", "."))
        except ValueError:
            pass

#============================================================================
# Dialogues
#============================================================================
class LengthListEditorDialog(QtGui.QDialog):
    def __init__(self, values_str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Édition de la liste de longueurs")
        self.setMinimumSize(320, 420)
        self._result_str = values_str
        self._setup(values_str)

    def _setup(self, values_str):
        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(QtGui.QLabel("Définissez les longueurs standard (en mm)."))

        center = QtGui.QHBoxLayout()
        self.list_widget = QtGui.QListWidget()
        self.list_widget.setDragDropMode(QtGui.QAbstractItemView.InternalMove)

        if values_str:
            for v in values_str.split(";"):
                v = v.strip()
                if v:
                    self._add_item(v)

        center.addWidget(self.list_widget, 1)

        side = QtGui.QVBoxLayout()
        side.setSpacing(4)
        for label, tip, slot in [
            ("+", "Ajouter", self._on_add),
            ("-", "Supprimer", self._on_remove),
            (None, None, None),
            ("\u25B2", "Monter", self._on_up),
            ("\u25BC", "Descendre", self._on_down),
            (None, None, None),
            ("Tri", "Tri croissant", self._on_sort),
        ]:
            if label is None:
                side.addSpacing(10)
                continue
            btn = QtGui.QPushButton(label)
            btn.setToolTip(tip)
            btn.setMaximumWidth(36)
            btn.clicked.connect(slot)
            side.addWidget(btn)
        side.addStretch()
        center.addLayout(side)
        layout.addLayout(center)

        self.label_preview = QtGui.QLabel()
        self.label_preview.setStyleSheet("color:#666;font-style:italic;")
        self._update_preview()
        layout.addWidget(self.label_preview)

        bl = QtGui.QHBoxLayout()
        bl.addStretch()
        bc = QtGui.QPushButton("Annuler")
        bc.clicked.connect(self.reject)
        bl.addWidget(bc)
        bo = QtGui.QPushButton("OK")
        bo.setDefault(True)
        bo.clicked.connect(self._on_ok)
        bl.addWidget(bo)
        layout.addLayout(bl)

    def _add_item(self, v):
        item = QtGui.QListWidgetItem(v)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsDragEnabled)
        self.list_widget.addItem(item)
        return item

    def _collect(self):
        return [self.list_widget.item(i).text().strip() for i in range(self.list_widget.count())
                if self.list_widget.item(i).text().strip()]

    def _update_preview(self):
        v = self._collect()
        self.label_preview.setText(f"Aperçu: {';'.join(v)}" if v else "Aperçu: (vide)")

    def _on_add(self):
        val, ok = QtGui.QInputDialog.getText(self, "Ajouter", "Longueur (mm):")
        if ok and val.strip():
            try:
                float(val.strip().replace(",", "."))
            except ValueError:
                QtGui.QMessageBox.warning(self, "Invalide", f"'{val}' n'est pas numérique.")
                return
            self._add_item(val.strip())
            self._update_preview()

    def _on_remove(self):
        r = self.list_widget.currentRow()
        if r >= 0:
            self.list_widget.takeItem(r)
            self._update_preview()

    def _on_up(self):
        r = self.list_widget.currentRow()
        if r > 0:
            it = self.list_widget.takeItem(r)
            self.list_widget.insertItem(r - 1, it)
            self.list_widget.setCurrentRow(r - 1)
            self._update_preview()

    def _on_down(self):
        r = self.list_widget.currentRow()
        if 0 <= r < self.list_widget.count() - 1:
            it = self.list_widget.takeItem(r)
            self.list_widget.insertItem(r + 1, it)
            self.list_widget.setCurrentRow(r + 1)
            self._update_preview()

    def _on_sort(self):
        vals = self._collect()
        try:
            vals.sort(key=lambda x: float(x.replace(",", ".")))
        except ValueError:
            vals.sort()
        self.list_widget.clear()
        for v in vals:
            self._add_item(v)
        self._update_preview()

    def _on_ok(self):
        self._result_str = ";".join(self._collect())
        self.accept()

    def result_string(self):
        return self._result_str

class ProfileConfigDialog(QtGui.QDialog):
    def __init__(self, part, spreadsheet, parent=None):
        super().__init__(parent)
        self.part = part
        self.spreadsheet = spreadsheet
        self.setWindowTitle("Configuration du profil")
        self.setMinimumSize(600, 520)
        self._build_ui()
        self._update_description()

    def _build_ui(self):
        layout = QtGui.QVBoxLayout(self)
        layout.setSpacing(10)

        h = QtGui.QLabel(
            "<h3>Configuration initiale du profil</h3>"
            "<p>Choisissez le mode de fonctionnement. Ce choix détermine "
            "les colonnes de la spreadsheet et le comportement du "
            "paramètre Longueur dans les propriétés du Part.</p>"
        )
        h.setWordWrap(True)
        layout.addWidget(h)

        cg = QtGui.QGroupBox("Type de profil et mode de longueur")
        cl = QtGui.QVBoxLayout(cg)
        self.check_single = QtGui.QCheckBox("Profil unique (une seule variante)")
        self.check_single.stateChanged.connect(self._on_changed)
        cl.addWidget(self.check_single)

        line = QtGui.QFrame()
        line.setFrameShape(QtGui.QFrame.HLine)
        line.setFrameShadow(QtGui.QFrame.Sunken)
        cl.addWidget(line)

        cl.addWidget(QtGui.QLabel("Mode de longueur:"))
        self.r_user = QtGui.QRadioButton("Saisie manuelle par l'utilisateur")
        self.r_user.setChecked(True)
        self.r_user.toggled.connect(self._on_changed)
        cl.addWidget(self.r_user)

        self.r_list = QtGui.QRadioButton("Choisie dans une liste de valeurs")
        self.r_list.toggled.connect(self._on_changed)
        cl.addWidget(self.r_list)

        self.r_variant = QtGui.QRadioButton("Fixe, liée à la variante")
        self.r_variant.toggled.connect(self._on_changed)
        cl.addWidget(self.r_variant)

        layout.addWidget(cg)

        dg = QtGui.QGroupBox("Description du mode sélectionné")
        dl = QtGui.QVBoxLayout(dg)
        self.txt_desc = QtGui.QTextEdit()
        self.txt_desc.setReadOnly(True)
        self.txt_desc.setMinimumHeight(160)
        self.txt_desc.setStyleSheet(
            "QTextEdit{background:#f5f9ff;color:#333333;"
            "border:1px solid #b0c4de;border-radius:4px;padding:8px;font-size:12px;}"
        )
        dl.addWidget(self.txt_desc)
        layout.addWidget(dg)

        layout.addStretch()

        bl = QtGui.QHBoxLayout()
        bl.addStretch()
        bc = QtGui.QPushButton("Annuler")
        bc.clicked.connect(self.reject)
        bl.addWidget(bc)

        bv = QtGui.QPushButton("Valider et continuer")
        bv.setStyleSheet(
            "QPushButton{background:#4CAF50;color:white;font-weight:bold;"
            "padding:8px 20px;border-radius:4px;}"
            "QPushButton:hover{background:#45a049;}"
        )
        bv.clicked.connect(self._on_validate)
        bl.addWidget(bv)
        layout.addLayout(bl)

    def _config_num(self):
        s = self.check_single.isChecked()
        if self.r_list.isChecked():
            m = "list"
        elif self.r_variant.isChecked():
            m = "variant"
        else:
            m = "user"
        return CONFIG_MAP.get((s, m), 1)

    def _on_changed(self):
        s = self.check_single.isChecked()
        self.r_variant.setEnabled(not s)
        if s and self.r_variant.isChecked():
            self.r_user.setChecked(True)
        self._update_description()

    def _update_description(self):
        n = self._config_num()
        info = MODE_DESCRIPTIONS.get(n, {})
        t = info.get('title', '')
        d = info.get('description', '')
        self.txt_desc.setText(f"{t}\n{'=' * len(t)}\n\n{d}")

    def _on_validate(self):
        try:
            cn = self._config_num()
            if not hasattr(self.part, 'Config'):
                self.part.addProperty(
                    "App::PropertyInteger", "Config", "profile",
                    "Mode de configuration (1-5)"
                )
            self.part.Config = cn
            self.part.setEditorMode("Config", 1)

            # Configurations 1 et 2 : profil unique → Section en lecture seule
            if cn in (1, 2):
                if hasattr(self.part, 'Section'):
                    if isinstance(self.part.Section, (list, tuple)) and len(self.part.Section) > 0:
                        first_variant = self.part.Section[0]
                        self.part.Section = [first_variant]
                        self.part.setEditorMode("Section", 1)

            _, lm = CONFIG_MAP_INV[cn]
            self._configure_spreadsheet(lm)
            configure_part_for_config(self.part, cn, self.spreadsheet)

            self.part.Document.recompute()
            print(f"Library- Config={cn} ({MODE_DESCRIPTIONS[cn]['title']})")
            self.accept()
        except Exception as e:
            print(f"Library- Erreur config: {e}")
            traceback.print_exc()
            QtGui.QMessageBox.critical(self, "Erreur", str(e))

    def _configure_spreadsheet(self, length_mode):
        ss = self.spreadsheet
        C = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        headers = {}
        last = -1
        for i, c in enumerate(C[:20]):
            try:
                v = ss.getContents(f"{c}1")
                if v and v.strip():
                    # ── CORRECTION: strip("'") des DEUX côtés ──
                    headers[c] = v.strip().strip("'")
                    last = i
                else:
                    break
            except Exception:
                break

        has_L = 'Longueur' in headers.values()
        has_LL = any(
            h.lower().replace('_', '').replace(' ', '') == 'longueurliste'
            for h in headers.values()
        )

        pref = None
        for c, h in headers.items():
            if h in ('Preferred', 'Prefered'):
                pref = c
                break

        def ins():
            return pref if pref else C[last + 1]

        if not has_L and length_mode in ("user", "variant"):
            at = ins()
            if pref and at == pref:
                self._shift_right(ss, pref)
            ss.set(f"{at}1", "'Longueur")
            ss.set(f"{at}2", f"=.{at}3")
            try:
                ss.setAlias(f"{at}2", "Longueur")
            except:
                pass
            ss.set(f"{at}3", "=100 mm")

        if not has_LL and length_mode == "list":
            pn = None
            for c, h in self._read_h(ss).items():
                if h in ('Preferred', 'Prefered'):
                    pn = c
                    break
            if pn:
                at = pn
                self._shift_right(ss, pn)
            else:
                at = C[last + 1]
            ss.set(f"{at}1", "'Longueur_liste")
            ss.set(f"{at}2", "'100;200;300;500;1000")
            try:
                ss.setAlias(f"{at}2", "Longueur_liste")
            except:
                pass
            ss.set(f"{at}3", "'100;200;300;500;1000")

    def _read_h(self, ss):
        C = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        h = {}
        for c in C[:20]:
            try:
                v = ss.getContents(f"{c}1")
                if v and v.strip():
                    # ── CORRECTION: strip("'") des DEUX côtés ──
                    h[c] = v.strip().strip("'")
                else:
                    break
            except Exception:
                break
        return h

    def _shift_right(self, ss, col):
        C = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        si = C.index(col)
        for row in range(1, 50):
            try:
                v = ss.getContents(f"{col}{row}")
                if v and v.strip():
                    ss.set(f"{C[si + 1]}{row}", v)
                    ss.clear(f"{col}{row}")
                elif row > 3:
                    break
            except Exception:
                break

class VariantEditorDialog(QtGui.QDialog):
    def __init__(self, part, parent=None):
        super().__init__(parent)
        self.part = part
        self.doc = part.Document
        self.spreadsheet = None
        self.all_columns = []
        self.columns = []
        self.data_start_row = 3
        self.modified = False
        self.config_num = getattr(part, 'Config', 0)
        self.is_single_profile = self.config_num in (1, 2)  # Profil unique = Config 1 ou 2

        for obj in part.Group:
            if obj.TypeId == "Spreadsheet::Sheet":
                self.spreadsheet = obj
                break
        if not self.spreadsheet:
            raise ValueError("Aucune Spreadsheet trouvée")

        self.setWindowTitle(f"Édition des variantes - {part.Label}")
        self.setMinimumSize(850, 600)
        self._build_ui()
        self.load_data()

    def _build_ui(self):
        layout = QtGui.QVBoxLayout(self)
        layout.addWidget(QtGui.QLabel(f"<h3>Variantes de {self.part.Label}</h3>"))

        if self.config_num in MODE_DESCRIPTIONS:
            lbl = QtGui.QLabel(f"<b>{MODE_DESCRIPTIONS[self.config_num]['title']}</b>")
            lbl.setStyleSheet(
                "QLabel{background:#e8f4e8;border:1px solid #a0c8a0;"
                "border-radius:4px;padding:6px 10px;color:#2e7d32;}"
            )
            layout.addWidget(lbl)

        il = QtGui.QLabel(f"Spreadsheet: {self.spreadsheet.Label}")
        il.setStyleSheet("color:#666;")
        layout.addWidget(il)

        self.table = QtGui.QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.table.cellDoubleClicked.connect(self._on_dbl_click)
        layout.addWidget(self.table)

        #=== BOUTONS D'ÉDITION DES VARIANTES (masqués pour profil unique) ===
        if not self.is_single_profile:
            bl = QtGui.QHBoxLayout()
            for txt, slot in [
                ("Ajouter variante", self.add_variant),
                ("Dupliquer", self.duplicate_variant),
                ("Supprimer", self.delete_variant),
            ]:
                b = QtGui.QPushButton(txt)
                b.clicked.connect(slot)
                bl.addWidget(b)

            bu = QtGui.QPushButton("Monter")
            bu.setMaximumWidth(60)
            bu.clicked.connect(self.move_up)
            bl.addWidget(bu)

            bd = QtGui.QPushButton("Descendre")
            bd.setMaximumWidth(70)
            bd.clicked.connect(self.move_down)
            bl.addWidget(bd)

            bl.addStretch()
            layout.addLayout(bl)

        dl = QtGui.QHBoxLayout()
        dl.addStretch()
        bc = QtGui.QPushButton("Annuler")
        bc.clicked.connect(self.reject)
        dl.addWidget(bc)

        ba = QtGui.QPushButton("Appliquer")
        ba.clicked.connect(self.apply_changes)
        dl.addWidget(ba)

        bo = QtGui.QPushButton("OK")
        bo.setDefault(True)
        bo.clicked.connect(self.accept_and_save)
        dl.addWidget(bo)

        layout.addLayout(dl)

    @staticmethod
    def _classify(name):
        n = name.lower().replace('_', '').replace(' ', '')
        if n == 'section':
            return 'text'
        if n == 'longueurliste':
            return 'text'
        if name in BOOL_COLUMNS or n in ('preferred', 'prefered'):
            return 'bool'
        if n == 'longueur':
            return 'length'
        return 'numeric'

    @staticmethod
    def _norm(name):
        return name.lower().replace('_', '').replace(' ', '')

    def _hidden(self, name):
        return self._norm(name) in HIDDEN_COLUMNS_BY_CONFIG.get(self.config_num, set())

    def _is_ll(self, ci):
        return (0 <= ci < len(self.columns) and self._norm(self.columns[ci]['name']) == 'longueurliste')

    def _make_item(self, ci, text):
        item = QtGui.QTableWidgetItem(text)
        if self._is_ll(ci):
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
            item.setToolTip("Double-cliquez pour éditer la liste")
        return item

    def load_data(self):
        self.table.blockSignals(True)
        self.table.clear()
        self.all_columns = []
        self.columns = []
        try:
            C = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            for ci, c in enumerate(C[:20]):
                try:
                    h = self.spreadsheet.getContents(f"{c}1")
                    if h and h.strip():
                        # ══════════════════════════════════════════════
                        # CORRECTION: strip("'") des DEUX côtés
                        # au lieu de lstrip("'") seulement
                        # ══════════════════════════════════════════════
                        h = h.strip().strip("'")
                        if self._norm(h) in SYSTEM_COLUMNS_NORM:
                            continue
                        self.all_columns.append({
                            'name': h,
                            'col_letter': c,
                            'col_index': ci,
                            'col_type': self._classify(h)
                        })
                    else:
                        break
                except Exception:
                    break

            self.columns = [c for c in self.all_columns if not self._hidden(c['name'])]
            if not self.columns:
                return

            self.table.setColumnCount(len(self.columns))
            self.table.setHorizontalHeaderLabels([c['name'] for c in self.columns])

            ri = 0
            for row in range(self.data_start_row, 100):
                fc = self.spreadsheet.getContents(f"A{row}")
                if not fc or not fc.strip():
                    break

                #=== PROFIL UNIQUE : ne charger QUE la première variante ===
                if self.is_single_profile and ri >= 1:
                    break

                self.table.setRowCount(ri + 1)
                for ci, col in enumerate(self.columns):
                    cl = col['col_letter']
                    ct = col['col_type']
                    try:
                        v = self.spreadsheet.getContents(f"{cl}{row}")
                        if v:
                            if ct in ('text', 'bool'):
                                # ── CORRECTION: strip("'") des DEUX côtés ──
                                v = v.strip().strip("'")
                            else:
                                v = (v.lstrip("'=").replace(" mm", "").replace("mm", ""))
                        else:
                            v = ""
                    except Exception:
                        v = ""
                    self.table.setItem(ri, ci, self._make_item(ci, v))
                ri += 1
            self.table.resizeColumnsToContents()

        except Exception as e:
            print(f"Library- Erreur chargement: {e}")
            traceback.print_exc()
        finally:
            self.table.blockSignals(False)

    def _on_dbl_click(self, row, col):
        if not self._is_ll(col):
            return
        item = self.table.item(row, col)
        cur = item.text() if item else ""
        dlg = LengthListEditorDialog(cur, self)
        if dlg.exec_() == QtGui.QDialog.Accepted:
            self.table.blockSignals(True)
            if item:
                item.setText(dlg.result_string())
            else:
                self.table.setItem(row, col, self._make_item(col, dlg.result_string()))
            self.table.blockSignals(False)
            self.modified = True

    def _on_cell_changed(self, r, c):
        self.modified = True

    #=== MÉTHODES D'ÉDITION DÉSACTIVÉES POUR PROFIL UNIQUE ===
    def add_variant(self):
        if self.is_single_profile:
            return
        rc = self.table.rowCount()
        self.table.setRowCount(rc + 1)
        self.table.setItem(rc, 0, QtGui.QTableWidgetItem(f"Variante_{rc + 1}"))
        if rc > 0:
            for c in range(1, self.table.columnCount()):
                p = self.table.item(rc - 1, c)
                if p:
                    self.table.setItem(rc, c, self._make_item(c, p.text()))
        else:
            for c in range(1, self.table.columnCount()):
                d = "0"
                if c < len(self.columns):
                    ct = self.columns[c]['col_type']
                    if self._is_ll(c):
                        d = "100;200;300;500;1000"
                    else:
                        d = {"text": "", "bool": "0", "length": "100"}.get(ct, "0")
                self.table.setItem(rc, c, self._make_item(c, d))
        self.modified = True

    def duplicate_variant(self):
        if self.is_single_profile:
            return
        cr = self.table.currentRow()
        if cr < 0:
            return
        rc = self.table.rowCount()
        self.table.setRowCount(rc + 1)
        for c in range(self.table.columnCount()):
            it = self.table.item(cr, c)
            if it:
                t = it.text()
                if c == 0:
                    t = f"{t}_copie"
                self.table.setItem(rc, c, self._make_item(c, t))
        self.modified = True

    def delete_variant(self):
        if self.is_single_profile:
            return
        cr = self.table.currentRow()
        if cr < 0:
            return
        if self.table.rowCount() <= 1:
            QtGui.QMessageBox.warning(self, "Impossible", "Au moins une variante requise.")
            return
        it = self.table.item(cr, 0)
        name = it.text() if it else f"Ligne {cr + 1}"
        if QtGui.QMessageBox.question(self, "Confirmer", f"Supprimer '{name}'?",
                                      QtGui.QMessageBox.Yes | QtGui.QMessageBox.No) == QtGui.QMessageBox.Yes:
            self.table.removeRow(cr)
            self.modified = True

    def move_up(self):
        if self.is_single_profile:
            return
        cr = self.table.currentRow()
        if cr <= 0:
            return
        self._swap(cr, cr - 1)
        self.table.setCurrentCell(cr - 1, 0)
        self.modified = True

    def move_down(self):
        if self.is_single_profile:
            return
        cr = self.table.currentRow()
        if cr < 0 or cr >= self.table.rowCount() - 1:
            return
        self._swap(cr, cr + 1)
        self.table.setCurrentCell(cr + 1, 0)
        self.modified = True

    def _swap(self, r1, r2):
        self.table.blockSignals(True)
        for c in range(self.table.columnCount()):
            i1 = self.table.takeItem(r1, c)
            i2 = self.table.takeItem(r2, c)
            if i1:
                self.table.setItem(r2, c, i1)
            if i2:
                self.table.setItem(r1, c, i2)
        self.table.blockSignals(False)

    def apply_changes(self):
        if not self.modified:
            return True
        try:
            hidden_cols = [c for c in self.all_columns if self._hidden(c['name'])]
            num_rows = self.table.rowCount()

            #=== PROFIL UNIQUE : ne garder QUE la première ligne ===
            if self.is_single_profile:
                num_rows = 1

            for row in range(self.data_start_row, self.data_start_row + 100):
                for col in self.columns:
                    try:
                        self.spreadsheet.clear(f"{col['col_letter']}{row}")
                    except:
                        pass

            for col in hidden_cols:
                cl = col['col_letter']
                ct = col['col_type']
                for ri in range(num_rows):
                    sr = self.data_start_row + ri
                    try:
                        v = self.spreadsheet.getContents(f"{cl}{sr}")
                        if v and v.strip():
                            continue
                    except:
                        pass
                    if ct in ('length', 'numeric'):
                        self.spreadsheet.set(f"{cl}{sr}", "=0 mm")
                    elif ct == 'text':
                        self.spreadsheet.set(f"{cl}{sr}", "''")

            for col in hidden_cols:
                cl = col['col_letter']
                for row in range(self.data_start_row + num_rows, self.data_start_row + 100):
                    try:
                        v = self.spreadsheet.getContents(f"{cl}{row}")
                        if v and v.strip():
                            self.spreadsheet.clear(f"{cl}{row}")
                        else:
                            break
                    except:
                        break

            for ri in range(num_rows):
                sr = self.data_start_row + ri
                for ci, col in enumerate(self.columns):
                    cl = col['col_letter']
                    ct = col['col_type']
                    it = self.table.item(ri, ci)
                    if not it:
                        continue
                    v = it.text().strip()
                    cell = f"{cl}{sr}"
                    if ct == 'text' or ci == 0:
                        self.spreadsheet.set(cell, f"'{v}")
                    elif ct == 'bool':
                        self.spreadsheet.set(cell, "1" if v in ("1", "true", "True", "oui", "Oui") else "0")
                    elif ct in ('length', 'numeric'):
                        if not v:
                            self.spreadsheet.set(cell, "=0 mm")
                        else:
                            try:
                                fv = float(v.replace(",", "."))
                                self.spreadsheet.set(cell, f"={fv} mm")
                            except ValueError:
                                self.spreadsheet.set(cell, f"'{v}")
                    else:
                        self.spreadsheet.set(cell, f"'{v}")

            #=== PROFIL UNIQUE : Section = première variante uniquement ===
            names = []
            for ri in range(num_rows):
                it = self.table.item(ri, 0)
                if it and it.text().strip():
                    names.append(it.text().strip())

            if names and hasattr(self.part, 'Section'):
                if self.is_single_profile:
                    # Config 1/2 : Section en lecture seule avec une seule valeur
                    self.part.Section = [names[0]]
                    self.part.setEditorMode("Section", 1)
                else:
                    # Config 3/4/5 : Section éditable avec plusieurs variantes
                    cur = self.part.Section
                    self.part.Section = names
                    if isinstance(cur, str) and cur in names:
                        self.part.Section = cur
                    elif isinstance(cur, (list, tuple)) and len(cur) > 0 and cur[0] in names:
                        self.part.Section = cur[0]

            if self.config_num in (2, 4):
                update_longueur_liste_enum(self.part, self.spreadsheet)

            self.doc.recompute()
            self.modified = False
            return True

        except Exception as e:
            traceback.print_exc()
            QtGui.QMessageBox.critical(self, "Erreur", str(e))
            return False

    def accept_and_save(self):
        if self.apply_changes():
            self.accept()

    def reject(self):
        if self.modified:
            if QtGui.QMessageBox.question(self, "Modifications", "Quitter sans sauvegarder?",
                                          QtGui.QMessageBox.Yes | QtGui.QMessageBox.No) == QtGui.QMessageBox.No:
                return
        super().reject()

def show_variant_editor(part, parent=None):
    try:
        ss = None
        for obj in part.Group:
            if obj.TypeId == "Spreadsheet::Sheet":
                ss = obj
                break
        if not ss:
            QtGui.QMessageBox.critical(parent, "Erreur", "Aucune Spreadsheet.")
            return False

        if not hasattr(part, 'Config'):
            dlg = ProfileConfigDialog(part, ss, parent)
            if dlg.exec_() != QtGui.QDialog.Accepted:
                return False

        cn = getattr(part, 'Config', 0)
        if cn in (2, 4):
            ensure_observer()

        ed = VariantEditorDialog(part, parent)
        if ed.exec_() == QtGui.QDialog.Accepted:
            # Post-édition : s'assurer que Section est en lecture seule pour profil unique
            if cn in (1, 2):
                if hasattr(part, 'Section'):
                    if isinstance(part.Section, (list, tuple)) and len(part.Section) > 0:
                        first_variant = part.Section[0]
                        part.Section = [first_variant]
                        part.setEditorMode("Section", 1)
            return True
        return False

    except Exception as e:
        QtGui.QMessageBox.critical(parent, "Erreur", str(e))
        traceback.print_exc()
        return False
