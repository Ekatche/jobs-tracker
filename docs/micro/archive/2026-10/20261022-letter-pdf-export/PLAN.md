---
task: Export PDF de la lettre de motivation avec en-tête candidat + entreprise
description: cover letter PDF export endpoint GET /applications/{id}/cover-letter/pdf — Jinja letter.html A4 template (sender block full_name/location/phone/email, recipient company + city, French date, "Objet : Candidature au poste de"), services/letter_pdf.py render_letter_html, reuse Playwright generate_cv_pdf, routers/cover_letters.py, lib/api.ts coverLetterApi.downloadPdf, CoverLetterPanel.tsx download button disabled on unsaved edits
status: done
created: 2026-10-22
---

# Export PDF de la lettre de motivation

## Context
- Existing code checked: `services/cv_pdf_renderer.py::generate_cv_pdf` (HTML → PDF A4 Playwright, générique, réutilisable tel quel) ; `routers/resumes.py::get_resume_pdf` (modèle de réponse `Response` application/pdf + slug de fichier) ; `routers/resumes.py::_build_candidate` (coordonnées depuis `candidate_profile.contact`) ; `services/cv_templates.py` (env Jinja avec autoescape) ; `routers/cover_letters.py` (GET/PATCH lettre, contrôle d'appartenance) ; `CoverLetterPanel.tsx` ; `lib/api.ts::resumeApi.downloadPdf` (pattern blob + lien).
- Le corps de lettre contient déjà « Madame, Monsieur, » et la formule de politesse (prompt `02_style.md`) : le gabarit n'ajoute que l'en-tête, pas de salutation.
- Candidature : seuls `company`, `position`, `location` existent (pas d'adresse postale) — validé avec l'utilisateur.
- Fresh info looked up: n/a (Playwright/Jinja déjà utilisés à l'identique dans le projet).
- Git status checked: seul `docs/micro/` modifié (archive sweep précédent), hors scope.

## Simpler Alternative Considered
Impression navigateur (`window.print()`) côté front : pas de mise en page A4 maîtrisée ni d'en-tête fiable. Le backend a déjà le moteur PDF → réutilisation.

## Surgical Scope
- **Files touched**:
  - `backend/app/templates/letter/letter.html` (nouveau)
  - `backend/app/services/letter_pdf.py` (nouveau)
  - `backend/app/routers/cover_letters.py`
  - `backend/tests/test_letter_pdf.py` (nouveau)
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/applications/CoverLetterPanel.tsx`
- **Files NOT touched**: tous les autres (`cv_pdf_renderer.py`, `resumes.py`, gabarits CV inchangés)
- **Symbols replaced**: none
- **Symbols extended**: `coverLetterApi` (+ `downloadPdf`), `CoverLetterPanel` (+ bouton PDF)

## Definition of Done
- [x] Build passes: `cd frontend && npm run build`
- [x] Tests pass: `cd backend && uv run pytest tests/test_letter_pdf.py tests/test_cover_letters_api.py -v`
- [x] No dead code: n/a — none replaced
- [x] Type check: `cd frontend && npx tsc --noEmit`
- [x] En-tête contient nom, ville, téléphone, email, entreprise, ville entreprise, date FR, objet avec le poste : couvert par `test_render_letter_html_header` (assertions sur chaque champ)
- [x] Échappement HTML du corps (`<script>` rendu `&lt;script&gt;`) : `test_render_letter_html_escapes_body`
- [x] Sécurité : 403 si la candidature appartient à un autre utilisateur, 404 si aucune lettre prête : `test_letter_pdf_forbidden`, `test_letter_pdf_not_ready`
- [x] 200 `application/pdf` + `Content-Disposition` avec `Lettre_` : `test_letter_pdf_ok`
- [x] Pas de style inline dans le gabarit : `grep -c 'style="' backend/app/templates/letter/letter.html` → 0
- [x] Bouton désactivé si modifications non enregistrées : `grep -c 'isDirty' frontend/src/components/applications/CoverLetterPanel.tsx` ≥ 2
- [ ] Manual check: sur une candidature avec lettre prête, cliquer « PDF » → fichier A4 téléchargé avec en-tête complet (observateur : utilisateur)

## Steps
- [x] Step 1: Créer `templates/letter/letter.html` (A4, `@page { size: A4; margin: 22mm 20mm }`, police serif sobre, bloc expéditeur en haut à gauche, bloc destinataire à droite, date « Le 22 octobre 2026 », ligne « Objet : Candidature au poste de {position} », paragraphes du corps). Tout le CSS dans `<style>`.
- [x] Step 2: Créer `services/letter_pdf.py` : env Jinja autoescape dédié, `format_french_date(d: date) -> str`, `render_letter_html(body: str, candidate: dict, company: str, position: str, location: str | None, today: date | None = None) -> str` (corps découpé en paragraphes sur lignes vides).
- [x] Step 3: Endpoint `GET /applications/{application_id}/cover-letter/pdf` dans `cover_letters.py` : ObjectId valide, appartenance (403), lettre `ready` avec version courante (sinon 404), coordonnées via `_build_candidate` avec `full_name` = contact → `current_user.full_name` → fallback, rendu via `generate_cv_pdf`, `Response` attachment `Lettre_<nom>_<entreprise>.pdf`.
- [x] Step 4: Écrire `tests/test_letter_pdf.py` (rendu HTML + contrats HTTP, `generate_cv_pdf` patché pour ne pas lancer Chromium) ; lancer pytest.
- [x] Step 5: `coverLetterApi.downloadPdf(applicationId, filename?)` dans `api.ts` (même pattern que `resumeApi.downloadPdf`).
- [x] Step 6: Bouton « PDF » (`FiDownload`) dans `CoverLetterPanel.tsx`, désactivé quand `isDirty` (texte ≠ version enregistrée) avec `title` explicatif ; état de chargement ; build + tsc.
- [x] Step 7 (teardown): Delete all dead code created by this plan. Run an orphan scan bounded to the new symbols (`render_letter_html`, `format_french_date`, `downloadPdf`). Confirm 0 orphans.

## Code Review
- Dead code removed: yes (0 orphans)
- Build status: pass (`npm run build` exit 0, pytest 16 passed exit 0)
- Type errors: none (`npx tsc --noEmit` exit 0)
- Unintended side effects: none
- Security surface touched: yes (autoescape HTML Jinja2 + semgrep 0 findings)
- Verdict: ✅ DONE

## Execution Log
- 2026-10-22T15:40Z | antigravity | step 1 | started
- 2026-10-22T15:41Z | antigravity | step 1 | done | template created, grep -c style=0
- 2026-10-22T15:41Z | antigravity | step 2 | started
- 2026-10-22T15:42Z | antigravity | step 2 | done | render_letter_html verified, autoescape and header fields checked exit 0
- 2026-10-22T15:42Z | antigravity | step 3 | started
- 2026-10-22T15:43Z | antigravity | step 3 | done | endpoint registered in FastAPI routes exit 0
- 2026-10-22T15:43Z | antigravity | step 4 | started
- 2026-10-22T15:45Z | antigravity | step 4 | done | pytest 16 passed exit 0
- 2026-10-22T15:45Z | antigravity | step 5 | started
- 2026-10-22T15:46Z | antigravity | step 5 | done | downloadPdf added to coverLetterApi, tsc --noEmit exit 0
- 2026-10-22T15:46Z | antigravity | step 6 | started
- 2026-10-22T15:48Z | antigravity | step 6 | done | FiDownload button added, isDirty count 5, tsc and npm run build exit 0
- 2026-10-22T15:49Z | antigravity | step 7 | started
- 2026-10-22T15:50Z | antigravity | step 7 | done | 0 orphans, semgrep 0 findings, DoD 100% green
- 2026-10-22T15:51Z | antigravity | closeout | done | plan completed successfully

## Notes
- Preflight baseline (2026-10-22T15:40Z): `cd frontend && npx tsc --noEmit` exit 0, `cd backend && uv run pytest tests/test_cover_letters_api.py -q` exit 0 (8 passed). Convention files read: AGENTS.md, GEMINI.md.

