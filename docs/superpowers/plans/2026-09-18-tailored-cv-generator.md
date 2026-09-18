# Tailored ATS CV Generator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end tailored CV generation pipeline that extracts candidate context from `CandidateProfile`, aligns it against target `JobOffer` requirements and Two-Pass evaluation matches (Bloc B), renders two European-standard A4 vector templates (Sidebar Elegance & Executive Minimalist), and provides a dedicated `/resumes` management hub in Next.js.

**Architecture:** A FastAPI service orchestrates an LLM adaptation agent (Gemini 3.7 Flash) constrained by an anti-hallucination guardrail (`verify_cv_honesty`), formats the structured data via Jinja2 HTML5/CSS Paged Media templates, and compiles pixel-perfect selectable A4 PDFs via a headless vector renderer. A dedicated frontend route `/resumes` offers interactive preview, template switching, photo toggling, and 1-click downloads, with cross-links from `/offers/[id]` and `/applications`.

**Tech Stack:** FastAPI, Pydantic v2, Motor / PyMongo, Jinja2, Playwright / PDF Engine, Next.js (App Router), TailwindCSS, TypeScript.

## Global Constraints

- Paper format MUST strictly adhere to standard European A4 (`210mm x 297mm`) with `@page { size: A4; margin: 10mm 12mm; }`.
- Generated PDFs MUST contain selectable vector text (zero rasterized text images) with semantic heading tags for 100% ATS parser compatibility.
- Anti-hallucination guardrail MUST reject any generated skill, company, or degree not present in or verified by the source `CandidateProfile`.
- Multi-tenant isolation: All CV documents stored in `tailored_resumes` collection MUST be scoped by `user_id` matching the authenticated JWT token.
- Quota enforcement: `require_user_quota(user, "cv_tailoring")` MUST be evaluated before any LLM adaptation pass.
- All code and docstrings in English; all conversational user interactions in French.

---

### Task 1: Pydantic Schemas & Anti-Hallucination Guardrail

**Files:**
- Create: `backend/app/models/tailored_cv.py`
- Create: `backend/app/services/cv_guards.py`
- Test: `backend/tests/test_cv_guards.py`

**Interfaces:**
- Consumes: `CandidateProfile` from `backend/app/models.py`
- Produces:
  - `TailoredCVSchema`, `TailoredExperienceItem`, `TailoredProjectItem`, `TailoredSkillGroup`, `TailoredEducationItem`, `TailoredLanguage`, `TailoredResumeInDB` in `backend/app/models/tailored_cv.py`
  - `verify_cv_honesty(tailored: TailoredCVSchema, source_profile: dict) -> tuple[bool, list[str]]` in `backend/app/services/cv_guards.py`

- [ ] **Step 1: Write failing tests for CV honesty guardrail**

Create `backend/tests/test_cv_guards.py`:
```python
import pytest
from app.models.tailored_cv import (
    TailoredCVSchema, TailoredExperienceItem, TailoredProjectItem,
    TailoredSkillGroup, TailoredEducationItem, TailoredLanguage
)
from app.services.cv_guards import verify_cv_honesty

def test_verify_cv_honesty_valid():
    source_profile = {
        "experiences": [{"company": "Deloitte", "title": "Data Scientist"}],
        "education": [{"degree": "Master IA", "school": "Centrale Lyon"}],
        "skills": ["Python", "PyTorch", "Docker"],
    }
    tailored = TailoredCVSchema(
        target_role_title="Senior AI Engineer",
        professional_summary="Impact-driven engineer...",
        prioritized_skills=[TailoredSkillGroup(category="AI", skills=["Python", "PyTorch"])],
        experiences=[TailoredExperienceItem(
            title="Data Scientist", company="Deloitte", start_date="2022",
            bullet_points=["Built LLM service delivering 35% lower latency."]
        )],
        featured_projects=[],
        education=[TailoredEducationItem(degree="Master IA", institution="Centrale Lyon", year="2022")],
        languages=[TailoredLanguage(language="Français", level="Natif")]
    )
    is_valid, violations = verify_cv_honesty(tailored, source_profile)
    assert is_valid is True
    assert len(violations) == 0

def test_verify_cv_honesty_flags_invented_company_and_skills():
    source_profile = {
        "experiences": [{"company": "Deloitte", "title": "Data Scientist"}],
        "skills": ["Python"],
        "education": [],
    }
    hallucinated = TailoredCVSchema(
        target_role_title="Senior AI Engineer",
        professional_summary="...",
        prioritized_skills=[TailoredSkillGroup(category="AI", skills=["Python", "BrainSurgeryFramework"])],
        experiences=[TailoredExperienceItem(
            title="VP AI", company="Google Brain Fake", start_date="2020",
            bullet_points=["Fake bullet"]
        )],
        featured_projects=[],
        education=[],
        languages=[]
    )
    is_valid, violations = verify_cv_honesty(hallucinated, source_profile)
    assert is_valid is False
    assert any("Google Brain Fake" in v for v in violations)
    assert any("BrainSurgeryFramework" in v for v in violations)
```

- [ ] **Step 2: Run test to verify it fails**
Run: `docker exec jobtracker-backend pytest tests/test_cv_guards.py`

- [ ] **Step 3: Implement `backend/app/models/tailored_cv.py` and `backend/app/services/cv_guards.py`**
Define schemas and verification function checking company names against profile experiences and skill keywords against profile skills with fuzzy tolerance for casing/punctuation.

- [ ] **Step 4: Run test to verify it passes**
Run: `docker exec jobtracker-backend pytest tests/test_cv_guards.py`

- [ ] **Step 5: Commit changes**
`git add backend/app/models/tailored_cv.py backend/app/services/cv_guards.py backend/tests/test_cv_guards.py && git commit -m "feat(cv): add tailored CV schemas and anti-hallucination guardrail"`

---

### Task 2: AI Adaptation Engine (`CV Tailor`)

**Files:**
- Create: `backend/app/llm/prompts/cv/tailor_prompt.md`
- Create: `backend/app/services/cv_tailor.py`
- Test: `backend/tests/test_cv_tailor.py`

**Interfaces:**
- Consumes: `CandidateProfile`, `JobOffer`, `OfferEvaluationInDB` (Bloc B matches)
- Produces: `async def generate_tailored_cv_content(profile: dict, offer: dict, evaluation: Optional[dict] = None) -> TailoredCVSchema`

- [ ] **Step 1: Write failing unit test for `generate_tailored_cv_content` with mocked LLM**
Test that `generate_tailored_cv_content` constructs prompt with Bloc B requirements, parses structured JSON response into `TailoredCVSchema`, and passes the honesty guardrail.

- [ ] **Step 2: Run test to verify it fails**
Run: `docker exec jobtracker-backend pytest tests/test_cv_tailor.py`

- [ ] **Step 3: Implement prompt template and `cv_tailor.py`**
Use `SUMMARY_MODEL` / `EVAL_MODEL` via litellm or LangChain, passing explicit instructions:
- Align terminology to offer (e.g. mention AWS if target role emphasizes AWS and candidate has AWS).
- Never fabricate experiences or unlisted tools.
- Highlight metrics and deliverables.

- [ ] **Step 4: Run test to verify it passes**
Run: `docker exec jobtracker-backend pytest tests/test_cv_tailor.py`

- [ ] **Step 5: Commit changes**
`git add backend/app/llm/prompts/cv/tailor_prompt.md backend/app/services/cv_tailor.py backend/tests/test_cv_tailor.py && git commit -m "feat(cv): implement AI CV tailoring engine with Bloc B context fusion"`

---

### Task 3: Jinja2 Templates (Sidebar Elegance & Executive Minimalist)

**Files:**
- Create: `backend/app/templates/cv/base_cv.css`
- Create: `backend/app/templates/cv/sidebar_elegance.html`
- Create: `backend/app/templates/cv/executive_minimalist.html`
- Test: `backend/tests/test_cv_templates.py`

**Interfaces:**
- Consumes: `TailoredCVSchema`, candidate personal details, `with_photo: bool`, `avatar_url: Optional[str]`
- Produces: `def render_cv_html(data: dict, template_name: str, with_photo: bool = False) -> str`

- [ ] **Step 1: Write unit tests verifying template rendering**
Create `backend/tests/test_cv_templates.py`:
- Test `render_cv_html` with `sidebar_elegance` produces 2-column DOM containing candidate name, experiences, language CECRL badges, and `@page` rules.
- Test `render_cv_html` with `executive_minimalist` produces clean 1-column DOM.
- Test `with_photo=True` renders `<img>` and `with_photo=False` renders monogram initials.

- [ ] **Step 2: Run test to verify it fails**
Run: `docker exec jobtracker-backend pytest tests/test_cv_templates.py`

- [ ] **Step 3: Implement CSS styling and HTML templates**
Create responsive print styles:
- `@page { size: A4; margin: 10mm 12mm; }`
- Inter & Geist system typography with fallback to standard sans-serif.
- Clean pills for skills, subtle separators, `break-inside: avoid` on experience blocks.

- [ ] **Step 4: Run test to verify it passes**
Run: `docker exec jobtracker-backend pytest tests/test_cv_templates.py`

- [ ] **Step 5: Commit changes**
`git add backend/app/templates/cv/ backend/tests/test_cv_templates.py && git commit -m "feat(cv): create European A4 Jinja2 templates for Sidebar and Minimalist styles"`

---

### Task 4: High-Fidelity Vector PDF Renderer

**Files:**
- Create: `backend/app/services/cv_pdf_renderer.py`
- Test: `backend/tests/test_cv_pdf_renderer.py`

**Interfaces:**
- Consumes: Rendered HTML string from Task 3
- Produces: `async def generate_cv_pdf(html_content: str) -> bytes`

- [ ] **Step 1: Write test verifying PDF generation and vector text extraction**
Create `backend/tests/test_cv_pdf_renderer.py`:
- Call `generate_cv_pdf(sample_html)`.
- Assert bytes begin with `%PDF-`.
- Open with `pdfplumber` or `pypdf`, verify extracted text contains candidate name and sections.

- [ ] **Step 2: Run test to verify it fails**
Run: `docker exec jobtracker-backend pytest tests/test_cv_pdf_renderer.py`

- [ ] **Step 3: Implement `generate_cv_pdf` using Playwright headless**
Launch headless browser, set content, generate PDF with `format="A4"`, `print_background=True`, and return raw bytes.

- [ ] **Step 4: Run test to verify it passes**
Run: `docker exec jobtracker-backend pytest tests/test_cv_pdf_renderer.py`

- [ ] **Step 5: Commit changes**
`git add backend/app/services/cv_pdf_renderer.py backend/tests/test_cv_pdf_renderer.py && git commit -m "feat(cv): implement vector A4 PDF renderer using headless engine"`

---

### Task 5: Backend REST Router & MongoDB Persistence

**Files:**
- Create: `backend/app/routers/resumes.py`
- Modify: `backend/main.py` (mount router)
- Test: `backend/tests/test_resumes_api.py`

**Interfaces:**
- Endpoints:
  - `GET /resumes` : List all user's tailored CVs
  - `POST /resumes/generate` : Body `{ offer_id: str, template: Optional[str] }`
  - `GET /resumes/{id}` : Get structured JSON
  - `PUT /resumes/{id}` : Update fields manually
  - `GET /resumes/{id}/pdf?template=sidebar_elegance&with_photo=false` : Stream `application/pdf`
  - `DELETE /resumes/{id}` : Delete resume

- [ ] **Step 1: Write integration tests for `/resumes` endpoints**
Create `backend/tests/test_resumes_api.py`:
- Test auth requirement (401 if missing token).
- Test quota check (`require_user_quota`).
- Test generate, list, retrieve, update, and stream PDF.

- [ ] **Step 2: Run test to verify it fails**
Run: `docker exec jobtracker-backend pytest tests/test_resumes_api.py`

- [ ] **Step 3: Implement `app/routers/resumes.py` and register in `main.py`**
Include MongoDB collection `tailored_resumes`, atomic upserts, quota tracking with `record_api_usage`.

- [ ] **Step 4: Run test to verify it passes**
Run: `docker exec jobtracker-backend pytest tests/test_resumes_api.py`

- [ ] **Step 5: Commit changes**
`git add backend/app/routers/resumes.py backend/main.py backend/tests/test_resumes_api.py && git commit -m "feat(api): add REST endpoints for tailored CV generation, retrieval and PDF streaming"`

---

### Task 6: Frontend Resume Hub (`/resumes`) & Navigation Integration

**Files:**
- Create: `frontend/src/app/resumes/page.tsx`
- Create: `frontend/src/components/resumes/ResumeCard.tsx`
- Create: `frontend/src/components/resumes/ResumePreviewModal.tsx`
- Modify: `frontend/src/lib/api.ts` (add resume client methods)
- Modify: `frontend/src/app/offers/[id]/page.tsx` (add "Générer CV adapté" action)
- Modify: `frontend/src/components/applications/ApplicationDetails.tsx` (add CV link badge)

- [ ] **Step 1: Add API client methods in `frontend/src/lib/api.ts`**
Add `getResumes()`, `generateResume(offerId, template)`, `getResume(id)`, `updateResume(id, data)`, `downloadResumePdf(id, template, withPhoto)`, `deleteResume(id)`.

- [ ] **Step 2: Create `ResumeCard.tsx` and `ResumePreviewModal.tsx`**
Build modern UI cards with template badge, target company/role, 1-click PDF download, template switcher toggle, and embedded PDF viewer modal.

- [ ] **Step 3: Build `/resumes` hub page**
Render grid of tailored CVs with search, empty state guide, and "Create from offer" modal.

- [ ] **Step 4: Wire cross-links from `/offers/[id]` and Kanban application sidebar**
Add direct trigger buttons to generate a CV from any active offer and link existing CVs in the Kanban.

- [ ] **Step 5: Verify frontend builds without errors**
Run: `docker exec jobtracker-frontend npm run build` (or `npm run lint`)

- [ ] **Step 6: Commit changes**
`git add frontend/src/ && git commit -m "feat(ui): add dedicated /resumes hub with PDF viewer and 1-click downloads"`

---

### Task 7: End-to-End Validation & Documentation Update

**Files:**
- Modify: `README.md`
- Modify: `docs/CAREER_OPS_INTEGRATION_PLAN.md` (check off Phase 5B)
- Test: Full integration test suite

- [ ] **Step 1: Run full test suite across backend and verify zero regressions**
Run: `docker exec jobtracker-backend pytest tests/test_cv_guards.py tests/test_cv_tailor.py tests/test_cv_templates.py tests/test_cv_pdf_renderer.py tests/test_resumes_api.py -v`

- [ ] **Step 2: Test live PDF generation end-to-end for a real MongoDB offer**
Generate a tailored CV for an existing offer (e.g. Deloitte Lyon), download both `sidebar_elegance` and `executive_minimalist` PDFs, and confirm ATS parsing integrity.

- [ ] **Step 3: Update documentation and commit**
Update `README.md` and `docs/CAREER_OPS_INTEGRATION_PLAN.md`.
`git add README.md docs/CAREER_OPS_INTEGRATION_PLAN.md && git commit -m "docs: complete Phase 5B tailored CV generator in Master Plan"`
