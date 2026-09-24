---
task: Évaluation d'offres — blocs A, B, G plus discriminants et adéquation au poste (hors description brute)
status: done
created: 2026-09-23
---

# Blocs A / B / G

## Context
- 7 évaluations, scores 4.0–5.0 (4 à ≥ 4.8) : le score ne discrimine pas.
- Talan : « 5 ans » critical en partial_match → 5.0 (partiel jamais pénalisé).
- Pass 2 peut rebaisser le poids d'une exigence Pass 1 ou l'oublier (aucune réconciliation).
- Talan : 3/5 verbatim_quote introuvables dans la description.
- Mairie (lolal) : 3 exigences, aucune critical → 5.0 ; définitions/exemples de prompt tech.
- Préférences (contract_types, seniority_levels, min_salary) jamais confrontées à l'offre.
- domain_coherence "partial" ignoré ; is_ghost_job (LLM seul) plafonne à 1.5 ; reposted_frequency jamais rempli.
- Données : âge max offre 7 j (archivage) ; mode_travail 94/126 non spécifié, remote_policy des 2 users = flexible ; salaire renseigné 26/126 ; reposts entreprise+canonical_title : 2 groupes.

## Décisions
- Écartés (données) : âge de l'offre, télétravail, localisation déterministe (recherche FT par rayon → faux écarts).
- B1 partiel : critical -0.5, high -0.25.
- B2 Pass 1 numérote R1..Rn ; Pass 2 renvoie req_id ; poids = Pass 1 ; exigence non traitée → manquante. Sans req_id : comportement actuel.
- B3 quote_verified sur RequirementMatch ; non vérifiée → exclue du bonus critical.
- A1 preference_mismatches (contrat high, séniorité distance 1 meaningful / ≥2 high, salaire max < min_salary high) ; pénalité = même barème que missing.
- A2 domain_coherence stocké ; partial -0.5.
- G1 reposted_frequency (entreprise + canonical_title, supprimées incluses) ; description < 500 car. → warning.
- G2 ghost plafonne seulement si republication détectée ; scam plafonne toujours.
- B4 prompts multi-métiers (critical = diplôme/certif exigé, permis, expérience minimale, cœur de métier).

- (2026-09-24) S1 note = couverture pondérée : poids critical 3 / high 2 / meaningful 1 ; crédit full 1, partial 0.5, manquante 0 ; note = 1 + 4 × couverture ; puis préférences (barème manquant) et domaine partiel (-0.5) soustraits. Aucune exigence évaluée → 3.0 (neutre). Bonus +0.3 supprimé (la couverture récompense déjà) ; quote_verified reste un signal affiché.
- (2026-09-24) S2 plafond 4.0 si description < 500 caractères ou < 4 exigences évaluées (offre trop pauvre pour justifier plus).

## Steps
- [x] 1 offer_fit.py (préférences + signaux G) + tests
- [x] 2 modèles (BlocA, RequirementMatch) + calculate_evaluation_score + tests
- [x] 3 evaluator : req_id, réconciliation, quote check, reposts, branchement + tests
- [x] 4 prompts B4
- [x] 5 suite complète ; affichage front si les champs existent côté UI
- [x] 6 (quota, accord requis) relancer les 7 évaluations, comparer avant/après

- [x] 7 score par couverture + plafond offre pauvre + tests
- [x] 8 recalcul des 6 évaluations existantes depuis leurs blocs (sans LLM), comparaison

## Execution Log
- 2026-09-23 | claude | 1-4 | offer_fit.py + tests (24) ; score : partiel, préférences, domaine partiel, bonus sur citations vérifiées, ghost plafonne si republication ; evaluator : R1..Rn, reconcile_with_pass1 (actif seulement si Pass 2 renvoie ≥1 req_id connu), quote_in_offer, count_documents entreprise(i)+canonical_title, warnings G ; prompts Pass 1 multi-métiers + définition critical, Pass 2 exhaustivité req_id + règle diplôme/certification ; test_offer_evaluation 30 passed
- 2026-09-23 | claude | 5 | suite backend : 550 passed, 1 failed (test_usage_tier_api dépendant de l'ordre, connu) ; front offers/[id] : badge citation non vérifiée, cohérence métier, écarts de préférences, ghost « non corroboré » ; warnings G déjà affichés ; tsc + eslint OK ; rendu non vérifié visuellement (anciennes évaluations sans champs : rien ne s'affiche)
- 2026-09-23 | user+claude | 6 | relance accordée ; backup evaluations_before.json (7), rapport evaluations_rerun_report.json. Talan 5.0→4.0 (« 5 ans » critical manquante, correct) ; Lizeo 5.0→4.75 ; Esker 4.5=4.5 ; Excelleria 4.0→4.5 ; Mairie 5.0=5.0 (2 critical full, republication 2, description courte en warning) ; N2jsoft 4.8→1.5 FAUX POSITIF pré-filtre métier existant (sim 0.283 < 0.3 sur « Développeur Confirmé Ia », hors plan) ; 1 offre supprimée → 404, évaluation orpheline laissée. 0 citation non vérifiée après consigne « mot pour mot ».
- 2026-09-23 | claude | 6b | pré-filtre métier : sigle « IA » développé en « intelligence artificielle » avant embedding (domain_relevance.expand_title_acronyms). Mesure sur 31 offres × 2 profils : min métier propre eliel 0.283→0.430, max hors métier 0.234 inchangé ; titre+compétences (N2jsoft sans compétences) et titre+description testés, moins bons. N2jsoft relancée : 1.5→4.5 (critical « 3 à 5 ans » partiel). tests domain_relevance + offer_evaluation : 42 passed
- 2026-09-24 | claude | 7 | calculate_evaluation_score : couverture pondérée + plafond 4.0 offre pauvre (description_length passé par l'évaluateur) ; bonus +0.3 et PARTIAL_PENALTY supprimés ; tests unitaires réécrits, 3 tests d'intégration ajustés (0-1 exigence : 3.0 / 4.0) ; 68 passed (offer_evaluation, offer_fit, domain_relevance)
- 2026-09-24 | claude | 8 | rescore_evaluations.py (sans LLM, backup evaluations_before_rescore.json) : N2jsoft 4.5→4.33, Lizeo 4.75→4.67, Esker 4.5→4.25, Excelleria 4.5→4.6, Mairie 5.0→4.0, Talan 4.0→4.08 ; offer_evaluations.score/headline + job_offers.evaluation_score mis à jour ; orpheline ignorée. Constat : écart resserré (4.0–4.67) car le LLM signale peu de manques ; une critical manquante ne pèse que sa part de couverture.
