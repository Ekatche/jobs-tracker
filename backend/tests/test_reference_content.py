"""Seuils de volume et d'intégrité du contenu réel du jeu de référence commun.

Hors réseau, déterministe. Le validateur structurel est testé ailleurs
(test_reference_dataset.py) ; ici on vérifie que le jeu livré respecte les
exigences de couverture du plan profil/matching.
"""

import re
from collections import Counter

from app.models import CandidatePreferences, RemotePolicy
from app.services.company_profiles import COMPANY_SIZES, SECTORS
from app.services.evaluation.offer_fit import SENIORITY_ORDER
from app.services.offer_scoring.assess import KNOWN_WORK_MODES
from app.services.profile.merge import build_profile_from_sources
from scripts.reference_dataset import (
    coverage_report,
    load_reference,
    validate_reference,
)

REF = load_reference()
PROFILES = REF["profiles"]
PROFILE_IDS = [p["profile_id"] for p in PROFILES]
ALLOWED_EMAIL = re.compile(r"@example\.(com|org)$")


def _leaf_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _leaf_strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _leaf_strings(value)


def _profile(pid):
    return next(p for p in PROFILES if p["profile_id"] == pid)


def _count(pred):
    return sum(1 for p in PROFILES if pred(p))


def test_reference_is_structurally_valid():
    assert validate_reference(REF) == []


def test_volume_subgroup_and_source_thresholds():
    assert len(PROFILES) >= 22
    assert len(REF["offers"]) >= 90
    assert len(REF["matching_labels"]) >= 350
    assert len(REF["letter_requirements"]) >= 12
    assert _count(lambda p: p["subgroup"]["niveau"] == "junior") >= 5
    assert _count(lambda p: p["subgroup"]["reconversion"]) >= 4
    assert _count(lambda p: p["subgroup"]["langue"] == "en") >= 4
    assert len({p["subgroup"]["metier"] for p in PROFILES}) >= 10
    assert all(p["sources"].get("cv") for p in PROFILES)
    assert _count(lambda p: p["sources"].get("manual")) >= 6
    assert _count(lambda p: p["sources"].get("github") or p["sources"].get("website")) >= 2


def test_preferences_present_on_majority_absent_on_some():
    def has_prefs(p):
        return any(
            isinstance(s, dict) and s.get("preferences") for s in p["sources"].values()
        )

    with_prefs = _count(has_prefs)
    assert with_prefs > len(PROFILES) // 2
    assert len(PROFILES) - with_prefs >= 2


def test_long_and_thin_profiles():
    def n_exp(p):
        return len(p["sources"]["cv"].get("experiences") or [])

    assert _count(lambda p: n_exp(p) >= 6) >= 3
    thin = [
        p for p in PROFILES if p["subgroup"]["niveau"] == "junior" and n_exp(p) <= 1
    ]
    assert thin


def test_timeseries_profile_has_no_industrial_sensor_experience():
    ts = [p for p in PROFILES if "séries temporelles" in p["subgroup"]["metier"]]
    assert len(ts) == 1
    text = " ".join(_leaf_strings(ts[0]["sources"])).lower()
    for banned in ("iot", "scada", "capteur", "sensor", "plc", "automate"):
        assert banned not in text, banned


def test_manual_corrects_cv_experience_for_three_profiles():
    corrected = 0
    for p in PROFILES:
        _profile_built, conflicts = build_profile_from_sources(p["sources"])
        if any(c["field"] in ("role", "end") for c in conflicts):
            corrected += 1
    assert corrected >= 3


def test_no_foreign_email():
    emails = [
        s
        for s in _leaf_strings([p["sources"] for p in PROFILES])
        if "@" in s and re.fullmatch(r"\S+@\S+", s)
    ]
    assert emails, "au moins un e-mail synthétique attendu"
    assert all(ALLOWED_EMAIL.search(e) for e in emails), emails


def test_offers_cover_traps_and_unknown_fields():
    offers = REF["offers"]
    assert sum(1 for o in offers if o.get("piege_filtre_metier") is True) >= 12
    assert sum(1 for o in offers if not (o.get("localisation") or "").strip()) >= 1
    assert sum(1 for o in offers if not (o.get("type_contrat") or "").strip()) >= 1
    sensors = [
        o
        for o in offers
        if re.search(
            r"capteur|iot|maintenance pr[ée]dictive",
            o["poste"] + o["description"],
            re.I,
        )
    ]
    assert len(sensors) >= 2
    assert (
        sum(1 for o in offers if re.search(r"\b(you|we|our)\b", o["description"], re.I))
        >= 5
    )


def test_offers_have_multiline_descriptions():
    for o in REF["offers"]:
        lines = [ln for ln in o["description"].split("\n") if ln.strip()]
        assert len(lines) >= 6, o["offer_id"]


def test_each_profile_has_enough_labels_of_each_kind():
    by_profile = {pid: Counter() for pid in PROFILE_IDS}
    for row in REF["matching_labels"]:
        by_profile[row["profile_id"]][row["label"]] += 1
    for pid, counts in by_profile.items():
        assert sum(counts.values()) >= 16, pid
        assert set(counts) == {"pertinent", "partiel", "hors_sujet"}, pid
        assert counts["pertinent"] >= 3, pid


def _has_prefs(profile):
    return any(
        isinstance(s, dict) and s.get("preferences")
        for s in profile["sources"].values()
    )


def test_each_profile_has_trap_reject_and_violated_preference():
    traps = {o["offer_id"] for o in REF["offers"] if o.get("piege_filtre_metier")}
    for p in PROFILES:
        pid = p["profile_id"]
        rows = [r for r in REF["matching_labels"] if r["profile_id"] == pid]
        assert any(
            r["offer_id"] in traps and r["label"] == "hors_sujet" for r in rows
        ), pid
        violated = any(
            r["label"] == "partiel" and r.get("preference_violee") is True for r in rows
        )
        # Sans préférence déclarée, aucune préférence ne peut être violée.
        assert violated == _has_prefs(p), pid


def test_preference_violee_only_on_partiel():
    for r in REF["matching_labels"]:
        if r.get("preference_violee"):
            assert r["label"] == "partiel", (r["profile_id"], r["offer_id"])


def test_cv_facts_per_profile_and_pages():
    by_profile = Counter(f["profile_id"] for f in REF["cv_facts"])
    for pid in PROFILE_IDS:
        assert by_profile[pid] >= 5, pid
    assert coverage_report(REF)["profiles_with_fact_page_ge_4"] >= 3
    critical = {
        "experiences.company",
        "experiences.role",
        "experiences.dates",
        "education.degree",
    }
    for f in REF["cv_facts"]:
        if f["champ"] in critical:
            assert f["critique"] is True, f


def test_letter_requirements_thresholds():
    letters = REF["letter_requirements"]
    ids = {r["profile_id"] for r in letters}
    pid_of = {p["profile_id"]: p for p in PROFILES}
    assert sum(1 for p in ids if pid_of[p]["subgroup"]["reconversion"]) >= 2
    assert sum(1 for p in ids if pid_of[p]["subgroup"]["langue"] == "en") >= 2
    assert any("séries temporelles" in pid_of[p]["subgroup"]["metier"] for p in ids)
    labels = {
        (r["profile_id"], r["offer_id"]): r["label"] for r in REF["matching_labels"]
    }
    for r in letters:
        assert labels.get((r["profile_id"], r["offer_id"])) in (
            "pertinent",
            "partiel",
        ), r


def test_timeseries_letter_against_sensor_offer_states_gap():
    ts = next(p for p in PROFILES if "séries temporelles" in p["subgroup"]["metier"])
    offers = {o["offer_id"]: o for o in REF["offers"]}
    hits = [
        r
        for r in REF["letter_requirements"]
        if r["profile_id"] == ts["profile_id"]
        and re.search(r"capteur", offers[r["offer_id"]]["description"], re.I)
    ]
    assert hits
    for r in hits:
        assert any("capteur" in g.lower() for g in r["lacunes"]), r
        assert r["transferables"], r


def test_letter_proofs_are_literal_source_substrings():
    pid_of = {p["profile_id"]: p for p in PROFILES}
    for r in REF["letter_requirements"]:
        texts = list(_leaf_strings(pid_of[r["profile_id"]]["sources"]))
        for proof in r["preuves_exactes"]:
            assert any(proof["preuve"] in t for t in texts), (r["profile_id"], proof)
        for tr in r["transferables"]:
            assert any(tr["element"] in t for t in texts), (r["profile_id"], tr)


def test_offers_use_stored_vocabularies():
    modes = KNOWN_WORK_MODES | {""}
    for o in REF["offers"]:
        oid = o["offer_id"]
        assert o["mode_travail"] in modes, oid
        assert o["seniority_level"] in SENIORITY_ORDER, oid
        assert o["sector"] in SECTORS, oid
        assert o["company_size"] in COMPANY_SIZES, oid
        assert o["type_contrat"] in {"CDI", "CDD", "Alternance", "Stage", ""}, oid


def _source_preferences(profile):
    for src in profile["sources"].values():
        if isinstance(src, dict) and src.get("preferences"):
            yield src["preferences"]


def test_preferences_match_stored_models():
    allowed = {m.value for m in RemotePolicy}
    for profile in PROFILES:
        for prefs in _source_preferences(profile):
            if "remote_policy" in prefs:
                assert prefs["remote_policy"] in allowed, profile["profile_id"]
            assert "Remote" not in prefs.get("locations", []), profile["profile_id"]
            assert set(prefs.get("seniority_levels", [])) <= set(SENIORITY_ORDER)
        merged, _ = build_profile_from_sources(profile["sources"])
        CandidatePreferences(**(merged.get("preferences") or {}))


# Table humaine remote_policy x mode d'offre ; un mode inconnu n'est jamais une violation.
REMOTE_VIOLATIONS = {
    "hybrid": {"Présentiel"},
    "on_site": {"Télétravail total"},
    "full_remote": {"Présentiel", "Hybride"},
    "flexible": set(),
}


def test_remote_violations_flag_preference_violee():
    offers = {o["offer_id"]: o for o in REF["offers"]}
    for r in REF["matching_labels"]:
        if r["label"] == "hors_sujet":
            continue  # un hors-sujet ne porte jamais le flag (autre métier)
        profile = _profile(r["profile_id"])
        merged, _ = build_profile_from_sources(profile["sources"])
        policy = (merged.get("preferences") or {}).get("remote_policy")
        if not policy:
            continue
        mode = offers[r["offer_id"]]["mode_travail"]
        if mode in REMOTE_VIOLATIONS[policy]:
            assert r.get("preference_violee") is True, (r["profile_id"], r["offer_id"])


def test_letter_exigences_and_transferables_are_consistent():
    for r in REF["letter_requirements"]:
        exigences = set(r["exigences"])
        for item in r["preuves_exactes"] + r["transferables"]:
            assert item["exigence"] in exigences, (r["profile_id"], r["offer_id"], item)
        for tr in r["transferables"]:
            assert len(tr["element"]) >= 15, tr
