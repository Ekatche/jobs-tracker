---
task: Préparation d'entretien — contexte candidat/offre/évaluation aligné sur le modèle réel (étape 1)
status: done
created: 2026-09-23
---

# Contexte candidat partagé évaluateur / entretien

## Context
- interview_prep_service.format_candidate_profile_context lit title/start_date/end_date/description (inexistants) : « Ingénieur », « à présent », missions ignorées.
- format_evaluation_context lit criticality (champ réel : weight) ; ignore reason, status, evidence_tier, score_justification, bloc_a.summary, bloc_g.warnings.
- Les 4 générateurs + export lisent offer["title"]/["company"] ; les offres stockent poste/entreprise.
- Évaluateur construit son propre dict candidat (evaluator.py ~249) sans achievements ni sector.
- excluded_* déjà filtrés au merge (profile/merge.py) : rien à faire.

## Décisions
- Un seul builder : build_candidate_context(profile) dans app/services/profile/context.py, utilisé par l'évaluateur et l'entretien (JSON dans le prompt).
- Ajout achievements (text+metric) et sector aux expériences (profite aussi à l'évaluation).
- Offre : poste/entreprise avec repli title/company.

## Steps
- [x] 1 context.py + tests
- [x] 2 evaluator branché sur build_candidate_context
- [x] 3 interview prep : profil, évaluation, champs offre + tests
- [x] 4 tests complets + vérif sur profils réels (eliel, lolal)

## Execution Log
- 2026-09-23 | claude | 1-4 | context.py partagé ; evaluator + interview prep branchés ; offre poste/entreprise ; 510 passed (1 échec test_usage_tier_api dépendant de l'ordre, passe seul) ; profils réels : headline OK, dates OK, missions 29/12 ; achievements = 0 dans les 2 profils (parser ne les remplit pas)
- 2026-09-23 | claude | tests | test_interview_prep_api seedait la base réelle (get_database direct) : origine de candidate_profiles (14 docs) et de 6 fausses offres title/company. Fixture test_db ajoutée au conftest. mongo_test redémarré (était Exited 255). Nettoyage base réelle en attente d'accord.
- 2026-09-23 | claude | nettoyage | backup test_pollution_backup.json (14 candidate_profiles, 6 offres, 25 interview_preps fictives) ; suppression refusée par le classifieur auto mode — script delete_test_pollution.py prêt, à lancer par l'utilisateur
- 2026-09-23 | user+claude | nettoyage | script lancé par l'utilisateur : offers 6, interview_preps 25, candidate_profiles 14 supprimés ; vérifié : 0 restant, 1 interview_prep réelle conservée
