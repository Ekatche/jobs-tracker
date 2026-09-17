---
task: Nettoyage déterministe hors-IA des offres d'emploi (déséchappement HTML, entités, normalisation titres et champs)
status: done
created: 2026-09-17
completed: 2026-09-17
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Nettoyage déterministe hors-IA des offres d'emploi

## Context
- Existing code checked:
  - `backend/app/services/normalization.py`: `clean_job_title_syntax` ne déséchappait pas les entités HTML (ex: `&amp;`, `&quot;`, `&#39;`, `&nbsp;`), ne supprimait pas les balises HTML éventuelles et laissait parfois des parenthèses orphelines `()` après suppression des mentions `(H/F)`.
  - Résultat visible : offres avec des titres pollués comme `"Junior Data Scientist / ML Engineer (R&amp;D)"` au lieu de `"(R&D)"`.
  - `backend/app/tasks/job_offers_collectors.py`: le pipeline d'ingestion `enrich_offers_sync` et `save_offers_to_database` applique `clean_job_title_syntax` mais n'appliquait pas un nettoyage complet sur l'ensemble des champs bruts (`entreprise`, `localisation`, `type_contrat`, etc.).
  - Base de données MongoDB : 1 offre avec entité HTML dans le titre (`Junior Data Scientist / ML Engineer (R&amp;D)` chez Recupere Metals) et 4 descriptions avec entités résiduelles.
- Fresh info looked up: n/a
- Git status checked: modifications récentes de tests et commits précédents intégrés.

## Simpler Alternative Considered
- Nettoyer uniquement au moment du rendu frontend : rejeté car cela laisse la base de données polluée, fausse les clés d'unicité et pénalise la recherche et les matching LLM.

## Surgical Scope
- **Files touched**:
  - `backend/app/services/normalization.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `backend/scripts/sanitize_existing_offers.py` (nouveau script de nettoyage rétroactif de la base)
  - `backend/tests/test_normalization.py`
- **Files NOT touched**:
  - Frontend files, LLM prompts, crawler raw scrapers
- **Symbols replaced**:
  - none
- **Symbols extended**:
  - `clean_job_title_syntax` in `backend/app/services/normalization.py` (déséchappement HTML, suppression balises, nettoyage parenthèses orphelines)
  - `normalize_offer_fields` in `backend/app/services/normalization.py` (fonction centralisée de nettoyage hors-IA de tous les champs d'une offre)
  - `enrich_offers_sync` in `backend/app/tasks/job_offers_collectors.py` (application systématique de `normalize_offer_fields`)

## Definition of Done
- [x] Build passes: `docker exec jobtracker-backend pytest tests/test_normalization.py` (11 passed in 0.05s)
- [x] Tests pass: `docker exec jobtracker-backend pytest tests/test_normalization.py tests/test_job_offers_pipeline.py` (23 passed in 0.26s)
- [x] No dead code: confirm no unused functions or legacy patterns
- [x] Type check: `docker exec jobtracker-backend python -m py_compile app/services/normalization.py app/tasks/job_offers_collectors.py` (passed exit 0)
- [x] Manual check: Vérifier dans MongoDB que l'offre `"Junior Data Scientist / ML Engineer (R&amp;D)"` est propre (`"Junior Data Scientist / ML Engineer (R&D)"`) et que 0 offre ne contient d'entité HTML résiduelle. (Vérifié: `POSTE: 'Junior Data Scientist / ML Engineer (R&D)'`).

## Steps
- [x] Step 1: Normalization - Améliorer `clean_job_title_syntax` et créer `normalize_offer_fields` dans `backend/app/services/normalization.py` (déséchappement `html.unescape` 2 passes, nettoyage des balises HTML `<...>`, suppression des parenthèses orphelines `()`, normalisation de `entreprise`, `localisation`, `contrat`, `salaire`).
- [x] Step 2: Collectors - Intégrer `normalize_offer_fields` et `clean_html_entities_and_tags` dans `backend/app/tasks/job_offers_collectors.py` lors de l'ingestion (`enrich_offers`).
- [x] Step 3: Tests - Ajouter des tests unitaires complets dans `backend/tests/test_normalization.py` couvrant les entités HTML (`R&amp;D` -> `R&D`), les balises HTML, les parenthèses vides, et les champs entreprise/localisation.
- [x] Step 4: Script rétroactif - Créer et exécuter `backend/scripts/sanitize_existing_offers.py` pour nettoyer toutes les offres déjà présentes dans MongoDB (98 analysées, 61 modifiées, titres et descriptions nettoyés, idempotence vérifiée à 0 modification).
- [x] Step 5: Teardown - Exécuter les tests backend de régression (23/23 passed) et vérifier la propreté de la base MongoDB.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 10:10 | agy | step 1 | started
- 10:10 | agy | step 1 | completed clean_html_entities_and_tags and clean_job_title_syntax in normalization.py
- 10:11 | agy | step 2 | wired sanitization into enrich_offers in job_offers_collectors.py
- 10:11 | agy | step 3 | added unit tests in test_normalization.py
- 10:12 | agy | step 4 | created and executed scripts/sanitize_existing_offers.py (98 scanned, 61 updated)
- 10:13 | agy | step 5 | verified 23/23 tests pass, confirmed Recupere Metals title clean, idempotence confirmed

## Notes
- `clean_job_title_syntax` et `clean_html_entities_and_tags` supportent désormais le double unescaping, la préservation des balises techniques légitimes comme `(R&D)` tout en supprimant les mentions légales `(H/F)`, `(H/F/NB)` et les balises HTML résiduelles.
