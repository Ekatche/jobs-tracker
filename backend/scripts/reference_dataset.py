"""Jeu de référence synthétique commun (profil, parseur CV, lettres).

Chargement, validation structurelle et rapport de couverture. Les seuils de
volume sont vérifiés par un test sur le contenu réel, pas ici. Schéma :
``scripts/reference/README.md``.
"""

import json
from collections import Counter
from pathlib import Path

REFERENCE_DIR = Path(__file__).resolve().parent / "reference"
LABELS = ("pertinent", "partiel", "hors_sujet")
NIVEAUX = ("junior", "confirme", "senior")
LANGUES = ("fr", "en")
SOURCES = ("manual", "cv", "website", "github")
_FILES = {
    "profiles": "profiles.json",
    "offers": "offers.json",
    "matching_labels": "matching_labels.json",
    "cv_facts": "cv_facts.json",
    "letter_requirements": "letter_requirements.json",
}


def load_reference(directory=REFERENCE_DIR) -> dict:
    directory = Path(directory)
    return {
        key: json.loads((directory / name).read_text(encoding="utf-8"))
        for key, name in _FILES.items()
    }


def _blank(value) -> bool:
    return not isinstance(value, str) or not value.strip()


def _duplicates(rows, key):
    # Seules les chaînes sont comptées : une valeur non hachable (liste) est déjà
    # signalée par `_check_ids` et ferait planter `Counter`.
    counts = Counter(v for v in (r.get(key) for r in rows) if isinstance(v, str))
    return [v for v, n in counts.items() if n > 1 and not _blank(v)]


def _dict_rows(rows, name, errors):
    """Ne garde que les lignes objets ; signale les autres."""
    if not isinstance(rows, list):
        errors.append(f"{name} : une liste est attendue")
        return []
    good = []
    for i, r in enumerate(rows):
        if isinstance(r, dict):
            good.append(r)
        else:
            errors.append(f"{name}[{i}] : objet attendu, reçu {type(r).__name__}")
    return good


def _check_ids(rows, name, keys, errors):
    for i, r in enumerate(rows):
        for key in keys:
            if _blank(r.get(key)):
                errors.append(f"{name}[{i}] : {key} manquant ou vide")


def _check_profiles(profiles, errors):
    for pid in _duplicates(profiles, "profile_id"):
        errors.append(f"profiles : profile_id dupliqué {pid!r}")
    for p in profiles:
        pid = p.get("profile_id")
        sources = p.get("sources")
        if not isinstance(sources, dict) or not any(sources.values()):
            errors.append(f"profil {pid} : aucune source non vide")
        elif unknown := sorted(str(name) for name in sources if name not in SOURCES):
            errors.append(f"profil {pid} : source inconnue {unknown} (attendu : {SOURCES})")
        sub = p.get("subgroup")
        if not isinstance(sub, dict):
            errors.append(f"profil {pid} : sous-groupe absent")
            continue
        if _blank(sub.get("metier")):
            errors.append(f"profil {pid} : sous-groupe sans metier")
        if sub.get("niveau") not in NIVEAUX:
            errors.append(f"profil {pid} : sous-groupe niveau invalide {sub.get('niveau')!r}")
        if sub.get("langue") not in LANGUES:
            errors.append(f"profil {pid} : sous-groupe langue invalide {sub.get('langue')!r}")
        if not isinstance(sub.get("reconversion"), bool):
            errors.append(f"profil {pid} : sous-groupe reconversion doit être booléen")


def _check_offers(offers, errors):
    for oid in _duplicates(offers, "offer_id"):
        errors.append(f"offers : offer_id dupliqué {oid!r}")
    for o in offers:
        oid = o.get("offer_id")
        for field in ("poste", "description"):
            if _blank(o.get(field)):
                errors.append(f"offre {oid} : {field} vide")
        if "piege_filtre_metier" in o and not isinstance(o["piege_filtre_metier"], bool):
            errors.append(f"offre {oid} : piege_filtre_metier doit être booléen")


def _is_known(value, known) -> bool:
    return isinstance(value, str) and value in known


def _check_refs(rows, name, pids, oids, errors):
    for r in rows:
        if not _is_known(r.get("profile_id"), pids):
            errors.append(f"{name} : profile_id inexistant {r.get('profile_id')!r}")
        if oids is not None and not _is_known(r.get("offer_id"), oids):
            errors.append(f"{name} : offer_id inexistant {r.get('offer_id')!r}")


def _check_labels(labels, errors):
    seen = Counter(
        pair
        for pair in ((r.get("profile_id"), r.get("offer_id")) for r in labels)
        if all(isinstance(v, str) for v in pair)
    )
    for (pid, oid), n in seen.items():
        if n > 1:
            errors.append(f"matching_labels : paire dupliquée ({pid}, {oid})")
    for r in labels:
        pair = (r.get("profile_id"), r.get("offer_id"))
        if r.get("label") not in LABELS:
            errors.append(f"matching_labels {pair} : label inconnu {r.get('label')!r}")
        if _blank(r.get("motif")):
            errors.append(f"matching_labels {pair} : motif vide")
        if "preference_violee" in r and not isinstance(r["preference_violee"], bool):
            errors.append(f"matching_labels {pair} : preference_violee doit être booléen")


def _check_facts(facts, errors):
    for f in facts:
        pid = f.get("profile_id")
        if _blank(f.get("fait")):
            errors.append(f"cv_facts {pid} : fait doit être une chaîne non vide")
        page = f.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            errors.append(f"cv_facts {pid} : page doit être un entier >= 1 ({page!r})")
        if not isinstance(f.get("critique"), bool):
            errors.append(f"cv_facts {pid} : critique doit être booléen")


def validate_reference(ref) -> list[str]:
    """Erreurs structurelles lisibles ; liste vide si le jeu est valide."""
    errors: list[str] = []
    names = ("profiles", "offers", "matching_labels", "cv_facts", "letter_requirements")
    ref = {n: _dict_rows(ref[n], n, errors) for n in names}
    for n, keys in (
        ("profiles", ("profile_id",)),
        ("offers", ("offer_id",)),
        ("matching_labels", ("profile_id", "offer_id")),
        ("cv_facts", ("profile_id",)),
        ("letter_requirements", ("profile_id", "offer_id")),
    ):
        _check_ids(ref[n], n, keys, errors)
    profiles, offers = ref["profiles"], ref["offers"]
    _check_profiles(profiles, errors)
    _check_offers(offers, errors)
    pids = {p["profile_id"] for p in profiles if isinstance(p.get("profile_id"), str)}
    oids = {o["offer_id"] for o in offers if isinstance(o.get("offer_id"), str)}
    _check_refs(ref["matching_labels"], "matching_labels", pids, oids, errors)
    _check_refs(ref["cv_facts"], "cv_facts", pids, None, errors)
    _check_refs(ref["letter_requirements"], "letter_requirements", pids, oids, errors)
    _check_labels(ref["matching_labels"], errors)
    _check_facts(ref["cv_facts"], errors)
    return errors
