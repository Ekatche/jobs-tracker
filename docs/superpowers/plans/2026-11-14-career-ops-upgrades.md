# Plan d'Implémentation — Exploitation des améliorations Career-Ops (Chantiers A, B, C, D)

Date : 2026-11-14
Statut : Terminé

## Liste de suivi des chantiers

- [x] **Chantier A — Évaluation & Matching (`evaluator.py`, `offer_fit.py`, `models.py`)**
  - [x] `importance_evidence_tier` + gate Pass 1 (`inferred` plafonné à `meaningful`)
  - [x] Budget de 12 lignes Bloc B (`apply_bloc_b_row_budget`) conservant 100 % des `critical` et `high`, tri `unmet` avant `met`
  - [x] Signaux Bloc G déterministes (`check_pay_range_width`, `check_employment_classification_risk`, `check_ai_buzzword_mismatch`, `company_history_note`, `build_risk_summary`)
  - [x] Bloc H déterministe (`build_bloc_h_draft` si `score >= 4.0`)
  - [x] Tests unitaires (`test_offer_fit.py`, `test_scoring_rules.py`, `test_evaluation_service.py`)

- [x] **Chantier B — Garde-fous CV, Score ATS & Clean-Markers (`cv_guards.py`, `ats_score.py`, `resumes.py`, `applications.py`)**
  - [x] Détection d'horizon prospectif 30/60/90j (`_is_plan_horizon`) + noms éducation/formation + rattachement au nom de métrique le plus proche
  - [x] Blocage de l'escalade d'autorité (`participé`/`prestataire` -> `dirigé`/`architecturé`)
  - [x] Service `ats_score.py` : `scan_invisible_markers`, `clean_invisible_markers`, `score_cv_ats_friendliness`, `export_cv_ats_plain_text`
  - [x] Nettoyage Unicode automatique + endpoints `GET /resumes/{resume_id}/ats-score` et `GET /resumes/{resume_id}/export-text`
  - [x] Tests unitaires (`backend/tests/cv_guards/test_career_ops_guards.py`)

- [x] **Chantier C — Collecte & Connecteurs ATS (`backend/app/services/ats/router.py`)**
  - [x] `detect_non_content_marker` (murs de connexion, 404 shell, paywall, JS shell)
  - [x] Extracteur Zero-Token Ashby (`extract_ashby_job`)
  - [x] Extracteur Zero-Token Workday CXS (`extract_workday_job`)
  - [x] Correctif SmartRecruiters board fantôme (`check_smartrecruiters_board_status` #4215) + durcissement description
  - [x] Tests unitaires (`backend/tests/test_ats_career_ops.py`)

- [x] **Chantier D — Analytics & Pilotage (`backend/app/services/analytics/calibration.py`, `applications.py`, `job_offers.py`)**
  - [x] `compute_score_calibration` (exclusion stricte des candidatures `in_flight`, plancher `min_band_n`, détection historique entretien)
  - [x] `compute_jd_skill_gaps` (agrégation des exigences manquantes / couvertes partiellement)
  - [x] Endpoints `GET /applications/pipeline/calibrate` et `GET /job-offers/analytics/skill-gaps`
  - [x] Tests unitaires (`backend/tests/pipeline/test_calibration_and_skill_gaps.py`)

- [x] **Finalisation**
  - [x] Mise à jour de `docs/CAREER_OPS_INTEGRATION_PLAN.md` et de ce suivi
  - [x] Vérification complète pytest + vérification `wc -l` <= 400 lignes sur les fichiers de tests
