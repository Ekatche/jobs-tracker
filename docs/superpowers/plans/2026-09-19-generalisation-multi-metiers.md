# Généralisation multi-métiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'application (collecte d'offres, évaluation Two-Pass, profil, CV adapté) fonctionnelle pour n'importe quel métier, pas seulement tech/data/IA, sans régression pour les profils tech existants.

**Architecture:** Suppression chirurgicale du gate de domaine codé en dur (`is_relevant_position`) côté collecte ; ajout d'un pré-filtre de cohérence métier par similarité d'embedding + garde-fou LLM complémentaire côté évaluation ; neutralisation du wording tech-only dans `merge.py`, le frontend et le prompt de CV adapté.

**Tech Stack:** FastAPI + Motor (MongoDB) côté backend, React/TypeScript (Next.js) côté frontend, `litellm` pour LLM/embeddings, `pytest` + `pytest-asyncio` + `unittest.mock` pour les tests.

**Spec:** `docs/superpowers/specs/2026-09-19-generalisation-multi-metiers-design.md`

## Global Constraints

- Pas de migration de renommage de champ en base (`stack` reste `stack`) — relabelling UI/prompts uniquement.
- Pas de nouveaux connecteurs d'import de profil.
- Pas de refonte i18n/multi-langue.
- Pas de changement du modèle `CandidatePreferences`/`CandidateProfile` au-delà de l'ajout de `BlocA.domain_mismatch`.
- `is_off_domain_url`, `OFF_DOMAIN_URL_SLUGS`, `RELEVANCE_KEYWORDS`, `RELEVANCE_FILTER_ENABLED` restent inchangés — ce garde-fou est scopé BTP et corrige un bug de production réel indépendant de cette généralisation.
- `DEFAULT_QUERIES` (fallback tech de `job_offers_collectors.py`) reste inchangé.
- Seuil du pré-filtre embedding : `DOMAIN_RELEVANCE_THRESHOLD = 0.30`, conservateur (biaisé vers laisser passer).
- Toutes les commandes de test s'exécutent depuis `backend/` : `cd backend && python -m pytest <chemin> -v`.

---

### Task 1: Supprimer le gate de domaine `is_relevant_position` de `relevance.py`

**Files:**
- Modify: `backend/app/services/relevance.py:131-136`
- Modify: `backend/tests/test_relevance.py`

**Interfaces:**
- Consumes: rien (module pur, aucune dépendance externe).
- Produces: `relevance.py` n'exporte plus `is_relevant_position`. `contains_keyword`, `normalize_text`, `is_off_domain_url`, `RELEVANCE_KEYWORDS`, `OFF_DOMAIN_URL_SLUGS`, `RELEVANCE_FILTER_ENABLED` restent exportés à l'identique, consommés par la Task 2.

- [ ] **Step 1: Retirer les tests de `is_relevant_position` et son import**

Dans `backend/tests/test_relevance.py`, remplacer :

```python
from app.services.relevance import (
    contains_keyword,
    is_off_domain_url,
    is_relevant_position,
    normalize_text,
    RELEVANCE_KEYWORDS,
)
```

par :

```python
from app.services.relevance import (
    contains_keyword,
    is_off_domain_url,
    normalize_text,
    RELEVANCE_KEYWORDS,
)
```

Puis supprimer entièrement ces deux blocs (le paramétrage `test_is_relevant_position` et le test de régression associé) :

```python
@pytest.mark.parametrize(
    "title,expected",
    [
        # Cas réels de production — postes hors-domaine rejetés à tort avant ce plan.
        ("Référent Bureau d'Études Acier (H/F)", False),
        ("Ingénieur Calcul de Structure (H/F)", False),
        ("Ingénieur(e) structure", False),
        ("Responsable Calculs Mécaniques Défense - Nucléaire (H/F)", False),
        ("Ingénieur calcul de structures métalliques et charpentes (H/F)", False),
        # Postes pertinents (data / IA / ML), doivent passer.
        ("Data analyste - CDD", True),
        ("Tech lead IA", True),
        ("Machine Learning Engineer", True),
        ("Ingénieur MLOps", True),
        ("Data Scientist Senior", True),
        # Titre vide.
        ("", False),
    ],
)
def test_is_relevant_position(title, expected):
    assert is_relevant_position(title) is expected


def test_word_boundary_no_false_positive_on_specialiste():
    """Régression la plus probable : "ia" ne doit pas matcher dans "spécialiste"."""
    assert is_relevant_position("Spécialiste sécurité") is False
```

Les tests `TestNormalizeText`, `test_is_off_domain_url`, `test_host_does_not_influence_verdict` et `test_contains_keyword_requires_word_boundary` restent inchangés.

- [ ] **Step 2: Supprimer `is_relevant_position` de `relevance.py`**

Dans `backend/app/services/relevance.py`, supprimer :

```python
def is_relevant_position(title: str) -> bool:
    """True si l'intitulé de poste appartient au domaine cible (data/IA/ML).

    Un titre vide retourne False.
    """
    return contains_keyword(title, RELEVANCE_KEYWORDS)


```

(le bloc se trouve entre `contains_keyword()` et `_url_path()`). Ne rien changer d'autre dans le fichier.

- [ ] **Step 3: Lancer la suite de tests du module**

Run: `cd backend && python -m pytest tests/test_relevance.py -v`
Expected: PASS — 6 tests restants (`TestNormalizeText` ×2, `test_is_off_domain_url` ×4 paramétrés, `test_host_does_not_influence_verdict`, `test_contains_keyword_requires_word_boundary`), 0 erreur d'import.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/relevance.py backend/tests/test_relevance.py
git commit -m "refactor(relevance): remove hardcoded data/AI domain gate on job titles"
```

---

### Task 2: Retirer l'appel à `is_relevant_position` dans le pipeline de collecte

**Files:**
- Modify: `backend/app/tasks/job_offers_collectors.py:27-31,240,309-314,380-383`

**Interfaces:**
- Consumes: Task 1 (`relevance.py` n'exporte plus `is_relevant_position`).
- Produces: `enrich_offers()` garde son interface `async def enrich_offers(offers: list, query: str) -> list` inchangée ; `get_urls_for_query()` et son usage de `is_off_domain_url`/`RELEVANCE_FILTER_ENABLED` restent identiques.

- [ ] **Step 1: Retirer l'import de `is_relevant_position`**

Remplacer :

```python
from app.services.relevance import (
    RELEVANCE_FILTER_ENABLED,
    is_off_domain_url,
    is_relevant_position,
)
```

par :

```python
from app.services.relevance import (
    RELEVANCE_FILTER_ENABLED,
    is_off_domain_url,
)
```

- [ ] **Step 2: Retirer le compteur `off_domain_count` et le bloc de filtrage**

Dans `enrich_offers`, supprimer la ligne d'initialisation :

```python
        off_domain_count = 0
```

(elle se trouve juste après `invalid_count = 0`).

Puis supprimer le bloc de filtrage juste après le rejet des offres invalides :

```python
                    if RELEVANCE_FILTER_ENABLED and not is_relevant_position(poste):
                        logger.warning(
                            f"🚫 Offre hors-domaine rejetée: poste='{poste}' (requête: '{query}')"
                        )
                        off_domain_count += 1
                        continue

```

- [ ] **Step 3: Nettoyer le message de log final**

Remplacer :

```python
        logger.info(
            f"✅ {len(enriched_offers)} offres enrichies selon le modèle MongoDB "
            f"({invalid_count} invalides, {off_domain_count} hors-domaine)"
        )
```

par :

```python
        logger.info(
            f"✅ {len(enriched_offers)} offres enrichies selon le modèle MongoDB "
            f"({invalid_count} invalides)"
        )
```

- [ ] **Step 4: Vérifier qu'aucun test existant ne référence ce comportement**

Run: `cd backend && python -m pytest tests/test_job_offers_collectors_queries.py -v`
Expected: PASS — ce fichier ne teste ni `is_relevant_position` ni `off_domain_count` (vérifié : aucune occurrence dans le fichier).

- [ ] **Step 5: Commit**

```bash
git add backend/app/tasks/job_offers_collectors.py
git commit -m "refactor(collectors): stop rejecting offers via the data/AI title gate"
```

---

### Task 3: Ajouter `BlocA.domain_mismatch` et l'intégrer au calcul du score

**Files:**
- Modify: `backend/app/models.py:399-405`
- Modify: `backend/app/services/evaluation/evaluator.py:57-58`
- Test: `backend/tests/test_offer_evaluation.py`

**Interfaces:**
- Produces: `BlocA` gagne un champ `domain_mismatch: bool = False`, consommé par la Task 5 (construction du bloc) et par `calculate_evaluation_score`.

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `backend/tests/test_offer_evaluation.py`, juste après `test_calculate_evaluation_score_red_flag_caps` :

```python
def test_calculate_evaluation_score_domain_mismatch_caps():
    bloc_a = BlocA(archetype="Data Scientist", domain_mismatch=True)
    bloc_b = BlocB(matched_requirements=[], missing_requirements=[])
    bloc_g = BlocG(is_ghost_job=False, is_scam_risk=False)
    assert calculate_evaluation_score(bloc_a, bloc_b, bloc_g) == 1.5
```

- [ ] **Step 2: Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && python -m pytest tests/test_offer_evaluation.py::test_calculate_evaluation_score_domain_mismatch_caps -v`
Expected: FAIL — `BlocA` n'a pas de champ `domain_mismatch` (`ValidationError` ou `TypeError` selon la config Pydantic).

- [ ] **Step 3: Ajouter le champ au modèle**

Dans `backend/app/models.py`, remplacer :

```python
class BlocA(BaseModel):
    summary: str = ""
    archetype: str = ""
    red_flags: List[str] = Field(default_factory=list)
    geo_mismatch: bool = False
    visa_sponsoring_refused: bool = False
    notes: Optional[str] = None
```

par :

```python
class BlocA(BaseModel):
    summary: str = ""
    archetype: str = ""
    red_flags: List[str] = Field(default_factory=list)
    geo_mismatch: bool = False
    visa_sponsoring_refused: bool = False
    domain_mismatch: bool = False
    notes: Optional[str] = None
```

- [ ] **Step 4: Étendre le cap déterministe dans `calculate_evaluation_score`**

Dans `backend/app/services/evaluation/evaluator.py`, remplacer :

```python
    if bloc_a.geo_mismatch or bloc_a.visa_sponsoring_refused or bloc_g.is_ghost_job or bloc_g.is_scam_risk:
        return 1.5
```

par :

```python
    if (
        bloc_a.geo_mismatch
        or bloc_a.visa_sponsoring_refused
        or bloc_a.domain_mismatch
        or bloc_g.is_ghost_job
        or bloc_g.is_scam_risk
    ):
        return 1.5
```

- [ ] **Step 5: Lancer le test pour vérifier qu'il passe**

Run: `cd backend && python -m pytest tests/test_offer_evaluation.py -v`
Expected: PASS — tous les tests, y compris le nouveau et les 4 tests bout-en-bout existants (`domain_mismatch` a une valeur par défaut `False`, donc ils ne sont pas affectés par ce Task).

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/services/evaluation/evaluator.py backend/tests/test_offer_evaluation.py
git commit -m "feat(evaluation): add domain_mismatch cap to BlocA scoring"
```

---

### Task 4: Créer le module `domain_relevance.py` (pré-filtre embedding)

**Files:**
- Create: `backend/app/services/evaluation/domain_relevance.py`
- Test: `backend/tests/test_domain_relevance.py`

**Interfaces:**
- Consumes: `cosine_similarity` de `app.services.role_normalizer` (signature existante : `cosine_similarity(v1: list[float], v2: list[float]) -> float`).
- Produces:
  - `DOMAIN_RELEVANCE_THRESHOLD: float = 0.30`
  - `build_candidate_identity(headline: str, target_roles: List[str]) -> str`
  - `async def compute_domain_relevance(candidate_identity: str, offer_title: str) -> Optional[float]` — fail-open (retourne `None` sur entrée vide ou erreur), consommé par la Task 5.

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `backend/tests/test_domain_relevance.py` :

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.evaluation.domain_relevance import (
    DOMAIN_RELEVANCE_THRESHOLD,
    build_candidate_identity,
    compute_domain_relevance,
)


def test_build_candidate_identity_joins_headline_and_roles():
    assert build_candidate_identity("Animatrice 2D", ["Animatrice 2D", "Motion designer"]) == \
        "Animatrice 2D Animatrice 2D Motion designer"


def test_build_candidate_identity_ignores_empty_parts():
    assert build_candidate_identity("", ["", "Animatrice 2D", None]) == "Animatrice 2D"


def test_build_candidate_identity_all_empty_returns_empty_string():
    assert build_candidate_identity("", []) == ""


@pytest.mark.asyncio
async def test_compute_domain_relevance_empty_input_returns_none():
    assert await compute_domain_relevance("", "Data Scientist") is None
    assert await compute_domain_relevance("Animatrice 2D", "") is None


@pytest.mark.asyncio
async def test_compute_domain_relevance_similar_roles_high_score():
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [1.0, 0.0]}, {"embedding": [0.95, 0.05]}]

    with patch("litellm.aembedding", AsyncMock(return_value=fake_resp)):
        score = await compute_domain_relevance("Data Engineer", "Senior Data Engineer")

    assert score is not None
    assert score > DOMAIN_RELEVANCE_THRESHOLD


@pytest.mark.asyncio
async def test_compute_domain_relevance_unrelated_roles_low_score():
    fake_resp = MagicMock()
    fake_resp.data = [{"embedding": [1.0, 0.0]}, {"embedding": [0.0, 1.0]}]

    with patch("litellm.aembedding", AsyncMock(return_value=fake_resp)):
        score = await compute_domain_relevance("Animatrice 2D", "Data Scientist / Machine Learning Engineer")

    assert score is not None
    assert score < DOMAIN_RELEVANCE_THRESHOLD


@pytest.mark.asyncio
async def test_compute_domain_relevance_fails_open_on_exception():
    with patch("litellm.aembedding", AsyncMock(side_effect=Exception("quota exceeded"))):
        score = await compute_domain_relevance("Animatrice 2D", "Data Scientist")

    assert score is None
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/test_domain_relevance.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.services.evaluation.domain_relevance'`.

- [ ] **Step 3: Créer le module**

Créer `backend/app/services/evaluation/domain_relevance.py` :

```python
"""Pré-filtre de cohérence métier entre le profil candidat et une offre.

Réutilise l'infrastructure d'embeddings de app.services.role_normalizer
(text-embedding-3-small + cosine_similarity) pour écarter, avant le coût
du Two-Pass LLM complet, une offre manifestement hors du domaine du
candidat (ex: profil animatrice face à une offre Data Scientist).
"""

import logging
from typing import List, Optional

from app.services.role_normalizer import cosine_similarity

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"

# Seuil de départ conservateur (biaisé vers laisser passer plutôt que
# rejeter) — cf. section Risques du spec
# docs/superpowers/specs/2026-09-19-generalisation-multi-metiers-design.md.
DOMAIN_RELEVANCE_THRESHOLD = 0.30


def build_candidate_identity(headline: str, target_roles: List[str]) -> str:
    """Construit le texte identitaire du candidat pour comparaison d'embedding.

    Concatène le headline et les rôles ciblés ; les entrées vides sont ignorées.
    """
    parts = [headline] + list(target_roles or [])
    return " ".join(p.strip() for p in parts if p and p.strip())


async def compute_domain_relevance(candidate_identity: str, offer_title: str) -> Optional[float]:
    """Similarité cosinus entre l'identité candidat et l'intitulé de l'offre.

    Fail-open : retourne None si l'un des deux textes est vide, ou si l'appel
    d'embedding échoue (timeout, quota, erreur réseau). L'appelant doit alors
    traiter l'absence de score comme "ne pas court-circuiter l'évaluation",
    jamais comme un mismatch.
    """
    if not candidate_identity.strip() or not offer_title.strip():
        return None

    try:
        from litellm import aembedding

        resp = await aembedding(model=EMBEDDING_MODEL, input=[candidate_identity, offer_title])
        data = resp.data if hasattr(resp, "data") else resp["data"]

        def _extract(item):
            return item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", item["embedding"])

        emb_candidate = _extract(data[0])
        emb_offer = _extract(data[1])
        return cosine_similarity(emb_candidate, emb_offer)
    except Exception as e:
        logger.warning(
            f"⚠️ Erreur pré-filtre de cohérence métier (candidat='{candidate_identity}', "
            f"offre='{offer_title}'): {e}, fail-open (pas de court-circuit)"
        )
        return None
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && python -m pytest tests/test_domain_relevance.py -v`
Expected: PASS — 8 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/evaluation/domain_relevance.py backend/tests/test_domain_relevance.py
git commit -m "feat(evaluation): add embedding-based domain relevance pre-filter"
```

---

### Task 5: Brancher le pré-filtre et le garde-fou `domain_coherence` dans `evaluate_offer_two_pass`

**Files:**
- Modify: `backend/app/services/evaluation/evaluator.py`
- Modify: `backend/tests/test_offer_evaluation.py`

**Interfaces:**
- Consumes: `DOMAIN_RELEVANCE_THRESHOLD`, `build_candidate_identity`, `compute_domain_relevance` de la Task 4 ; `BlocA.domain_mismatch` de la Task 3.
- Produces: `evaluate_offer_two_pass` garde exactement sa signature (`async def evaluate_offer_two_pass(db, user_id, offer_id, model=None) -> OfferEvaluation`) ; le comportement de court-circuit et le champ `domain_coherence` du Pass 2 sont internes, non exposés à l'appelant.

- [ ] **Step 1: Importer le nouveau module dans `evaluator.py`**

Remplacer :

```python
from app.services.usage_tracker import record_api_usage, require_user_quota
```

par :

```python
from app.services.evaluation.domain_relevance import (
    DOMAIN_RELEVANCE_THRESHOLD,
    build_candidate_identity,
    compute_domain_relevance,
)
from app.services.usage_tracker import record_api_usage, require_user_quota
```

- [ ] **Step 2: Calculer le pré-filtre juste après la récupération du profil candidat**

Remplacer :

```python
    candidate_languages = profile_doc.get("languages", [])

    start_time = time.time()
    input_tokens_total = 0
    output_tokens_total = 0

    # ==========================================
    # PASS 1 : Analyse de l'offre seule
    # ==========================================
    pass1_prompt = f"""Tu es un analyste expert en recrutement technique.
```

par :

```python
    candidate_languages = profile_doc.get("languages", [])

    candidate_target_roles = (
        candidate_preferences.get("target_roles", [])
        if isinstance(candidate_preferences, dict)
        else []
    )
    candidate_identity = build_candidate_identity(candidate_headline, candidate_target_roles)
    domain_similarity = await compute_domain_relevance(candidate_identity, job_title)
    domain_mismatch_prefilter = (
        domain_similarity is not None and domain_similarity < DOMAIN_RELEVANCE_THRESHOLD
    )
    if domain_mismatch_prefilter:
        logger.info(
            f"🚫 Offre '{job_title}' écartée par le pré-filtre de cohérence métier "
            f"(similarité={domain_similarity:.3f} < seuil={DOMAIN_RELEVANCE_THRESHOLD})"
        )

    start_time = time.time()
    input_tokens_total = 0
    output_tokens_total = 0

    # ==========================================
    # PASS 1 : Analyse de l'offre seule
    # ==========================================
    pass1_prompt = f"""Tu es un analyste expert en recrutement.
```

Note : le module ne définissait pas encore `logger` avant cette ligne — il est déjà défini en tête de fichier (`logger = logging.getLogger(__name__)`), aucun ajout requis.

- [ ] **Step 3: Court-circuiter le Two-Pass LLM quand le pré-filtre déclenche**

Remplacer le bloc qui va de l'appel `acompletion` du Pass 1 jusqu'au calcul de `latency_ms` (juste avant `# Construction des Blocs & Calcul du Score`) :

```python
    response_pass1 = await acompletion(
        model=eval_model,
        messages=[{"role": "user", "content": pass1_prompt}],
        response_format={"type": "json_object"},
        temperature=0.1,
        drop_params=True,
    )

    if hasattr(response_pass1, "usage") and response_pass1.usage:
        input_tokens_total += getattr(response_pass1.usage, "prompt_tokens", 0)
        output_tokens_total += getattr(response_pass1.usage, "completion_tokens", 0)

    pass1_data = _clean_json_output(response_pass1.choices[0].message.content)
```

par :

```python
    if domain_mismatch_prefilter:
        pass1_data = {
            "archetype": job_title,
            "summary": "",
            "is_ghost_job": False,
            "is_scam_risk": False,
            "ghost_job_warnings": [],
        }
    else:
        response_pass1 = await acompletion(
            model=eval_model,
            messages=[{"role": "user", "content": pass1_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            drop_params=True,
        )

        if hasattr(response_pass1, "usage") and response_pass1.usage:
            input_tokens_total += getattr(response_pass1.usage, "prompt_tokens", 0)
            output_tokens_total += getattr(response_pass1.usage, "completion_tokens", 0)

        pass1_data = _clean_json_output(response_pass1.choices[0].message.content)
```

Puis, plus bas, remplacer le bloc allant de la construction de `candidate_context` jusqu'au calcul de `latency_ms` :

```python
    candidate_context = {
```

... (tout le bloc jusqu'à) ...

```python
    pass2_data = _clean_json_output(response_pass2.choices[0].message.content)
    latency_ms = int((time.time() - start_time) * 1000)
```

par (le contenu de `candidate_context`, `pass2_prompt` et l'appel `acompletion` restent identiques, seule leur exécution devient conditionnelle — voir Step 4 pour le contenu neutralisé de `pass2_prompt`) :

```python
    if domain_mismatch_prefilter:
        pass2_data = {
            "domain_coherence": "mismatch",
            "geo_mismatch": False,
            "visa_sponsoring_refused": False,
            "red_flags": [],
            "matched_requirements": [],
            "missing_requirements": [],
            "score_justification": (
                "Offre écartée par le pré-filtre de cohérence métier : le métier de "
                "l'offre ne correspond pas au profil du candidat."
            ),
        }
    else:
        candidate_context = {
            "headline": candidate_headline,
            "summary": candidate_summary,
            "preferences": candidate_preferences,
            "skills": candidate_skills,
            "experiences": [
                {
                    "role": exp.get("role"),
                    "company": exp.get("company"),
                    "start": exp.get("start"),
                    "end": exp.get("end"),
                    "stack": exp.get("stack", []),
                    "missions": exp.get("missions", []),
                }
                for exp in candidate_experiences
            ],
            "education": [
                {
                    "school": edu.get("school"),
                    "degree": edu.get("degree"),
                    "years": edu.get("years"),
                    "topics": edu.get("topics", []),
                }
                for edu in candidate_education
            ],
            "projects": [
                {
                    "name": proj.get("name"),
                    "description": proj.get("description"),
                    "stack": proj.get("stack", []),
                    "context": proj.get("context"),
                    "url": proj.get("url"),
                    "repo": proj.get("repo"),
                    "highlights": proj.get("highlights", []),
                }
                for proj in candidate_projects
            ],
            "certifications": [
                {
                    "name": cert.get("name"),
                    "issuer": cert.get("issuer"),
                    "year": cert.get("year"),
                    "topics": cert.get("topics", []),
                }
                for cert in candidate_certifications
            ],
            "languages": candidate_languages,
        }

        pass2_prompt = f"""Tu es l'évaluateur de matching Career-Ops.
Tu disposes de l'analyse préalable de l'offre (Pass 1) et du profil complet du candidat (expériences, formations/diplômes, projets concrets/réalisations, certifications, compétences et préférences).

OFFRE ANALYSÉE (Pass 1) :
{json.dumps(pass1_data, ensure_ascii=False, indent=2)}

LOCALISATION OFFRE : {location} | MODE DE TRAVAIL OFFRE : {work_mode}

PROFIL COMPLET DU CANDIDAT :
{json.dumps(candidate_context, ensure_ascii=False, indent=2)}

CONSIGNES STRICTES :
1. Cohérence métier (Bloc A) :
   - Compare le métier réel de l'offre (voir "archetype") au métier réel du candidat (headline, expériences, préférences) — pas seulement les compétences isolées.
   - Renseigne "domain_coherence" : "match" si le métier de l'offre correspond au métier du candidat, "partial" si recoupement partiel légitime (ex: rôle hybride), "mismatch" si le métier de l'offre n'a manifestement rien à voir avec celui du candidat.
2. Bloc A (Drapeaux Rouges) :
   - Vérifie s'il y a un geo-mismatch (ex: offre sur site à Paris alors que le candidat veut du remote complet à Lyon).
   - Vérifie si le sponsoring de visa est explicitement refusé alors que le candidat en a besoin.
3. Bloc B (Match Exigences) :
   - Pour chaque exigence de l'offre (diplôme requis, compétences, années d'expérience, outils, langues), cherche une preuve tangible dans le profil complet du candidat (expériences professionnelles, formations/diplômes, projets/réalisations, certifications, compétences, langues).
   - RÈGLE DIPLÔME : Si l'offre exige un diplôme particulier (ex: Bac+5, Master, diplôme d'ingénieur ou équivalent) dans un domaine donné, inspecte attentivement la section "education" : un diplôme ou une spécialisation validée dans le MÊME domaine que celui demandé par l'offre constitue un statut "full_match" (evidence_tier: "stated").
   - RÈGLE DU VERBATIM : Pour chaque match, tu DOIS obligatoirement fournir la citation exacte ('verbatim_quote') issue de l'offre.
   - RÈGLE DE LA PREUVE : pour chaque match, indique 'evidence_tier' :
     - "stated" : le profil mentionne explicitement ce diplôme, ce poste, cette compétence, ce projet ou cette mission.
     - "inferred" : tu déduis la compétence sans mention explicite (ex: "a fait du Kubernetes" déduit de "a géré une infra cloud").
     Une preuve "inferred" ne peut JAMAIS à elle seule justifier un statut "full_match" sur une exigence 'critical' ou 'high' — descends-la en "partial_match" dans ce cas.
   - Liste les exigences manquantes ('missing_requirements') avec leur niveau de criticité et la raison factuelle.
4. Rédige une brève justification du score.

Réponds STRICTEMENT au format JSON avec cette structure :
{{{{
  "domain_coherence": "match" | "partial" | "mismatch",
  "geo_mismatch": false,
  "visa_sponsoring_refused": false,
  "red_flags": ["string"],
  "matched_requirements": [
    {{{{
      "requirement": "string",
      "weight": "critical" | "high" | "meaningful",
      "candidate_evidence": "preuve dans le CV/profil",
      "verbatim_quote": "citation exacte issue de l'offre",
      "status": "full_match" | "partial_match",
      "evidence_tier": "stated" | "inferred"
    }}}}
  ],
  "missing_requirements": [
    {{{{
      "requirement": "string",
      "weight": "critical" | "high" | "meaningful",
      "reason": "explication du manque",
      "impact_on_role": "conséquence sur le poste"
    }}}}
  ],
  "score_justification": "string"
}}}}"""

        response_pass2 = await acompletion(
            model=eval_model,
            messages=[{"role": "user", "content": pass2_prompt}],
            response_format={"type": "json_object"},
            temperature=0.1,
            drop_params=True,
        )

        if hasattr(response_pass2, "usage") and response_pass2.usage:
            input_tokens_total += getattr(response_pass2.usage, "prompt_tokens", 0)
            output_tokens_total += getattr(response_pass2.usage, "completion_tokens", 0)

        pass2_data = _clean_json_output(response_pass2.choices[0].message.content)

    latency_ms = int((time.time() - start_time) * 1000)
```

**Attention aux accolades JSON** : dans le nouveau `pass2_prompt`, chaque accolade littérale du schéma JSON doit être doublée (`{{{{` / `}}}}`) car ce bloc reste à l'intérieur d'un f-string Python — exactement comme dans le prompt original (vérifier que le nombre d'accolades doublées correspond à celles déjà présentes dans le fichier avant modification).

- [ ] **Step 4: Mapper `domain_coherence` vers `BlocA.domain_mismatch`**

Remplacer :

```python
    bloc_a = BlocA(
        summary=pass1_data.get("summary", ""),
        archetype=pass1_data.get("archetype", job_title),
        red_flags=pass2_data.get("red_flags", []),
        geo_mismatch=bool(pass2_data.get("geo_mismatch", False)),
        visa_sponsoring_refused=bool(pass2_data.get("visa_sponsoring_refused", False)),
    )
```

par :

```python
    domain_mismatch = domain_mismatch_prefilter or (pass2_data.get("domain_coherence") == "mismatch")

    bloc_a = BlocA(
        summary=pass1_data.get("summary", ""),
        archetype=pass1_data.get("archetype", job_title),
        red_flags=pass2_data.get("red_flags", []),
        geo_mismatch=bool(pass2_data.get("geo_mismatch", False)),
        visa_sponsoring_refused=bool(pass2_data.get("visa_sponsoring_refused", False)),
        domain_mismatch=domain_mismatch,
    )
```

- [ ] **Step 5: Patcher les 4 tests bout-en-bout existants pour mocker le pré-filtre**

Ces tests appellent `evaluate_offer_two_pass` réellement (pas seulement `calculate_evaluation_score`) et n'ont jamais mocké `litellm.aembedding` — sans patch, `compute_domain_relevance` tenterait un vrai appel réseau. Dans `backend/tests/test_offer_evaluation.py`, ajouter un patch de `compute_domain_relevance` retournant `None` (fail-open, comportement identique à avant ce plan) à chacun des 4 tests suivants.

a) Ajouter l'import en tête de fichier, juste après les imports existants de `app.services.evaluation.evaluator` :

```python
from app.services.evaluation.evaluator import (
    _clean_json_output,
    calculate_evaluation_score,
    evaluate_offer_two_pass,
)
```

reste inchangé (on patche par chemin de chaîne, pas par import direct).

b) Dans `test_evaluate_offer_two_pass_success`, remplacer :

```python
    with patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
        evaluation = await evaluate_offer_two_pass(
```

par :

```python
    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
        evaluation = await evaluate_offer_two_pass(
```

c) Dans `test_evaluate_endpoint_and_get_evaluation`, remplacer :

```python
        with patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
```

par :

```python
        with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
             patch("app.services.evaluation.evaluator.acompletion", AsyncMock(side_effect=[pass1_response, pass2_response])):
```

d) Dans `test_evaluate_offer_candidate_profile_lookup_supports_objectid_and_str`, remplacer :

```python
    with patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
```

par :

```python
    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
```

e) Dans `test_evaluate_offer_pass2_receives_education_and_projects`, remplacer :

```python
    with patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
```

par :

```python
    with patch("app.services.evaluation.evaluator.compute_domain_relevance", AsyncMock(return_value=None)), \
         patch("app.services.evaluation.evaluator.acompletion", side_effect=[mock_p1, mock_p2]) as mock_acompletion:
```

- [ ] **Step 6: Écrire un test du court-circuit par pré-filtre**

Ajouter dans `backend/tests/test_offer_evaluation.py`, à la fin du fichier :

```python
@pytest.mark.asyncio
async def test_evaluate_offer_two_pass_short_circuits_on_domain_mismatch():
    """Une offre manifestement hors du domaine du candidat est écartée sans appel LLM Two-Pass."""
    db = MagicMock()
    job_offers_col = AsyncMock()
    job_offers_col.find_one.return_value = {
        "_id": ObjectId(TEST_OFFER_ID),
        "poste": "Data Scientist / Machine Learning Engineer",
        "entreprise": "Excelleria",
        "description": "Poste data science avec Python, TensorFlow et Spark.",
        "localisation": "Lyon",
        "type_contrat": "CDI",
        "mode_travail": "hybride",
    }
    job_offers_col.update_one.return_value = MagicMock(modified_count=1)

    candidate_profile_col = AsyncMock()
    candidate_profile_col.find_one.return_value = {
        "user_id": TEST_USER_ID,
        "headline": "Animatrice 2D",
        "summary": "Animatrice 2D spécialisée en motion design.",
        "skills": {"outils": ["Toon Boom Harmony", "After Effects"]},
        "experiences": [{"role": "Animatrice 2D", "company": "Studio Anim", "stack": []}],
        "preferences": {"target_roles": ["Animatrice 2D"]},
    }

    offer_evaluations_col = AsyncMock()
    offer_evaluations_col.update_one.return_value = MagicMock(upserted_id="eval_anim")

    users_col = AsyncMock()
    users_col.find_one.return_value = {"_id": ObjectId(TEST_USER_ID), "tier": "free"}

    async def mock_cursor(*args, **kwargs):
        if False:
            yield {}

    api_usage_col = AsyncMock()
    api_usage_col.aggregate = MagicMock(side_effect=lambda *a, **k: mock_cursor())
    api_usage_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))

    def db_getitem(name):
        mapping = {
            "job_offers": job_offers_col,
            "candidate_profile": candidate_profile_col,
            "offer_evaluations": offer_evaluations_col,
            "users": users_col,
            "api_usage": api_usage_col,
        }
        return mapping.get(name, AsyncMock())

    db.__getitem__.side_effect = db_getitem

    with patch(
        "app.services.evaluation.evaluator.compute_domain_relevance",
        AsyncMock(return_value=0.05),
    ), patch("app.services.evaluation.evaluator.acompletion") as mock_acompletion:
        evaluation = await evaluate_offer_two_pass(
            db=db,
            user_id=TEST_USER_ID,
            offer_id=TEST_OFFER_ID,
        )

    mock_acompletion.assert_not_called()
    assert evaluation.score == 1.5
    assert evaluation.bloc_a.domain_mismatch is True
    job_offers_col.update_one.assert_called_once()
    offer_evaluations_col.update_one.assert_called_once()
```

- [ ] **Step 7: Lancer toute la suite d'évaluation pour vérifier qu'elle passe**

Run: `cd backend && python -m pytest tests/test_offer_evaluation.py tests/test_domain_relevance.py -v`
Expected: PASS — tous les tests, y compris les 4 tests bout-en-bout patchés et le nouveau test de court-circuit.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/evaluation/evaluator.py backend/tests/test_offer_evaluation.py
git commit -m "feat(evaluation): short-circuit Two-Pass on domain mismatch, neutralize prompt wording"
```

---

### Task 6: Neutraliser le fallback de headline dans `merge.py`

**Files:**
- Modify: `backend/app/services/profile/merge.py:58-68`
- Modify: `backend/tests/test_profile_merge.py:333`

**Interfaces:**
- Consumes: rien de nouveau.
- Produces: `_derive_headline` garde sa signature (`_derive_headline(experiences, summary, skills) -> str`), consommée uniquement par `build_profile_from_sources` dans le même fichier.

- [ ] **Step 1: Mettre à jour le test qui capture l'heuristique IA à retirer**

Dans `backend/tests/test_profile_merge.py`, dans `test_headline_derived_automatically_when_missing`, remplacer :

```python
    sources_with_role_only = {
        "cv": {
            "experiences": [{"company": "A", "role": "Data Engineer", "start": "2025-01"}],
            "skills": {"ia": ["RAG", "Machine Learning"]},
        }
    }
    profile2, _ = build_profile_from_sources(sources_with_role_only)
    assert profile2["headline"] == "Data Engineer & AI Specialist"
```

par :

```python
    sources_with_role_only = {
        "cv": {
            "experiences": [{"company": "A", "role": "Data Engineer", "start": "2025-01"}],
            "skills": {"ia": ["RAG", "Machine Learning"]},
        }
    }
    profile2, _ = build_profile_from_sources(sources_with_role_only)
    assert profile2["headline"] == "Data Engineer"
```

Ajouter également, à la fin du fichier, un test couvrant le nouveau fallback vide :

```python
def test_headline_fallback_is_empty_string_without_summary_or_experience():
    """Sans résumé ni expérience, le fallback ne doit plus être un intitulé tech codé en dur."""
    profile, _ = build_profile_from_sources({"manual": {"skills": {}}})
    assert profile["headline"] == ""
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && python -m pytest tests/test_profile_merge.py -v -k "headline"`
Expected: FAIL sur les deux tests — `_derive_headline` retourne encore `"Data Engineer & AI Specialist"` et `"Ingénieur Data & IA"`.

- [ ] **Step 3: Neutraliser `_derive_headline`**

Remplacer :

```python
    if experiences:
        top_role = (experiences[0].get("role") or "").strip()
        if top_role:
            lower_role = top_role.lower()
            all_skills = [s.lower() for cat in skills.values() for s in cat]
            has_ai = any(kw in all_skills for kw in ("rag", "machine learning", "ia", "deep learning", "llm"))
            if has_ai and "ia" not in lower_role and "ai" not in lower_role and "ml" not in lower_role and "machine learning" not in lower_role:
                return f"{top_role} & AI Specialist"
            return top_role

    return "Ingénieur Data & IA"
```

par :

```python
    if experiences:
        top_role = (experiences[0].get("role") or "").strip()
        if top_role:
            return top_role

    return ""
```

Le paramètre `skills` de `_derive_headline` n'est plus utilisé dans le corps de la fonction mais doit être conservé dans la signature (appelé positionnellement par `build_profile_from_sources` à la ligne `headline = _derive_headline(experiences, summary or "", skills)`).

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && python -m pytest tests/test_profile_merge.py -v`
Expected: PASS — tous les tests du fichier.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/profile/merge.py backend/tests/test_profile_merge.py
git commit -m "refactor(profile): remove hardcoded AI headline fallback and heuristic"
```

---

### Task 7: Neutraliser les libellés et placeholders tech-only dans `CandidateProfileSection.tsx`

**Files:**
- Modify: `frontend/src/components/profile/CandidateProfileSection.tsx:1110,1158,1163,1175,1271,1276`

**Interfaces:**
- Consumes: rien (changements de texte statique uniquement, aucune signature de composant ou de prop modifiée).
- Produces: rien de nouveau consommé ailleurs.

- [ ] **Step 1: Neutraliser le placeholder du rôle d'expérience**

Remplacer :

```tsx
                        placeholder="ex: Senior Data Engineer"
```

par (dans le bloc "Poste / Rôle" d'une expérience, ligne ~1110) :

```tsx
                        placeholder="ex: Chef de Projet, Animatrice 2D, Data Engineer"
```

- [ ] **Step 2: Renommer le label "Technologies / Stack" d'une expérience**

Remplacer :

```tsx
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Technologies / Stack (séparées par virgule)</label>
```

par :

```tsx
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Outils & compétences (séparés par virgule)</label>
```

- [ ] **Step 3: Neutraliser le placeholder de la stack d'expérience**

Remplacer :

```tsx
                      placeholder="Python, Spark, Airflow, Azure"
```

par :

```tsx
                      placeholder="Python, Illustrator, Gestion de projet, Anglais courant"
```

- [ ] **Step 4: Neutraliser le placeholder des missions/réalisations**

Remplacer :

```tsx
                      placeholder={"Déploiement de pipelines de données temps réel sous Databricks\nOptimisation des requêtes SQL et réduction des temps de calcul de 35%\nMise en place du monitoring des modèles de Machine Learning"}
```

par :

```tsx
                      placeholder={"Pilotage d'un projet transverse avec réduction des délais de 30%\nCoordination d'une équipe de 5 personnes\nMise en place d'un nouveau processus qualité"}
```

- [ ] **Step 5: Renommer le label "Stack technique" d'un projet**

Remplacer :

```tsx
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Stack technique (séparée par virgule)</label>
```

par :

```tsx
                    <label className="text-[10px] text-slate-400 font-medium block mb-0.5">Outils & compétences (séparés par virgule)</label>
```

- [ ] **Step 6: Neutraliser le placeholder de la stack d'un projet**

Remplacer :

```tsx
                      placeholder="React, FastAPI, PostgreSQL"
```

par :

```tsx
                      placeholder="React, FastAPI, PostgreSQL / ou : Storyboard, Animation 2D, After Effects"
```

- [ ] **Step 7: Vérifier visuellement dans le navigateur**

Run: `cd frontend && npm run dev`, ouvrir la page de profil candidat, passer en mode édition, vérifier que les nouveaux labels ("Outils & compétences") et placeholders s'affichent correctement sur les sections Expériences et Projets, sans erreur de compilation TypeScript/JSX.
Expected: rendu correct, aucune régression visuelle, aucune erreur console.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/profile/CandidateProfileSection.tsx
git commit -m "refactor(profile-ui): neutralize tech-only labels and placeholders"
```

---

### Task 8: Neutraliser la copie tech-only de `CvDropzone.tsx` et `onboarding/page.tsx`

**Files:**
- Modify: `frontend/src/components/profile/CvDropzone.tsx:135-137,179-182`
- Modify: `frontend/src/app/onboarding/page.tsx:293-296,387-389`

**Interfaces:**
- Consumes: rien.
- Produces: rien de nouveau consommé ailleurs.

- [ ] **Step 1: Neutraliser la description sous le titre de `CvDropzone.tsx`**

Remplacer :

```tsx
            <p className="text-xs text-slate-400 mt-1">
              Déposez votre CV au format PDF. Notre moteur IA extrait automatiquement vos expériences,
              projets et compétences techniques.
            </p>
```

par :

```tsx
            <p className="text-xs text-slate-400 mt-1">
              Déposez votre CV au format PDF. Notre moteur IA extrait automatiquement vos expériences,
              projets et compétences.
            </p>
```

- [ ] **Step 2: Neutraliser le message affiché pendant le traitement**

Remplacer :

```tsx
            <p className="text-xs text-slate-400 max-w-md">
              Traitement par les agents LLM (normalisation des dates, déduplication et mapping de
              la stack technique).
            </p>
```

par :

```tsx
            <p className="text-xs text-slate-400 max-w-md">
              Traitement par les agents LLM (normalisation des dates, déduplication et mapping des
              compétences).
            </p>
```

- [ ] **Step 3: Neutraliser la description de l'étape 2 dans `onboarding/page.tsx`**

Remplacer :

```tsx
                <p className="text-sm text-gray-400 mt-1">
                  Chargez votre CV au format PDF. Le parseur multi-modal (Mistral VLM + LLM) extrait automatiquement
                  vos expériences, stacks techniques, réalisations et formations.
                </p>
```

par :

```tsx
                <p className="text-sm text-gray-400 mt-1">
                  Chargez votre CV au format PDF. Le parseur multi-modal (Mistral VLM + LLM) extrait automatiquement
                  vos expériences, compétences, réalisations et formations.
                </p>
```

- [ ] **Step 4: Neutraliser la description du connecteur Website**

Remplacer :

```tsx
                    <p className="text-xs text-gray-400 mb-3">
                      Crawl profond avec navigation interne pour extraire vos projets, articles et réalisations.
                    </p>
```

Vérifier d'abord que cette description n'est pas déjà neutre : elle l'est (aucune mention "technique"). Ne pas la modifier. Modifier uniquement la phrase d'accroche du panneau "Présence Web & Finalisation" un peu plus haut :

```tsx
                <p className="text-sm text-gray-400 mt-1">
                  Connectez vos profils publics pour consolider vos réalisations techniques réelles.
                </p>
```

par :

```tsx
                <p className="text-sm text-gray-400 mt-1">
                  Connectez vos profils publics pour consolider vos réalisations concrètes.
                </p>
```

- [ ] **Step 5: Vérifier visuellement dans le navigateur**

Run: `cd frontend && npm run dev`, parcourir le flow d'onboarding (étapes 2 et 3) et la zone de dépôt de CV du profil candidat.
Expected: la nouvelle copie s'affiche sans erreur, aucune régression du flow d'upload/import.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/profile/CvDropzone.tsx frontend/src/app/onboarding/page.tsx
git commit -m "refactor(onboarding-ui): neutralize tech-only copy"
```

---

### Task 9: Neutraliser les catégories de compétences imposées dans `tailor_prompt.md`

**Files:**
- Modify: `backend/app/llm/prompts/cv/tailor_prompt.md:47`

**Interfaces:**
- Consumes: rien.
- Produces: rien — fichier de prompt texte, consommé au runtime par le service de génération de CV adapté (aucun changement de schéma JSON, `prioritized_skills[].category` reste une chaîne libre).

- [ ] **Step 1: Vérifier l'absence de test snapshot sur ce fichier**

Run: `cd backend && grep -rl "tailor_prompt" tests/ || echo "aucun test ne charge ce fichier"`
Expected: aucun test ne dépend du contenu exact de `tailor_prompt.md` (fichier de prompt chargé au runtime, pas testé unitairement) — confirmer avant de modifier.

- [ ] **Step 2: Remplacer les exemples de catégories tech-only**

Remplacer :

```markdown
5. **COMPÉTENCES GROUPÉES (prioritized_skills)** :
   - Structure les compétences en 2 à 4 catégories cohérentes (ex: "Backend & Microservices", "Cloud & DevOps", "Data & IA", "Frontend & UI").
   - Mets en tête de liste les compétences requises par l'offre que le candidat possède réellement.
```

par :

```markdown
5. **COMPÉTENCES GROUPÉES (prioritized_skills)** :
   - Structure les compétences en 2 à 4 catégories cohérentes et pertinentes pour le métier réel du candidat (déduis les catégories du profil et de l'offre — ne force AUCUNE catégorie type "Data & IA" si le candidat exerce un autre métier).
   - Mets en tête de liste les compétences requises par l'offre que le candidat possède réellement.
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/llm/prompts/cv/tailor_prompt.md
git commit -m "docs(prompts): let tailored CV skill categories follow the candidate's actual domain"
```

---

## Self-Review

**Couverture du spec :**
- Phase 1 (collecte) → Tasks 1-2. ✅
- Phase 2 (évaluateur : pré-filtre embedding + `domain_coherence` + neutralisation wording) → Tasks 3-5. ✅
- Phase 3 (merge.py) → Task 6. ✅
- Phase 4 (frontend labels/copie) → Tasks 7-8. `TargetingPreferencesSection.tsx` confirmé déjà générique (non modifié, conforme au spec). Parité visuelle GitHub/Website dans l'onboarding vérifiée déjà satisfaite par lecture directe du code (`onboarding/page.tsx:411-497`, deux formulaires au style et à la structure identiques) — aucune tâche nécessaire sur ce point précis, contrairement à l'hypothèse initiale du spec. ✅
- Phase 5 (CV adapté) → Task 9. Vérification `ResumeCard.tsx`/`ResumePreviewModal.tsx` effectuée : aucune occurrence du mot "technologies" affichée littéralement à l'utilisateur — le point de vigilance noté dans le spec est résolu sans action. ✅
- Plan de test du spec (scénario animatrice, non-régression tech) → couvert par `test_evaluate_offer_two_pass_short_circuits_on_domain_mismatch` (Task 5) et les tests de `domain_relevance.py` (Task 4) sur des paires rôle/offre similaires vs non-reliées. ✅

**Scan de placeholders :** aucun "TBD"/"TODO" — chaque step contient le code exact à écrire ou la commande exacte à lancer.

**Cohérence des types/signatures :**
- `BlocA.domain_mismatch: bool = False` (Task 3) utilisé identiquement dans `calculate_evaluation_score` (Task 3) et dans la construction du bloc en Task 5.
- `compute_domain_relevance(candidate_identity: str, offer_title: str) -> Optional[float]` (Task 4) appelé avec ces mêmes noms de paramètres positionnels en Task 5.
- `build_candidate_identity(headline: str, target_roles: List[str]) -> str` (Task 4) appelé avec `(candidate_headline, candidate_target_roles)` en Task 5 — types compatibles (`candidate_headline: str`, `candidate_target_roles: list` extrait de `candidate_preferences.get("target_roles", [])`).
- Patch de test `app.services.evaluation.evaluator.compute_domain_relevance` (Task 5) cible bien le nom importé dans `evaluator.py` (import nommé ajouté au Step 1 de la Task 5), pas `app.services.evaluation.domain_relevance.compute_domain_relevance`.
