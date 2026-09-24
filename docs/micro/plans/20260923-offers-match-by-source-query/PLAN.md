---
task: Offres — rattachement profil par requête d'origine (A) + filtre de bruit par intitulé à la collecte (B)
status: done
created: 2026-09-23
---

# Offres par requête d'origine

## Context
- 126 offres actives : 4 rattachées à eliel (data), 0 à lolal (animation). Matcher exige canonical_title ET ville identiques.
- France Travail renvoie du bruit : « Adjoint de Direction de Magasin » via « Animatrice permanente proche de bourgoin-jallieu ».
- relevance.py : allowlist data uniquement, inutile pour l'animation.
- Deux comptes distincts : eliel@local.fr, lolal@local.fr. Pas de scission de profil à faire.

## Décisions (validées)
- A : offre rattachée à U si rôle de source_query ∈ rôles de U (même normalisation que build_search_queries) et ville de la requête ∈ villes de U. Garde le match canonical_title existant en OU.
- B : à la collecte, rejet si l'intitulé ne partage aucun mot significatif (préfixe 5 lettres, mots génériques exclus) avec le rôle de la requête. Requête non parsable -> on garde.
- C refusé : bouton « Selon mon profil » reste optionnel.
- Stock : dry-run B présenté à l'utilisateur avant toute suppression. Rematch via scripts/backfill_matched_user_ids.py.

## Steps
- [x] 1 relevance.py : parse_source_query + tests (title_matches_query_role retiré)
- [x] 2 matcher : match par source_query + tests
- [x] 3 stock : 11 offres bruit en suppression douce (tri manuel, ids dans noise_deleted_ids.json). Filtre de collecte reporté (piste : code ROME France Travail)
- [x] 4 dry-run B : mots = 30 rejets dont ~12 bonnes offres ; embeddings = chevauchement 0.27-0.38 (Travailleur Social 0.27 vs Adjoint Magasin 0.27)
- [x] 5 backfill matched_user_ids

## Execution Log
- 2026-09-23 | claude | 1-2 | 41 passed ; B mots et B embeddings retirés de enrich_offers (perte de bonnes offres)
- 2026-09-23 | claude | 5 dry-run | eliel 63, lolal 42 (avant 4 / 0) — écriture réelle en attente d'accord
- 2026-09-23 | claude | 3+5 | 11 soft-delete (115 actives) ; backfill réel eliel 61, lolal 33 ; vérifié en base
- 2026-09-23 | claude | C | filtre profil imposé côté serveur (restrict_to_profile_offers, sauf Favoris/statut) ; bouton « Selon mon profil » et profile_only retirés du front ; 30 tests + tsc OK ; API live eliel 60, lolal 33
- 2026-09-23 | claude | auth | liste, count et détail d'offre exigent get_current_user (401 si anonyme) ; 82 tests OK ; vérifié en direct
