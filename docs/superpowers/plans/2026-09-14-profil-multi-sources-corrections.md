# Profil candidat multi-sources + corrections de la revue — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construire le profil candidat à partir de trois sources indépendantes — CV, GitHub, site personnel — sans perdre de données ni écraser les corrections manuelles, puis corriger les défauts relevés à la revue du 2026-09-14.

**Architecture:** Le document `candidate_profile` cesse d'être un profil unique écrasé à chaque import. Il devient un conteneur de sources brutes (`sources.cv`, `sources.github`, `sources.website`, `sources.manual`) plus un profil dérivé recalculé par une fonction pure à chaque import. Chaque collecteur ne fait qu'une chose : remplir sa source. La fusion vit à un seul endroit, testable sans réseau ni base.

**LinkedIn est écarté**, sur mesure et non par principe : le crawl anonyme du profil ne renvoie que le mur de consentement (vérifié le 2026-09-14, `success=True`, 4788 caractères, zéro donnée de profil). Le lien LinkedIn disparaît donc des champs d'enrichissement. Il reste un simple champ de contact, affiché et jamais crawlé. `sources` étant un dictionnaire ouvert, ajouter LinkedIn plus tard ne coûterait qu'un collecteur et une entrée dans `SOURCE_PRIORITY`.

**Tech Stack:** FastAPI, Motor, Pydantic v2, litellm (`acompletion`), Crawl4AI 0.6.3 (`arun_many`), PyMuPDF, API REST GitHub, pytest.

**Spec:** [docs/superpowers/specs/2026-09-13-lettres-motivation-design.md](../specs/2026-09-13-lettres-motivation-design.md) — ce plan corrige l'implémentation existante et étend la partie « profil candidat » de la spec à trois sources collectées plus les corrections manuelles.

## Global Constraints

- Aucune donnée personnelle committée. `data/profile/` et `backend/app/uploads/` restent gitignorés. Les PDF uploadés sont supprimés après parsing.
- Fonction pure = zéro I/O : `build_profile_from_sources` ne touche ni réseau, ni base, ni LLM. Tous ses tests tournent sans fixture externe.
- Aucun appel LLM synchrone dans une coroutine. `litellm.acompletion` dans le code async, `asyncio.to_thread` pour le CPU-bound (PyMuPDF).
- `litellm.drop_params` ne doit plus être positionné en global de module : passer `drop_params=True` par appel.
- Modèles LLM épinglés : aucun identifiant contenant `latest` ou `preview`. Contrôle déjà en place dans `validate_no_floating_alias`.
- Toute écriture dans `candidate_profile` passe par la validation Pydantic `CandidateProfile`. Plus de `dict` brut venu d'un LLM écrit tel quel.
- Ordre déterministe partout : jamais de `list(set(...))` sur des données qui atteignent un prompt.
- Chaque tâche finit sur `cd backend && .venv/bin/python -m pytest tests/ -q` au vert. La suite est actuellement à **5 failed, 96 passed** : la phase 0 la remet au vert et rien ne doit la faire régresser ensuite.

---

## État de départ mesuré (2026-09-14)

```
cd backend && .venv/bin/python -m pytest tests/ -q
5 failed, 96 passed
```

- La collecte échouait d'abord sur `ModuleNotFoundError: No module named 'fitz'` (pymupdf déclaré mais absent du venv local).
- 4 échecs (`test_users.py` ×3, `test_tasks.py` ×1) sont causés par `tests/test_cover_letters_api.py` qui laisse fuiter `app.dependency_overrides`. Ces fichiers passent isolément (12 passed).
- 1 échec est un vrai bug : `test_letter_llm.py::test_valid_cross_provider_resolution` → `assert 'google' == 'openai'`.

Comportement de fusion mesuré sur les données réelles (CV FR + site EN) :

```
experiences apres merge: 3
  - Agence Nile Août 2025 -> PRESENT
  - Agence Nile Aug. 2026 -> Present
  - Agence Nile Aug. 2025 -> Aug. 2026
conflicts: []
projects: ['Sentinel']          # WideDocs (CV) perdu
```

Faisabilité des sources, vérifiée et non supposée :

| Source | Mécanisme retenu | Preuve |
|---|---|---|
| CV | PyMuPDF + LLM (déjà en place) | fonctionne |
| Site perso | `sitemap.xml` puis `arun_many` | sitemap 200, 9 URLs |
| GitHub | API REST `/users/{u}/repos` + README, forks exclus | 24 repos, forks présents, descriptions souvent vides |
| LinkedIn | **écarté** — lien retiré de l'enrichissement, conservé en contact | crawl anonyme renvoie le mur de cookies (4788 car., 0 donnée) |

Le site personnel reprend le rôle que LinkedIn aurait tenu : sa page `/experience` porte le détail que le CV ne peut pas contenir, et le sitemap la rend découvrable sans deviner de chemin.

---

## File Structure

**Créés :**

| Fichier | Responsabilité |
|---|---|
| `backend/app/services/profile/periods.py` | Normalisation des dates et du nom d'entreprise. Zéro dépendance. |
| `backend/app/services/profile/merge.py` | `build_profile_from_sources` : fonction pure, seule autorité sur la fusion. |
| `backend/app/services/profile/collectors/website.py` | Sitemap + `arun_many` + extraction LLM. |
| `backend/app/services/profile/collectors/github.py` | API REST GitHub, forks exclus, README. |
| `backend/app/services/profile/urls.py` | Validation anti-SSRF des URLs fournies par l'utilisateur. |
| `backend/tests/test_profile_periods.py` | Tests de normalisation. |
| `backend/tests/test_profile_merge.py` | Tests de fusion, sans réseau ni base. |
| `backend/tests/test_profile_collectors.py` | Tests des collecteurs, réseau mocké. |
| `backend/tests/test_profile_urls.py` | Tests anti-SSRF. |
| `backend/tests/test_profile_endpoints.py` | Tests des endpoints d'import et d'enrichissement. |

**Modifiés :**

| Fichier | Changement |
|---|---|
| `backend/app/routers/cover_letters.py` | Imports en tête, endpoints d'import par source, anti-SSRF, upload durci, plus de blocage de boucle. |
| `backend/app/utils.py` | `merge_profile_sources` supprimée (remplacée par `profile/merge.py`). |
| `backend/app/models.py` | `CandidateProfile.sources`, `CandidateConflict`, `provenance.source` étendu. |
| `backend/app/services/cv_parser.py` | `acompletion`, plus de `print`, schéma aligné sur le modèle Pydantic. |
| `backend/app/services/web_enricher.py` | Supprimé, remplacé par `profile/collectors/`. |
| `backend/app/routers/applications.py` | Idempotence qui ignore `failed`, historique conservé, imports en tête. |
| `backend/job_trackers/src/job_trackers/letter_llm.py` | Branche Mistral corrigée, plus de clé factice, températures réellement utilisées. |
| `backend/job_trackers/src/job_trackers/cover_letter_crew.py` | Prompts chargés depuis les `.md`, profil en dur retiré, `drop_params` local. |
| `backend/app/services/letter_guards.py` | Garde-fou entités réel, bornes alignées sur le prompt. |
| `backend/tests/test_cover_letters_api.py` | Fixture qui nettoie `dependency_overrides`. |
| `docker-compose.yml` | `MISTRAL_API_KEY` lignes 33 et 157. |
| `frontend/src/components/profile/CandidateProfileSection.tsx` | Trois boutons d'import, conflits affichés, état par source, lien LinkedIn en simple contact. |
| `frontend/src/lib/api.ts` | Endpoints par source. |

**Pourquoi un modèle `sources` plutôt qu'un correctif de `merge_profile_sources`**

L'objectif « le CV ne peut pas tout contenir » implique des imports répétés depuis plusieurs sources. Avec un profil unique écrasé, chaque import écrase le précédent — mesuré ci-dessus : `projects` remplacé, pas fusionné, et `WideDocs` perdu. Avec les sources conservées séparément, l'import est idempotent (réimporter GitHub ne touche que `sources.github`), le profil dérivé est reproductible, la provenance est exacte par construction, et les corrections manuelles (`sources.manual`) survivent à tous les imports suivants. C'est la seule façon de rendre l'enrichissement répétable, et c'est aussi ce qui rend la fusion testable sans réseau.

---

# Phase 0 — Remettre la suite au vert

Rien n'est vérifiable tant que `pytest tests/` est rouge. Deux tâches, mécaniques.

### Task 1: Import PyMuPDF paresseux et étanchéité des overrides de test

**Files:**
- Modify: `backend/app/services/cv_parser.py:1`
- Modify: `backend/tests/test_cover_letters_api.py:1-16`

**Interfaces:**
- Consumes: rien.
- Produits: aucune signature nouvelle. `extract_text_from_pdf(pdf_path: str) -> str` inchangée.

- [ ] **Step 1: Écrire le test qui échoue**

Créer `backend/tests/test_profile_endpoints.py` avec ce premier test — il vérifie que l'application s'importe sans PyMuPDF installé :

```python
import importlib
import sys


def test_app_imports_without_pymupdf(monkeypatch):
    """L'absence de pymupdf ne doit pas empêcher l'API de démarrer."""
    monkeypatch.setitem(sys.modules, "fitz", None)
    for mod in ("app.services.cv_parser", "app.routers.cover_letters"):
        sys.modules.pop(mod, None)
    module = importlib.import_module("app.services.cv_parser")
    assert hasattr(module, "extract_text_from_pdf")
```

- [ ] **Step 2: Lancer le test, vérifier qu'il échoue**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_endpoints.py -q
```

Attendu : FAIL — `import fitz` au niveau module lève quand `sys.modules["fitz"]` vaut `None`.

- [ ] **Step 3: Rendre l'import paresseux**

Dans `backend/app/services/cv_parser.py`, supprimer la ligne 1 `import fitz  # PyMuPDF` et déplacer l'import dans la fonction :

```python
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extrait le texte d'un PDF en conservant la structure."""
    import fitz  # PyMuPDF — import local : dépendance lourde, hors du chemin de démarrage

    doc = fitz.open(pdf_path)
    try:
        return "\n\n".join(page.get_text() for page in doc)
    finally:
        doc.close()
```

- [ ] **Step 4: Vérifier que le test passe**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_endpoints.py -q
```

Attendu : PASS.

- [ ] **Step 5: Étancher les overrides de `test_cover_letters_api.py`**

Ce fichier pose `app.dependency_overrides[...]` dans cinq tests sans jamais nettoyer, ce qui casse `test_users.py` et `test_tasks.py`. Ajouter en tête du fichier, après les imports :

```python
@pytest.fixture(autouse=True)
def _clean_dependency_overrides():
    """Les overrides de ce fichier ne doivent pas fuiter vers les autres modules de test."""
    snapshot = dict(app.dependency_overrides)
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(snapshot)
```

- [ ] **Step 6: Vérifier que la fuite est bouchée**

```bash
cd backend && .venv/bin/python -m pytest tests/test_cover_letters_api.py tests/test_users.py tests/test_tasks.py -q
```

Attendu : 17 passed. Avant le correctif : `4 failed, 13 passed`.

- [ ] **Step 7: Commit**

```bash
cd /Users/elielkatche/job-tracker && git checkout -b fix/profile-multi-sources
git add backend/app/services/cv_parser.py backend/tests/test_cover_letters_api.py backend/tests/test_profile_endpoints.py
git commit -m "fix: import PyMuPDF paresseux et overrides de test étanches"
```

---

### Task 2: Critique inter-fournisseur pour un rédacteur Mistral

**Files:**
- Modify: `backend/job_trackers/src/job_trackers/letter_llm.py:43-49`
- Test: `backend/tests/test_letter_llm.py` (test existant, déjà rouge)

**Interfaces:**
- Consumes: `get_model_provider(model: str) -> str`.
- Produits: `validate_cross_provider(writer_model: str, critic_model: Optional[str]) -> str` — comportement corrigé, signature inchangée.

- [ ] **Step 1: Constater l'échec existant**

```bash
cd backend && .venv/bin/python -m pytest tests/test_letter_llm.py -q
```

Attendu : FAIL — `assert 'google' == 'openai'`. Le test est juste, le code a tort : la spec impose qu'un rédacteur Mistral ou Google soit critiqué par OpenAI.

- [ ] **Step 2: Corriger la résolution automatique**

Remplacer les lignes 43-49 de `letter_llm.py` :

```python
    # Résolution automatique : le critique doit toujours changer de fournisseur
    CROSS_PROVIDER_CRITIC = {
        "openai": "gemini/gemini-3.8-flash",
        "google": "openai/gpt-5.6-terra",
        "mistral": "openai/gpt-5.6-terra",
    }
    return CROSS_PROVIDER_CRITIC[writer_prov]
```

- [ ] **Step 3: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Attendu : `101 passed`. C'est la barre de référence pour tout le reste du plan.

- [ ] **Step 4: Commit**

```bash
git add backend/job_trackers/src/job_trackers/letter_llm.py
git commit -m "fix: critique OpenAI quand le rédacteur est Mistral"
```

---

# Phase 1 — Fondation : normalisation, sources, fusion pure

C'est le cœur de la demande. Sans cette phase, ajouter des sources multiplie les doublons.

### Task 3: Normalisation des périodes et des noms d'entreprise

**Files:**
- Create: `backend/app/services/profile/__init__.py` (vide)
- Create: `backend/app/services/profile/periods.py`
- Test: `backend/tests/test_profile_periods.py`

**Interfaces:**
- Produits :
  - `normalize_month(raw: str | None) -> str | None` — « Août 2025 » → `"2025-08"`, « Aug. 2025 » → `"2025-08"`, « 2022 » → `"2022"`, « PRESENT » → `None`.
  - `company_slug(raw: str) -> str` — « Agence Nile(Mauritius — International Assignment (VIE)) » → `"agence nile"`.
  - `is_open_ended(raw: str | None) -> bool`.

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_profile_periods.py` :

```python
import pytest

from app.services.profile.periods import company_slug, is_open_ended, normalize_month


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Août 2025", "2025-08"),
        ("aout 2025", "2025-08"),
        ("Aug. 2025", "2025-08"),
        ("August 2025", "2025-08"),
        ("Sept 2021", "2021-09"),
        ("Fev 2023", "2023-02"),
        ("February 2023", "2023-02"),
        ("2022", "2022"),
        ("03/2021", "2021-03"),
        ("2021-03", "2021-03"),
        ("PRESENT", None),
        ("Present", None),
        ("en cours", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_month(raw, expected):
    assert normalize_month(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Agence Nile", "agence nile"),
        ("Agence Nile(Mauritius — International Assignment (VIE))", "agence nile"),
        ("AGENCE NILE, VIE - Ile Maurice", "agence nile"),
        ("Centre Léon Bérard", "centre leon berard"),
        ("CENTRE LEON BERARD, LYON", "centre leon berard"),
        ("Bimedoc  SAS", "bimedoc"),
        ("bioMérieux", "biomerieux"),
        ("Nodya Group(Lyon, France)", "nodya group"),
    ],
)
def test_company_slug(raw, expected):
    assert company_slug(raw) == expected


def test_is_open_ended():
    assert is_open_ended("PRESENT") is True
    assert is_open_ended("aujourd'hui") is True
    assert is_open_ended(None) is True
    assert is_open_ended("Aug. 2026") is False
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_periods.py -q
```

Attendu : erreur de collecte — `ModuleNotFoundError: No module named 'app.services.profile'`.

- [ ] **Step 3: Implémenter**

`backend/app/services/profile/periods.py` :

```python
"""Normalisation des périodes et des employeurs.

Les sources n'écrivent pas les dates de la même façon : le CV dit « Août 2025 »,
le site dit « Aug. 2025 ». Comparer les chaînes brutes crée un doublon par
variante d'écriture ; tout passe donc par ces fonctions avant comparaison.
"""

import re
import unicodedata

_MONTHS = {
    "janvier": 1, "january": 1, "jan": 1,
    "fevrier": 2, "february": 2, "feb": 2, "fev": 2,
    "mars": 3, "march": 3, "mar": 3,
    "avril": 4, "april": 4, "apr": 4, "avr": 4,
    "mai": 5, "may": 5,
    "juin": 6, "june": 6, "jun": 6,
    "juillet": 7, "july": 7, "jul": 7, "juil": 7,
    "aout": 8, "august": 8, "aug": 8,
    "septembre": 9, "september": 9, "sep": 9, "sept": 9,
    "octobre": 10, "october": 10, "oct": 10,
    "novembre": 11, "november": 11, "nov": 11,
    "decembre": 12, "december": 12, "dec": 12,
}

_OPEN_ENDED = {
    "present", "presente", "aujourd'hui", "aujourdhui", "en cours",
    "current", "now", "actuel", "actuellement", "today", "",
}

_LEGAL_SUFFIXES = {"sas", "sa", "sarl", "sasu", "inc", "llc", "ltd", "gmbh", "group" }


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def is_open_ended(raw: str | None) -> bool:
    """Vrai quand la période n'a pas de fin connue (poste en cours)."""
    if raw is None:
        return True
    return _strip_accents(raw).strip().lower() in _OPEN_ENDED


def normalize_month(raw: str | None) -> str | None:
    """Retourne 'YYYY-MM', ou 'YYYY' si le mois est absent, ou None si sans fin.

    None signifie « pas de date exploitable » : période ouverte, chaîne vide,
    ou format non reconnu. L'appelant traite None comme une information absente,
    jamais comme une erreur.
    """
    if is_open_ended(raw):
        return None

    text = _strip_accents(str(raw)).strip().lower()

    # 2021-03 ou 2021/03
    iso = re.match(r"^(\d{4})[-/](\d{1,2})$", text)
    if iso:
        return f"{iso.group(1)}-{int(iso.group(2)):02d}"

    # 03/2021 ou 03-2021
    reverse = re.match(r"^(\d{1,2})[-/](\d{4})$", text)
    if reverse:
        return f"{reverse.group(2)}-{int(reverse.group(1)):02d}"

    year_match = re.search(r"(19|20)\d{2}", text)
    if not year_match:
        return None
    year = year_match.group(0)

    for name, number in _MONTHS.items():
        if re.search(rf"\b{name}\b", text):
            return f"{year}-{number:02d}"

    return year


def company_slug(raw: str) -> str:
    """Clé stable pour un employeur, insensible à la casse, aux accents et au lieu.

    Les sources accolent le lieu ou le type de contrat au nom : on coupe à la
    première parenthèse et à la première virgule, puis on retire les suffixes
    juridiques.
    """
    if not raw:
        return ""
    text = _strip_accents(raw).lower()
    text = re.split(r"[(,|]", text)[0]
    text = re.sub(r"[^a-z0-9&\s-]", " ", text)
    tokens = [t for t in text.split() if t and t not in _LEGAL_SUFFIXES]
    return " ".join(tokens).strip()
```

- [ ] **Step 4: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_periods.py -q
```

Attendu : tous les cas passent. Si `("Nodya Group(Lyon, France)", "nodya group")` échoue parce que `group` est dans `_LEGAL_SUFFIXES`, retirer `group` de cet ensemble : c'est un mot porteur de sens dans un nom d'entreprise, contrairement à `sas` ou `ltd`. Le test est l'autorité.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/profile/ backend/tests/test_profile_periods.py
git commit -m "feat: normalisation des périodes et des noms d'entreprise"
```

---

### Task 4: Fusion pure multi-sources

**Files:**
- Create: `backend/app/services/profile/merge.py`
- Test: `backend/tests/test_profile_merge.py`

**Interfaces:**
- Consomme : `company_slug`, `normalize_month`, `is_open_ended` (Task 3).
- Produit :
  - `SOURCE_PRIORITY: tuple[str, ...] = ("manual", "cv", "website", "github")`
  - `build_profile_from_sources(sources: dict[str, dict]) -> tuple[dict, list[dict]]` → `(profil_dérivé, conflits)`

**Règles de fusion, explicites parce que ce sont elles qui portent la valeur :**

1. **Clé d'expérience** : `(company_slug(company), normalize_month(start))`. La date de fin est exclue de la clé — le CV dit « PRESENT » là où le site dit « Aug. 2026 » pour le même poste, et deux passages chez le même employeur se distinguent déjà par leur date de début.
2. **Ordre des sources** : `manual` > `cv` > `website` > `github`. `manual` gagne toujours, c'est ce qui protège les corrections à la main. La liste est ouverte : une source inconnue est traitée après les sources connues, par ordre alphabétique, ce qui rend l'ajout d'une source ultérieure sans effet sur les tests existants.
3. **Champs scalaires** (`role`, `location`, `contract`, `sector`) : première source non vide dans l'ordre de priorité. Une divergence entre deux sources devient un conflit, jamais un écrasement silencieux.
4. **Missions** : on prend le **bloc** de la source qui en a le plus, pas l'union. Le CV est en français et le site en anglais ; unir produirait chaque mission deux fois dans deux langues, et ces missions partent dans le prompt du rédacteur. Les autres blocs sont conservés dans `missions_alt` pour l'édition manuelle.
5. **Stack** : union, ordre stable (ordre d'apparition selon la priorité des sources), dédup insensible à la casse.
6. **Fin de période** : la date la plus informative gagne — une date réelle bat une période ouverte. Si deux sources donnent deux dates différentes, conflit.
7. **Projets** : union par `name` normalisé ; description la plus longue retenue ; `url` première non vide.
8. **Conflits** : toujours retournés, jamais résolus en silence.

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_profile_merge.py` :

```python
from app.services.profile.merge import build_profile_from_sources

CV = {
    "headline": "Ingénieur Data & IA",
    "summary": "Résumé issu du CV.",
    "experiences": [
        {
            "company": "AGENCE NILE, VIE - Ile Maurice",
            "role": "Data Engineer",
            "start": "Août 2025",
            "end": "PRESENT",
            "missions": ["Agents LLM en production", "Pipelines ETL/ELT Azure"],
            "stack": ["Python", "Mistral"],
        }
    ],
    "projects": [{"name": "WideDocs", "description": "Plateforme documentaire."}],
}

WEBSITE = {
    "summary": "Résumé issu du site.",
    "experiences": [
        {
            "company": "Agence Nile(Mauritius — International Assignment (VIE))",
            "role": "Data Engineer",
            "start": "Aug. 2025",
            "end": "Aug. 2026",
            "missions": ["RAG with Qdrant", "CRM/ERP sync", "PySpark medallion pipeline"],
            "stack": ["Qdrant", "PySpark", "python"],
        },
        {
            "company": "Agence Nile(Lyon, France)",
            "role": "Data Engineer",
            "start": "Aug. 2026",
            "end": None,
            "missions": ["Industrializing production pipelines"],
            "stack": ["Microsoft Fabric"],
        },
        {
            "company": "bioMérieux",
            "role": "Supply Chain Data Analyst",
            "start": "March 2021",
            "end": "Sept. 2021",
            "missions": ["KPI modeling"],
            "stack": ["Power BI"],
        },
    ],
    "projects": [{"name": "Sentinel", "description": "Trading quantitatif."}],
}


def test_same_role_across_sources_is_merged_once():
    """Deux écritures de la même période ne doivent produire qu'une expérience."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    nile = [e for e in profile["experiences"] if "nile" in e["company"].lower()]
    assert len(nile) == 2  # le poste mauricien et le poste lyonnais, pas trois


def test_experience_absent_from_cv_is_added():
    """Le CV ne contient pas tout : le site apporte les postes manquants."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    companies = {e["company"] for e in profile["experiences"]}
    assert any("bioMérieux" in c or "bioMerieux" in c for c in companies)


def test_open_ended_end_date_is_replaced_by_a_real_one():
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(
        e for e in profile["experiences"] if e["start"] == "2025-08"
    )
    assert mauritius["end"] == "2026-08"


def test_missions_are_not_duplicated_across_languages():
    """Le bloc le plus fourni gagne ; l'autre reste accessible mais séparé."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(e for e in profile["experiences"] if e["start"] == "2025-08")
    assert len(mauritius["missions"]) == 3
    assert "Agents LLM en production" in mauritius["missions_alt"]


def test_stack_is_unioned_without_case_duplicates():
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(e for e in profile["experiences"] if e["start"] == "2025-08")
    lowered = [s.lower() for s in mauritius["stack"]]
    assert lowered.count("python") == 1
    assert {"python", "mistral", "qdrant", "pyspark"} <= set(lowered)


def test_projects_are_unioned_not_replaced():
    """Le bug mesuré le 2026-09-14 : WideDocs disparaissait au profit de Sentinel."""
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    names = {p["name"] for p in profile["projects"]}
    assert names == {"WideDocs", "Sentinel"}


def test_manual_source_always_wins():
    manual = {"headline": "Lead Data Engineer"}
    profile, _ = build_profile_from_sources({"cv": CV, "manual": manual})
    assert profile["headline"] == "Lead Data Engineer"


def test_role_divergence_is_reported_as_conflict():
    variant = {
        "experiences": [
            {
                "company": "Agence Nile",
                "role": "Lead Data Engineer",
                "start": "Août 2025",
                "end": "PRESENT",
            }
        ]
    }
    profile, conflicts = build_profile_from_sources({"cv": CV, "website": variant})
    assert any(c["field"] == "role" for c in conflicts)
    assert profile["experiences"][0]["role"] == "Data Engineer"  # cv > website


def test_unknown_source_is_accepted_after_the_known_ones():
    """Ajouter une source plus tard ne doit pas casser la fusion existante."""
    extra = {"experiences": [{"company": "Agence Nile", "role": "Ingénieur", "start": "Août 2025"}]}
    profile, _ = build_profile_from_sources({"cv": CV, "annuaire": extra})
    assert profile["experiences"][0]["role"] == "Data Engineer"
    assert "annuaire" in profile["experiences"][0]["sources"]


def test_provenance_names_every_contributing_source():
    profile, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    mauritius = next(e for e in profile["experiences"] if e["start"] == "2025-08")
    assert set(mauritius["sources"]) == {"cv", "website"}


def test_merge_is_idempotent_and_deterministic():
    once, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    twice, _ = build_profile_from_sources({"cv": CV, "website": WEBSITE})
    assert once == twice


def test_empty_sources_yield_empty_profile():
    profile, conflicts = build_profile_from_sources({})
    assert profile["experiences"] == []
    assert conflicts == []
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_merge.py -q
```

Attendu : `ModuleNotFoundError: No module named 'app.services.profile.merge'`.

- [ ] **Step 3: Implémenter**

`backend/app/services/profile/merge.py` :

```python
"""Fusion des sources du profil candidat.

Fonction pure : aucun I/O, aucun LLM, aucune base. Un seul endroit décide quelle
source gagne sur quel champ, ce qui rend la règle lisible et testable.
"""

from typing import Any, Dict, List, Tuple

from app.services.profile.periods import company_slug, is_open_ended, normalize_month

SOURCE_PRIORITY: Tuple[str, ...] = ("manual", "cv", "website", "github")

_SCALAR_FIELDS = ("role", "location", "contract", "sector")


def _ordered_sources(sources: Dict[str, Dict[str, Any]]) -> List[str]:
    known = [s for s in SOURCE_PRIORITY if sources.get(s)]
    extra = sorted(s for s in sources if s not in SOURCE_PRIORITY and sources.get(s))
    return known + extra


def _dedup_preserving_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        key = value.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value.strip())
    return result


def _first_non_empty(field: str, contributions: List[Tuple[str, Dict[str, Any]]]):
    for _source, payload in contributions:
        value = payload.get(field)
        if value:
            return value
    return None


def _merge_one_experience(
    contributions: List[Tuple[str, Dict[str, Any]]],
    conflicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    winner_source, winner = contributions[0]
    merged: Dict[str, Any] = {
        "company": winner.get("company", ""),
        "start": normalize_month(winner.get("start")),
        "sources": [source for source, _ in contributions],
    }

    for field in _SCALAR_FIELDS:
        merged[field] = _first_non_empty(field, contributions)
        for source, payload in contributions[1:]:
            other = payload.get(field)
            if other and merged[field] and other != merged[field]:
                conflicts.append(
                    {
                        "company": merged["company"],
                        "field": field,
                        "kept": merged[field],
                        "kept_source": winner_source,
                        "discarded": other,
                        "discarded_source": source,
                    }
                )

    # Fin de période : une date réelle bat une période ouverte.
    ends = [
        (source, normalize_month(payload.get("end")))
        for source, payload in contributions
        if not is_open_ended(payload.get("end"))
    ]
    merged["end"] = ends[0][1] if ends else None
    distinct_ends = {value for _source, value in ends if value}
    if len(distinct_ends) > 1:
        conflicts.append(
            {
                "company": merged["company"],
                "field": "end",
                "kept": merged["end"],
                "kept_source": ends[0][0],
                "discarded": sorted(distinct_ends - {merged["end"]}),
                "discarded_source": "autres sources",
            }
        )

    # Missions : le bloc le plus fourni, pas l'union — évite le doublon FR/EN.
    blocks = [
        (source, payload.get("missions") or [])
        for source, payload in contributions
    ]
    blocks_sorted = sorted(
        blocks,
        key=lambda item: (-len(item[1]), SOURCE_PRIORITY.index(item[0]) if item[0] in SOURCE_PRIORITY else 99),
    )
    merged["missions"] = _dedup_preserving_order(list(blocks_sorted[0][1]))
    merged["missions_source"] = blocks_sorted[0][0]
    alternates: List[str] = []
    for _source, block in blocks_sorted[1:]:
        alternates.extend(block)
    merged["missions_alt"] = _dedup_preserving_order(alternates)

    stack: List[str] = []
    for _source, payload in contributions:
        stack.extend(payload.get("stack") or [])
    merged["stack"] = _dedup_preserving_order(stack)

    achievements: List[Dict[str, Any]] = []
    for _source, payload in contributions:
        achievements.extend(payload.get("achievements") or [])
    merged["achievements"] = achievements

    return merged


def _merge_experiences(
    sources: Dict[str, Dict[str, Any]],
    order: List[str],
    conflicts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str | None], List[Tuple[str, Dict[str, Any]]]] = {}
    key_order: List[Tuple[str, str | None]] = []

    for source in order:
        for experience in sources[source].get("experiences") or []:
            key = (
                company_slug(experience.get("company", "")),
                normalize_month(experience.get("start")),
            )
            if key not in grouped:
                grouped[key] = []
                key_order.append(key)
            grouped[key].append((source, experience))

    merged = [_merge_one_experience(grouped[key], conflicts) for key in key_order]
    # Ordre stable et lisible : du poste le plus récent au plus ancien.
    return sorted(merged, key=lambda e: e["start"] or "", reverse=True)


def _merge_projects(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for project in sources[source].get("projects") or []:
            name = (project.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key not in grouped:
                grouped[key] = dict(project)
                grouped[key]["sources"] = [source]
                continue
            current = grouped[key]
            current["sources"].append(source)
            if len(project.get("description") or "") > len(current.get("description") or ""):
                current["description"] = project["description"]
            current["url"] = current.get("url") or project.get("url")
            current["stack"] = _dedup_preserving_order(
                (current.get("stack") or []) + (project.get("stack") or [])
            )
    return list(grouped.values())


def _merge_skills(
    sources: Dict[str, Dict[str, Any]], order: List[str]
) -> Dict[str, List[str]]:
    merged: Dict[str, List[str]] = {}
    for source in order:
        for category, skills in (sources[source].get("skills") or {}).items():
            merged.setdefault(category, []).extend(skills or [])
    return {cat: _dedup_preserving_order(values) for cat, values in merged.items()}


def _merge_simple_list(
    field: str, sources: Dict[str, Dict[str, Any]], order: List[str], key: str
) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for source in order:
        for item in sources[source].get(field) or []:
            identity = (item.get(key) or "").strip().lower()
            if identity and identity not in grouped:
                grouped[identity] = dict(item)
    return list(grouped.values())


def build_profile_from_sources(
    sources: Dict[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Construit le profil dérivé et la liste des conflits non résolus.

    `sources` est un dictionnaire {nom de source: payload}. Les sources vides ou
    absentes sont ignorées. Le résultat ne dépend que de l'entrée : réappeler la
    fonction avec les mêmes sources rend exactement le même profil.
    """
    order = _ordered_sources(sources)
    conflicts: List[Dict[str, Any]] = []

    if not order:
        return (
            {
                "headline": "",
                "summary": "",
                "contact": {},
                "experiences": [],
                "projects": [],
                "education": [],
                "certifications": [],
                "languages": [],
                "skills": {},
            },
            conflicts,
        )

    contributions = [(source, sources[source]) for source in order]

    contact: Dict[str, Any] = {}
    for source in reversed(order):  # la priorité la plus forte écrit en dernier
        contact.update({k: v for k, v in (sources[source].get("contact") or {}).items() if v})

    languages: List[str] = []
    for source in order:
        languages.extend(sources[source].get("languages") or [])

    profile = {
        "headline": _first_non_empty("headline", contributions) or "",
        "summary": _first_non_empty("summary", contributions) or "",
        "contact": contact,
        "experiences": _merge_experiences(sources, order, conflicts),
        "projects": _merge_projects(sources, order),
        "education": _merge_simple_list("education", sources, order, "school"),
        "certifications": _merge_simple_list("certifications", sources, order, "name"),
        "languages": _dedup_preserving_order(languages),
        "skills": _merge_skills(sources, order),
    }
    return profile, conflicts
```

- [ ] **Step 4: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_merge.py -q
```

Attendu : 12 passed.

- [ ] **Step 5: Vérifier la non-régression globale**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Attendu : `0 failed`. Les décomptes globaux ne sont plus donnés en valeur absolue à partir d'ici : chaque tâche en ajoute, et un nombre figé périmerait à la tâche suivante.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/profile/merge.py backend/tests/test_profile_merge.py
git commit -m "feat: fusion pure multi-sources du profil candidat"
```

---

### Task 5: Modèle Pydantic des sources et validation à l'écriture

**Files:**
- Modify: `backend/app/models.py:341-361`
- Test: `backend/tests/test_cover_letter_models.py`

**Interfaces:**
- Consomme : `build_profile_from_sources` (Task 4).
- Produit :
  - `CandidateProvenance.source: Literal["cv", "github", "website", "manual", "saisie"]`
  - `CandidateConflict` — `company`, `field`, `kept`, `kept_source`, `discarded`, `discarded_source`
  - `CandidateProfile.sources: Dict[str, dict]`, `CandidateProfile.conflicts: List[CandidateConflict]`
  - `CandidateExperience.missions_alt`, `.missions_source`, `.sources`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_cover_letter_models.py` :

```python
from app.models import CandidateConflict, CandidateProfile


def test_profile_accepts_sources_and_conflicts():
    profile = CandidateProfile(
        user_id="60c72b2f9b1d8b2bad7f9999",
        sources={"cv": {"headline": "Ingénieur Data"}, "github": {"projects": []}},
        conflicts=[
            CandidateConflict(
                company="Agence Nile",
                field="role",
                kept="Data Engineer",
                kept_source="cv",
                discarded="Lead Data Engineer",
                discarded_source="website",
            )
        ],
    )
    assert set(profile.sources) == {"cv", "github"}
    assert profile.conflicts[0].field == "role"


def test_experience_carries_alternate_missions_and_sources():
    profile = CandidateProfile(
        user_id="60c72b2f9b1d8b2bad7f9999",
        experiences=[
            {
                "company": "Agence Nile",
                "role": "Data Engineer",
                "start": "2025-08",
                "missions": ["RAG Qdrant"],
                "missions_alt": ["Agents LLM"],
                "missions_source": "website",
                "sources": ["cv", "website"],
            }
        ],
    )
    assert profile.experiences[0].missions_alt == ["Agents LLM"]
    assert profile.experiences[0].sources == ["cv", "website"]


def test_provenance_accepts_every_collector():
    for source in ("cv", "github", "website", "manual"):
        profile = CandidateProfile(
            user_id="60c72b2f9b1d8b2bad7f9999",
            provenance=[{"field_path": "experiences.0", "source": source}],
        )
        assert profile.provenance[0].source == source
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_cover_letter_models.py -q
```

Attendu : FAIL — `CandidateConflict` n'existe pas, et `Literal["cv","site","saisie"]` refuse `github`.

- [ ] **Step 3: Implémenter**

Dans `backend/app/models.py`, remplacer `CandidateProvenance` et compléter `CandidateExperience` / `CandidateProfile` :

```python
CandidateSource = Literal["cv", "github", "website", "manual", "saisie"]


class CandidateProvenance(BaseModel):
    field_path: str
    source: CandidateSource


class CandidateConflict(BaseModel):
    company: str = ""
    field: str
    kept: Any = None
    kept_source: str = ""
    discarded: Any = None
    discarded_source: str = ""
```

Ajouter à `CandidateExperience` :

```python
    missions_alt: List[str] = Field(default_factory=list)
    missions_source: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
```

Ajouter à `CandidateProfile` :

```python
    sources: Dict[str, Any] = Field(default_factory=dict)
    conflicts: List[CandidateConflict] = Field(default_factory=list)
```

Note : `CandidateProject.context` est un `Literal[...]` obligatoire. Un LLM ne devinera pas ces quatre valeurs de façon fiable — lui donner un défaut, sinon toute validation de projet extrait échouera :

```python
    context: Literal["perso", "client", "recherche", "consortium"] = "perso"
```

- [ ] **Step 4: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/test_cover_letter_models.py tests/ -q
```

Attendu : `0 failed`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_cover_letter_models.py
git commit -m "feat: modèle de profil à sources multiples et conflits typés"
```

---

# Phase 2 — Les collecteurs

Un collecteur par source, chacun testable isolément, réseau mocké. Aucun n'écrit en base : il rend un payload que la Task 9 range dans `sources.<nom>`.

### Task 6: Validation anti-SSRF des URLs

**Files:**
- Create: `backend/app/services/profile/urls.py`
- Test: `backend/tests/test_profile_urls.py`

**Interfaces:**
- Produit : `validate_public_url(raw: str, allowed_hosts: set[str] | None = None) -> str` — lève `ValueError` sinon.

**Pourquoi d'abord** : le collecteur de site consomme cette fonction, et l'endpoint actuel crawle n'importe quelle URL fournie par un compte authentifié, y compris `http://169.254.169.254/latest/meta-data/` ou un service interne du réseau Docker.

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_profile_urls.py` :

```python
import pytest

from app.services.profile.urls import validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/Ekatche",
        "https://www.elielkatche.me/experience",
    ],
)
def test_public_https_urls_are_accepted(url):
    assert validate_public_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",   # métadonnées cloud
        "http://localhost:8000/admin",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://10.0.0.5/internal",
        "http://192.168.1.10/",
        "http://mongodb:27017/",                      # service interne Docker
        "file:///etc/passwd",
        "gopher://evil/",
        "https://user:pass@github.com/",              # credentials dans l'URL
        "not-a-url",
        "",
    ],
)
def test_dangerous_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_allowed_hosts_restricts_further():
    validate_public_url("https://github.com/Ekatche", allowed_hosts={"github.com"})
    with pytest.raises(ValueError):
        validate_public_url("https://example.com/x", allowed_hosts={"github.com"})


def test_subdomain_of_allowed_host_is_accepted():
    assert validate_public_url(
        "https://www.elielkatche.me/experience", allowed_hosts={"elielkatche.me"}
    )
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_urls.py -q
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3: Implémenter**

`backend/app/services/profile/urls.py` :

```python
"""Contrôle des URLs fournies par l'utilisateur avant toute requête sortante.

Sans ce filtre, un compte authentifié peut faire émettre au serveur des requêtes
vers le réseau interne ou vers l'endpoint de métadonnées cloud, et récupérer la
réponse dans son propre profil.
"""

import ipaddress
import socket
from urllib.parse import urlparse


def _resolves_to_public_ip(hostname: str) -> bool:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Hôte introuvable : {hostname}") from exc

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        ):
            return False
    return True


def validate_public_url(raw: str, allowed_hosts: set[str] | None = None) -> str:
    """Retourne l'URL si elle est publique et autorisée, lève ValueError sinon."""
    if not raw or not raw.strip():
        raise ValueError("URL vide")

    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Schéma non autorisé : {parsed.scheme or 'absent'}")
    if parsed.username or parsed.password:
        raise ValueError("Les identifiants dans l'URL ne sont pas acceptés")
    if not parsed.hostname:
        raise ValueError("Hôte absent de l'URL")

    host = parsed.hostname.lower()
    if allowed_hosts is not None:
        if not any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
            raise ValueError(f"Hôte non autorisé : {host}")

    if not _resolves_to_public_ip(host):
        raise ValueError(f"L'hôte {host} résout vers une adresse non publique")

    return raw.strip()
```

- [ ] **Step 4: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_urls.py -q
```

Attendu : tous passent. `http://mongodb:27017/` est rejeté par `getaddrinfo` hors de Docker (hôte introuvable) et par la résolution privée dans Docker : les deux lèvent `ValueError`, le test tient dans les deux environnements.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/profile/urls.py backend/tests/test_profile_urls.py
git commit -m "feat: validation anti-SSRF des URLs de profil"
```

---

### Task 7: Collecteur site personnel — sitemap puis pages multiples

**Files:**
- Create: `backend/app/services/profile/collectors/__init__.py` (vide)
- Create: `backend/app/services/profile/collectors/website.py`
- Test: `backend/tests/test_profile_collectors.py`

**Interfaces:**
- Consomme : `validate_public_url` (Task 6).
- Produit :
  - `async def discover_pages(base_url: str, fetch=None) -> list[str]`
  - `async def collect_website(base_url: str, crawler=None, extract=None) -> dict`

**Faits qui dictent l'implémentation :** `https://www.elielkatche.me/sitemap.xml` renvoie 200 avec 9 URLs, mais celles-ci pointent le domaine `elielkatche.dev` alors que le site interrogé est `www.elielkatche.me`. Le collecteur réécrit donc chaque chemin sur le domaine fourni par l'utilisateur. Une seule page ne suffit pas : les expériences sont sur `/experience`, les projets sur `/work`, les diplômes sur `/formation`, les compétences sur `/competences`. Crawl4AI expose `arun_many(urls, ...)`, ce qui évite d'ouvrir un navigateur par page comme le fait le code actuel.

- [ ] **Step 1: Écrire les tests qui échouent**

`backend/tests/test_profile_collectors.py` :

```python
import pytest

from app.services.profile.collectors.website import discover_pages

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://elielkatche.dev</loc></url>
  <url><loc>https://elielkatche.dev/work</loc></url>
  <url><loc>https://elielkatche.dev/experience</loc></url>
  <url><loc>https://elielkatche.dev/formation</loc></url>
  <url><loc>https://elielkatche.dev/competences</loc></url>
  <url><loc>https://elielkatche.dev/contact</loc></url>
</urlset>
"""


@pytest.mark.asyncio
async def test_sitemap_paths_are_rewritten_on_the_requested_domain():
    """Le sitemap du site cite un autre domaine : on ne doit pas le suivre."""

    async def fake_fetch(url):
        return SITEMAP if url.endswith("sitemap.xml") else None

    pages = await discover_pages("https://www.elielkatche.me", fetch=fake_fetch)
    assert all(p.startswith("https://www.elielkatche.me") for p in pages)
    assert "https://www.elielkatche.me/experience" in pages
    assert "https://www.elielkatche.me/contact" not in pages  # page sans substance


@pytest.mark.asyncio
async def test_fallback_paths_when_no_sitemap():
    async def fake_fetch(url):
        return None

    pages = await discover_pages("https://example.com", fetch=fake_fetch)
    assert "https://example.com" in pages
    assert "https://example.com/experience" in pages


@pytest.mark.asyncio
async def test_page_count_is_capped():
    many = "".join(
        f"<url><loc>https://example.com/p{i}</loc></url>" for i in range(50)
    )
    async def fake_fetch(url):
        return f"<urlset>{many}</urlset>"

    pages = await discover_pages("https://example.com", fetch=fake_fetch)
    assert len(pages) <= 12
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_collectors.py -q
```

Attendu : `ModuleNotFoundError`. Si `pytest.mark.asyncio` est inconnu, vérifier que `pytest-asyncio` est bien dans `requirements.txt` — les tests existants de `test_verify_job_offers.py` en utilisent déjà, donc il l'est.

- [ ] **Step 3: Implémenter**

`backend/app/services/profile/collectors/website.py` :

```python
"""Collecte du site personnel du candidat.

Un CV tient sur deux pages, un site n'a pas cette limite : c'est la source la
plus riche en expériences et en projets. On lit le sitemap pour savoir quoi
crawler plutôt que de deviner les chemins.
"""

import json
import logging
import re
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import httpx
from litellm import acompletion

from app.services.profile.urls import validate_public_url

logger = logging.getLogger(__name__)

MAX_PAGES = 12
FALLBACK_PATHS = ("", "/experience", "/work", "/projects", "/formation", "/competences", "/about")
SKIP_PATTERNS = ("/contact", "/mentions", "/legal", "/privacy", "/blog/tag")
MODEL = "gemini/gemini-3.8-flash"


async def _default_fetch(url: str) -> Optional[str]:
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.text
    except httpx.HTTPError as exc:
        logger.info("sitemap indisponible sur %s: %s", url, exc)
    return None


async def discover_pages(
    base_url: str,
    fetch: Optional[Callable[[str], Awaitable[Optional[str]]]] = None,
) -> List[str]:
    """Liste les pages à crawler, plafonnée à MAX_PAGES.

    Les chemins viennent du sitemap quand il existe, mais toujours résolus sur le
    domaine demandé : un sitemap peut citer un domaine voisin.
    """
    base = validate_public_url(base_url).rstrip("/")
    fetch = fetch or _default_fetch

    sitemap = await fetch(f"{base}/sitemap.xml")
    paths: List[str] = []
    if sitemap:
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sitemap):
            path = urlparse(loc).path or "/"
            paths.append(path)
    if not paths:
        paths = list(FALLBACK_PATHS)

    pages: List[str] = []
    for path in paths:
        if any(skip in path.lower() for skip in SKIP_PATTERNS):
            continue
        url = base if path in ("", "/") else urljoin(base + "/", path.lstrip("/"))
        if url not in pages:
            pages.append(url)
        if len(pages) >= MAX_PAGES:
            break
    return pages


async def _extract_with_llm(pages_markdown: Dict[str, str]) -> Dict[str, Any]:
    corpus = "\n\n".join(
        f"### Page : {url}\n{markdown[:6000]}" for url, markdown in pages_markdown.items()
    )
    prompt = f"""Voici le contenu de plusieurs pages du site personnel d'un candidat.
Extrais les faits, sans rien inventer et sans reformuler en langage commercial.

{corpus}

Réponds uniquement par un objet JSON avec ces clés :
- "headline": titre professionnel
- "summary": résumé factuel
- "experiences": [{{"company", "role", "location", "contract", "start", "end", "missions": [], "stack": []}}]
- "projects": [{{"name", "description", "stack": [], "url"}}]
- "education": [{{"school", "degree", "years"}}]
- "certifications": [{{"name", "issuer", "year"}}]
- "skills": {{"catégorie": ["compétence"]}}
Pour "start" et "end", recopie la date telle qu'écrite sur la page.
Si une information est absente, rends une liste vide."""

    response = await acompletion(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        drop_params=True,
    )
    content = response.choices[0].message.content.strip()
    content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
    return json.loads(content)


async def collect_website(
    base_url: str,
    crawler=None,
    extract: Optional[Callable[[Dict[str, str]], Awaitable[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    """Rend un payload de source prêt à être rangé dans `sources.website`."""
    pages = await discover_pages(base_url)
    extract = extract or _extract_with_llm

    if crawler is None:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False) as instance:
            results = await instance.arun_many(pages)
    else:
        results = await crawler.arun_many(pages)

    markdown_by_url: Dict[str, str] = {}
    for result in results:
        markdown = getattr(result, "markdown", None)
        if markdown:
            markdown_by_url[getattr(result, "url", "")] = str(markdown)

    if not markdown_by_url:
        raise ValueError("Aucune page exploitable sur ce site")

    payload = await extract(markdown_by_url)
    payload["_pages"] = list(markdown_by_url)
    return payload
```

- [ ] **Step 4: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_collectors.py -q
```

Attendu : 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/profile/collectors/ backend/tests/test_profile_collectors.py
git commit -m "feat: collecteur site personnel multi-pages via sitemap"
```

---

### Task 8: Collecteur GitHub via l'API REST

**Files:**
- Create: `backend/app/services/profile/collectors/github.py`
- Test: `backend/tests/test_profile_collectors.py` (ajouts)

**Interfaces:**
- Produit :
  - `def parse_github_username(url_or_handle: str) -> str`
  - `async def collect_github(url_or_handle: str, client=None) -> dict`

**Pourquoi l'API et pas le crawl :** mesuré sur `Ekatche` — 24 repos, dont des forks (`transformerlab-app`, `stanford-cme-295-transformers-large-language-models`) qui ne sont pas son travail, et des `description` vides sur ses propres projets. Le crawl de la page de profil donnerait moins. L'API donne `fork`, `language`, `topics`, `pushed_at`, `stargazers_count`, et le README apporte la substance. `GITHUB_TOKEN` est optionnel : 60 requêtes/h sans, 5000 avec.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_profile_collectors.py` :

```python
from app.services.profile.collectors.github import collect_github, parse_github_username


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://github.com/Ekatche", "Ekatche"),
        ("https://github.com/Ekatche/", "Ekatche"),
        ("github.com/Ekatche", "Ekatche"),
        ("Ekatche", "Ekatche"),
    ],
)
def test_parse_github_username(raw, expected):
    assert parse_github_username(raw) == expected


@pytest.mark.parametrize("raw", ["https://github.com/", "", "https://gitlab.com/x"])
def test_parse_github_username_rejects_invalid(raw):
    with pytest.raises(ValueError):
        parse_github_username(raw)


class FakeGitHubClient:
    """Répond comme l'API REST GitHub, sans réseau."""

    def __init__(self):
        self.calls = []

    async def get_repos(self, username):
        self.calls.append(("repos", username))
        return [
            {
                "name": "WideDocs",
                "description": "Plateforme documentaire pour avocats",
                "language": "Python",
                "topics": ["fastapi", "ocr"],
                "html_url": "https://github.com/Ekatche/WideDocs",
                "fork": False,
                "archived": False,
                "pushed_at": "2026-09-01T00:00:00Z",
                "stargazers_count": 3,
            },
            {
                "name": "transformerlab-app",
                "description": "Fork amont",
                "language": "TypeScript",
                "topics": [],
                "html_url": "https://github.com/Ekatche/transformerlab-app",
                "fork": True,
                "archived": False,
                "pushed_at": "2026-01-01T00:00:00Z",
                "stargazers_count": 0,
            },
        ]

    async def get_readme(self, username, repo):
        self.calls.append(("readme", repo))
        return "# WideDocs\n\nImport et OCR de dossiers, anonymisation RGPD."


@pytest.mark.asyncio
async def test_forks_are_excluded():
    payload = await collect_github("https://github.com/Ekatche", client=FakeGitHubClient())
    names = {p["name"] for p in payload["projects"]}
    assert names == {"WideDocs"}


@pytest.mark.asyncio
async def test_readme_feeds_the_description_and_language_feeds_the_stack():
    payload = await collect_github("Ekatche", client=FakeGitHubClient())
    project = payload["projects"][0]
    assert "OCR" in project["description"]
    assert "Python" in project["stack"]
    assert project["url"] == "https://github.com/Ekatche/WideDocs"


@pytest.mark.asyncio
async def test_github_never_produces_experiences():
    """GitHub documente des projets, pas des emplois : ne pas inventer d'expérience."""
    payload = await collect_github("Ekatche", client=FakeGitHubClient())
    assert payload.get("experiences", []) == []
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_collectors.py -q
```

Attendu : `ModuleNotFoundError`.

- [ ] **Step 3: Implémenter**

`backend/app/services/profile/collectors/github.py` :

```python
"""Collecte GitHub par l'API REST.

L'API distingue les forks des dépôts propres, ce qu'un scrape de la page de
profil ne fait pas. GitHub documente des projets, jamais des emplois : ce
collecteur ne produit donc aucune expérience.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
MAX_REPOS = 12
README_CHARS = 1200


def parse_github_username(url_or_handle: str) -> str:
    """Extrait le pseudo depuis une URL GitHub ou un pseudo nu."""
    value = (url_or_handle or "").strip().rstrip("/")
    if not value:
        raise ValueError("Identifiant GitHub vide")

    if "/" in value or "." in value:
        match = re.search(r"github\.com/([A-Za-z0-9-]+)", value)
        if not match:
            raise ValueError(f"URL GitHub non reconnue : {url_or_handle}")
        return match.group(1)

    if not re.fullmatch(r"[A-Za-z0-9-]+", value):
        raise ValueError(f"Pseudo GitHub invalide : {url_or_handle}")
    return value


class GitHubClient:
    """Accès minimal à l'API REST. Le token est optionnel mais relève le quota."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_repos(self, username: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{API_ROOT}/users/{username}/repos",
                params={"per_page": 100, "sort": "pushed"},
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_readme(self, username: str, repo: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{API_ROOT}/repos/{username}/{repo}/readme",
                headers={**self._headers(), "Accept": "application/vnd.github.raw"},
            )
            if response.status_code == 200:
                return response.text
        return None


async def collect_github(url_or_handle: str, client=None) -> Dict[str, Any]:
    """Rend un payload de source prêt à être rangé dans `sources.github`."""
    username = parse_github_username(url_or_handle)
    client = client or GitHubClient()

    repos = await client.get_repos(username)
    own = [
        repo
        for repo in repos
        if not repo.get("fork") and not repo.get("archived")
    ]
    own.sort(
        key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at", "")),
        reverse=True,
    )

    projects: List[Dict[str, Any]] = []
    languages: List[str] = []
    for repo in own[:MAX_REPOS]:
        description = repo.get("description") or ""
        if len(description) < 40:
            readme = await client.get_readme(username, repo["name"])
            if readme:
                body = re.sub(r"^#.*$", "", readme, flags=re.MULTILINE).strip()
                description = (description + " " + body[:README_CHARS]).strip()

        stack = list(repo.get("topics") or [])
        if repo.get("language"):
            stack.insert(0, repo["language"])
            languages.append(repo["language"])

        projects.append(
            {
                "name": repo["name"],
                "description": description,
                "stack": stack,
                "url": repo.get("html_url"),
                "context": "perso",
            }
        )

    payload: Dict[str, Any] = {
        "projects": projects,
        "experiences": [],  # GitHub ne documente pas d'emploi
        "contact": {"github": f"https://github.com/{username}"},
    }
    if languages:
        payload["skills"] = {"langages": list(dict.fromkeys(languages))}
    return payload
```

- [ ] **Step 4: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_collectors.py -q
```

Attendu : `0 failed`, avec les tests de site et de GitHub dans le même fichier.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/profile/collectors/github.py backend/tests/test_profile_collectors.py
git commit -m "feat: collecteur GitHub via API REST, forks exclus"
```

---

### Task 9: Endpoints par source, upload durci, boucle non bloquée

**Files:**
- Modify: `backend/app/routers/cover_letters.py`
- Modify: `backend/app/services/cv_parser.py`
- Modify: `backend/app/utils.py` (retirer `merge_profile_sources`)
- Delete: `backend/app/services/web_enricher.py`
- Test: `backend/tests/test_profile_endpoints.py`

**Interfaces:**
- Consomme : `build_profile_from_sources`, `collect_website`, `collect_github`, `validate_public_url`.
- Produit :
  - `POST /profile/candidate/sources/cv` (multipart, PDF)
  - `POST /profile/candidate/sources/github` (`{"url": "..."}`)
  - `POST /profile/candidate/sources/website` (`{"url": "..."}`)
  - `async def _store_source(db, user_id, name, payload) -> dict` — range la source, recalcule le profil dérivé, retourne le profil sérialisé.

**Règles de l'upload :** taille plafonnée à 10 Mo lue par blocs, signature `%PDF` vérifiée sur les premiers octets, extension forcée à `.pdf`, `UPLOAD_DIR` résolu en absolu depuis le fichier du module, fichier supprimé dans un `finally`. Le détail d'exception ne sort jamais vers le client.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_profile_endpoints.py` :

```python
import io

import pytest
from bson import ObjectId

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel
from main import app

USER_ID = "60c72b2f9b1d8b2bad7f1234"


@pytest.fixture
def profile_db(monkeypatch):
    """Base en mémoire pour la collection candidate_profile."""
    from unittest.mock import AsyncMock, MagicMock

    stored = {}

    async def find_one(_query):
        return dict(stored) if stored else None

    async def update_one(_filter, update, upsert=False):
        stored.update(update["$set"])
        stored.setdefault("_id", ObjectId())
        return MagicMock()

    collection = MagicMock()
    collection.find_one = AsyncMock(side_effect=find_one)
    collection.update_one = AsyncMock(side_effect=update_one)
    db = MagicMock()
    db.__getitem__.return_value = collection

    app.dependency_overrides[get_database] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: UserModel(
        id=USER_ID, username="tester", email="t@example.com", hashed_password="x"
    )
    yield stored
    app.dependency_overrides.clear()


def test_non_pdf_upload_is_rejected(client, profile_db):
    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("evil.pdf", io.BytesIO(b"MZ executable"), "application/pdf")},
    )
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


def test_oversized_upload_is_rejected(client, profile_db):
    payload = b"%PDF-1.7" + b"0" * (11 * 1024 * 1024)
    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(payload), "application/pdf")},
    )
    assert res.status_code == 413


def test_uploaded_file_is_deleted_after_parsing(client, profile_db, monkeypatch, tmp_path):
    import app.routers.cover_letters as router

    monkeypatch.setattr(router, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(router, "extract_text_from_pdf", lambda path: "texte du CV")

    async def fake_parse(_text):
        return {"headline": "Ingénieur Data", "experiences": []}

    monkeypatch.setattr(router, "parse_cv_with_llm", fake_parse)

    res = client.post(
        "/profile/candidate/sources/cv",
        files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.7 contenu"), "application/pdf")},
    )
    assert res.status_code == 200
    assert list(tmp_path.iterdir()) == []
    assert profile_db["sources"]["cv"]["headline"] == "Ingénieur Data"


def test_github_source_is_stored_and_profile_rebuilt(client, profile_db, monkeypatch):
    import app.routers.cover_letters as router

    async def fake_collect(url, client=None):
        return {"projects": [{"name": "WideDocs", "description": "Doc"}], "experiences": []}

    monkeypatch.setattr(router, "collect_github", fake_collect)
    res = client.post(
        "/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"}
    )
    assert res.status_code == 200
    assert res.json()["projects"][0]["name"] == "WideDocs"
    assert "github" in profile_db["sources"]


def test_private_url_is_refused_on_website_source(client, profile_db):
    res = client.post(
        "/profile/candidate/sources/website",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert res.status_code == 400


def test_reimporting_a_source_is_idempotent(client, profile_db, monkeypatch):
    import app.routers.cover_letters as router

    async def fake_collect(url, client=None):
        return {"projects": [{"name": "WideDocs", "description": "Doc"}], "experiences": []}

    monkeypatch.setattr(router, "collect_github", fake_collect)
    first = client.post("/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"})
    second = client.post("/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"})
    assert first.json()["projects"] == second.json()["projects"]


def test_manual_edits_survive_a_later_import(client, profile_db, monkeypatch):
    import app.routers.cover_letters as router

    client.put("/profile/candidate", json={"headline": "Lead Data Engineer"})

    async def fake_collect(url, client=None):
        return {"headline": "Ingénieur Data", "projects": [], "experiences": []}

    monkeypatch.setattr(router, "collect_github", fake_collect)
    res = client.post("/profile/candidate/sources/github", json={"url": "https://github.com/Ekatche"})
    assert res.json()["headline"] == "Lead Data Engineer"
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_profile_endpoints.py -q
```

Attendu : 404 sur les nouvelles routes.

- [ ] **Step 3: Rendre `parse_cv_with_llm` asynchrone**

Dans `backend/app/services/cv_parser.py`, remplacer `completion` par `acompletion`, supprimer le `print` et la relance nue :

```python
import json
import logging
import re
from typing import Any, Dict

from litellm import acompletion

logger = logging.getLogger(__name__)


async def parse_cv_with_llm(cv_text: str, model: str = "gemini/gemini-3.8-flash") -> Dict[str, Any]:
    """Extrait les données structurées du texte d'un CV."""
    prompt = f"""..."""  # prompt existant, inchangé

    response = await acompletion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        drop_params=True,
    )
    content = response.choices[0].message.content.strip()
    content = re.sub(r"^```(?:json)?|```$", "", content, flags=re.MULTILINE).strip()
    return json.loads(content)
```

- [ ] **Step 4: Réécrire la section profil du routeur**

Dans `backend/app/routers/cover_letters.py` : remonter tous les imports en tête de fichier (les imports des lignes 111-115 et le `sys.path.insert` des lignes 201-206 disparaissent), puis remplacer `upload_and_parse_cv` et `enrich_candidate_profile` par :

```python
import asyncio
import os
from pathlib import Path
from uuid import uuid4

from app.models import CandidateProfile
from app.services.cv_parser import extract_text_from_pdf, parse_cv_with_llm
from app.services.profile.collectors.github import collect_github
from app.services.profile.collectors.website import collect_website
from app.services.profile.merge import build_profile_from_sources
from app.services.profile.urls import validate_public_url

UPLOAD_DIR = str(Path(__file__).resolve().parent.parent / "uploads")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PDF_MAGIC = b"%PDF"


async def _read_upload(file: UploadFile, magic: bytes) -> bytes:
    """Lit un upload en plafonnant la taille et en vérifiant la signature."""
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(1024 * 1024):
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Fichier trop volumineux (10 Mo maximum)")
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content.startswith(magic):
        raise HTTPException(status_code=400, detail="Le contenu du fichier n'est pas un PDF valide")
    return content


async def _store_source(db, user_id: str, name: str, payload: dict) -> dict:
    """Range une source, recalcule le profil dérivé, retourne le profil à jour."""
    existing = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)}) or {}
    sources = dict(existing.get("sources") or {})
    sources[name] = payload

    derived, conflicts = build_profile_from_sources(sources)
    document = {
        **derived,
        "sources": sources,
        "conflicts": conflicts,
        "user_id": ObjectId(user_id),
        "updated_at": datetime.now(timezone.utc),
    }
    # La validation refuse d'écrire une sortie de LLM malformée en base.
    CandidateProfile.model_validate({**document, "user_id": str(user_id)})

    await db["candidate_profile"].update_one(
        {"user_id": ObjectId(user_id)}, {"$set": document}, upsert=True
    )
    stored = await db["candidate_profile"].find_one({"user_id": ObjectId(user_id)})
    return serialize_mongodb_doc(stored)


@cover_letters_router.post("/profile/candidate/sources/cv")
async def import_cv_source(
    file: UploadFile = File(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    content = await _read_upload(file, PDF_MAGIC)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(UPLOAD_DIR, f"cv_{current_user.id}_{uuid4().hex}.pdf")

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        text = await asyncio.to_thread(extract_text_from_pdf, file_path)
        payload = await parse_cv_with_llm(text)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Échec du parsing de CV pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="Le CV n'a pas pu être analysé")
    finally:
        # Donnée personnelle : le PDF ne survit pas à la requête.
        if os.path.exists(file_path):
            os.remove(file_path)

    return await _store_source(db, str(current_user.id), "cv", payload)


@cover_letters_router.post("/profile/candidate/sources/github")
async def import_github_source(
    payload_in: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        payload = await collect_github(payload_in.get("url", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Échec de l'import GitHub pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="L'import GitHub a échoué")

    return await _store_source(db, str(current_user.id), "github", payload)


@cover_letters_router.post("/profile/candidate/sources/website")
async def import_website_source(
    payload_in: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    try:
        url = validate_public_url(payload_in.get("url", ""))
        payload = await collect_website(url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        logger.exception("Échec de l'import du site pour %s", current_user.id)
        raise HTTPException(status_code=502, detail="L'import du site a échoué")

    return await _store_source(db, str(current_user.id), "website", payload)
```

Et `update_candidate_profile` (PUT) écrit désormais dans `sources.manual`, ce qui rend les corrections manuelles permanentes :

```python
@cover_letters_router.put("/profile/candidate")
async def update_candidate_profile(
    profile_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    for key in ("_id", "id", "user_id", "sources", "conflicts", "updated_at"):
        profile_data.pop(key, None)
    return await _store_source(db, str(current_user.id), "manual", profile_data)
```

- [ ] **Step 5: Retirer l'ancienne fusion et l'ancien collecteur**

Supprimer `merge_profile_sources` de `backend/app/utils.py` (lignes 43-106) : elle n'a plus d'appelant, et la garder inviterait à s'en resservir.

Supprimer `backend/app/services/web_enricher.py`, remplacé par `collectors/website.py` et `collectors/github.py`. Il ouvrait un navigateur par URL, appelait `completion` synchrone dans une coroutine — donc sans parallélisme réel et en gelant la boucle — et crawlait LinkedIn en vain.

```bash
cd /Users/elielkatche/job-tracker && git rm backend/app/services/web_enricher.py
cd backend && rtk grep -rn "merge_profile_sources\|web_enricher\|enrich_profile_from_urls" app/ tests/
```

Attendu : aucune occurrence.

- [ ] **Step 6: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Attendu : `0 failed`. Un `ModuleNotFoundError` sur `web_enricher` signale un import oublié dans le routeur.

- [ ] **Step 7: Commit**

```bash
git add -A backend/app/routers/cover_letters.py backend/app/services/ backend/app/utils.py backend/tests/test_profile_endpoints.py
git commit -m "feat: un endpoint par source de profil, upload durci, plus de blocage de boucle"
```

---

### Task 10: Interface des trois sources et affichage des conflits

**Files:**
- Modify: `frontend/src/lib/api.ts:567-577`
- Modify: `frontend/src/components/profile/CandidateProfileSection.tsx`

**Interfaces:**
- Consomme : les trois endpoints de la Task 9.
- Produit : `coverLetterApi.importCv`, `.importGithub`, `.importWebsite`.

**Le lien LinkedIn quitte la zone d'enrichissement.** Il reste un champ de `contact`, éditable et affiché, mais aucun bouton ne le déclenche : le serveur ne va plus le chercher. Laisser un bouton qui rapporte un mur de cookies vaut moins que pas de bouton du tout.

- [ ] **Step 1: Remplacer les appels d'API**

Dans `frontend/src/lib/api.ts`, remplacer `uploadCV` et `enrichProfile`. Le `Content-Type: multipart/form-data` posé à la main disparaît : axios 1.8 le remplace lui-même par la valeur avec `boundary` quand le corps est un `FormData`, et l'écrire à la main n'ajoute qu'une fausse piste.

```ts
  importCv: async (file: File): Promise<CandidateProfile> => {
    const formData = new FormData();
    formData.append("file", file);
    return fetchApi<CandidateProfile>("/profile/candidate/sources/cv", "POST", formData);
  },
  importGithub: async (url: string): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate/sources/github", "POST", { url }),
  importWebsite: async (url: string): Promise<CandidateProfile> =>
    fetchApi<CandidateProfile>("/profile/candidate/sources/website", "POST", { url }),
```

- [ ] **Step 2: Un état d'import par source**

Dans `CandidateProfileSection.tsx`, remplacer `isUploading` / `isEnriching` par un état indexé, pour qu'un import GitHub n'affiche pas un spinner sur le bouton CV :

```tsx
type SourceName = "cv" | "github" | "website";

const [busySource, setBusySource] = useState<SourceName | null>(null);

const runImport = async (source: SourceName, call: () => Promise<CandidateProfile>) => {
  setBusySource(source);
  setSaveError(null);
  try {
    const updated = await call();
    setProfile(updated);
    populateForm(updated);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 4000);
  } catch (err: unknown) {
    setSaveError(err instanceof Error ? err.message : `Échec de l'import ${source}`);
  } finally {
    setBusySource(null);
  }
};
```

Trois boutons appellent `runImport`, chacun désactivé quand `busySource !== null` : « Importer mon CV », « Importer depuis GitHub », « Importer depuis mon site ». Les deux anciens boutons — « Importer mon CV » et « Enrichir depuis mes liens avec l'IA » — disparaissent : le second agrégeait les trois liens en un seul appel, ce qui empêchait de savoir laquelle des sources avait échoué.

Le champ LinkedIn reste dans le bloc contact, avec une mention courte à côté : « affiché sur votre profil, non importé ». Sans cette phrase, l'absence de bouton passe pour un oubli.

- [ ] **Step 3: Afficher les conflits et la provenance**

Sous la liste des expériences, rendre `profile.conflicts` visible — c'est la garantie de la spec : signaler sans trancher.

```tsx
{profile?.conflicts && profile.conflicts.length > 0 && (
  <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-200">
    <p className="font-medium mb-1">
      Divergences entre vos sources ({profile.conflicts.length})
    </p>
    <ul className="space-y-1">
      {profile.conflicts.map((c, i) => (
        <li key={i}>
          {c.company} — {c.field} : « {String(c.kept)} » retenu depuis {c.kept_source},
          « {String(c.discarded)} » écarté depuis {c.discarded_source}.
        </li>
      ))}
    </ul>
  </div>
)}
```

Et sur chaque expérience, afficher `sources` en petites étiquettes : l'utilisateur voit d'où vient chaque ligne de son profil.

- [ ] **Step 4: Vérifier la compilation et le parcours**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Attendu : aucune erreur. Puis, application lancée : importer le CV, importer `https://github.com/Ekatche`, importer `https://www.elielkatche.me`, et vérifier qu'une seule entrée Agence Nile mauricienne apparaît, que `WideDocs` et `Sentinel` coexistent, et qu'une correction manuelle du `headline` survit à un réimport.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/profile/CandidateProfileSection.tsx
git commit -m "feat: import des trois sources de profil et affichage des conflits"
```

---

# Phase 3 — Génération de lettre

Ces tâches dépendent d'un profil propre : un rédacteur nourri de doublons produit une lettre qui se répète.

### Task 11: Prompts chargés depuis les fichiers, profil en dur retiré

**Files:**
- Modify: `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
- Modify: `backend/app/llm/prompts/cover_letter/*.md`
- Test: `backend/tests/test_cover_letter_prompts.py`

**Interfaces:**
- Produit : `def load_prompt(name: str, **context) -> str` dans `cover_letter_crew.py`.

**Le défaut corrigé :** les quatre fichiers de prompts existent, `test_cover_letter_prompts.py` les valide au vert, et aucune ligne de code ne les charge. Les prompts réellement envoyés sont des f-strings, et celle du rédacteur contient « Tu es Eliel Katche » plus trois noms d'entreprise en dur. Cela casse le multi-utilisateur et contourne l'anti-hallucination : le rédacteur reçoit des noms d'employeur qui ne viennent pas du JSON de l'analyste.

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `backend/tests/test_cover_letter_prompts.py` :

```python
import re

import cover_letter_crew


def test_writer_prompt_is_loaded_from_file():
    rendered = cover_letter_crew.load_prompt(
        "02_style",
        company_name="Acme",
        missions="['Pipelines']",
        experiences="[]",
        stacks="Python",
        projects="",
    )
    assert "Acme" in rendered
    assert "{company_name}" not in rendered


def test_no_identity_is_hardcoded_in_the_module():
    """Aucun nom de personne ou d'employeur ne doit vivre dans le code."""
    source = open(cover_letter_crew.__file__, encoding="utf-8").read()
    for forbidden in ("Eliel Katche", "Agence Nile", "Centre Léon Bérard", "Bimedoc"):
        assert forbidden not in source, f"{forbidden} codé en dur dans le crew"


def test_prompt_files_have_no_identity_either():
    for name in ("01_fond", "02_style", "03_critique", "04_revision"):
        content = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        assert "Eliel Katche" not in content
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_cover_letter_prompts.py -q
```

Attendu : FAIL — `load_prompt` n'existe pas, et « Eliel Katche » est présent dans le module.

- [ ] **Step 3: Implémenter le chargeur**

Dans `cover_letter_crew.py` :

```python
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "app" / "llm" / "prompts" / "cover_letter"


def load_prompt(name: str, **context: object) -> str:
    """Charge un prompt depuis son fichier et y substitue le contexte.

    Une seule source de vérité pour les prompts : le fichier. Le code ne
    reformule pas les règles, il les interpole.
    """
    template = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return template.format(**context)
```

- [ ] **Step 4: Déplacer les prompts dans les fichiers**

`02_style.md` reçoit le prompt du rédacteur, avec des emplacements nommés et **aucune identité** : le nom du candidat, les employeurs et la signature viennent de `analyst_json`. Le squelette :

```markdown
Tu rédiges une lettre de motivation pour {candidate_name}, {candidate_headline},
qui postule chez {company_name}.

Écriture sobre, directe, factuelle. Aucune formule commerciale.

RÈGLES DE FORME
1. Longueur : entre {min_words} et {max_words} mots.
2. Trois ou quatre paragraphes séparés par une ligne vide.
...

FAITS AUTORISÉS — n'en cite aucun autre
Missions visées : {missions}
Expériences : {experiences}
Technologies : {stacks}
Projets : {projects}

Signe « {candidate_name} ».
```

`_call_writer` devient :

```python
def _call_writer(analyst_json: Dict[str, Any], company_name: str) -> str:
    llm = get_letter_llm("writer")
    prompt = load_prompt(
        "02_style",
        candidate_name=analyst_json.get("candidate_name", ""),
        candidate_headline=analyst_json.get("candidate_headline", ""),
        company_name=company_name,
        min_words=MIN_WORDS,
        max_words=MAX_WORDS,
        missions=json.dumps(analyst_json.get("missions", []), ensure_ascii=False),
        experiences=json.dumps(analyst_json.get("selected_experiences", []), ensure_ascii=False),
        stacks=", ".join(analyst_json.get("stacks", [])[:15]),
        projects=", ".join(analyst_json.get("projects", [])),
    )
    ...
```

Et `_call_analyst` ajoute `candidate_name` et `candidate_headline` à sa sortie, tirés de `candidate_profile` — le rédacteur ne reçoit toujours que le JSON de l'analyste.

- [ ] **Step 5: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
```

Attendu : `0 failed`.

- [ ] **Step 6: Commit**

```bash
git add backend/job_trackers/src/job_trackers/cover_letter_crew.py backend/app/llm/prompts/cover_letter/ backend/tests/test_cover_letter_prompts.py
git commit -m "refactor: prompts chargés depuis les fichiers, identité hors du code"
```

---

### Task 12: Garde-fous alignés sur le prompt et garde-fou d'entités réel

**Files:**
- Modify: `backend/app/services/letter_guards.py`
- Modify: `backend/app/llm/prompts/cover_letter/02_style.md`
- Test: `backend/tests/test_letter_guards.py`

**Interfaces:**
- Produit : `LETTER_RULES` — dictionnaire unique consommé par les garde-fous **et** injecté dans le prompt.

**Les défauts corrigés :** trois bornes de longueur coexistent (250-400 dans les garde-fous, 270-330 dans le prompt du rédacteur, 260-330 dans celui du réviseur) ; `CAPPED_REPETITIONS` plafonne « je suis », « je souhaite », « je serais » sans que le rédacteur en soit informé, ce qui déclenche une révision presque systématique et double le coût ; le garde-fou d'entités compare à `["google","meta","amazon","apple","microsoft","netflix"]` en dur, donc une entreprise inventée passe.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
from app.services.letter_guards import LETTER_RULES, evaluate_letter_guards

ANALYST = {
    "stacks": ["Python", "Azure"],
    "companies": ["Agence Nile", "Bimedoc"],
}


def test_invented_company_is_flagged():
    letter = (
        "Madame, Monsieur,\n\nJ'ai conduit des projets chez Initech avant de rejoindre "
        "Agence Nile.\n\nMa méthode repose sur Python.\n\nCordialement"
    )
    report = evaluate_letter_guards(letter, "offre", ANALYST)
    assert any("Initech" in v for v in report.violations)


def test_known_company_is_not_flagged():
    letter = (
        "Madame, Monsieur,\n\nChez Agence Nile, j'ai industrialisé des flux.\n\n"
        "Ma méthode repose sur Python.\n\nCordialement"
    )
    report = evaluate_letter_guards(letter, "offre", ANALYST)
    assert not any("Entité non autorisée" in v for v in report.violations)


def test_word_bounds_come_from_a_single_source():
    assert LETTER_RULES["min_words"] == 250
    assert LETTER_RULES["max_words"] == 400
    assert "je suis" in LETTER_RULES["capped_repetitions"]
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_letter_guards.py -q
```

Attendu : FAIL — `LETTER_RULES` n'existe pas, et « Initech » n'est pas détecté.

- [ ] **Step 3: Implémenter**

Regrouper les seuils dans `LETTER_RULES` et remplacer le garde-fou n°12 par une détection de majuscules internes comparée aux entités connues :

```python
LETTER_RULES = {
    "min_words": 250,
    "max_words": 400,
    "min_paragraphs": 3,
    "max_paragraphs": 5,
    "max_head_connectors": 1,
    "max_semicolons": 1,
    "capped_repetitions": CAPPED_REPETITIONS,
    "banned_lexicon": BANNED_LEXICON,
    "banned_openings": BANNED_OPENINGS,
    "generic_compliments": GENERIC_COMPLIMENTS,
}

_ENTITY_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9&.\-]{2,}(?:\s+[A-Z][A-Za-z0-9&.\-]{2,})?")
_SENTENCE_START_STOPWORDS = {"Madame", "Monsieur", "Cordialement", "Je", "Mon", "Ma", "Mes", "Votre", "Vos", "Chez", "Au", "Le", "La", "Les"}


def _check_entities(letter_text: str, analyst_data: Dict[str, Any]) -> List[str]:
    """Toute entité nommée doit venir des faits fournis à l'analyste."""
    allowed = {
        _normalize_entity(value)
        for value in (
            list(analyst_data.get("companies") or [])
            + list(analyst_data.get("stacks") or [])
            + list(analyst_data.get("projects") or [])
            + [analyst_data.get("company_name") or ""]
        )
        if value
    }
    violations: List[str] = []
    for candidate in set(_ENTITY_PATTERN.findall(letter_text)):
        if candidate in _SENTENCE_START_STOPWORDS:
            continue
        if _normalize_entity(candidate) in allowed:
            continue
        violations.append(f"Entité non autorisée citée dans la lettre : '{candidate}'")
    return violations
```

`_normalize_entity` réutilise `company_slug` de la Task 3 — même règle de comparaison partout. Le nom de l'entreprise destinataire est ajouté aux entités autorisées, sinon la lettre est bloquée pour avoir cité son destinataire.

Puis injecter `LETTER_RULES` dans `02_style.md` via `load_prompt`, y compris la liste complète de `capped_repetitions` : le rédacteur doit connaître toutes les règles sur lesquelles il sera jugé.

- [ ] **Step 4: Vérifier, et mesurer le gain**

```bash
cd backend && .venv/bin/python -m pytest tests/test_letter_guards.py tests/ -q
```

Attendu : `0 failed`. Puis, en conditions réelles, générer trois lettres et relever `revised` dans `versions[]` : la part de lettres révisées doit baisser, puisque le rédacteur connaît désormais les règles qui le bloquaient.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/letter_guards.py backend/app/llm/prompts/cover_letter/02_style.md backend/tests/test_letter_guards.py
git commit -m "fix: seuils de lettre en source unique et garde-fou d'entités réel"
```

---

### Task 13: Historique des lettres, échecs non bloquants, configuration LLM

**Files:**
- Modify: `backend/app/routers/applications.py:58-159`
- Modify: `backend/app/routers/cover_letters.py:29-50`
- Modify: `backend/job_trackers/src/job_trackers/letter_llm.py`
- Modify: `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
- Modify: `docker-compose.yml:33,157`
- Test: `backend/tests/test_cover_letter_trigger.py`, `backend/tests/test_letter_llm.py`

**Interfaces:**
- Produit : `async def _append_letter_version(db, letter_id, version: dict) -> None`.

**Les défauts corrigés :** un document `failed` bloque définitivement toute génération ultérieure, parce que le contrôle d'idempotence retourne dès qu'un document existe ; `regenerate` supprime le document, donc perd l'historique et les versions éditées à la main alors que la décision de spec était « éditable + régénération, historisé » ; les clés API ont un défaut factice (`dummy_gemini_key_for_test`) qui neutralise le contrôle de clé manquante ; `ROLE_TEMPERATURES` n'atteint jamais `completion`, qui reçoit des valeurs en dur divergentes ; `litellm.drop_params = True` en global mute tout le processus ; `MISTRAL_API_KEY` manque dans `docker-compose.yml`.

- [ ] **Step 1: Écrire les tests qui échouent**

```python
import pytest

from app.routers.applications import _generate_cover_letter_bg


@pytest.mark.asyncio
async def test_failed_letter_does_not_block_a_later_run(monkeypatch):
    """Profil complété après un échec : la génération doit repartir."""
    # doc existant en status failed, pipeline mocké qui rend une lettre
    ...
    assert pipeline_called is True


@pytest.mark.asyncio
async def test_regenerate_appends_a_version_instead_of_deleting(client, ...):
    """L'historique et les versions éditées survivent à une régénération."""
    ...
    assert [v["n"] for v in stored["versions"]] == [1, 2]


def test_missing_api_key_raises_instead_of_using_a_placeholder(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("LETTER_MODEL_CRITIC", "gemini/gemini-3.8-flash")
    with pytest.raises(ValueError, match="Missing API key"):
        get_letter_llm("critic")


def test_role_temperature_reaches_the_completion_call(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return _fake_response("texte")

    monkeypatch.setattr(cover_letter_crew, "completion", fake_completion)
    cover_letter_crew._call_writer({"missions": []}, "Acme")
    assert captured["temperature"] == ROLE_TEMPERATURES["writer"]
    assert captured["drop_params"] is True


def test_module_does_not_mutate_litellm_globally():
    source = open(cover_letter_crew.__file__, encoding="utf-8").read()
    assert "litellm.drop_params = True" not in source
```

- [ ] **Step 2: Lancer, vérifier l'échec**

```bash
cd backend && .venv/bin/python -m pytest tests/test_cover_letter_trigger.py tests/test_letter_llm.py -q
```

- [ ] **Step 3: Idempotence qui ignore les échecs**

Dans `applications.py`, remplacer le contrôle de la ligne 62 :

```python
        existing = await db["cover_letters"].find_one(
            {"application_id": ObjectId(application_id), "status": {"$ne": "failed"}}
        )
        if existing:
            logger.info("[cover_letter_bg] Lettre déjà présente pour %s", application_id)
            return

        # Un échec antérieur ne doit pas geler la candidature : on le remplace.
        await db["cover_letters"].delete_many(
            {"application_id": ObjectId(application_id), "status": "failed"}
        )
```

Et l'insertion du document `pending` doit précéder tout travail susceptible d'échouer, pour que le `except` ait toujours un document à marquer `failed`.

- [ ] **Step 4: Régénération qui empile**

Dans `cover_letters.py`, remplacer le `delete_one` de la ligne 43 par une remise en `pending` qui conserve `versions`, et faire écrire au travail de fond une nouvelle version numérotée :

```python
    await db["cover_letters"].update_one(
        {"application_id": ObjectId(application_id)},
        {"$set": {"status": "pending", "error": None, "updated_at": datetime.now(timezone.utc)}},
    )
```

```python
async def _append_letter_version(db, letter_id, version: dict) -> None:
    """Ajoute une version numérotée sans jamais écraser les précédentes."""
    letter = await db["cover_letters"].find_one({"_id": letter_id})
    version["n"] = len(letter.get("versions", [])) + 1
    await db["cover_letters"].update_one(
        {"_id": letter_id},
        {
            "$set": {
                "status": "ready",
                "current_version": version["n"],
                "updated_at": datetime.now(timezone.utc),
            },
            "$push": {"versions": version},
        },
    )
```

Ajouter `prompt_version` à l'entrée de version : sans lui, impossible de savoir quel prompt a produit quelle lettre.

- [ ] **Step 5: Configuration LLM**

Dans `letter_llm.py`, supprimer les défauts factices et faire porter la température par l'appel :

```python
    api_key = os.getenv(API_KEY_ENV[provider])
    if not api_key:
        raise ValueError(
            f"Clé API absente pour le fournisseur '{provider}' requis par le rôle '{role}'. "
            f"Renseignez {API_KEY_ENV[provider]} dans .env."
        )
```

Les tests qui avaient besoin d'une clé la posent eux-mêmes par `monkeypatch.setenv`. Dans `cover_letter_crew.py`, supprimer `litellm.drop_params = True` du niveau module, passer `drop_params=True` et `temperature=ROLE_TEMPERATURES[role]` à chaque `completion`, et activer `response_format={"type": "json_object"}` pour tous les fournisseurs — le test de la substring `"gpt" in llm.model` privait Gemini et Mistral du mode JSON alors qu'ils le prennent en charge.

- [ ] **Step 6: Clé Mistral dans les conteneurs**

Dans `docker-compose.yml`, ajouter `- MISTRAL_API_KEY=${MISTRAL_API_KEY}` à côté de `GEMINI_API_KEY`, lignes 33 (backend) et 157 (worker). Sans cela, le conteneur ne voit pas la clé que l'utilisateur a ajoutée à `.env`.

- [ ] **Step 7: Vérifier**

```bash
cd backend && .venv/bin/python -m pytest tests/ -q
cd /Users/elielkatche/job-tracker && docker compose config | rtk grep -n MISTRAL_API_KEY
```

Attendu : suite au vert, et `MISTRAL_API_KEY` présent deux fois dans la configuration résolue.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/applications.py backend/app/routers/cover_letters.py backend/job_trackers/src/job_trackers/ docker-compose.yml backend/tests/
git commit -m "fix: historique des lettres, échecs non bloquants, configuration LLM"
```

---

### Task 14: Choix du rédacteur par bake-off

**Files:**
- Create: `backend/scripts/letter_bakeoff.py`
- Modify: `backend/job_trackers/src/job_trackers/letter_llm.py` (`DEFAULT_MODELS["writer"]`)

**Interface :** script hors application, lancé à la main, qui écrit son rapport dans `docs/micro/`.

**Pourquoi en dernier :** le bake-off ne vaut quelque chose qu'une fois le profil propre et les prompts alignés — sinon il mesure les défauts de la chaîne, pas les modèles. Aujourd'hui `DEFAULT_MODELS["writer"]` vaut `openai/gpt-5.6-sol`, à 8 $ en entrée et 40 $ en sortie par million de jetons, soit le plus cher des trois candidats, retenu sans mesure alors que la décision de spec était « départagé à l'implémentation ».

- [ ] **Step 1: Écrire le script**

Un `offer_analyst` exécuté une seule fois, sa sortie réutilisée pour les trois rédacteurs afin que les lettres soient comparables. Candidats : `openai/gpt-5.6-sol`, `mistral/mistral-large-3`, `gemini/gemini-3.8-flash`. Pour chaque lettre : nombre de violations de garde-fous, verdict du critique, nombre de jetons, coût estimé, durée. Sortie anonymisée pour permettre un classement à l'aveugle.

- [ ] **Step 2: Lancer sur trois offres réelles**

```bash
cd backend && .venv/bin/python scripts/letter_bakeoff.py --offers 3 --out ../docs/micro/20260914-letter-bakeoff/
```

- [ ] **Step 3: Classer à l'aveugle, puis décider**

Lire les neuf lettres sans voir le modèle, les classer, puis lever l'anonymat et croiser avec le nombre de violations et le coût. Le modèle retenu devient `DEFAULT_MODELS["writer"]`, et `validate_cross_provider` fixe le critique en conséquence.

- [ ] **Step 4: Commit**

```bash
git add backend/scripts/letter_bakeoff.py backend/job_trackers/src/job_trackers/letter_llm.py docs/micro/20260914-letter-bakeoff/
git commit -m "feat: bake-off du rédacteur et choix de modèle mesuré"
```

---

## Ordre et dépendances

```
Phase 0  T1 ── T2                       suite au vert, barre de référence
            │
Phase 1     └─ T3 ── T4 ── T5           normalisation, fusion pure, modèle
                         │
Phase 2                  ├─ T6 ── T7    anti-SSRF puis site personnel
                         ├─────── T8    GitHub (indépendant de T7)
                         └─ T9 ── T10   endpoints puis interface
                                 │
Phase 3                          └─ T11 ── T12 ── T13 ── T14
```

T7 et T8 ne dépendent que de T6 : deux collecteurs parallélisables. T9 attend les deux. La phase 3 ne dépend de la phase 2 que par T9, mais la faire après garantit que le bake-off de T14 mesure des modèles et non des doublons de profil.

## Auto-revue

**Couverture de la demande** — « prendre des infos de LinkedIn, GitHub et d'un potentiel website » : T8 (GitHub par API), T7 (site personnel, multi-pages via sitemap), T9 (un endpoint par source), T10 (interface). LinkedIn est écarté sur demande après la preuve du mur de consentement ; son lien reste un champ de contact non crawlé, et `sources` reste ouvert si la voie de l'archive officielle devient souhaitable. « Un CV ne peut pas tout contenir » : T4 ajoute les expériences absentes du CV au lieu de les écraser, vérifié par `test_experience_absent_from_cv_is_added`.

**Couverture de la revue du 2026-09-14** — les sept bloquants : T1 (imports, tests étanches), T2 (critique croisé), T3 et T4 (duplication, perte de données, conflits), T13 (échec bloquant, historique), T11 (profil en dur), T9 (boucle d'événements), T1 (import fitz). Les quatre points de sécurité : T6 (SSRF), T9 (upload, fuite d'erreurs), T13 (clé factice). Les écarts de spec : T11 (prompts), T12 (entités, seuils), T14 (bake-off), T13 (températures, `drop_params`, `docker-compose`), T5 (validation Pydantic).

**Cohérence de nommage** — `build_profile_from_sources` rend `(profil, conflits)` partout ; `SOURCE_PRIORITY` est la seule autorité sur l'ordre ; `company_slug` sert à la fois de clé de fusion (T4) et de comparaison d'entités (T12) ; `validate_public_url` est appelée dans T7 et dans T9.

**Reste hors périmètre, à traiter séparément** — `summarize_chunks` ([backend/app/llm/utils.py:179](../../../backend/app/llm/utils.py#L179)) a encore OpenAI en dur ; `app/llm/utils.py:17` émet `DeprecationWarning: There is no current event loop` ; aucun index unique sur `cover_letters.application_id`, ce qui laisse une fenêtre de concurrence entre une régénération et un changement de statut simultanés.
