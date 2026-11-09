# Bilan vérifié : comparaison Serper / Tavily

**Date :** 2026-11-08  
**Décision :** conserver Tavily pour la collecte ; aucune migration Serper n'est retenue.  
**Statut de la branche d'exploration :** archivée dans ce document puis supprimée (`feature/exploration-serper`).

## Résultat observé

Le fichier local ignoré par Git `backend/scripts/data/bench_serper_tavily/run_bench_20261108_210029_604d3c_results.json` contient un run commun sur une requête `q01`. Les deux recherches sont marquées réussies :

| Mesure du rapport | Tavily | Serper |
|---|---:|---:|
| Appels enregistrés | 2 | 3 |
| Crédits enregistrés par le banc | 4 | 3 |
| URL uniques retenues | 30 | 8 |
| Offres extraites | 20 | 4 |
| URL préannotées pertinentes | 13 | 4 |

Le rapport compte 4 URL communes et 34 enregistrements évalués. **Aucune annotation humaine n'est enregistrée** : les 13 et 4 sont des préannotations automatiques, et non des offres confirmées pertinentes par un lecteur. Les résultats proviennent d'une seule requête ; ils ne démontrent ni un avantage général de couverture ni un facteur de qualité durable. Les stratégies et nombres de résultats demandés ne sont pas strictement identiques.

Le banc utilise une référence JobSpy vide dans ce run (`jobspy_urls=set()`). La métrique affichée comme incrémentale par rapport à JobSpy ne démontre donc pas le gain réel par rapport à cette source. Les données brutes restent locales dans `backend/scripts/data/bench_serper_tavily/` ; ce document ne reprend pas les URL ou contenus d'offres.

## Coûts : hypothèses du modèle

Selon la [documentation Tavily](https://docs.tavily.com/documentation/api-credits), une recherche `advanced` coûte 2 crédits, 1 000 crédits mensuels sont gratuits et le tarif à l'usage indiqué est de 0,008 $ par crédit au-delà du quota du plan. Deux passes par requête complète représentent 4 crédits, hors replis et autres usages du compte : le quota couvrirait donc au plus **250 requêtes complètes par mois** s'il leur était entièrement réservé.

Le [tarif Serper affiché](https://serper.dev/) indique 2 500 recherches d'essai et un pack de 50 000 crédits à 50 $ hors taxes, valable six mois. Le modèle du banc suppose l'essai épuisé et amortit un pack sur six mois : 50 / 6 = 8,33 $/mois. Avec Tavily en paiement à l'usage et 4 crédits par requête, l'égalité théorique est `250 + (50 / 6) / (4 × 0,008) = 510,42` requêtes complètes par mois. À volume entier constant, le dépassement intervient à 511 requêtes.

Ce seuil dépend du plan Tavily actif, du partage du quota gratuit, des essais, du nombre de passes et replis, des taxes et de l'amortissement d'un achat prépayé.

## Éléments conservés et intégrés sur `main`

1. **Filtrage anti-bruit ATS en production (`87ef7bd`)** :
   - Intégré dans [`backend/job_trackers/src/job_trackers/tools/custom_tool.py`](file:///Users/elielkatche/job-tracker/backend/job_trackers/src/job_trackers/tools/custom_tool.py) et couvert par `test_ats_noise_filtering` dans [`backend/tests/test_crew_models_and_tools.py`](file:///Users/elielkatche/job-tracker/backend/tests/test_crew_models_and_tools.py).
   - Exclusion des sous-domaines support/documentation (`support.`, `help.`, `docs.`, `blog.`, `status.`, `community.`), des pages vitrines `recruitee.com` / `teamtailor.com` sans chemin d'offre, et des portails génériques (`/resources/`, `/temoignages`, `jobsearch.ftl`, `joblist.ftl`, `/jobs/search`).
2. **Rotation journalière équitable et observabilité (`8030e98`)** :
   - Rotation déterministe des requêtes par jour calendrier (`toordinal()`) dans `build_search_queries` et corrélation des logs de collecte via `collection_query_id`.
3. **Hygiène et modularisation de la suite de tests (`1999dbf` à `1046251`)** :
   - Découpage des monolithes de tests en sous-modules < 300–400 lignes (`tests/evaluation/`, `tests/pipeline/`, `tests/interview_prep/`, `test_normalization.py`, `test_offer_dedup.py`, `test_matching_bench.py`).

## Suite éventuelle

Conserver Tavily en production. Si le volume mensuel dépasse durablement le seuil des ~510 requêtes complètes/mois, réévaluer sur un échantillon multi-métiers annoté humainement avec référence JobSpy figée.
