# Interview Prep ("STAR+R & Behavioral Intelligence") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular Interview Prep system for Job-Tracker based on Career-Ops principles, generating STAR+R stories, 3 audience packs, anticipated questions, and reverse questions with an interactive UI on `/offers/[id]` and shortcuts in the application Kanban.

**Architecture:** Modular backend service using Gemini 3.7 Flash via LiteLLM to analyze candidate profile and offer evaluation (Bloc B), enforced with quotas under `ApiUsageAction.INTERVIEW_PREP`. A dedicated REST router exposes modular generation, CRUD, and Markdown export. A responsive Next.js frontend tab provides interactive accordions, audience switchers, and single-click copy/export.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Motor (MongoDB), LiteLLM, Next.js 14, React, TailwindCSS, TypeScript.

---

## Global Constraints
- Python type hints required for all backend code.
- Preservation of existing models and code annotations.
- Code and comments in English; user chat in French.
- Conventional commits in English imperative style.
- No dummy or hallucinated experiences: STAR+R stories must derive from candidate profile facts.
- Quota check `require_user_quota(user_id, ApiUsageAction.INTERVIEW_PREP)` before every LLM call.

---

### Task 1: Pydantic Data Models for Interview Prep

**Files:**
- Modify: `backend/app/models.py`
- Create: `backend/tests/test_interview_prep_models.py`

**Interfaces:**
- Produces:
  - `StarRStory`: id, title, theme, target_requirement, situation, task, action, result, reflection, key_tags
  - `AudiencePackRecruiter`: pitch_30s, comp_strategy, red_flags_they_screen_for, key_questions_to_ask_recruiter
  - `AudiencePackHiringManager`: strategic_alignment, internal_vocabulary, sharp_questions
  - `AudiencePackTechPanel`: architecture_points, tradeoffs_and_risks, reverse_questions
  - `AnticipatedQuestion`: id, category, question, why_it_will_be_asked, mapped_story_id, key_points_to_cover
  - `ReverseQuestion`: id, category, question, probe_intent
  - `InterviewPrep`: id, offer_id, user_id, stories, recruiter_pack, hm_pack, tech_pack, anticipated_questions, reverse_questions, created_at, updated_at

- [ ] **Step 1: Write failing model unit test**
Create `backend/tests/test_interview_prep_models.py`:
```python
import pytest
from bson import ObjectId
from app.models import (
    StarRStory,
    AudiencePackRecruiter,
    AudiencePackHiringManager,
    AudiencePackTechPanel,
    AnticipatedQuestion,
    ReverseQuestion,
    InterviewPrep,
)

def test_interview_prep_model_instantiation():
    story = StarRStory(
        title="[Scalabilité] Pipeline Kafka",
        theme="Architecture",
        target_requirement="Expérience Kafka",
        situation="Charge de 50k req/s",
        task="Concevoir l'ingestion",
        action="Mise en place de partitions et consumer groups",
        result="Latence réduite de 40%",
        reflection="Mieux anticiper les rebalances",
        key_tags=["kafka", "python"]
    )
    assert story.id is not None
    assert story.title.startswith("[Scalabilité]")

    prep = InterviewPrep(
        offer_id=ObjectId(),
        user_id=ObjectId(),
        stories=[story],
        recruiter_pack=AudiencePackRecruiter(
            pitch_30s="Ingénieur backend senior...",
            comp_strategy={"volunteer": "fourchette marché", "avoid": "chiffre ferme prématuré"},
            red_flags_they_screen_for=["instabilité"],
            key_questions_to_ask_recruiter=["Quel est le calendrier ?"]
        ),
        anticipated_questions=[
            AnticipatedQuestion(
                category="behavioral",
                question="Parlez-moi d'une panne complexe.",
                why_it_will_be_asked="Bloc B: Fiabilité système",
                mapped_story_id=story.id,
                key_points_to_cover=["Isolation", "Communication"]
            )
        ],
        reverse_questions=[
            ReverseQuestion(
                category="Dette Technique",
                question="Comment gérez-vous la dette technique ?",
                probe_intent="Vérifier si les refactors sont autorisés"
            )
        ]
    )
    assert len(prep.stories) == 1
    assert prep.recruiter_pack.pitch_30s.startswith("Ingénieur")
    assert prep.anticipated_questions[0].mapped_story_id == story.id
```

- [ ] **Step 2: Run test to verify it fails**
Run inside docker container:
```bash
docker exec jobtracker-backend pytest tests/test_interview_prep_models.py -v
```
Expected: FAIL with `ImportError: cannot import name 'StarRStory'`

- [ ] **Step 3: Add models in `backend/app/models.py`**
Append `StarRStory`, `AudiencePackRecruiter`, `AudiencePackHiringManager`, `AudiencePackTechPanel`, `AnticipatedQuestion`, `ReverseQuestion`, `InterviewPrep` to `backend/app/models.py`.

- [ ] **Step 4: Run test to verify it passes**
```bash
docker exec jobtracker-backend pytest tests/test_interview_prep_models.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/models.py backend/tests/test_interview_prep_models.py
git commit -m "feat(interview): add Pydantic models for interview prep system"
```

---

### Task 2: Prompt Templates for the 4 Generation Modules

**Files:**
- Create: `backend/app/llm/prompts/interview/star_stories.md`
- Create: `backend/app/llm/prompts/interview/audience_packs.md`
- Create: `backend/app/llm/prompts/interview/anticipated_questions.md`
- Create: `backend/app/llm/prompts/interview/reverse_questions.md`

**Interfaces:**
- Produces: 4 markdown template files with precise instructions and JSON output schemas matching the Pydantic models.

- [ ] **Step 1: Create `star_stories.md` prompt**
Prompt instruction enforcing STAR+R format, grounded in candidate profile experiences and targeting Bloc B requirements. JSON output format matching `List[StarRStory]`.

- [ ] **Step 2: Create `audience_packs.md` prompt**
Prompt instruction segmenting the prep for Recruiter / HM / Tech Panel, containing pitch, compensation strategies, company vocabulary, and tradeoffs. JSON output matching `recruiter_pack`, `hm_pack`, `tech_pack`.

- [ ] **Step 3: Create `anticipated_questions.md` prompt**
Prompt generating behavioral questions (referencing generated STAR stories by title/id) and technical deep dives tagged `[inferred from JD]`.

- [ ] **Step 4: Create `reverse_questions.md` prompt**
Prompt generating tactical reverse questions to audit project health, on-call culture, tech debt, and autonomy.

- [ ] **Step 5: Commit**
```bash
git add backend/app/llm/prompts/interview/
git commit -m "feat(interview): add modular prompt templates for interview prep"
```

---

### Task 3: Interview Prep Service (`app/services/interview_prep_service.py`)

**Files:**
- Create: `backend/app/services/interview_prep_service.py`
- Create: `backend/tests/test_interview_prep_service.py`

**Interfaces:**
- Produces:
  - `generate_star_stories(profile, offer, evaluation) -> List[StarRStory]`
  - `generate_audience_packs(profile, offer, evaluation) -> Tuple[AudiencePackRecruiter, AudiencePackHiringManager, AudiencePackTechPanel]`
  - `generate_anticipated_questions(profile, offer, evaluation, stories) -> List[AnticipatedQuestion]`
  - `generate_reverse_questions(offer, evaluation) -> List[ReverseQuestion]`
  - `export_interview_prep_markdown(prep: InterviewPrep, offer: Dict[str, Any]) -> str`

- [ ] **Step 1: Write failing unit tests with mocks**
In `backend/tests/test_interview_prep_service.py`, test generation functions with mocked LiteLLM `acompletion` outputs, verifying JSON extraction, parsing, and Markdown generation.

- [ ] **Step 2: Run test to verify it fails**
```bash
docker exec jobtracker-backend pytest tests/test_interview_prep_service.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.interview_prep_service'`

- [ ] **Step 3: Implement `app/services/interview_prep_service.py`**
Implement the 4 module generators, JSON cleaning helper `_clean_json_output`, quota integration `record_api_usage`, and the Markdown export renderer.

- [ ] **Step 4: Run test to verify it passes**
```bash
docker exec jobtracker-backend pytest tests/test_interview_prep_service.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/services/interview_prep_service.py backend/tests/test_interview_prep_service.py
git commit -m "feat(interview): implement interview prep generation service with modular prompts"
```

---

### Task 4: FastAPI Router (`app/routers/interview_prep.py`) & App Registration

**Files:**
- Create: `backend/app/routers/interview_prep.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_interview_prep_api.py`

**Interfaces:**
- Endpoints:
  - `GET /api/offers/{offer_id}/interview-prep`
  - `POST /api/offers/{offer_id}/interview-prep/generate/stories`
  - `POST /api/offers/{offer_id}/interview-prep/generate/audience-packs`
  - `POST /api/offers/{offer_id}/interview-prep/generate/questions`
  - `POST /api/offers/{offer_id}/interview-prep/generate/reverse-questions`
  - `POST /api/offers/{offer_id}/interview-prep/generate/all`
  - `PUT /api/offers/{offer_id}/interview-prep`
  - `GET /api/offers/{offer_id}/interview-prep/export`

- [ ] **Step 1: Write failing router integration test**
In `backend/tests/test_interview_prep_api.py`, test:
  - GET empty prep -> returns empty template
  - Quota verification (`require_user_quota`)
  - PUT update persistence in MongoDB `interview_preps`
  - GET export markdown returns text/markdown

- [ ] **Step 2: Run test to verify it fails**
```bash
docker exec jobtracker-backend pytest tests/test_interview_prep_api.py -v
```
Expected: FAIL (404 Not Found or router missing)

- [ ] **Step 3: Implement `backend/app/routers/interview_prep.py` and register in `main.py`**
Include authentication `get_current_user`, database collection `db.interview_preps`, quota guards, error handling.

- [ ] **Step 4: Run test to verify it passes**
```bash
docker exec jobtracker-backend pytest tests/test_interview_prep_api.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/routers/interview_prep.py backend/app/main.py backend/tests/test_interview_prep_api.py
git commit -m "feat(interview): implement FastAPI router for interview prep endpoints"
```

---

### Task 5: Frontend TypeScript Types & API Client

**Files:**
- Create: `frontend/src/types/interview.ts`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces:
  - TypeScript types: `StarRStory`, `AudiencePackRecruiter`, `AudiencePackHiringManager`, `AudiencePackTechPanel`, `AnticipatedQuestion`, `ReverseQuestion`, `InterviewPrep`
  - `interviewPrepApi`:
    - `get(offerId)`
    - `generateStories(offerId)`
    - `generateAudiencePacks(offerId)`
    - `generateQuestions(offerId)`
    - `generateReverseQuestions(offerId)`
    - `generateAll(offerId)`
    - `update(offerId, data)`
    - `exportMarkdown(offerId)`

- [ ] **Step 1: Create `frontend/src/types/interview.ts`**
Define interfaces mirroring backend Pydantic models.

- [ ] **Step 2: Add `interviewPrepApi` to `frontend/src/lib/api.ts`**
Add API methods calling `/api/offers/${offerId}/interview-prep/*` using dynamic `getApiBaseUrl()`.

- [ ] **Step 3: Verify TypeScript compilation**
```bash
cd frontend && npm run build
```
Expected: PASS with no TS errors.

- [ ] **Step 4: Commit**
```bash
git add frontend/src/types/interview.ts frontend/src/lib/api.ts
git commit -m "feat(interview): add frontend TypeScript types and interviewPrepApi client"
```

---

### Task 6: Frontend UI Components & Offer Page Integration

**Files:**
- Create: `frontend/src/components/interview/InterviewPrepTab.tsx`
- Create: `frontend/src/components/interview/StarStoryCard.tsx`
- Create: `frontend/src/components/interview/AudiencePacksViewer.tsx`
- Create: `frontend/src/components/interview/AnticipatedQuestionsViewer.tsx`
- Create: `frontend/src/components/interview/ReverseQuestionsViewer.tsx`
- Modify: `frontend/src/app/offers/[id]/page.tsx`
- Modify: `frontend/src/components/applications/ApplicationDetails.tsx`

**Interfaces:**
- Produces:
  - Tab "🎯 Préparation Entretien" on `/offers/[id]`
  - Modular generation buttons with loading states
  - Accordion for STAR+R with editable modal/form
  - 3-way segment switcher for Recruiter / HM / Tech Panel
  - Interactive question cards linked to stories
  - Direct quick link from `ApplicationDetails.tsx` in Kanban

- [ ] **Step 1: Create sub-components in `frontend/src/components/interview/`**
Implement story cards, audience viewer, question cards with clean aesthetics and badges.

- [ ] **Step 2: Create `InterviewPrepTab.tsx` container**
Implement action bar (Module progress, "Tout générer", "Exporter Markdown"), notification banners, and section layout.

- [ ] **Step 3: Integrate tab into `frontend/src/app/offers/[id]/page.tsx`**
Add tab button `activeTab === "interview"`, URL query parameter support `?tab=interview`.

- [ ] **Step 4: Add quick button in `ApplicationDetails.tsx`**
Under application details, add "🎯 Préparer l'entretien" pointing to `/offers/${offerId}?tab=interview`.

- [ ] **Step 5: Run Next.js build to verify zero errors**
```bash
cd frontend && npm run build
```
Expected: Build succeeds with 0 errors.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/components/interview/ frontend/src/app/offers/\[id\]/page.tsx frontend/src/components/applications/ApplicationDetails.tsx
git commit -m "feat(interview): implement interactive interview prep UI and Kanban integration"
```

---

### Task 7: End-to-End Verification & Master Plan Update

**Files:**
- Modify: `docs/CAREER_OPS_INTEGRATION_PLAN.md`

- [ ] **Step 1: Run all backend tests**
```bash
docker exec jobtracker-backend pytest tests/test_interview_prep_*.py -v
```
Expected: 100% PASS

- [ ] **Step 2: Verify frontend builds and runs**
Check Next.js routes, verify `/offers/[id]` renders the interview tab cleanly.

- [ ] **Step 3: Update `docs/CAREER_OPS_INTEGRATION_PLAN.md`**
Mark Phase 6 as complete (✅ 100%).

- [ ] **Step 4: Commit**
```bash
git add docs/CAREER_OPS_INTEGRATION_PLAN.md
git commit -m "docs: mark Phase 6 Interview Prep as completed in Master Plan"
```
