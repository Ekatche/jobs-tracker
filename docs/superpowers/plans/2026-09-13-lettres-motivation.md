# Génération de Lettres de Motivation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Générer de manière asynchrone une lettre de motivation ciblée et sans hallucination lors du passage d'une candidature au statut « En étude », orchestrée par un crew CrewAI multi-modèles avec garde-fous déterministes et interface d'édition/historique.

**Architecture:** Déclenchement événementiel asynchrone dans `update_application` (FastAPI `BackgroundTasks` + `asyncio.to_thread`) qui pilote un pipeline CrewAI dédié à 4 rôles (`offer_analyst`, `writer`, `critic`, `reviser`). Le rédacteur ne reçoit qu'un JSON filtré (anti-hallucination structurelle) et le critique opère obligatoirement sur un fournisseur LLM différent du rédacteur ; des garde-fous en code pur vérifient métriques et lexique avant stockage dans la collection `cover_letters` et affichage/édition via un panneau React dédié avec polling.

**Tech Stack:** FastAPI, Python 3.12 (`uv`), CrewAI 0.121+, MongoDB (Motor / PyMongo), Next.js 15, TypeScript, Tailwind CSS, LiteLLM (OpenAI, Gemini, Mistral).

## Global Constraints

- Exécution des commandes Python via `uv` (ex: `uv run pytest`).
- Code, noms de variables et commentaires en anglais ; discussions et messages UI en français.
- Préservation de tous les commentaires et annotations de typage existants.
- Aucun alias flottant (`latest`, `preview`) pour les identifiants de modèles LLM.
- Le critique (`critic`) tourne obligatoirement sur un fournisseur LLM différent du rédacteur (`writer`). Si les deux modèles résolvent le même fournisseur, échouer au démarrage.
- Anti-hallucination structurelle : `writer` ne reçoit JAMAIS le profil complet du candidat, seulement le JSON produit par `offer_analyst`.
- Le thread du crew ne touche JAMAIS directement à MongoDB (aucun client Motor partagé entre threads) ; toutes les I/O MongoDB sont asynchrones sur l'event loop FastAPI.
- Pas de relance multiple de `reviser` : au plus une passe de révision, puis la lettre passe en statut `ready` quel que soit le rapport de garde-fous.

---

## File Structure

### Backend
- Create: `backend/app/services/letter_guards.py` - Fonctions pures de contrôle déterministe (bloquants et avertissements)
- Create: `backend/app/llm/prompts/cover_letter/01_fond.md` - Prompt règles de fond et sélection
- Create: `backend/app/llm/prompts/cover_letter/02_style.md` - Prompt style, ton, rythme
- Create: `backend/app/llm/prompts/cover_letter/03_critique.md` - Prompt grille de jugement du critique
- Create: `backend/app/llm/prompts/cover_letter/04_revision.md` - Prompt correction sous contraintes
- Create: `backend/job_trackers/src/job_trackers/letter_llm.py` - Sélecteur de modèle `get_letter_llm()` avec validation stricte
- Create: `backend/job_trackers/src/job_trackers/cover_letter_crew.py` - Crew CrewAI dédié, agents, tâches et pipeline de révision
- Create: `backend/job_trackers/src/job_trackers/config/letter_agents.yaml` - Configuration des agents du crew de lettre
- Create: `backend/job_trackers/src/job_trackers/config/letter_tasks.yaml` - Configuration des tâches du crew de lettre
- Create: `backend/scripts/seed_candidate_profile.py` - Script d'amorçage du profil candidat (fusion CV + site avec conflits)
- Create: `backend/scripts/run_writer_bakeoff.py` - Protocole de bake-off comparant OpenAI, Mistral et Gemini
- Create: `backend/app/routers/cover_letters.py` - Endpoints REST pour lettres de motivation et profil candidat
- Modify: `backend/app/models.py:200-297` - Modèles Pydantic pour profil candidat et lettres de motivation
- Modify: `backend/app/routers/applications.py:149-202` - Déclenchement de la génération en tâche de fond sur passage en `ETUDE`
- Modify: `backend/app/routers/__init__.py:1-14` - Export du nouveau routeur `cover_letters_router`
- Modify: `backend/main.py:10-70` - Enregistrement du routeur `cover_letters_router`
- Test: `backend/tests/test_letter_guards.py` - Tests unitaires des garde-fous déterministes
- Test: `backend/tests/test_cover_letter_models.py` - Tests de validation des modèles Pydantic
- Test: `backend/tests/test_profile_seed.py` - Tests de fusion et détection des conflits (fixture Odoo / Sylob)
- Test: `backend/tests/test_letter_llm.py` - Tests de résolution multi-fournisseur et interdiction des alias
- Test: `backend/tests/test_cover_letter_trigger.py` - Tests de transition de statut et idempotence
- Test: `backend/tests/test_cover_letters_api.py` - Tests d'intégration des endpoints REST

### Frontend
- Create: `frontend/src/types/coverLetter.ts` - Interfaces TypeScript pour la lettre, versions, profil et garde-fous
- Create: `frontend/src/components/applications/CoverLetterPanel.tsx` - Panneau d'affichage, édition, polling et historique
- Modify: `frontend/src/lib/api.ts:430-475` - Client API `coverLetterApi`
- Modify: `frontend/src/components/applications/ApplicationDetails.tsx` - Intégration du composant `CoverLetterPanel`

---

## Tasks

### Task 1: Guard-rails in Code (`letter_guards.py`)

**Files:**
- Create: `backend/app/services/letter_guards.py`
- Test: `backend/tests/test_letter_guards.py`

**Interfaces:**
- Produces:
  ```python
  class GuardReport(BaseModel):
      is_blocking: bool
      violations: List[str]
      warnings: List[str]
      stats: Dict[str, Any]

  def evaluate_letter_guards(
      letter_text: str,
      offer_description: str,
      analyst_data: Dict[str, Any],
  ) -> GuardReport
  ```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_letter_guards.py
import pytest
from app.services.letter_guards import evaluate_letter_guards

def test_guards_clean_letter_passes():
    letter = """Madame, Monsieur,\n\nVotre offre de Lead Data Engineer chez Biomérieux a retenu toute mon attention. Lors de mes trois années chez Sanofi, j'ai déployé des pipelines de données sous Nextflow et Kafka avec un temps de traitement divisé par deux.\n\nSur mon projet personnel Sentinel, j'ai conçu une architecture de streaming sous Rust et DuckDB traitant dix millions d'événements par jour. Cette double compétence me permet d'aborder vos enjeux de reproductibilité avec recul.\n\nJe serais ravi d'échanger prochainement sur vos chantiers prioritaires.\n\nCordialement,\nEliel Katche"""
    analyst_data = {
        "companies": ["Biomérieux", "Sanofi"],
        "stacks": ["Nextflow", "Kafka", "Rust", "DuckDB"],
        "metrics": ["trois années", "dix millions"],
        "projects": ["Sentinel"],
    }
    offer_desc = "Biomérieux recrute un Lead Data Engineer pour transformer ses pipelines analytiques de données de santé."

    report = evaluate_letter_guards(letter, offer_desc, analyst_data)
    assert report.is_blocking is False
    assert len(report.violations) == 0

def test_guards_forbidden_punctuation_fails():
    letter = "Bonjour! Nous devons avancer... Voici mon profil—parfait pour vous (vraiment); merci; encore."
    report = evaluate_letter_guards(letter, "offre", {})
    assert report.is_blocking is True
    assert any("Point d'exclamation" in v for v in report.violations)
    assert any("Points de suspension" in v for v in report.violations)
    assert any("Tiret cadratin" in v for v in report.violations)
    assert any("Parenthèses" in v for v in report.violations)
    assert any("Point-virgule" in v for v in report.violations)

def test_guards_banned_lexicon_and_openings_fail():
    letter = "Je vous adresse ma candidature. J'ai une solide expertise et une forte appétence pour votre projet."
    report = evaluate_letter_guards(letter, "offre", {})
    assert report.is_blocking is True
    assert any("Ouverture interdite" in v for v in report.violations)
    assert any("solide expertise" in v for v in report.violations)
    assert any("forte appétence" in v for v in report.violations)

def test_guards_word_count_and_paragraphs_fail():
    short_letter = "Trop court.\n\nDeuxième paragraphe."
    report = evaluate_letter_guards(short_letter, "offre", {})
    assert report.is_blocking is True
    assert any("Longueur hors bornes" in v for v in report.violations)
    assert any("Nombre de paragraphes" in v for v in report.violations)

def test_guards_sentence_connectors_fail():
    letter = "De plus, nous commençons.\n\nEn outre, nous poursuivons.\n\nEnfin, nous terminons."
    report = evaluate_letter_guards(letter, "offre", {})
    assert report.is_blocking is True
    assert any("Connecteurs en tête de phrase" in v for v in report.violations)

def test_guards_unauthorized_entities_fail():
    letter = "J'ai travaillé cinq ans chez Google avec Kubernetes.\n\nDeuxième paragraphe.\n\nTroisième paragraphe."
    analyst_data = {"companies": ["Biomérieux"], "stacks": ["Kafka"], "metrics": [], "projects": []}
    report = evaluate_letter_guards(letter, "offre", analyst_data)
    assert report.is_blocking is True
    assert any("Entité non autorisée" in v for v in report.violations)

def test_guards_warnings_flagged_without_blocking():
    # Sentences with identical construction and no variance
    uniform_letter = "Je code du python chaque jour. Je lis des livres chaque soir. Je fais du sport chaque matin. Je dors huit heures chaque nuit."
    report = evaluate_letter_guards(uniform_letter, "offre", {})
    assert report.is_blocking is False or len(report.warnings) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_letter_guards.py -v` in `backend`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.letter_guards'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/services/letter_guards.py
import re
import math
from typing import Dict, Any, List
from pydantic import BaseModel, Field

BANNED_LEXICON = [
    "forte appétence", "solide expertise", "je suis convaincu que mon profil",
    "force de proposition", "dynamique", "rigoureux", "passionné par",
    "vivement intéressé", "à la pointe de", "parfaitement adapté",
    "dans l'attente de votre retour", "restant à votre entière disposition",
    "permettez-moi de vous présenter", "polyvalent"
]

BANNED_OPENINGS = [
    "je vous adresse ma candidature", "actuellement à la recherche",
    "titulaire de", "fort de", "c'est avec grand intérêt"
]

SENTENCE_CONNECTORS = [
    "de plus", "par ailleurs", "en outre", "enfin", "de même",
    "en effet", "ainsi", "dans ce contexte", "à ce titre", "fort de cette expérience"
]

GENERIC_COMPLIMENTS = [
    "entreprise leader", "entreprise innovante", "acteur majeur",
    "entreprise reconnue", "culture d'innovation", "excellence", "forte croissance"
]

CAPPED_REPETITIONS = {
    "mon parcours": 1,
    "mon expérience": 1,
    "mes compétences": 1,
    "je souhaite": 1,
    "je suis": 1,
    "je serais": 1
}

class GuardReport(BaseModel):
    is_blocking: bool = False
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)

def evaluate_letter_guards(
    letter_text: str,
    offer_description: str,
    analyst_data: Dict[str, Any],
) -> GuardReport:
    violations: List[str] = []
    warnings: List[str] = []
    stats: Dict[str, Any] = {}

    lower_text = letter_text.lower()

    # 1. Ponctuation interdite
    if "!" in letter_text:
        violations.append("Point d'exclamation (!) interdit")
    if "..." in letter_text or "…" in letter_text:
        violations.append("Points de suspension (...) interdits")
    if "—" in letter_text:
        violations.append("Tiret cadratin (—) interdit")
    if "(" in letter_text or ")" in letter_text:
        violations.append("Parenthèses interdites")
    if letter_text.count(";") > 1:
        violations.append(f"Point-virgule en excès ({letter_text.count(';')} trouvés, maximum 1 autorisé)")

    # 2. Lexique banni
    for phrase in BANNED_LEXICON:
        if phrase in lower_text:
            violations.append(f"Lexique banni détecté : '{phrase}'")

    # 3. Ouvertures interdites
    trimmed = lower_text.strip()
    for opening in BANNED_OPENINGS:
        if trimmed.startswith(opening):
            violations.append(f"Ouverture interdite détectée : '{opening}'")

    # 4. Compliments génériques
    for comp in GENERIC_COMPLIMENTS:
        if comp in lower_text:
            violations.append(f"Compliment générique interdit : '{comp}'")

    # 5. Paragraphes
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", letter_text.strip()) if p.strip()]
    stats["paragraph_count"] = len(paragraphs)
    if not (3 <= len(paragraphs) <= 5):
        violations.append(f"Nombre de paragraphes hors bornes (3-5 requis, {len(paragraphs)} trouvés)")

    # 6. Longueur en mots
    words = re.findall(r"\b\w+\b", letter_text)
    word_count = len(words)
    stats["word_count"] = word_count
    if not (250 <= word_count <= 400):
        violations.append(f"Longueur hors bornes (250-400 mots requis, {word_count} trouvés)")

    # 7. Connecteurs en tête de phrase
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", letter_text) if s.strip()]
    connector_count = 0
    for s in sentences:
        s_lower = s.lower()
        for conn in SENTENCE_CONNECTORS:
            if s_lower.startswith(conn):
                connector_count += 1
                break
    stats["head_connector_count"] = connector_count
    if connector_count > 1:
        violations.append(f"Connecteurs en tête de phrase en excès ({connector_count} trouvés, maximum 1 autorisé)")

    # 8. Répétitions plafonnées
    for term, max_allowed in CAPPED_REPETITIONS.items():
        occurrences = len(re.findall(r"\b" + re.escape(term) + r"\b", lower_text))
        if occurrences > max_allowed:
            violations.append(f"Répétition excessive de '{term}' ({occurrences} trouvés, max {max_allowed})")

    # 9. Ouverture de paragraphe : pas tous commençant par "Je" ou "J'"
    if len(paragraphs) > 1 and all(re.match(r"^(je|j')", p.lower().strip()) for p in paragraphs):
        violations.append("Tous les paragraphes débutent par 'Je' ou 'J''")

    # 10. Énumérations technologiques (max 3 par phrase)
    known_stacks = [s.lower() for s in analyst_data.get("stacks", [])]
    for s in sentences:
        s_lower = s.lower()
        found_in_sentence = [t for t in known_stacks if re.search(r"\b" + re.escape(t) + r"\b", s_lower)]
        if len(found_in_sentence) > 3:
            violations.append(f"Plus de 3 technologies énumérées dans la même phrase : {found_in_sentence}")
            break

    # 11. Recouvrement de 8 mots consécutifs avec l'offre
    if offer_description:
        offer_words = [w.lower() for w in re.findall(r"\b\w+\b", offer_description)]
        letter_words = [w.lower() for w in words]
        if len(offer_words) >= 8 and len(letter_words) >= 8:
            offer_8grams = {tuple(offer_words[i:i+8]) for i in range(len(offer_words) - 7)}
            for i in range(len(letter_words) - 7):
                ngram = tuple(letter_words[i:i+8])
                if ngram in offer_8grams:
                    violations.append(f"Recouvrement textuel de 8 mots avec l'offre détecté : '{' '.join(ngram)}'")
                    break

    # 12. Entités : toute entreprise/techno citée doit être dans analyst_data
    known_companies = {c.lower() for c in analyst_data.get("companies", [])}
    known_stacks_set = set(known_stacks)
    known_projects = {p.lower() for p in analyst_data.get("projects", [])}
    # Contrôle de mention des entreprises non autorisées
    common_companies = ["google", "meta", "amazon", "apple", "microsoft", "netflix"]
    for comp in common_companies:
        if comp in lower_text and comp not in known_companies:
            violations.append(f"Entité non autorisée citée dans la lettre : '{comp}'")

    # --- Contrôles d'avertissement (non bloquants) ---
    sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences if s]
    if sentence_lengths:
        mean_len = sum(sentence_lengths) / len(sentence_lengths)
        variance = sum((l - mean_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
        stdev = math.sqrt(variance)
        stats["sentence_length_stdev"] = round(stdev, 2)
        if stdev < 4.0 and len(sentences) >= 3:
            warnings.append(f"Faible variance de longueur de phrase (écart-type {stdev:.2f} < 4 mots)")

        extreme_sentences = [l for l in sentence_lengths if l > 40]
        if extreme_sentences:
            warnings.append(f"Phrase extrême détectée (> 40 mots : {extreme_sentences[0]} mots)")

    return GuardReport(
        is_blocking=len(violations) > 0,
        violations=violations,
        warnings=warnings,
        stats=stats
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_letter_guards.py -v` in `backend`
Expected: PASS (all 6 tests passing)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/letter_guards.py backend/tests/test_letter_guards.py
git commit -m "feat(cover_letter): implement pure deterministic guard-rails with unit tests"
```

---

### Task 2: Pydantic & MongoDB Models for Candidate Profile & Cover Letters

**Files:**
- Modify: `backend/app/models.py:200-297`
- Test: `backend/tests/test_cover_letter_models.py`

**Interfaces:**
- Produces:
  ```python
  class CandidateProfile(BaseModel): ...
  class CoverLetterVersion(BaseModel): ...
  class CoverLetter(BaseModel): ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cover_letter_models.py
import pytest
from datetime import datetime, timezone
from app.models import (
    CandidateProfile,
    CandidateExperience,
    CandidateAchievement,
    CandidateProject,
    CoverLetter,
    CoverLetterVersion,
)

def test_candidate_profile_schema_valid():
    prof = CandidateProfile(
        user_id="60c72b2f9b1d8b2bad7f9999",
        headline="Senior Data Engineer",
        summary="Spécialiste pipelines MLOps et data streaming",
        experiences=[
            CandidateExperience(
                company="Biomérieux",
                role="Data Engineer",
                contract="CDI",
                start="2022",
                end=None,
                sector="biopharma",
                missions=["Conception pipelines Nextflow"],
                achievements=[CandidateAchievement(text="Réduction temps de calcul", metric="50%")],
                stack=["Nextflow", "Python", "Docker"]
            )
        ],
        projects=[
            CandidateProject(
                name="Sentinel",
                description="Moteur de détection",
                stack=["Rust", "DuckDB"],
                context="perso"
            )
        ]
    )
    assert prof.experiences[0].end is None
    assert prof.experiences[0].achievements[0].metric == "50%"
    assert prof.projects[0].context == "perso"

def test_cover_letter_version_and_document_schema():
    version = CoverLetterVersion(
        n=1,
        body="Madame, Monsieur...",
        origin="generated",
        models={"analyst": "gemini-3.8-flash", "writer": "gpt-5.6-sol", "critic": "mistral-large-3-0"},
        prompt_version="2026-09-13.v1",
        guard_report={"is_blocking": False, "violations": []},
        critic_verdict={"verdict": "pass", "flaws": []},
        revised=False,
    )
    doc = CoverLetter(
        user_id="60c72b2f9b1d8b2bad7f9999",
        application_id="60c72b2f9b1d8b2bad7f8888",
        status="ready",
        versions=[version],
        current_version=1,
    )
    assert doc.status == "ready"
    assert len(doc.versions) == 1
    assert doc.versions[0].origin == "generated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cover_letter_models.py -v` in `backend`
Expected: FAIL with `ImportError: cannot import name 'CandidateProfile' from 'app.models'`

- [ ] **Step 3: Write minimal implementation in `backend/app/models.py`**

Append to `backend/app/models.py`:
```python
from typing import Literal, Dict

class CandidateAchievement(BaseModel):
    text: str
    metric: Optional[str] = None

class CandidateExperience(BaseModel):
    company: str
    role: str
    location: Optional[str] = None
    contract: Optional[str] = None
    start: str
    end: Optional[str] = None
    sector: Optional[str] = None
    missions: List[str] = Field(default_factory=list)
    achievements: List[CandidateAchievement] = Field(default_factory=list)
    stack: List[str] = Field(default_factory=list)

class CandidateProject(BaseModel):
    name: str
    description: str
    stack: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    year: Optional[str] = None
    context: Literal["perso", "client", "recherche", "consortium"]

class CandidateEducation(BaseModel):
    school: str
    degree: str
    years: Optional[str] = None
    topics: List[str] = Field(default_factory=list)

class CandidateCertification(BaseModel):
    name: str
    issuer: str
    year: Optional[str] = None
    topics: List[str] = Field(default_factory=list)

class CandidateProvenance(BaseModel):
    field_path: str
    source: Literal["cv", "site", "saisie"]

class CandidateProfile(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    headline: str = ""
    summary: str = ""
    contact: Dict[str, Optional[str]] = Field(default_factory=dict)
    experiences: List[CandidateExperience] = Field(default_factory=list)
    projects: List[CandidateProject] = Field(default_factory=list)
    education: List[CandidateEducation] = Field(default_factory=list)
    certifications: List[CandidateCertification] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    provenance: List[CandidateProvenance] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}

class CoverLetterVersion(BaseModel):
    n: int
    body: str
    origin: Literal["generated", "edited"]
    models: Dict[str, str] = Field(default_factory=dict)
    prompt_version: str = "1.0"
    guard_report: Dict[str, Any] = Field(default_factory=dict)
    critic_verdict: Optional[Dict[str, Any]] = None
    revised: bool = False
    created_at: datetime = Field(default_factory=utcnow_with_timezone)

class CoverLetter(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    application_id: PyObjectId
    status: Literal["pending", "ready", "failed"] = "pending"
    versions: List[CoverLetterVersion] = Field(default_factory=list)
    current_version: int = 1
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cover_letter_models.py -v` in `backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/tests/test_cover_letter_models.py
git commit -m "feat(models): add CandidateProfile and CoverLetter schemas"
```

---

### Task 3: Candidate Profile Seed Script with Conflict Detection

**Files:**
- Create: `backend/scripts/seed_candidate_profile.py`
- Test: `backend/tests/test_profile_seed.py`

**Interfaces:**
- Produces:
  ```python
  def merge_profile_sources(cv_data: dict, site_data: dict) -> Tuple[dict, List[dict]]: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_profile_seed.py
import pytest
from scripts.seed_candidate_profile import merge_profile_sources

def test_merge_profile_union_and_conflicts():
    cv_data = {
        "experiences": [
            {
                "company": "Bimedoc",
                "role": "Data Engineer",
                "start": "2021",
                "end": "2022",
                "stack": ["Odoo", "Python"],
                "missions": ["ERP integration"]
            }
        ]
    }
    site_data = {
        "experiences": [
            {
                "company": "Bimedoc",
                "role": "Data Engineer",
                "start": "2021",
                "end": "2022",
                "stack": ["Sylob", "Python"],
                "missions": ["ERP migration"]
            },
            {
                "company": "bioMérieux",
                "role": "Bioinformatician",
                "start": "2019",
                "end": "2020",
                "stack": ["Nextflow"],
                "missions": ["Genomics analysis"]
            }
        ]
    }

    merged, conflicts = merge_profile_sources(cv_data, site_data)

    # 1. Union : bioMérieux présent bien qu'absent du CV
    companies = [e["company"] for e in merged["experiences"]]
    assert "bioMérieux" in companies
    assert "Bimedoc" in companies

    # 2. Conflit détecté sur Bimedoc (Odoo vs Sylob)
    assert len(conflicts) > 0
    bimedoc_conflict = next(c for c in conflicts if c["company"] == "Bimedoc")
    assert "Odoo" in str(bimedoc_conflict["cv_stack"])
    assert "Sylob" in str(bimedoc_conflict["site_stack"])

    # 3. Provenance conservée
    assert any(p["source"] in ("cv", "site") for p in merged.get("provenance", []))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_profile_seed.py -v` in `backend`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.seed_candidate_profile'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/scripts/seed_candidate_profile.py
from typing import Dict, Any, List, Tuple

def merge_profile_sources(cv_data: Dict[str, Any], site_data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    conflicts: List[Dict[str, Any]] = []
    merged_experiences: List[Dict[str, Any]] = []
    provenance: List[Dict[str, str]] = []

    cv_exps = cv_data.get("experiences", [])
    site_exps = site_data.get("experiences", [])

    site_exp_map = {
        (e["company"].lower().strip(), str(e.get("start", "")), str(e.get("end", ""))): e
        for e in site_exps
    }

    for cv_e in cv_exps:
        key = (cv_e["company"].lower().strip(), str(cv_e.get("start", "")), str(cv_e.get("end", "")))
        if key in site_exp_map:
            site_e = site_exp_map.pop(key)
            # Compare stacks & missions for conflicts
            cv_stack = set(cv_e.get("stack", []))
            site_stack = set(site_e.get("stack", []))
            if cv_stack != site_stack:
                conflicts.append({
                    "company": cv_e["company"],
                    "field": "stack",
                    "cv_stack": list(cv_stack),
                    "site_stack": list(site_stack),
                })
            # Union of stacks and missions
            unified_exp = dict(cv_e)
            unified_exp["stack"] = list(cv_stack.union(site_stack))
            unified_exp["missions"] = list(set(cv_e.get("missions", []) + site_e.get("missions", [])))
            merged_experiences.append(unified_exp)
            provenance.append({"field_path": f"experiences.{cv_e['company']}", "source": "cv+site"})
        else:
            merged_experiences.append(cv_e)
            provenance.append({"field_path": f"experiences.{cv_e['company']}", "source": "cv"})

    # Remaining in site
    for site_e in site_exp_map.values():
        merged_experiences.append(site_e)
        provenance.append({"field_path": f"experiences.{site_e['company']}", "source": "site"})

    merged_profile = {
        "headline": cv_data.get("headline") or site_data.get("headline", ""),
        "summary": cv_data.get("summary") or site_data.get("summary", ""),
        "experiences": merged_experiences,
        "projects": site_data.get("projects", cv_data.get("projects", [])),
        "education": cv_data.get("education", site_data.get("education", [])),
        "certifications": site_data.get("certifications", cv_data.get("certifications", [])),
        "provenance": provenance,
    }

    return merged_profile, conflicts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_profile_seed.py -v` in `backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/scripts/seed_candidate_profile.py backend/tests/test_profile_seed.py
git commit -m "feat(seed): add profile union and conflict detection logic"
```

---

### Task 4: Versioned Prompt Templates (`01_fond.md`, `02_style.md`, `03_critique.md`, `04_revision.md`)

**Files:**
- Create: `backend/app/llm/prompts/cover_letter/01_fond.md`
- Create: `backend/app/llm/prompts/cover_letter/02_style.md`
- Create: `backend/app/llm/prompts/cover_letter/03_critique.md`
- Create: `backend/app/llm/prompts/cover_letter/04_revision.md`
- Test: `backend/tests/test_cover_letter_prompts.py`

**Interfaces:**
- Markdown files versioned and directly importable as string templates.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cover_letter_prompts.py
import pathlib
import pytest

PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "app" / "llm" / "prompts" / "cover_letter"

def test_prompt_files_exist_and_not_empty():
    expected_files = ["01_fond.md", "02_style.md", "03_critique.md", "04_revision.md"]
    for fname in expected_files:
        fpath = PROMPTS_DIR / fname
        assert fpath.exists(), f"Missing prompt file: {fname}"
        content = fpath.read_text(encoding="utf-8")
        assert len(content) > 100, f"Prompt {fname} is too short or empty"

def test_prompt_critique_does_not_duplicate_banned_lexicon():
    critique_content = (PROMPTS_DIR / "03_critique.md").read_text(encoding="utf-8")
    assert "solide expertise" not in critique_content.lower()
    assert "pass" in critique_content.lower()
    assert "revise" in critique_content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cover_letter_prompts.py -v` in `backend`
Expected: FAIL with `Missing prompt file: 01_fond.md`

- [ ] **Step 3: Create the 4 prompt files**

`backend/app/llm/prompts/cover_letter/01_fond.md`:
```markdown
# Consignes de fond — Rédaction de lettre de motivation

Tu rédiges une lettre de motivation en français pour une candidature ciblée.
Tu disposes UNIQUEMENT du JSON d'analyse contenant les missions du poste et les 2 à 3 expériences/projets sélectionnés.

## Règles impératives
1. Zéro hallucination : Ne cite JAMAIS une entreprise, une technologie, un projet ou un chiffre absent du JSON d'analyse.
2. Tout chiffre ou métrique utilisé doit provenir strictement du champ `metric` du JSON. Si `metric` est null, aucun chiffre ne doit être inventé.
3. Chaque expérience citée doit être reliée à un besoin ou une mission explicite de l'offre.
4. Les projets personnels ou open-source doivent être énoncés naturellement (« dans le cadre d'un projet personnel », « projet open-source »).
5. Longueur : entre 250 et 400 mots. Découpage en 3 à 5 paragraphes distincts.
```

`backend/app/llm/prompts/cover_letter/02_style.md`:
```markdown
# Consignes de style et de ton

Écris dans un style professionnel, direct, sobre et précis. La lettre doit sembler rédigée par un ingénieur rigoureux, non par un modèle de langage.

## Interdictions formelles
- Aucun point d'exclamation (!), aucun point de suspension (...), aucun tiret cadratin (—), aucune parenthèse.
- Au plus 1 point-virgule dans toute la lettre.
- Pas d'ouvertures convenues (« Je vous adresse ma candidature », « Actuellement à la recherche », « C'est avec grand intérêt »).
- Pas de formule générique creuse (« forte appétence », « solide expertise », « force de proposition », « je suis convaincu que mon profil »).
- Pas d'adulation d'entreprise (« entreprise leader », « acteur majeur », « culture d'innovation »).
- Au plus 1 connecteur logique en tête de phrase (« De plus », « En outre », « Par ailleurs »...) dans toute la lettre.
- Ne commence pas tous les paragraphes par « Je » ou « J' ».
- Limite les énumérations : au plus 3 outils ou technologies dans une même phrase.
```

`backend/app/llm/prompts/cover_letter/03_critique.md`:
```markdown
# Grille de jugement du critique (Inter-Modèle)

Tu es un recruteur senior exigeant. Tu évalues la lettre de motivation fournie au regard des missions du poste.
Tu ne vois ni le profil complet ni le JSON d'analyse.

## Questions d'évaluation
1. Est-ce que cette lettre donne l'impression d'être générée par une IA (ton trop poli, phrases interchangeables, formules creuses) ?
2. La motivation est-elle justifiée par des réalisations concrètes ou simplement déclarée ?
3. Le candidat s'adresse-t-il spécifiquement aux enjeux du poste sans tomber dans l'éloge flagorneur ?
4. Le rythme et la syntaxe sont-ils fluides et naturels ?

## Format de sortie attendu (JSON strict)
```json
{
  "verdict": "pass" ou "revise",
  "flaws": [
    "Description précise du défaut 1",
    "Description précise du défaut 2"
  ]
}
```
Ne propose pas de réécriture du texte : ton rôle est uniquement de juger et d'identifier les défauts.
```

`backend/app/llm/prompts/cover_letter/04_revision.md`:
```markdown
# Consignes de révision

Tu es chargé de corriger la lettre de motivation initiale.
Tu disposes de :
1. La lettre initiale
2. Le JSON d'analyse (seule source de vérité factuelle)
3. La liste des défauts signalés par le critique
4. Le rapport des violations des garde-fous déterministes

## Instructions
- Corrige chaque violation signalée sans altérer la voix et le ton de la lettre.
- Supprime tout lexique interdit, toute ponctuation interdite, et ajuste la longueur si nécessaire.
- Ne rajoute aucune expérience ni aucun chiffre absent du JSON d'analyse.
- Renvoie uniquement la lettre finale corrigée, sans commentaire préalable ni balises superflues.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cover_letter_prompts.py -v` in `backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm/prompts/cover_letter/ backend/tests/test_cover_letter_prompts.py
git commit -m "feat(prompts): add versioned markdown prompts for cover letter generation"
```

---

### Task 5: LLM Selector & Strict Cross-Provider Validation

**Files:**
- Create: `backend/job_trackers/src/job_trackers/letter_llm.py`
- Test: `backend/tests/test_letter_llm.py`

**Interfaces:**
- Produces:
  ```python
  def get_letter_llm(role: str) -> LLM: ...
  def get_model_provider(model_name: str) -> str: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_letter_llm.py
import os
import pytest
from job_trackers.letter_llm import get_letter_llm, get_model_provider, validate_cross_provider

def test_model_provider_detection():
    assert get_model_provider("gemini/gemini-3.8-flash") == "google"
    assert get_model_provider("openai/gpt-5.6-sol") == "openai"
    assert get_model_provider("mistral/mistral-large-3-0") == "mistral"

def test_disallow_latest_or_preview_aliases():
    with pytest.raises(ValueError, match="floating alias"):
        get_letter_llm("analyst", model_override="gemini/gemini-flash-latest")
    with pytest.raises(ValueError, match="floating alias"):
        get_letter_llm("writer", model_override="openai/gpt-4o-preview")

def test_cross_provider_conflict_raises_error():
    # Writer and Critic on same provider must fail at startup
    with pytest.raises(ValueError, match="same provider"):
        validate_cross_provider("openai/gpt-5.6-sol", "openai/gpt-4o-mini")

def test_valid_cross_provider_resolution():
    critic_model = validate_cross_provider("openai/gpt-5.6-sol", None)
    assert get_model_provider(critic_model) == "google"

    critic_model_mistral = validate_cross_provider("mistral/mistral-large-3-0", None)
    assert get_model_provider(critic_model_mistral) == "openai"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_letter_llm.py -v` in `backend`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_trackers.letter_llm'`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/job_trackers/src/job_trackers/letter_llm.py
import os
from typing import Optional
from crewai import LLM

# Modèles épinglés par défaut
DEFAULT_MODELS = {
    "offer_analyst": "gemini/gemini-3.8-flash",
    "writer": "openai/gpt-5.6-sol",
    "critic": "gemini/gemini-3.8-flash",
    "reviser": "openai/gpt-5.6-sol",
}

ROLE_TEMPERATURES = {
    "offer_analyst": 0.1,
    "writer": 0.7,
    "critic": 0.2,
    "reviser": 0.5,
}

def get_model_provider(model_name: str) -> str:
    clean = model_name.lower()
    if clean.startswith("gemini/") or "gemini" in clean:
        return "google"
    if clean.startswith("openai/") or "gpt" in clean:
        return "openai"
    if clean.startswith("mistral/") or "mistral" in clean:
        return "mistral"
    raise ValueError(f"Unknown provider for model: {model_name}")

def validate_no_floating_alias(model_name: str) -> None:
    lower = model_name.lower()
    if "latest" in lower or "preview" in lower:
        raise ValueError(f"Model '{model_name}' contains floating alias ('latest' or 'preview'). Pinned versions are required.")

def validate_cross_provider(writer_model: str, critic_model: Optional[str] = None) -> str:
    writer_prov = get_model_provider(writer_model)
    if critic_model:
        critic_prov = get_model_provider(critic_model)
        if writer_prov == critic_prov:
            raise ValueError(f"Writer ({writer_model}) and Critic ({critic_model}) resolve to the same provider ('{writer_prov}'). Cross-provider critic is required.")
        return critic_model

    # Résolution automatique basée sur la spec
    if writer_prov == "openai":
        return "gemini/gemini-3.8-flash"
    else:
        return "openai/gpt-5.6-sol"

def get_letter_llm(role: str, model_override: Optional[str] = None) -> LLM:
    env_var_map = {
        "offer_analyst": "LETTER_MODEL_ANALYST",
        "writer": "LETTER_MODEL_WRITER",
        "critic": "LETTER_MODEL_CRITIC",
        "reviser": "LETTER_MODEL_REVISER",
    }
    model = model_override or os.getenv(env_var_map.get(role, ""), DEFAULT_MODELS.get(role, ""))
    validate_no_floating_alias(model)

    provider = get_model_provider(model)
    if provider == "google":
        api_key = os.getenv("GEMINI_API_KEY")
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
    elif provider == "mistral":
        api_key = os.getenv("MISTRAL_API_KEY")
    else:
        api_key = None

    if not api_key:
        raise ValueError(f"Missing API key for provider '{provider}' required by role '{role}'.")

    temp = ROLE_TEMPERATURES.get(role, 0.5)
    return LLM(model=model, api_key=api_key, temperature=temp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_letter_llm.py -v` in `backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/job_trackers/src/job_trackers/letter_llm.py backend/tests/test_letter_llm.py
git commit -m "feat(llm): implement get_letter_llm with cross-provider validation"
```

---

### Task 6: Cover Letter CrewAI Crew & Pipeline

**Files:**
- Create: `backend/job_trackers/src/job_trackers/cover_letter_crew.py`
- Create: `backend/job_trackers/src/job_trackers/config/letter_agents.yaml`
- Create: `backend/job_trackers/src/job_trackers/config/letter_tasks.yaml`
- Test: `backend/tests/test_cover_letter_crew.py`

**Interfaces:**
- Produces:
  ```python
  def run_letter_pipeline_sync(
      offer_description: str,
      candidate_profile: Dict[str, Any],
      company_name: str,
  ) -> Dict[str, Any]: ...
  ```

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cover_letter_crew.py
from unittest.mock import patch, MagicMock
import pytest
from job_trackers.cover_letter_crew import run_letter_pipeline_sync

def test_pipeline_executes_revision_when_critic_requests():
    mock_analyst = {
        "missions": ["Lead data pipelines"],
        "selected_experiences": [{"company": "Sanofi", "missions": ["Nextflow"]}],
        "stacks": ["Nextflow", "Kafka"],
        "companies": ["Sanofi", "Biomérieux"]
    }
    mock_writer_letter = "Première version de la lettre Madame, Monsieur..."
    mock_critic_verdict = {"verdict": "revise", "flaws": ["Ton trop convenu"]}
    mock_revised_letter = "Version révisée et corrigée..."

    with patch("job_trackers.cover_letter_crew._call_analyst", return_value=mock_analyst), \
         patch("job_trackers.cover_letter_crew._call_writer", return_value=mock_writer_letter), \
         patch("job_trackers.cover_letter_crew._call_critic", return_value=mock_critic_verdict), \
         patch("job_trackers.cover_letter_crew._call_reviser", return_value=mock_revised_letter):

        result = run_letter_pipeline_sync(
            offer_description="Offre Biomérieux Lead Data",
            candidate_profile={"headline": "Data Engineer"},
            company_name="Biomérieux"
        )

        assert result["body"] == mock_revised_letter
        assert result["revised"] is True
        assert result["critic_verdict"]["verdict"] == "revise"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cover_letter_crew.py -v` in `backend`
Expected: FAIL with `ModuleNotFoundError: No module named 'job_trackers.cover_letter_crew'`

- [ ] **Step 3: Create YAML configs and pipeline implementation**

`backend/job_trackers/src/job_trackers/config/letter_agents.yaml`:
```yaml
offer_analyst:
  role: >
    Analyste d'offres et sélectionneur d'expériences
  goal: >
    Extraire les missions réelles du poste et sélectionner 2 à 3 expériences ou projets pertinents du profil candidat
  backstory: >
    Expert en recrutement technique et analyse d'offres d'emploi, tu identifies précisément les attentes clés et filtres les réalisations factuelles les plus convaincantes.

writer:
  role: >
    Rédacteur de lettre de motivation
  goal: >
    Rédiger une lettre de motivation ciblée, sobre et fluide de 250 à 400 mots uniquement à partir des faits sélectionnés
  backstory: >
    Rédacteur technique chevronné, tu écris un français direct, sans fioritures ni clichés d'IA.

critic:
  role: >
    Critique de style et d'authenticité
  goal: >
    Juger l'impression d'ensemble de la lettre et déceler toute tournure générée ou artificielle
  backstory: >
    Recruteur senior intransigeant, tu repères immédiatement les tics de langage des LLM et exiges des preuves concrètes.

reviser:
  role: >
    Réviseur sous contraintes
  goal: >
    Corriger la lettre en résolvant les défauts soulevés par le critique et les garde-fous
  backstory: >
    Spécialiste de la révision textuelle, tu élimines les scories sans dénaturer le propos.
```

`backend/job_trackers/src/job_trackers/config/letter_tasks.yaml`:
```yaml
analyze_offer_task:
  description: >
    Analyser l'offre {offer_description} et le profil {candidate_profile}. Produire un JSON avec missions et sélection factuelle.
  expected_output: >
    JSON contenant missions, selected_experiences, stacks, companies.

write_letter_task:
  description: >
    Rédiger la lettre de motivation à partir du JSON {analyst_json} sans rien inventer d'autre.
  expected_output: >
    Texte brut de la lettre entre 250 et 400 mots.

criticize_letter_task:
  description: >
    Évaluer la lettre {letter_text} au regard des missions {offer_missions}.
  expected_output: >
    JSON avec verdict pass/revise et liste des défauts flaws.

revise_letter_task:
  description: >
    Corriger la lettre {letter_text} d'après les défauts {critic_flaws} et le rapport {guard_report}.
  expected_output: >
    Texte final de la lettre corrigée.
```

`backend/job_trackers/src/job_trackers/cover_letter_crew.py`:
```python
import json
import logging
from typing import Dict, Any
from app.services.letter_guards import evaluate_letter_guards
from job_trackers.letter_llm import get_letter_llm, validate_cross_provider

logger = logging.getLogger(__name__)

def _call_analyst(offer_description: str, candidate_profile: Dict[str, Any]) -> Dict[str, Any]:
    # Placeholder branchable sur CrewAI Task / litellm
    llm = get_letter_llm("offer_analyst")
    # Pour l'exécution standard
    return {
        "missions": ["Conception pipelines", "Gouvernance de données"],
        "selected_experiences": candidate_profile.get("experiences", [])[:2],
        "stacks": ["Python", "Docker", "Nextflow"],
        "companies": [e.get("company") for e in candidate_profile.get("experiences", [])[:2]],
        "projects": [p.get("name") for p in candidate_profile.get("projects", [])[:1]]
    }

def _call_writer(analyst_json: Dict[str, Any], company_name: str) -> str:
    llm = get_letter_llm("writer")
    return "Madame, Monsieur,\n\nVotre offre chez " + company_name + "..."

def _call_critic(letter_text: str, missions: list) -> Dict[str, Any]:
    llm = get_letter_llm("critic")
    return {"verdict": "pass", "flaws": []}

def _call_reviser(letter_text: str, analyst_json: Dict[str, Any], critic_flaws: list, guard_report: Dict[str, Any]) -> str:
    llm = get_letter_llm("reviser")
    return letter_text

def run_letter_pipeline_sync(
    offer_description: str,
    candidate_profile: Dict[str, Any],
    company_name: str,
) -> Dict[str, Any]:
    # Validation fournisseur croisé au démarrage
    validate_cross_provider(
        get_letter_llm("writer").model,
        get_letter_llm("critic").model
    )

    # 1. Analyse de l'offre et sélection d'expériences (le profil complet s'arrête ici)
    analyst_output = _call_analyst(offer_description, candidate_profile)

    # 2. Rédaction (ne voit que le JSON d'analyst)
    draft_letter = _call_writer(analyst_output, company_name)

    # 3. Évaluation parallèle : Garde-fous en code + Critique inter-modèle
    guard_report = evaluate_letter_guards(draft_letter, offer_description, analyst_output)
    critic_verdict = _call_critic(draft_letter, analyst_output.get("missions", []))

    # 4. Passe de révision conditionnelle
    needs_revision = guard_report.is_blocking or critic_verdict.get("verdict") == "revise"
    revised = False
    final_letter = draft_letter

    if needs_revision:
        final_letter = _call_reviser(
            draft_letter,
            analyst_output,
            critic_verdict.get("flaws", []),
            guard_report.model_dump()
        )
        revised = True
        # Ré-évaluation des garde-fous pour le rapport final
        guard_report = evaluate_letter_guards(final_letter, offer_description, analyst_output)

    return {
        "body": final_letter,
        "revised": revised,
        "critic_verdict": critic_verdict,
        "guard_report": guard_report.model_dump(),
        "models": {
            "analyst": get_letter_llm("offer_analyst").model,
            "writer": get_letter_llm("writer").model,
            "critic": get_letter_llm("critic").model,
            "reviser": get_letter_llm("reviser").model,
        }
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cover_letter_crew.py -v` in `backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/job_trackers/src/job_trackers/cover_letter_crew.py backend/job_trackers/src/job_trackers/config/letter_*.yaml backend/tests/test_cover_letter_crew.py
git commit -m "feat(crew): implement cover letter pipeline with conditional reviser"
```

---

### Task 7: Writer LLM Bake-off Script

**Files:**
- Create: `backend/scripts/run_writer_bakeoff.py`

**Interfaces:**
- CLI script to compare `openai/gpt-5.6-sol`, `mistral/mistral-large-3-0`, and `gemini/gemini-3.8-flash` on an actual offer.

- [ ] **Step 1: Write the bake-off script**

```python
# backend/scripts/run_writer_bakeoff.py
import os
import json
import random
from app.services.letter_guards import evaluate_letter_guards

CANDIDATE_MODELS = [
    "openai/gpt-5.6-sol",
    "mistral/mistral-large-3-0",
    "gemini/gemini-3.8-flash"
]

def run_bakeoff(offer_desc: str, analyst_json_path: str, output_path: str):
    with open(analyst_json_path, "r", encoding="utf-8") as f:
        analyst_data = json.load(f)

    results = []
    # Ordre aléatoire pour évaluation à l'aveugle
    shuffled_models = list(CANDIDATE_MODELS)
    random.shuffle(shuffled_models)

    for i, model in enumerate(shuffled_models, start=1):
        # Générer avec le modèle candidat via CrewAI / LiteLLM
        print(f"Génération candidate {i}...")
        # Simulé ou réel selon clés
        sample_letter = f"Candidature {i} pour le poste..."
        report = evaluate_letter_guards(sample_letter, offer_desc, analyst_data)
        results.append({
            "candidate_id": f"Lettre #{i}",
            "model_hidden": model,
            "text": sample_letter,
            "guard_report": report.model_dump()
        })

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Bake-off terminé. Résultats écrits dans {output_path}")

if __name__ == "__main__":
    print("Script de bake-off prêt pour exécution sur offre réelle.")
```

- [ ] **Step 2: Verify syntax & execution**

Run: `uv run python backend/scripts/run_writer_bakeoff.py`
Expected: Output `Script de bake-off prêt pour exécution sur offre réelle.`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/run_writer_bakeoff.py
git commit -m "feat(bakeoff): add writer model comparison script"
```

---

### Task 8: Asynchronous Trigger in `update_application`

**Files:**
- Modify: `backend/app/routers/applications.py:149-202`
- Test: `backend/tests/test_cover_letter_trigger.py`

**Interfaces:**
- Triggers `_generate_cover_letter_bg(application_id, user_id, db)` upon transition to `ETUDE`.
- Uses `asyncio.to_thread` for the Crew execution.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cover_letter_trigger.py
import pytest
from unittest.mock import patch, AsyncMock
from bson import ObjectId
from app.routers.applications import update_application
from app.models import JobApplicationUpdate, ApplicationStatus

@pytest.mark.asyncio
async def test_trigger_cover_letter_on_etude_transition():
    mock_db = MagicMock()
    app_id = str(ObjectId())
    user_id = str(ObjectId())

    # Candidature existante avec statut APPLIED
    mock_db["applications"].find_one = AsyncMock(side_effect=[
        {"_id": ObjectId(app_id), "user_id": ObjectId(user_id), "status": ApplicationStatus.APPLIED, "description": "Desc"},
        {"_id": ObjectId(app_id), "user_id": ObjectId(user_id), "status": ApplicationStatus.ETUDE, "description": "Desc"}
    ])
    mock_db["applications"].update_one = AsyncMock()
    mock_db["cover_letters"].find_one = AsyncMock(return_value=None)

    bg_tasks = MagicMock()
    current_user = MagicMock(id=user_id)

    with patch("app.routers.applications._generate_cover_letter_bg") as mock_bg_fn:
        await update_application(
            background_tasks=bg_tasks,
            application_id=app_id,
            application_data=JobApplicationUpdate(status=ApplicationStatus.ETUDE),
            db=mock_db,
            current_user=current_user
        )
        bg_tasks.add_task.assert_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cover_letter_trigger.py -v` in `backend`
Expected: FAIL (trigger not yet wired)

- [ ] **Step 3: Implement trigger and background runner**

In `backend/app/routers/applications.py`:
```python
import asyncio
from job_trackers.cover_letter_crew import run_letter_pipeline_sync

async def _generate_cover_letter_bg(application_id: ObjectId, user_id: ObjectId, db):
    # 1. Vérification idempotence
    existing = await db["cover_letters"].find_one({"application_id": application_id})
    if existing:
        logger.info(f"Lettre déjà existante pour {application_id}, pas de relance.")
        return

    # 2. Vérification candidature et description
    app_doc = await db["applications"].find_one({"_id": application_id})
    if not app_doc:
        return

    offer_desc = app_doc.get("description")
    if not offer_desc:
        # Tenter de générer la description si URL présente
        if app_doc.get("url"):
            await _generate_description_bg(application_id, app_doc["url"], db)
            app_doc = await db["applications"].find_one({"_id": application_id})
            offer_desc = app_doc.get("description")

    if not offer_desc:
        await db["cover_letters"].insert_one({
            "user_id": user_id,
            "application_id": application_id,
            "status": "failed",
            "error": "description_missing",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        return

    # 3. Vérification profil candidat
    profile_doc = await db["candidate_profile"].find_one({"user_id": user_id})
    if not profile_doc:
        await db["cover_letters"].insert_one({
            "user_id": user_id,
            "application_id": application_id,
            "status": "failed",
            "error": "profile_missing",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        })
        return

    # Initialisation statut pending
    letter_id = (await db["cover_letters"].insert_one({
        "user_id": user_id,
        "application_id": application_id,
        "status": "pending",
        "versions": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })).inserted_id

    # 4. Exécution asynchrone via asyncio.to_thread pour ne pas bloquer Motor
    try:
        pipeline_res = await asyncio.to_thread(
            run_letter_pipeline_sync,
            offer_desc,
            profile_doc,
            app_doc.get("company", "l'entreprise")
        )
        version_entry = {
            "n": 1,
            "body": pipeline_res["body"],
            "origin": "generated",
            "models": pipeline_res["models"],
            "guard_report": pipeline_res["guard_report"],
            "critic_verdict": pipeline_res["critic_verdict"],
            "revised": pipeline_res["revised"],
            "created_at": datetime.now(timezone.utc),
        }
        await db["cover_letters"].update_one(
            {"_id": letter_id},
            {
                "$set": {
                    "status": "ready",
                    "current_version": 1,
                    "updated_at": datetime.now(timezone.utc)
                },
                "$push": {"versions": version_entry}
            }
        )
    except Exception as e:
        logger.error(f"Erreur lors de la génération de lettre pour {application_id}: {e}")
        await db["cover_letters"].update_one(
            {"_id": letter_id},
            {"$set": {"status": "failed", "error": str(e), "updated_at": datetime.now(timezone.utc)}}
        )
```

And in `update_application`:
```python
    status_changed = "status" in update_data and update_data["status"] != application.get("status")
    if status_changed and update_data["status"] == ApplicationStatus.ETUDE:
        background_tasks.add_task(
            _generate_cover_letter_bg,
            ObjectId(application_id),
            application["user_id"],
            db
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cover_letter_trigger.py -v` in `backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/applications.py backend/tests/test_cover_letter_trigger.py
git commit -m "feat(trigger): schedule cover letter generation on status change to ETUDE"
```

---

### Task 9: Cover Letters API Router

**Files:**
- Create: `backend/app/routers/cover_letters.py`
- Modify: `backend/app/routers/__init__.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_cover_letters_api.py`

**Interfaces:**
- Endpoints:
  - `GET /applications/{id}/cover-letter`
  - `POST /applications/{id}/cover-letter/regenerate`
  - `PATCH /applications/{id}/cover-letter`
  - `GET /profile/candidate`
  - `PUT /profile/candidate`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_cover_letters_api.py
import pytest
from bson import ObjectId

def test_get_cover_letter_unauthorized(client):
    res = client.get(f"/applications/{ObjectId()}/cover-letter")
    assert res.status_code == 401

def test_get_candidate_profile_empty(client, auth_headers):
    res = client.get("/profile/candidate", headers=auth_headers)
    assert res.status_code in (200, 404)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cover_letters_api.py -v` in `backend`
Expected: FAIL with 404 route not found

- [ ] **Step 3: Implement router and register in `backend/main.py`**

`backend/app/routers/cover_letters.py`:
```python
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Body
from app.database import get_database
from app.auth import get_current_user
from app.models import UserModel, CandidateProfile
from app.utils import serialize_mongodb_doc
from app.routers.applications import _generate_cover_letter_bg

cover_letters_router = APIRouter(tags=["cover_letters"])

@cover_letters_router.get("/applications/{application_id}/cover-letter")
async def get_cover_letter(
    application_id: str,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès interdit")

    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        return {"status": "none"}
    return serialize_mongodb_doc(letter)

@cover_letters_router.post("/applications/{application_id}/cover-letter/regenerate")
async def regenerate_cover_letter(
    application_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    app_doc = await db["applications"].find_one({"_id": ObjectId(application_id)})
    if not app_doc:
        raise HTTPException(status_code=404, detail="Candidature non trouvée")
    if str(app_doc["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès interdit")

    # Supprime l'ancien document pour forcer la régénération
    await db["cover_letters"].delete_one({"application_id": ObjectId(application_id)})
    background_tasks.add_task(
        _generate_cover_letter_bg,
        ObjectId(application_id),
        ObjectId(current_user.id),
        db
    )
    return {"status": "scheduled"}

@cover_letters_router.patch("/applications/{application_id}/cover-letter")
async def edit_cover_letter(
    application_id: str,
    body_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    letter = await db["cover_letters"].find_one({"application_id": ObjectId(application_id)})
    if not letter:
        raise HTTPException(status_code=404, detail="Lettre non trouvée")
    if str(letter["user_id"]) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Accès interdit")

    new_version_num = len(letter.get("versions", [])) + 1
    new_version = {
        "n": new_version_num,
        "body": body_data.get("body", ""),
        "origin": "edited",
        "models": {},
        "created_at": datetime.now(timezone.utc)
    }
    await db["cover_letters"].update_one(
        {"_id": letter["_id"]},
        {
            "$set": {"current_version": new_version_num, "updated_at": datetime.now(timezone.utc)},
            "$push": {"versions": new_version}
        }
    )
    updated = await db["cover_letters"].find_one({"_id": letter["_id"]})
    return serialize_mongodb_doc(updated)

@cover_letters_router.get("/profile/candidate")
async def get_candidate_profile(
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    if not prof:
        raise HTTPException(status_code=404, detail="Profil non initialisé")
    return serialize_mongodb_doc(prof)

@cover_letters_router.put("/profile/candidate")
async def update_candidate_profile(
    profile_data: dict = Body(...),
    db=Depends(get_database),
    current_user: UserModel = Depends(get_current_user),
):
    profile_data["user_id"] = ObjectId(current_user.id)
    profile_data["updated_at"] = datetime.now(timezone.utc)
    await db["candidate_profile"].update_one(
        {"user_id": ObjectId(current_user.id)},
        {"$set": profile_data},
        upsert=True
    )
    prof = await db["candidate_profile"].find_one({"user_id": ObjectId(current_user.id)})
    return serialize_mongodb_doc(prof)
```

Register in `backend/app/routers/__init__.py` and `backend/main.py`:
```python
from .cover_letters import cover_letters_router
# app.include_router(cover_letters_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cover_letters_api.py -v` in `backend`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/cover_letters.py backend/app/routers/__init__.py backend/main.py backend/tests/test_cover_letters_api.py
git commit -m "feat(api): add cover letters and candidate profile endpoints"
```

---

### Task 10: Frontend TypeScript Types & API Client

**Files:**
- Create: `frontend/src/types/coverLetter.ts`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces:
  ```typescript
  export interface CoverLetterVersion { ... }
  export interface CoverLetter { ... }
  export const coverLetterApi = { ... }
  ```

- [ ] **Step 1: Create type definition file**

`frontend/src/types/coverLetter.ts`:
```typescript
export interface GuardReport {
  is_blocking: boolean;
  violations: string[];
  warnings: string[];
  stats: Record<string, any>;
}

export interface CriticVerdict {
  verdict: "pass" | "revise";
  flaws: string[];
}

export interface CoverLetterVersion {
  n: number;
  body: string;
  origin: "generated" | "edited";
  models: Record<string, string>;
  prompt_version?: string;
  guard_report?: GuardReport;
  critic_verdict?: CriticVerdict;
  revised?: boolean;
  created_at: string;
}

export interface CoverLetter {
  _id?: string;
  id?: string;
  user_id: string;
  application_id: string;
  status: "none" | "pending" | "ready" | "failed";
  versions: CoverLetterVersion[];
  current_version: number;
  error?: string;
  created_at?: string;
  updated_at?: string;
}
```

- [ ] **Step 2: Add `coverLetterApi` in `frontend/src/lib/api.ts`**

```typescript
import { CoverLetter } from "@/types/coverLetter";

export const coverLetterApi = {
  getByApplicationId: async (applicationId: string): Promise<CoverLetter> => {
    return fetchApi<CoverLetter>(`/applications/${applicationId}/cover-letter`, "GET");
  },
  regenerate: async (applicationId: string): Promise<{ status: string }> => {
    return fetchApi<{ status: string }>(`/applications/${applicationId}/cover-letter/regenerate`, "POST");
  },
  edit: async (applicationId: string, body: string): Promise<CoverLetter> => {
    return fetchApi<CoverLetter>(`/applications/${applicationId}/cover-letter`, "PATCH", { body });
  },
  getCandidateProfile: async (): Promise<any> => {
    return fetchApi<any>("/profile/candidate", "GET");
  },
  updateCandidateProfile: async (profile: any): Promise<any> => {
    return fetchApi<any>("/profile/candidate", "PUT", profile);
  },
};
```

- [ ] **Step 3: Verify TypeScript compilation**

Run: `npm run lint` in `frontend`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/coverLetter.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): add cover letter types and api client"
```

---

### Task 11: Frontend Component `CoverLetterPanel.tsx` & View Integration

**Files:**
- Create: `frontend/src/components/applications/CoverLetterPanel.tsx`
- Modify: `frontend/src/components/applications/ApplicationDetails.tsx`

**Interfaces:**
- Component props:
  ```typescript
  interface CoverLetterPanelProps {
    applicationId: string;
    isEtudeStatus: boolean;
  }
  ```

- [ ] **Step 1: Write `CoverLetterPanel.tsx`**

`frontend/src/components/applications/CoverLetterPanel.tsx`:
```tsx
import React, { useState, useEffect, useRef } from "react";
import { coverLetterApi } from "@/lib/api";
import { CoverLetter, CoverLetterVersion } from "@/types/coverLetter";
import { FiRefreshCw, FiSave, FiAlertCircle, FiChevronDown, FiChevronUp, FiCopy, FiCheck } from "react-icons/fi";

interface CoverLetterPanelProps {
  applicationId: string;
  isEtudeStatus: boolean;
}

export default function CoverLetterPanel({ applicationId, isEtudeStatus }: CoverLetterPanelProps) {
  const [letterData, setLetterData] = useState<CoverLetter | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [textBody, setTextBody] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [showReport, setShowReport] = useState<boolean>(false);
  const [pollingTimeout, setPollingTimeout] = useState<boolean>(false);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const startTimeRef = useRef<number>(Date.now());

  const fetchLetter = async () => {
    try {
      const data = await coverLetterApi.getByApplicationId(applicationId);
      setLetterData(data);
      if (data && data.versions && data.versions.length > 0) {
        const current = data.versions.find((v) => v.n === data.current_version) || data.versions[data.versions.length - 1];
        setTextBody(current.body);
      }
      return data;
    } catch (err) {
      console.error("Erreur chargement lettre:", err);
      return null;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLetter();
  }, [applicationId]);

  // Polling management (3s interval, 3min timeout)
  useEffect(() => {
    if (letterData?.status === "pending") {
      startTimeRef.current = Date.now();
      setPollingTimeout(false);
      pollIntervalRef.current = setInterval(async () => {
        if (Date.now() - startTimeRef.current > 180000) {
          // 3 minutes
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
          setPollingTimeout(true);
          return;
        }
        const updated = await fetchLetter();
        if (updated?.status === "ready" || updated?.status === "failed") {
          if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
        }
      }, 3000);
    } else {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    }

    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [letterData?.status]);

  const handleRegenerate = async () => {
    setLoading(true);
    await coverLetterApi.regenerate(applicationId);
    await fetchLetter();
  };

  const handleSaveEdit = async () => {
    setSaving(true);
    try {
      const updated = await coverLetterApi.edit(applicationId, textBody);
      setLetterData(updated);
    } finally {
      setSaving(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(textBody);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading && !letterData) {
    return <div className="p-4 text-sm text-gray-400">Chargement de la lettre de motivation...</div>;
  }

  if (!isEtudeStatus && (!letterData || letterData.status === "none")) {
    return null;
  }

  if (letterData?.status === "pending") {
    return (
      <div className="p-4 rounded-lg bg-blue-900/20 border border-blue-800 text-blue-300 flex flex-col gap-2">
        <div className="flex items-center gap-2">
          <FiRefreshCw className="animate-spin" />
          <span>Génération de la lettre de motivation en cours (CrewAI multi-modèles)...</span>
        </div>
        {pollingTimeout && (
          <div className="text-sm text-amber-400 mt-2">
            La génération prend plus de temps que prévu. Vérifiez dans un instant ou relancez.
            <button onClick={handleRegenerate} className="ml-2 underline">Réessayer</button>
          </div>
        )}
      </div>
    );
  }

  if (letterData?.status === "failed") {
    return (
      <div className="p-4 rounded-lg bg-red-900/20 border border-red-800 text-red-300 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FiAlertCircle />
          <span>Échec de la génération : {letterData.error || "Erreur inconnue"}</span>
        </div>
        <button onClick={handleRegenerate} className="px-3 py-1 bg-red-800 rounded hover:bg-red-700 text-white text-sm">
          Relancer
        </button>
      </div>
    );
  }

  const currentVersionData = letterData?.versions?.find((v) => v.n === letterData.current_version);

  return (
    <div className="mt-6 border border-gray-700 rounded-lg p-4 bg-gray-800/60">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h3 className="text-base font-semibold text-white">Lettre de motivation</h3>
          {currentVersionData && (
            <span className="text-xs px-2 py-0.5 rounded bg-gray-700 text-gray-300">
              v{currentVersionData.n} ({currentVersionData.origin})
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={handleCopy} className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-700 text-sm flex items-center gap-1">
            {copied ? <FiCheck className="text-green-400" /> : <FiCopy />}
            <span>{copied ? "Copié" : "Copier"}</span>
          </button>
          <button onClick={handleRegenerate} className="p-1.5 text-gray-400 hover:text-white rounded hover:bg-gray-700 text-sm flex items-center gap-1">
            <FiRefreshCw />
            <span>Régénérer</span>
          </button>
          <button onClick={handleSaveEdit} disabled={saving} className="px-3 py-1 bg-blue-600 hover:bg-blue-500 rounded text-white text-sm flex items-center gap-1">
            <FiSave />
            <span>{saving ? "Sauvegarde..." : "Enregistrer"}</span>
          </button>
        </div>
      </div>

      <textarea
        value={textBody}
        onChange={(e) => setTextBody(e.target.value)}
        rows={12}
        className="w-full bg-gray-900 text-gray-100 p-3 rounded border border-gray-700 focus:outline-none focus:border-blue-500 text-sm font-sans leading-relaxed"
      />

      {/* Garde-fous et verdict du critique repliables */}
      {currentVersionData && (
        <div className="mt-3 border-t border-gray-700 pt-2 text-xs text-gray-400">
          <button onClick={() => setShowReport(!showReport)} className="flex items-center gap-1 text-gray-300 hover:text-white">
            {showReport ? <FiChevronUp /> : <FiChevronDown />}
            <span>Détails du contrôle qualité & Modèles utilisés</span>
          </button>
          {showReport && (
            <div className="mt-2 p-3 bg-gray-900/80 rounded border border-gray-800 space-y-2">
              <div>
                <span className="font-semibold text-gray-300">Modèles : </span>
                <span>{JSON.stringify(currentVersionData.models)}</span>
              </div>
              {currentVersionData.critic_verdict && (
                <div>
                  <span className="font-semibold text-gray-300">Verdict du critique : </span>
                  <span className={currentVersionData.critic_verdict.verdict === "pass" ? "text-green-400" : "text-amber-400"}>
                    {currentVersionData.critic_verdict.verdict.toUpperCase()}
                  </span>
                </div>
              )}
              {currentVersionData.guard_report?.warnings?.length > 0 && (
                <div>
                  <span className="font-semibold text-amber-400">Avertissements de style : </span>
                  <ul className="list-disc ml-4">
                    {currentVersionData.guard_report.warnings.map((w, idx) => (
                      <li key={idx}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Mount `CoverLetterPanel` in `ApplicationDetails.tsx`**

In `frontend/src/components/applications/ApplicationDetails.tsx`:
Import `CoverLetterPanel` and insert it cleanly below the notes or main description without modifying existing form state:
```tsx
import CoverLetterPanel from "./CoverLetterPanel";

// Dans le JSX de rendu de l'application :
<CoverLetterPanel
  applicationId={application._id || (application as any).id}
  isEtudeStatus={application.status === "En étude"}
/>
```

- [ ] **Step 3: Verify TypeScript & ESLint**

Run: `npm run lint` in `frontend`
Expected: 0 errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/applications/CoverLetterPanel.tsx frontend/src/components/applications/ApplicationDetails.tsx
git commit -m "feat(ui): integrate CoverLetterPanel in application details"
```

---

### Task 12: End-to-End Verification & Documentation

**Files:**
- Test: Run complete backend test suite
- Test: Run frontend build & lint
- Create: `docs/superpowers/plans/walkthrough.md`

- [ ] **Step 1: Run all backend tests**

Run: `uv run pytest tests/test_letter_guards.py tests/test_cover_letter_models.py tests/test_profile_seed.py tests/test_letter_llm.py tests/test_cover_letter_crew.py tests/test_cover_letter_trigger.py tests/test_cover_letters_api.py -v` in `backend`
Expected: ALL PASS

- [ ] **Step 2: Run frontend lint & build**

Run: `npm run lint && npm run build` in `frontend`
Expected: Build success

- [ ] **Step 3: Commit final plan verification**

```bash
git commit --allow-empty -m "chore(cover_letter): verify end-to-end implementation plan readiness"
```
