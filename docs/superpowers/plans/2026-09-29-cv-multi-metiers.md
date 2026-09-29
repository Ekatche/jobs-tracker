# CV adapté multi-métiers : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** rendre le CV adapté crédible pour un profil RH, Marketing ou opérationnel (cariste, préparateur de commandes…), sans régression pour les profils tech.

**Architecture :** le métier est déduit par le LLM, donc aucune branche de code par métier. Le travail se répartit en 3 couches :
- **Données :** 2 nouveaux contextes de projet, avec une normalisation unique dans `app/models.py` que réutilisent le parseur et le collecteur. `contact.mobility` et `contact.availability` sont des clés libres du dict `contact`.
- **Prompts :** consignes neutres et quotas proportionnés à la pertinence (tailor), et routage des habilitations vers `certifications` (parseur).
- **Rendu :** extraction de `_build_candidate` dans `routers/resumes.py`, puis ajout de 4 éléments dans les 2 modèles Jinja : portfolio, ligne mobilité, centres d'intérêt et section « Certifications & habilitations » remontée.

**Tech Stack :** FastAPI, Pydantic v2, Jinja2, litellm, pytest (`uv run pytest`), Next.js/TypeScript.

**Spec :** `docs/superpowers/specs/2026-09-29-cv-multi-metiers-design.md`

## Global Constraints

- Aucun changement de `TailoredCVSchema`, aucune migration de base.
- Contextes de projet admis, exactement : `perso`, `client`, `recherche`, `consortium`, `associatif`, `evenement`. Toute valeur inconnue retombe sur `perso`.
- Synonymes :
  - `associatif`, `association`, `asso`, `bénévolat`, `benevolat`, `volunteer` → `associatif` ;
  - `evenement`, `événement`, `event`, `salon` → `evenement`.
- Libellés visibles dans les modèles : « Compétences » (jamais « Compétences Techniques »), « Certifications & habilitations », « Centres d'intérêt ».
- Séparateur de la ligne mobilité et disponibilités : `" · "`.
- `tailor_prompt.md` passe par `str.format()` : toute accolade littérale ajoutée doit être doublée (`{{ }}`). Le prompt texte de `parse_cv_with_llm` est une f-string, avec la même règle.
- Ne jamais écrire « Centres d'intérêt », « Compétences Techniques » ni « 🌐 » dans un commentaire HTML des modèles : les tests vérifient leur absence dans le HTML rendu.
- **Commits :** `git add` avec la liste explicite des fichiers de la tâche, jamais `git add -A` ni `git add .`. L'arbre de travail contient des modifications de l'utilisateur à ne pas toucher : `backend/app/llm/utils.py`, `backend/app/services/ats/router.py`, `backend/job_trackers/**`, `backend/tests/test_ats_parsers.py`, `backend/tests/test_cover_letter_crew.py`, `backend/tests/test_letter_llm.py`, `frontend/src/app/applications/page.tsx`, `frontend/src/app/offers/page.tsx`, `NewApplicationModal.tsx`, `Header.tsx`, `.mcp.json`, `docs/micro/plans/20260923-evaluation-blocs-abg-fit/*.json`.
- Les commits se terminent par `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Échecs préexistants connus, hors périmètre : `test_get_interview_prep_empty` et `test_update_user_tier` (ServerSelectionTimeoutError vers l'hôte `mongodb:27017`).

## Review Focus

1. **Portfolio identique au GitHub à une forme d'URL près** (`https://github.com/x` et `github.com/x/`) : le lien 🌐 ne doit pas apparaître en doublon. Test dans la tâche 4.
2. **Mobilité ou disponibilités vides ou faites d'espaces** : l'UI sauvegarde `""` quand le champ est vide. Aucune ligne `cv-mobility` vide ni « · » orphelin ne doit apparaître. Tests dans les tâches 4 et 5.
3. **Contexte saisi avec accent ou majuscule** (`Événement`, `Bénévolat`) : il doit être normalisé et non ramené à `perso`. Tests dans les tâches 1 et 2.
4. **`contact` renvoyé par le LLM du parseur sous forme de chaîne** au lieu d'un objet : sans garde, `merge.py` plante sur `.items()`. Le nettoyage doit supprimer la clé. Test dans la tâche 2.
5. **CV sans certification ni centre d'intérêt** (cas fréquent chez un profil tech junior) : aucun titre de section vide. Tests dans la tâche 5.

---

### Task 1 : normalisation unique des contextes de projet

**Files :**
- Modify : `backend/app/models.py:493-517` (`CandidateProject`)
- Create : `backend/tests/test_project_context.py`

**Interfaces :**
- Produces :
  - `PROJECT_CONTEXTS: tuple[str, ...]`, les 6 valeurs ;
  - `normalize_project_context(value: Any) -> str`, qui renvoie toujours l'une de `PROJECT_CONTEXTS`.

  Les deux sont importés par les tâches 2 (`cv_parser.py`, `website.py`).

- [ ] **Step 1 : écrire les tests qui échouent**

`backend/tests/test_project_context.py` :

```python
import pytest

from app.models import PROJECT_CONTEXTS, CandidateProject, normalize_project_context


def test_project_contexts_lists_the_six_values():
    assert set(PROJECT_CONTEXTS) == {
        "perso", "client", "recherche", "consortium", "associatif", "evenement",
    }


@pytest.mark.parametrize("raw,expected", [
    ("associatif", "associatif"),
    ("Association", "associatif"),
    ("asso", "associatif"),
    ("Bénévolat", "associatif"),
    ("benevolat", "associatif"),
    ("volunteer", "associatif"),
    ("evenement", "evenement"),
    ("Événement", "evenement"),
    ("event", "evenement"),
    ("salon", "evenement"),
    ("  Client ", "client"),
    ("research", "recherche"),
    ("consortium", "consortium"),
    ("personal", "perso"),
])
def test_normalize_project_context_maps_synonyms(raw, expected):
    assert normalize_project_context(raw) == expected


@pytest.mark.parametrize("raw", ["stage", "freelance", "", None, 42])
def test_normalize_project_context_falls_back_to_perso(raw):
    assert normalize_project_context(raw) == "perso"


def test_candidate_project_accepts_new_contexts():
    assert CandidateProject(name="Forum emploi", context="Événement").context == "evenement"
    assert CandidateProject(name="Restos du cœur", context="bénévolat").context == "associatif"
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && uv run pytest tests/test_project_context.py -v`
Expected : ERROR à la collecte, `ImportError: cannot import name 'PROJECT_CONTEXTS'`.

- [ ] **Step 3 : implémenter**

Dans `backend/app/models.py`, juste avant `class CandidateProject(BaseModel):`, ajouter :

```python
PROJECT_CONTEXTS = ("perso", "client", "recherche", "consortium", "associatif", "evenement")

_PROJECT_CONTEXT_SYNONYMS = {
    "perso": "perso", "personal": "perso",
    "client": "client", "professionnel": "client", "pro": "client",
    "entreprise": "client", "work": "client", "job": "client",
    "recherche": "recherche", "research": "recherche",
    "consortium": "consortium",
    "associatif": "associatif", "association": "associatif", "asso": "associatif",
    "bénévolat": "associatif", "benevolat": "associatif", "volunteer": "associatif",
    "evenement": "evenement", "événement": "evenement", "event": "evenement", "salon": "evenement",
}


def normalize_project_context(value: Any) -> str:
    """Ramène une valeur libre à l'un des PROJECT_CONTEXTS ; repli sur "perso"."""
    if isinstance(value, str):
        return _PROJECT_CONTEXT_SYNONYMS.get(value.strip().lower(), "perso")
    return "perso"
```

Dans `CandidateProject`, remplacer le champ et le validateur :

```python
    context: Literal["perso", "client", "recherche", "consortium", "associatif", "evenement"] = "perso"
```

```python
    @field_validator("context", mode="before")
    @classmethod
    def normalize_context(cls, v: Any) -> str:
        return normalize_project_context(v)
```

- [ ] **Step 4 : vérifier le succès et l'absence de régression**

Run : `cd backend && uv run pytest tests/test_project_context.py tests/test_profile_merge.py tests/test_profile_endpoints.py -v`
Expected : tout PASS.

- [ ] **Step 5 : commit**

```bash
git add backend/app/models.py backend/tests/test_project_context.py
git commit -m "feat(profil): contextes de projet associatif et evenement

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2 : parseur de CV et collecteur de site

**Files :**
- Modify : `backend/app/services/cv_parser.py`, aux endroits suivants :
  - imports ;
  - `PROFILE_JSON_SCHEMA` vers la ligne 49 ;
  - `_clean_parsed_cv` lignes 127-150 ;
  - prompt VLM lignes 196-231 ;
  - prompt texte lignes 305-326.
- Modify : `backend/app/services/profile/collectors/website.py:48-66` et prompt ligne 220.
- Test : `backend/tests/test_cv_vlm_parser.py`, `backend/tests/test_profile_collectors.py`

**Interfaces :**
- Consumes : `normalize_project_context(value: Any) -> str`, depuis `app.models` (tâche 1).
- Produces :
  - la sortie du parseur peut contenir `contact: {"mobility": str, "availability": str}`, sans clé vide ;
  - `merge.py:526` la fusionne déjà.

- [ ] **Step 1 : écrire les tests qui échouent**

Dans `backend/tests/test_cv_vlm_parser.py` :
- ajouter `MagicMock` à l'import : `from unittest.mock import AsyncMock, MagicMock, patch` ;
- ajouter `_clean_parsed_cv` à l'import depuis `app.services.cv_parser` ;
- puis ajouter en fin de fichier :

```python
def test_clean_parsed_cv_maps_new_project_contexts():
    data = _clean_parsed_cv({"projects": [
        {"name": "Restos du cœur", "context": "Bénévolat"},
        {"name": "Salon de l'emploi", "context": "salon"},
        {"name": "Stage", "context": "stage"},
    ]})
    assert [p["context"] for p in data["projects"]] == ["associatif", "evenement", "perso"]


def test_clean_parsed_cv_keeps_non_empty_mobility_and_availability():
    data = _clean_parsed_cv({"contact": {"mobility": " Permis B, véhiculé ", "availability": "", "phone": None}})
    assert data["contact"] == {"mobility": "Permis B, véhiculé"}


def test_clean_parsed_cv_drops_contact_that_is_not_an_object():
    data = _clean_parsed_cv({"contact": "Permis B"})
    assert "contact" not in data


@pytest.mark.asyncio
async def test_parse_cv_with_llm_prompt_routes_habilitations_and_mobility():
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content='{"headline": "Préparateur de commandes"}'))]
    with patch("app.services.cv_parser.acompletion", new_callable=AsyncMock, return_value=mock_resp) as mock_llm:
        await parse_cv_with_llm(cv_text="Jean Martin\nCACES R489 cat. 1, 3, 5\nPermis B")

    prompt = mock_llm.call_args.kwargs["messages"][0]["content"]
    assert "CACES" in prompt
    assert "mobility" in prompt and "availability" in prompt
    assert "associatif" in prompt
```

Dans `backend/tests/test_profile_collectors.py`, ajouter `_coerce_project_contexts` à l'import depuis `app.services.profile.collectors.website`, puis :

```python
def test_coerce_project_contexts_maps_synonyms_before_fallback():
    payload = {"projects": [
        {"name": "A", "context": "association"},
        {"name": "B", "context": "Événement"},
        {"name": "C", "context": "stage"},
        {"name": "D"},
    ]}
    _coerce_project_contexts(payload)
    assert [p["context"] for p in payload["projects"]] == ["associatif", "evenement", "perso", "perso"]
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && uv run pytest tests/test_cv_vlm_parser.py tests/test_profile_collectors.py -k "clean_parsed_cv or prompt_routes or coerce_project" -v`
Expected : 5 FAIL.
- contextes : `perso` au lieu de `associatif` ;
- contact : échec d'égalité, car `contact` n'est pas nettoyé (il garde `availability: ""` et `phone: None`) ;
- contact en chaîne : la clé est toujours présente ;
- prompt : `"CACES" in prompt` est faux ;
- collecteur : `perso` au lieu de `associatif`.

- [ ] **Step 3 : implémenter dans `cv_parser.py`**

Import (après `from litellm import acompletion`) :

```python
from app.models import normalize_project_context
```

`PROFILE_JSON_SCHEMA` : dans `"projects"`, remplacer la description du contexte par
`{"type": "string", "description": "perso, client, recherche, consortium, associatif ou evenement"}`.
Puis ajouter la propriété suivante juste avant `"skills"` :

```python
        "contact": {
            "type": "object",
            "properties": {
                "mobility": {"type": "string", "description": "Permis, véhicule ou zone de mobilité (ex: 'Permis B, véhiculé')"},
                "availability": {"type": "string", "description": "Disponibilité et horaires acceptés (ex: 'Disponible immédiatement · 2x8, nuit')"}
            }
        },
```

Dans `_clean_parsed_cv`, remplacer le bloc `ctx = …` / `if … else` des projets par :

```python
            if isinstance(p, dict):
                p["context"] = normalize_project_context(p.get("context"))
```

Puis, juste avant le traitement `raw_interests`, ajouter :

```python
    raw_contact = data.get("contact")
    if isinstance(raw_contact, dict):
        data["contact"] = {
            k: str(v).strip() for k, v in raw_contact.items()
            if v is not None and str(v).strip()
        }
    elif "contact" in data:
        data.pop("contact")
```

Prompt VLM (`instruction_text`, chaîne non formatée) :
- dans `"projects"`, remplacer `"context": "perso",` par `"context": "perso | client | recherche | consortium | associatif | evenement",` ;
- après la ligne `- "interests": …`, ajouter :

```
- "contact": {"mobility": "Permis, véhicule ou zone de mobilité, seulement si mentionnés", "availability": "Disponibilité et horaires acceptés (ex: 2x8, nuit, week-end), seulement si mentionnés"}
```

- sous `Consignes importantes :`, ajouter en première puce :

```
- Les titres réglementaires et habilitations — CACES (avec les catégories, ex: 'CACES R489 cat. 1, 3, 5'), permis de conduire (B, C, CE…), SST, habilitations électriques, FIMO/FCO — vont dans "certifications", jamais dans "skills".
```

Prompt texte de `parse_cv_with_llm` (f-string, **aucune accolade**) :
- remplacer `context ("perso" ou "client")` par `context (une valeur parmi "perso", "client", "recherche", "consortium", "associatif", "evenement")` ;
- remplacer la ligne `'certifications'` par :

```
- 'certifications': liste d'objets avec name, issuer, year. Les titres réglementaires et habilitations — CACES (avec les catégories, ex: 'CACES R489 cat. 1, 3, 5'), permis de conduire (B, C, CE…), SST, habilitations électriques, FIMO/FCO — vont ici, jamais dans 'skills'.
```

- après la ligne `'interests'`, ajouter :

```
- 'contact': objet avec 'mobility' (permis, véhicule, zone de mobilité) et 'availability' (disponibilité, horaires acceptés comme 2x8, nuit, week-end), renseignés seulement si le CV les mentionne.
```

- [ ] **Step 4 : implémenter dans `website.py`**

Ajouter l'import `from app.models import normalize_project_context` à côté de `from app.services.profile.urls import …`. Remplacer ensuite le commentaire, `_VALID_PROJECT_CONTEXTS` et `_coerce_project_contexts` par :

```python
def _coerce_project_contexts(payload: Dict[str, Any]) -> None:
    """Ramène le `context` de chaque projet à une valeur admise par
    `CandidateProject.context` (synonymes compris, repli sur "perso").

    Le prompt énumère les valeurs admises, mais un prompt n'est pas une
    garantie. Sans cette coercition, une valeur hors énumération (ex.
    "personnel", "freelance") fait échouer `CandidateProfile.model_validate`
    dans `_store_source` et retourne 502 sur l'import du site — la source la
    plus riche du profil. Modifie `payload` en place.
    """
    for project in payload.get("projects", []) or []:
        project["context"] = normalize_project_context(project.get("context"))
```

Prompt ligne 220 : remplacer `"context" (une valeur EXACTE parmi: "perso", "client", "recherche", "consortium")` par `"context" (une valeur EXACTE parmi: "perso", "client", "recherche", "consortium", "associatif", "evenement")`.

Vérifier que `_VALID_PROJECT_CONTEXTS` n'est plus référencé : `rtk grep -rn "_VALID_PROJECT_CONTEXTS" backend` ne doit rien renvoyer.

- [ ] **Step 5 : vérifier le succès**

Run : `cd backend && uv run pytest tests/test_cv_vlm_parser.py tests/test_profile_collectors.py tests/test_profile_endpoints.py -v`
Expected : tout PASS, y compris `test_website_import_with_invalid_project_context_is_coerced_to_perso`.

- [ ] **Step 6 : commit**

```bash
git add backend/app/services/cv_parser.py backend/app/services/profile/collectors/website.py backend/tests/test_cv_vlm_parser.py backend/tests/test_profile_collectors.py
git commit -m "feat(profil): habilitations, mobilité et nouveaux contextes dans le parseur et le collecteur

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3 : prompt du CV adapté neutre et proportionné

**Files :**
- Modify : `backend/app/llm/prompts/cv/tailor_prompt.md`, sections 3 à 6, ajout des sections 8 et 9, placeholders du JSON.
- Test : `backend/tests/test_cv_tailor.py`

**Interfaces :**
- Consumes : `load_tailor_prompt(profile, offer, evaluation) -> str`, inchangé.
- Produces : aucun contrat de code ; texte de prompt seulement.

- [ ] **Step 1 : écrire le test qui échoue**

Ajouter à `backend/tests/test_cv_tailor.py` :

```python
def test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas():
    from app.services.cv_tailor import load_tailor_prompt

    prompt = load_tailor_prompt(SAMPLE_PROFILE, SAMPLE_OFFER, SAMPLE_EVALUATION)

    assert "vocabulaire technique" not in prompt
    assert "vocabulaire métier" in prompt
    assert "colis ou lignes par heure" in prompt
    assert "délai de recrutement" in prompt
    assert "4 à 5 bullet points" in prompt
    assert "1 à 2 bullet points" in prompt
    assert "0 à 3 projets" in prompt
    assert "CACES" in prompt
    assert "Une page A4" in prompt
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && uv run pytest tests/test_cv_tailor.py::test_load_tailor_prompt_covers_non_tech_trades_and_relevance_quotas -v`
Expected : FAIL sur `assert "vocabulaire technique" not in prompt`.

- [ ] **Step 3 : réécrire les sections du prompt**

Dans `tailor_prompt.md`, section 3 (ACCROCHE), ajouter en dernière puce :

```
   - Les exigences de poids `critical` de l'analyse Bloc B guident la première phrase de l'accroche, dans la limite de ce que le profil prouve.
```

Remplacer toute la section 4 par :

```
4. **EXPÉRIENCES PROFESSIONNELLES** :
   - Déduis le métier réel du candidat à partir de son profil et de l'offre, et écris dans le vocabulaire métier correspondant.
   - Nombre de bullet points proportionné à la pertinence pour l'offre :
     - expérience qui couvre des exigences `critical` ou `high` de l'analyse Bloc B : 4 à 5 bullet points, en commençant par ceux qui prouvent ces exigences ;
     - expérience annexe : 1 à 2 bullet points. Conserve-la pour ne pas créer de trou dans le parcours ; ne la supprime jamais.
   - Formule les bullet points avec des verbes d'action et, quand le profil les fournit, des résultats quantifiés propres au métier. Exemples par famille :
     - tech : latence, volume de données, disponibilité ;
     - RH : délai de recrutement, nombre de recrutements, turnover ;
     - marketing : taux de conversion, audience, coût d'acquisition ;
     - logistique / terrain : cadence (colis ou lignes par heure), taux d'erreur, jours sans accident, tonnage.
     Ne retiens que les métriques du métier réel du candidat. N'invente JAMAIS un chiffre absent du profil.
   - Réaligne le vocabulaire métier sur celui de l'offre si le candidat a effectivement exercé ces missions.
   - Pour un métier opérationnel ou manuel (logistique, production, bâtiment, conduite…), écris des phrases simples et concrètes, sans jargon de bureau.
   - Isole dans `relevant_technologies` les outils, logiciels, engins ou méthodes réellement utilisés à chaque poste d'après le profil (ex : SAP, chariot élévateur, scanner RF, Canva, Python).
```

Section 5 : remplacer la puce `Mets en tête de liste…` par :

```
   - Mets en tête de liste les compétences requises par l'offre que le candidat possède réellement, en commençant par celles liées aux exigences de poids `critical`.
```

Remplacer toute la section 6 par :

```
6. **PROJETS CLÉS (featured_projects)** :
   - Sélectionne 0 à 3 projets concrets du candidat démontrant sa capacité à délivrer sur les enjeux de l'offre. Les projets associatifs ou événementiels comptent au même titre que les projets professionnels.
   - Renvoie une liste vide si aucun projet n'est pertinent pour l'offre.
```

Après la section 7 (inchangée), ajouter :

```
8. **CERTIFICATIONS & HABILITATIONS (certifications)** :
   - Reprends uniquement les certifications et habilitations présentes dans le profil.
   - Si l'offre exige une habilitation (CACES, permis de conduire, SST, habilitation électrique, FIMO/FCO…) que le candidat possède, cite-la dans l'accroche et place-la en tête de `certifications`.

9. **LONGUEUR** :
   - Une page A4 pour un profil de moins de 5 ans d'expérience ou un métier opérationnel ; deux pages maximum sinon.
   - Pour tenir ce budget, réduis d'abord les expériences annexes, jamais les expériences pertinentes.
```

Dans le bloc JSON de sortie :
- remplacer `"relevant_technologies": ["Tech1", "Tech2"]` par `"relevant_technologies": ["Outil1", "Outil2"]` ;
- remplacer `"technologies": ["Tech1", "Tech2"]` par `"technologies": ["Outil1", "Outil2"]` ;
- ne toucher à aucune accolade.

- [ ] **Step 4 : vérifier le succès**

Run : `cd backend && uv run pytest tests/test_cv_tailor.py -v`
Expected : tout PASS. Le test appelle `template.format(...)` : un `KeyError` ou un `ValueError` signalerait une accolade non doublée.

- [ ] **Step 5 : commit**

```bash
git add backend/app/llm/prompts/cv/tailor_prompt.md backend/tests/test_cv_tailor.py
git commit -m "feat(cv): prompt du CV adapté multi-métiers et quotas proportionnés à la pertinence

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4 : `_build_candidate` dans le routeur des CV

**Files :**
- Modify : `backend/app/routers/resumes.py:211-229` (route `get_resume_pdf`) et ajout de fonctions après `_slugify`.
- Test : `backend/tests/test_resumes_api.py`

**Interfaces :**
- Produces : `_build_candidate(profile_doc: Dict[str, Any], user: UserModel) -> Dict[str, Any]`, qui renvoie les clés :
  - `full_name`, `email`, `phone`, `location`, `linkedin_url`, `github_url`, qui existaient déjà ;
  - `website_url: Optional[str]` ;
  - `mobility: Optional[str]` ;
  - `availability: Optional[str]` ;
  - `interests: List[str]`.

  La tâche 5 consomme ces clés dans les modèles.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter en fin de `backend/tests/test_resumes_api.py` :

```python
from app.routers.resumes import _build_candidate


def test_build_candidate_drops_website_identical_to_github():
    profile = {"contact": {"github": "https://github.com/jdupont", "website": "github.com/jdupont/"}}
    assert _build_candidate(profile, mock_current_user)["website_url"] is None


def test_build_candidate_keeps_distinct_portfolio():
    profile = {"contact": {"github": "https://github.com/jdupont", "website": "https://jdupont.fr"}}
    assert _build_candidate(profile, mock_current_user)["website_url"] == "https://jdupont.fr"


def test_build_candidate_exposes_mobility_availability_and_interests():
    profile = {
        "contact": {"mobility": " Permis B, véhiculé ", "availability": "   "},
        "interests": ["Football", " ", "Randonnée"],
    }
    candidate = _build_candidate(profile, mock_current_user)
    assert candidate["mobility"] == "Permis B, véhiculé"
    assert candidate["availability"] is None
    assert candidate["interests"] == ["Football", "Randonnée"]


def test_build_candidate_falls_back_to_user_identity():
    candidate = _build_candidate({}, mock_current_user)
    assert candidate["full_name"] == "testengineer"
    assert candidate["email"] == "test@example.com"
    assert candidate["website_url"] is None
    assert candidate["interests"] == []
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && uv run pytest tests/test_resumes_api.py -k build_candidate -v`
Expected : ERROR à la collecte, `ImportError: cannot import name '_build_candidate'`.

- [ ] **Step 3 : implémenter**

Dans `resumes.py`, après `_slugify` :

```python
def _normalize_url(url: Optional[str]) -> str:
    return re.sub(r"^https?://(www\.)?", "", (url or "").strip().lower()).rstrip("/")


def _clean_text(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _build_candidate(profile_doc: Dict[str, Any], user: UserModel) -> Dict[str, Any]:
    """Coordonnées et informations annexes du CV, lues dans le profil au moment du rendu."""
    contact_info = profile_doc.get("personal_info") or profile_doc.get("contact") or {}
    github_url = contact_info.get("github_url") or contact_info.get("github") or profile_doc.get("github_url")
    website_url = _clean_text(contact_info.get("website_url") or contact_info.get("website"))
    if website_url and _normalize_url(website_url) == _normalize_url(github_url):
        website_url = None

    return {
        "full_name": contact_info.get("full_name") or profile_doc.get("full_name") or user.username,
        "email": contact_info.get("email") or profile_doc.get("email") or user.email,
        "phone": contact_info.get("phone") or profile_doc.get("phone"),
        "location": contact_info.get("location") or profile_doc.get("location"),
        "linkedin_url": contact_info.get("linkedin_url") or contact_info.get("linkedin") or profile_doc.get("linkedin_url"),
        "github_url": github_url,
        "website_url": website_url,
        "mobility": _clean_text(contact_info.get("mobility")),
        "availability": _clean_text(contact_info.get("availability")),
        "interests": [str(i).strip() for i in (profile_doc.get("interests") or []) if str(i).strip()],
    }
```

Dans `get_resume_pdf`, remplacer le littéral `candidate = { … }` (lignes 218-225) par :

```python
    candidate = _build_candidate(profile_doc, current_user)
```

Garder la ligne `contact_info = …` : elle sert encore à `photo_url`.

- [ ] **Step 4 : vérifier le succès**

Run : `cd backend && uv run pytest tests/test_resumes_api.py -v`
Expected : tout PASS, y compris `test_get_resume_pdf_stream`. Ce test nécessite la Mongo de test sur le port 27018.

- [ ] **Step 5 : commit**

```bash
git add backend/app/routers/resumes.py backend/tests/test_resumes_api.py
git commit -m "feat(cv): portfolio, mobilité, disponibilités et centres d'intérêt transmis au rendu

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5 : modèles Sidebar Elegance et Executive Minimalist

**Files :**
- Modify : `backend/app/templates/cv/sidebar_elegance.html`, `<aside>` lignes 213-278 et `main-header` lignes 283-286.
- Modify : `backend/app/templates/cv/executive_minimalist.html`, en-tête lignes 140-151, compétences lignes 196-211, pied de page lignes 238-266.
- Test : `backend/tests/test_cv_templates.py`

**Interfaces :**
- Consumes : les clés `candidate.website_url`, `candidate.mobility`, `candidate.availability` et `candidate.interests` (tâche 4). Une clé absente vaut `Undefined` en Jinja, donc falsy : les anciens appels restent valides.
- Produces : l'élément HTML `class="cv-mobility"` et les titres `>Certifications & habilitations<`, `>Centres d'intérêt<`.

- [ ] **Step 1 : écrire les tests qui échouent**

Ajouter en fin de `backend/tests/test_cv_templates.py` :

```python
TEMPLATES = ["sidebar_elegance", "executive_minimalist"]


def _render(template, cv=SAMPLE_CV, **candidate_overrides):
    return render_cv_html(
        cv=cv,
        candidate={**SAMPLE_CANDIDATE, **candidate_overrides},
        template_name=template,
    )


@pytest.mark.parametrize("template", TEMPLATES)
def test_skills_title_is_trade_neutral(template):
    assert "Compétences Techniques" not in _render(template)


@pytest.mark.parametrize("template", TEMPLATES)
def test_interests_section_shown_only_when_filled(template):
    html = _render(template, interests=["Football", "Randonnée"])
    assert "Centres d'intérêt" in html
    assert "Randonnée" in html
    assert "Centres d'intérêt" not in _render(template, interests=[])
    assert "Centres d'intérêt" not in _render(template)


@pytest.mark.parametrize("template", TEMPLATES)
def test_portfolio_link_shown_only_when_set(template):
    assert "https://jeandupont.fr" in _render(template, website_url="https://jeandupont.fr")
    assert "🌐" not in _render(template, website_url=None)


@pytest.mark.parametrize("template", TEMPLATES)
def test_mobility_line_joins_filled_values(template):
    both = _render(template, mobility="Permis B, véhiculé", availability="2x8, nuit")
    assert "Permis B, véhiculé · 2x8, nuit" in both
    only_one = _render(template, mobility=None, availability="Disponible immédiatement")
    assert 'class="cv-mobility"' in only_one
    assert "· Disponible immédiatement" not in only_one
    assert 'class="cv-mobility"' not in _render(template, mobility=None, availability=None)


@pytest.mark.parametrize("template", TEMPLATES)
def test_certifications_section_before_formation(template):
    html = _render(template)
    assert "AWS Certified Solutions Architect" in html
    assert html.index(">Certifications & habilitations<") < html.index(">Formation<")


@pytest.mark.parametrize("template", TEMPLATES)
def test_certifications_section_hidden_when_empty(template):
    html = _render(template, cv=SAMPLE_CV.model_copy(update={"certifications": []}))
    assert "Certifications & habilitations" not in html


@pytest.mark.parametrize("template", TEMPLATES)
def test_projects_section_hidden_when_empty(template):
    html = _render(template, cv=SAMPLE_CV.model_copy(update={"featured_projects": []}))
    assert "Projets Clés" not in html


def test_sidebar_order_skills_certifications_languages_formation_interests():
    html = _render("sidebar_elegance", interests=["Football"])
    positions = [
        html.index(">Compétences Clés<"),
        html.index(">Certifications & habilitations<"),
        html.index(">Langues<"),
        html.index(">Formation<"),
        html.index(">Centres d'intérêt<"),
    ]
    assert positions == sorted(positions)


def test_executive_certifications_follow_skills_and_languages_stay_last():
    html = _render("executive_minimalist")
    assert html.index(">Compétences<") < html.index(">Certifications & habilitations<")
    assert html.index(">Certifications & habilitations<") < html.index(">Langues<")
    assert "Langues & Certifications" not in html
```

- [ ] **Step 2 : vérifier l'échec**

Run : `cd backend && uv run pytest tests/test_cv_templates.py -v`
Expected :
- FAIL : `skills_title` (executive), `interests`, `portfolio`, `mobility`, `certifications_before_formation`, `sidebar_order`, `executive_certifications` ;
- PASS déjà : `projects_section_hidden_when_empty` et `certifications_section_hidden_when_empty`. Ce sont des garde-fous de non-régression, conformément au risque noté dans le spec.

- [ ] **Step 3 : modifier `sidebar_elegance.html`**

Dans le bloc Contact, après la ligne `💻 {{ candidate.github_url }}` et son `{% endif %}`, ajouter :

```html
        {% if candidate.website_url %}
          <div class="contact-item">🌐 {{ candidate.website_url }}</div>
        {% endif %}
```

Déplacer le bloc `<!-- Certifications -->` juste après le bloc Compétences Clés (avant Langues) et renommer son titre :

```html
      <!-- Certifications -->
      {% if cv.certifications %}
      <div class="sidebar-block">
        <div class="sidebar-block-title">Certifications & habilitations</div>
        {% for cert in cv.certifications %}
          <div class="edu-item">
            <div class="edu-degree">{{ cert }}</div>
          </div>
        {% endfor %}
      </div>
      {% endif %}
```

Ordre final de l'`<aside>` : en-tête, Contact, Compétences Clés, Certifications & habilitations, Langues, Formation, puis le bloc suivant, ajouté juste avant `</aside>` :

```html
      <!-- Intérêts -->
      {% if candidate.interests %}
      <div class="sidebar-block">
        <div class="sidebar-block-title">Centres d'intérêt</div>
        {% for interest in candidate.interests %}
          <div class="contact-item">{{ interest }}</div>
        {% endfor %}
      </div>
      {% endif %}
```

Dans `<header class="main-header">`, après `<div class="main-role-title">…</div>`, ajouter :

```html
        {% if candidate.mobility or candidate.availability %}
        <div class="cv-mobility" style="font-size: 8.5pt; color: var(--color-slate-600); margin-top: 3px;">{{ [candidate.mobility, candidate.availability] | select | join(" · ") }}</div>
        {% endif %}
```

- [ ] **Step 4 : modifier `executive_minimalist.html`**

En-tête : après `<div class="exec-title">…</div>`, ajouter :

```html
        {% if candidate.mobility or candidate.availability %}
        <div class="cv-mobility" style="font-size: 8pt; color: var(--color-slate-600); margin-top: 2px;">{{ [candidate.mobility, candidate.availability] | select | join(" · ") }}</div>
        {% endif %}
```

Dans `exec-contact`, après la ligne `💻 {{ candidate.github_url }}`, ajouter :

```html
          {% if candidate.website_url %}<span class="exec-contact-item">🌐 {{ candidate.website_url }}</span>{% endif %}
```

Section Compétences : remplacer `<h2 class="section-title">Compétences Techniques</h2>` par `<h2 class="section-title">Compétences</h2>`. Juste après le `{% endif %}` qui ferme cette section (avant `<!-- Projets Clés -->`), ajouter :

```html
    <!-- Certifications -->
    {% if cv.certifications %}
    <section class="section-block">
      <h2 class="section-title">Certifications & habilitations</h2>
      {% for cert in cv.certifications %}
      <div style="font-size: 8pt; margin-bottom: 3px; color: var(--color-slate-700);">🏅 {{ cert }}</div>
      {% endfor %}
    </section>
    {% endif %}
```

Pied de page : remplacer toute la colonne `<!-- Langues & Certifications -->` (le `<div>` qui contient le titre « Langues & Certifications » et les deux boucles) par :

```html
      <!-- Langues et intérêts -->
      <div>
        {% if cv.languages %}
        <h2 class="section-title">Langues</h2>
        {% for lang in cv.languages %}
        <div style="font-size: 8pt; margin-bottom: 3px;">
          <strong>{{ lang.language }}</strong> : <span style="color: var(--color-slate-600);">{{ lang.level }}</span>
        </div>
        {% endfor %}
        {% endif %}
        {% if candidate.interests %}
        <h2 class="section-title" style="margin-top: 8px;">Centres d'intérêt</h2>
        <div style="font-size: 8pt; color: var(--color-slate-700);">{{ candidate.interests | join(" · ") }}</div>
        {% endif %}
      </div>
```

Relecture des libellés : `rtk grep -n "Technolog\|Stack\|Techniques" backend/app/templates/cv/` ne doit renvoyer aucun libellé visible. Les noms de variables Jinja comme `relevant_technologies` sont acceptés.

- [ ] **Step 5 : vérifier le succès**

Run : `cd backend && uv run pytest tests/test_cv_templates.py tests/test_cv_pdf_renderer.py -v`
Expected : tout PASS.

- [ ] **Step 6 : commit**

```bash
git add backend/app/templates/cv/sidebar_elegance.html backend/app/templates/cv/executive_minimalist.html backend/tests/test_cv_templates.py
git commit -m "feat(cv): sections habilitations, centres d'intérêt, portfolio et mobilité dans les modèles

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6 : UI du profil (contexte en liste, mobilité, disponibilités)

**Files :**
- Modify : `frontend/src/types/coverLetter.ts:22`
- Modify : `frontend/src/components/profile/CandidateProfileSection.tsx`, aux endroits suivants :
  - import icônes ligne 25 ;
  - états lignes 80-84 ;
  - `populateForm` lignes 118-122 ;
  - sauvegarde lignes 380-386 ;
  - affichage du contexte lignes 827-829 ;
  - champs de coordonnées après la ligne 1170 ;
  - champ Contexte lignes 1375-1382.

**Interfaces :**
- Consumes : l'API accepte déjà toute clé texte dans `contact` (`Dict[str, Optional[str]]`), et `context` est normalisé côté backend (tâche 1).
- Produces : `contact.mobility` et `contact.availability` sont persistés à chaque sauvegarde du profil.

Le frontend n'a pas de runner de tests unitaires. La vérification se fait par `tsc`, le lint et un contrôle manuel.

- [ ] **Step 1 : types**

`frontend/src/types/coverLetter.ts:22` :

```ts
  context?: "perso" | "client" | "recherche" | "consortium" | "associatif" | "evenement" | string;
```

- [ ] **Step 2 : options de contexte**

Dans `CandidateProfileSection.tsx`, après les imports et au niveau du module, ajouter :

```tsx
const PROJECT_CONTEXT_OPTIONS = [
  { value: "perso", label: "Perso" },
  { value: "client", label: "Client" },
  { value: "recherche", label: "Recherche" },
  { value: "consortium", label: "Consortium" },
  { value: "associatif", label: "Associatif" },
  { value: "evenement", label: "Événement" },
];
```

Remplacer l'`<input type="text" … placeholder="perso, client, recherche" …/>` du champ « Contexte » (vers la ligne 1376) par :

```tsx
                      <select
                        value={proj.context || "perso"}
                        onChange={(e) => handleUpdateProject(idx, "context", e.target.value)}
                        className="w-full text-xs rounded bg-slate-950 border border-gray-700 py-1.5 px-2.5 text-white"
                      >
                        {PROJECT_CONTEXT_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
```

Dans l'affichage en lecture (vers la ligne 829), remplacer `{proj.context}` par :

```tsx
{PROJECT_CONTEXT_OPTIONS.find((option) => option.value === proj.context)?.label ?? proj.context}
```

- [ ] **Step 3 : mobilité et disponibilités**

1. Ajouter `FiTruck,` à la liste d'imports `react-icons/fi`. `FiCalendar` y est déjà.
2. Après `const [linkedin, setLinkedin] = useState("");`, ajouter les états :

```tsx
  const [mobility, setMobility] = useState("");
  const [availability, setAvailability] = useState("");
```

3. Dans `populateForm`, après `setLinkedin(...)`, ajouter :

```tsx
    setMobility(data.contact?.mobility || "");
    setAvailability(data.contact?.availability || "");
```

4. Dans l'objet `contact` de la sauvegarde, après `linkedin,`, ajouter les deux champs, sans quoi la sauvegarde les efface :

```tsx
        mobility,
        availability,
```

5. Dans la grille des coordonnées, juste après le `<div>` du champ `candidate_phone` (avant le `</div>` qui ferme la grille), ajouter :

```tsx
            <div>
              <label htmlFor="candidate_mobility" className="block text-xs font-medium text-gray-300 mb-1 flex items-center">
                <FiTruck className="mr-1.5" /> Mobilité
              </label>
              <input
                id="candidate_mobility"
                type="text"
                value={mobility}
                onChange={(e) => setMobility(e.target.value)}
                placeholder="Permis B, véhiculé"
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label htmlFor="candidate_availability" className="block text-xs font-medium text-gray-300 mb-1 flex items-center">
                <FiCalendar className="mr-1.5" /> Disponibilités
              </label>
              <input
                id="candidate_availability"
                type="text"
                value={availability}
                onChange={(e) => setAvailability(e.target.value)}
                placeholder="Disponible immédiatement · 2x8, nuit, week-end"
                className="w-full rounded-md bg-blue-night border border-gray-700 py-2 px-3 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
```

- [ ] **Step 4 : vérifier**

Run : `cd frontend && npx tsc --noEmit`
Expected : aucune erreur dans `CandidateProfileSection.tsx` ni dans `coverLetter.ts`. Une erreur dans un fichier que l'utilisateur modifie en parallèle est à signaler, pas à corriger.

Run : `cd frontend && npx next lint --file src/components/profile/CandidateProfileSection.tsx --file src/types/coverLetter.ts`
Expected : aucune nouvelle erreur.

- [ ] **Step 5 : commit**

```bash
git add frontend/src/types/coverLetter.ts frontend/src/components/profile/CandidateProfileSection.tsx
git commit -m "feat(profil): contexte de projet en liste, mobilité et disponibilités

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7 : vérification globale

**Files :** aucun.

- [ ] **Step 1 : suite backend complète**

Run : `cd backend && uv run pytest -q`. Elle dure plus de 10 minutes : la lancer en arrière-plan.
Expected : tout PASS sauf les 2 échecs préexistants connus (`test_get_interview_prep_empty`, `test_update_user_tier`). Tout autre échec est à nommer dans le rapport.

- [ ] **Step 2 : validation manuelle (utilisateur)**

Elle demande un LLM réel et l'UI, donc c'est l'utilisateur qui la conduit.

1. Profil **préparateur de commandes**, créé sur un compte de test :
   - certifications : CACES R489 cat. 1, 3, 5 et permis B ;
   - mobilité : « Permis B, véhiculé » ;
   - disponibilités : « 2x8, nuit » ;
   - aucun projet ;
   - centres d'intérêt : 2 valeurs.

   Générer un CV adapté sur une offre logistique, puis vérifier :
   - aucune section Projets ;
   - CACES cité dans l'accroche et en tête des « Certifications & habilitations » ;
   - ligne mobilité sous le titre ;
   - aucune métrique tech ;
   - une page.
2. **Profil tech actuel** : régénérer un CV existant pour vérifier la non-régression.
   - « Compétences » remplace « Compétences Techniques » ;
   - pas de lien 🌐 en doublon du GitHub ;
   - les expériences pertinentes ont 4 à 5 puces et les annexes 1 à 2.
3. Dans l'UI profil, changer le contexte d'un projet en « Associatif », sauvegarder, recharger : la valeur est conservée, et la mobilité aussi.
