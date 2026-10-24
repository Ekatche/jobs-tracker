---
task: Fusionner les doublons inter-job-boards quand le nom d'entreprise ou la ville varie d'un site à l'autre
description: "Doublons d'offres non fusionnés entre LinkedIn, Indeed, HelloWork et WTTJ : variantes de nom d'entreprise (BackMarket/Back Market, JEMS/Jems Group, Orange/Orange Business, Néosoft/Neosoft, Crédit Agricole/Crédit Agricole Centre-est) et ville avec apostrophe typographique. Touche company_match_strength, are_offers_duplicates et deduplicate_and_merge_offers (normalization.py), les candidats de save_offers_to_database via distinct(entreprise) et sans plafond to_list(20) (job_offers_collectors.py), et le script retroactive_dedup_job_offers.py (dry-run, garde sur candidatures, évaluations et kits d'entretien, user_offer_interactions)"
status: done
created: 2026-10-24
---

# Doublons inter-job-boards : variantes d'entreprise et de ville

## Context
- Existing code checked :
  - Signalement initial : offres Sanofi en double venant de plusieurs job boards. Le probe en lecture seule (lancé en prod par l'utilisateur) trouve 2 offres Sanofi aux intitulés distincts, déjà fusionnées (HelloWork « Data Scientist » avec 3 `alternative_urls`, LinkedIn « Data and AI Engineer » avec 1). La base locale ne contient aucun doublon Sanofi. Le frontend n'affiche jamais `alternative_urls` (aucune occurrence dans `frontend/src`). L'utilisateur demande ensuite de « régler ce problème pour toutes les offres ».
  - Scan de la base locale (419 offres, `scratchpad/dupes_prod_probe.py`) : les vrais doublons ratés viennent tous de **variantes du nom d'entreprise**. Exemples : « BackMarket » contre « Back Market », « JEMS » contre « Jems Group », « Orange » contre « Orange Business », « EPSA » contre « EPSA Tax », « Néosoft » contre « Neosoft ». S'y ajoutent deux paires Crédit Agricole, rejetées par la **ville** : « Champagne-Au-Mont-D'Or » contre « Champagne-Au-Mont-D’Or » (apostrophe typographique).
  - Probe prod en lecture seule, lancé par l'utilisateur le 2026-10-24 (498 offres) :
    - Sanofi : la fusion est correcte. L'offre HelloWork « Data Scientist » porte LinkedIn 4477677163 (sous deux formes d'URL) et `jobs.sanofi.com/.../data-scientist/...`, donc une seule et même offre. Aucune fusion erronée à séparer.
    - 22 paires suspectes entre variantes de nom, contre 6 dans une même entreprise (titres différents, hors périmètre). Exemples : Caisse d'Epargne/Caisse d'Epargne Ile-de-France, ELCIA/ELCIA Group, EPSA/EPSA France, GRAAD/GRAAD SANTE, Mantu/Mantu Manager Program, Nexton/Nexton Consulting, plus les cas déjà vus en local.
    - Troisième forme de ville ratée : « Lyon, Auvergne-Rhône-Alpes, France » (SmartRecruiters) contre « Lyon ». Elle fait rater Devoteam « Senior Data Engineer Snowflake » (titre 1.00, description 0.70).
    - Le titre genré « Contrôleur de gestion/Contrôleuse de gestion » contre « Contrôleur de Gestion » (JEMS, titre 0.65, description 0.71) n'est capté que si la règle faible reprend la voie Jaccard ≥ 0.65 de la règle standard.
  - Cause 1, `backend/app/services/normalization.py:768-811` `deduplicate_and_merge_offers` : regroupe par `normalize_company().lower()` exact. Deux variantes ne sont jamais comparées.
  - Cause 2, `backend/app/tasks/job_offers_collectors.py:479-489` `save_offers_to_database` : les candidats en base sont cherchés par regex `^{norm_comp}$` sur `entreprise` brut. Trois effets :
    - une variante n'est jamais trouvée ;
    - un nom stocké avec suffixe (« Sanofi SA ») n'est pas trouvé non plus ;
    - les candidats sont plafonnés à 20 sans tri.
  - Cause 3, `normalization.py:591-639` `are_offers_duplicates` :
    - entreprise acceptée seulement si égale ou si `SequenceMatcher` ≥ 0.85 sur les noms bruts normalisés. « jems » contre « jems group » (0.57) est rejeté, « néosoft » contre « neosoft » aussi en exact ;
    - ville comparée sans repli des accents ni de la ponctuation.
  - `normalize_company` (`normalization.py:58`) ne replie ni les accents ni la ponctuation. `compute_unique_key` en dépend : **non modifié**, sinon toutes les `unique_key` existantes changent (index d'unicité, `$group` de la liste).
  - Brouillon jetable validé sur la base locale (`scratchpad/company_match_spike.py`) :
    - **règle forte** : clés alphanumériques repliées égales, ou ratio ≥ 0.85 ;
    - **règle faible** : les jetons d'un nom sont un préfixe de ceux de l'autre. Elle applique la règle standard (intitulé concordant, ou Jaccard ≥ 0.65 avec titre ≥ 0.45) **et** exige en plus un Jaccard de description ≥ 0.5 ;
    - **ville** : comparaison repliée (accents, ponctuation) sur le segment avant la première virgule.
    - Vérifié aussi : 0 écart entre l'ancienne et la nouvelle règle sur les paires d'une même entreprise (`scratchpad/same_company_delta.py`).
    - Résultat : 8 nouvelles paires fusionnées, toutes de vrais doublons (titre 1.00 ou 0.93, description 0.46 à 0.74), aucun faux positif. Les 11 couples de noms en correspondance faible sont tous du même groupe (Akkodis/Akkodis France, Sopra Steria/Sopra Steria Next…). Les paires faibles aux intitulés différents restent séparées (Devoteam 0.15, Sopra 0.31, Orange HelloWork « Data Engineer Senior »).
  - `backend/retroactive_dedup_job_offers.py` (seul outil pour les doublons déjà en base) est **dangereux** en l'état :
    - il supprime le doublon sans rattacher `applications.offer_id`, `offer_evaluations` ni `interview_preps` (cause connue du « Offre non trouvée », mémoire `orphan-offer-ids-after-oct5-restore`) ;
    - il rattache les interactions à `user_interactions`, alors que la collection réelle est `user_offer_interactions` (16 usages dans `backend/app`) ;
    - il plafonne la lecture à 1000 offres et n'a pas de mode simulation.
  - Tests existants : `tests_for` donne `backend/tests/test_normalization_and_dedup.py` (`test_are_offers_duplicates_by_title_and_company`, `test_are_offers_duplicates_rejects_different_cities`, `test_deduplicate_and_merge_offers_trio`). Côté enregistrement : `backend/tests/test_job_offers_pipeline.py:586-720`. `test_save_offers_to_database_returns_offer_ids_on_insert` simule `find` mais pas `distinct` : son mock doit suivre le nouveau contrat.
- Fresh info looked up : n/a. `collection.distinct` et l'opérateur `$in` de Motor sont déjà utilisés dans le dépôt ; `unicodedata` fait partie de la stdlib.
- Git status checked :
  - `normalization.py`, `retroactive_dedup_job_offers.py` et `test_normalization_and_dedup.py` sont propres.
  - `job_offers_collectors.py`, `test_job_offers_pipeline.py` et `docs/JOB_INGESTION_AND_NORMALIZATION.md` portent les changements non commités du plan Tavily de cette même session, terminé : les deux diffs cohabitent, sans chevauchement de lignes.
  - Aucun fichier d'une autre session n'est dans le périmètre.

## Simpler Alternative Considered
Deux options plus simples ont été écartées :
- **Seulement abaisser le seuil de ratio d'entreprise (0.85 → 0.5)** : écarté. « jems » contre « jems group » passerait, mais aussi des noms sans rapport. Le seuil ne capte pas la vraie structure (nom de groupe en préfixe), et la ville avec apostrophe resterait rejetée.
- **Stocker un champ `company_key` indexé** : écarté. Il faudrait un backfill en prod avant que les nouvelles offres retrouvent les anciennes. `distinct("entreprise")`, lu une fois par lot, donne les mêmes candidats sans migration.

## Surgical Scope
- **Files touched** :
  - `backend/app/services/normalization.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `backend/retroactive_dedup_job_offers.py`
  - `backend/tests/test_normalization_and_dedup.py`
  - `backend/tests/test_job_offers_pipeline.py`
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md`
- **Files NOT touched** :
  - `backend/app/routers/job_offers.py`, `backend/app/routers/applications.py`, `backend/app/routers/interview_prep.py`, tout `frontend/` (autres sessions) ;
  - `compute_unique_key` et `normalize_company` (format des `unique_key` existantes inchangé) ;
  - aucune écriture en base de prod par Claude.
- **Symbols replaced** (to delete before done) :
  - le regroupement `company_groups` de `deduplicate_and_merge_offers` ;
  - la requête regex `^{norm_comp}$` et le `.to_list(20)` de `save_offers_to_database` ;
  - `import re` et l'import `normalize_company` de `job_offers_collectors.py` s'ils deviennent orphelins ;
  - la réaffectation vers `db["user_interactions"]` et le `to_list(1000)` du script rétroactif.
- **Symbols extended** (keep) : `are_offers_duplicates` (même signature, règle d'entreprise et de ville élargie), `save_offers_to_database`, `deduplicate_collection` ; ajout de `company_match_strength` dans `normalization.py` et de `pick_survivor` dans le script.

## Definition of Done
- [x] Build passes: `cd backend && uv run python -c "import app.tasks.job_offers_collectors, app.services.normalization, retroactive_dedup_job_offers"` exit 0
- [x] Tests pass: `cd backend && uv run pytest tests/test_normalization_and_dedup.py tests/test_job_offers_pipeline.py -q` exit 0
- [x] Variantes de nom fusionnées : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k company_variant` exit 0, au moins 3 tests sélectionnés. Ils couvrent la règle forte (BackMarket, Néosoft), la règle faible avec description (JEMS, y compris le titre genré « Contrôleur de gestion/Contrôleuse de gestion »), et le refus d'une variante faible sans description concordante.
- [x] Ville à apostrophe typographique compatible : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k apostrophe` exit 0, au moins 1 test sélectionné
- [x] Ville suivie d'une région ou d'un pays compatible (« Lyon, Auvergne-Rhône-Alpes, France » contre « Lyon ») : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k city_region` exit 0, au moins 1 test sélectionné
- [x] Enregistrement : une offre « Back Market » met à jour l'offre « BackMarket » existante au lieu d'en créer une : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q -k company_variant` exit 0, au moins 1 test sélectionné
- [x] Script rétroactif sûr : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k pick_survivor` exit 0, au moins 2 tests sélectionnés (survivant = offre référencée ; paire sautée quand les deux sont référencées)
- [x] Script en simulation par défaut : `grep -c '"--apply"' backend/retroactive_dedup_job_offers.py` >= 1 et `grep -c 'user_interactions"' backend/retroactive_dedup_job_offers.py` = 0
- [x] Rejeu sur la base locale, en simulation et sans écriture : `docker exec -w /app -e PYTHONPATH=/app jobtracker-backend python retroactive_dedup_job_offers.py` exit 0. Il liste les 8 paires du brouillon (BackMarket, EPSA, Orange, JEMS ×2, Crédit Agricole ×2, Néosoft) et aucune autre paire inter-entreprises.
- [x] Doc à jour : `grep -c 'company_match_strength' docs/JOB_INGESTION_AND_NORMALIZATION.md` >= 1
- [x] No dead code: `grep -cE 'company_groups|to_list\(20\)|\$regex' backend/app/tasks/job_offers_collectors.py backend/app/services/normalization.py` = 0 pour chacun ; aucun `import` inutilisé ajouté (vérifié par `uv run python -m pyflakes` sur les 3 fichiers source si disponible, sinon par lecture du diff)
- [x] Type check: n/a — ni mypy ni ruff configurés dans `backend/pyproject.toml`
- [x] Manual check: n/a pour ce plan. La fusion des doublons existants en prod (`--apply`) est lancée par l'utilisateur après relecture de la simulation, hors de ce plan.

## Steps
- [x] Step 1 : dans `normalization.py`, ajouter `company_match_strength(c1, c2)`, qui renvoie `"strong"`, `"weak"` ou `None` (jetons alphanumériques repliés sans accents, à partir de `normalize_company`). `are_offers_duplicates` l'utilise. En règle faible, il applique la règle standard et exige en plus un Jaccard ≥ 0.5. La compatibilité de ville se fait sur la forme repliée du segment avant la première virgule. `deduplicate_and_merge_offers` compare chaque offre à tous les survivants, au lieu des groupes par entreprise exacte. Ajouter les tests `company_variant`, `apostrophe` et `city_region` dans `test_normalization_and_dedup.py`. Vérif : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q` exit 0.
- [x] Step 2 : dans `save_offers_to_database`, quand la recherche directe échoue :
  - lire une fois par lot `await collection.distinct("entreprise")` ;
  - garder les noms pour lesquels `company_match_strength` n'est pas `None` ;
  - charger `find({"entreprise": {"$in": noms}}).to_list(None)`.
  
  Supprimer la regex, le plafond 20 et les imports devenus orphelins. Adapter le mock du test d'insertion (`distinct`) et ajouter le test `company_variant` d'enregistrement. Vérif : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q` exit 0.
- [x] Step 3 : `retroactive_dedup_job_offers.py`.
  - Simulation par défaut, écriture seulement avec `--apply`. Toutes les offres non supprimées sont lues (`to_list(None)`).
  - Les paires sont cherchées entre noms d'entreprise compatibles (`company_match_strength`), puis validées par `are_offers_duplicates`.
  - `pick_survivor` garde l'offre référencée par `applications`, `offer_evaluations` ou `interview_preps`, sous les formes `str` et `ObjectId`. La paire est sautée et signalée si les deux sont référencées.
  - Les interactions sont rattachées dans `user_offer_interactions`.
  - Ajouter les tests `pick_survivor`. Vérif : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k pick_survivor` exit 0, puis la simulation locale (commande du DoD) exit 0, avec la liste des paires lue.
- [x] Step 4 : mettre à jour la ligne `clean_duplicate_offers` de `docs/JOB_INGESTION_AND_NORMALIZATION.md`. Elle doit décrire la règle forte et la règle faible de `company_match_strength`, la ville repliée et le script rétroactif en simulation. Vérif : `grep -c 'company_match_strength' docs/JOB_INGESTION_AND_NORMALIZATION.md` >= 1.
- [x] Step 5 (teardown) : scan d'orphelins borné aux symboles remplacés (`company_groups`, regex `^{norm_comp}$`, `to_list(20)`, `user_interactions`, `import re`, import `normalize_company` des collecteurs). Confirmer 0 orphelin, puis relancer tout le DoD.

## Code Review
- Dead code removed: yes. Le regroupement `company_groups`, la recherche `$regex` `^{norm_comp}$` plafonnée par `to_list(20)`, la collection fautive `user_interactions`, ainsi que `import re` et l'import `normalize_company` des collecteurs ont été retirés. grep de code mort : 0 et 0 ; pyflakes exit 0 sur les 3 fichiers.
- Build status: pass (import des 3 modules, exit 0)
- Type errors: none (n/a, aucun type checker configuré)
- Unintended side effects: trois effets voulus, à connaître.
  - `deduplicate_and_merge_offers` rend les offres dans leur ordre de première apparition, et non plus groupées par entreprise. Aucun appelant ne dépend de cet ordre.
  - Deux offres d'entreprise inconnue (« non spécifié ») qui partagent la même URL fusionnent désormais. Avant, elles restaient dans des groupes séparés.
  - `save_offers_to_database` appelle `distinct("entreprise")` une seule fois par lot, et seulement quand la recherche directe échoue.
- Security surface touched: yes, requête Mongo. La regex construite depuis un nom d'entreprise scrapé est remplacée par un `$in` dont les valeurs viennent de `distinct`, donc de la base, ce qui réduit la surface. Écritures du script rétroactif seulement avec `--apply`. semgrep CLI (`p/python` + `p/secrets`, `--error`) sur les 3 fichiers : pass, 0 finding.
- Verdict: ✅ DONE

## Execution Log
- 2026-10-24T11:07Z | claude-code | preflight | done | build exit 0, 46 passed, test_duplicate_cleaning 1 passed
- 2026-10-24T11:07Z | claude-code | step 1 | started
- 2026-10-24T11:11Z | claude-code | step 1 | done | `pytest tests/test_normalization_and_dedup.py -q` exit 0 (24 passed) ; -k company_variant 4, apostrophe 1, city_region 1 ; test_duplicate_cleaning exit 0 ; dédup locale 419 offres en 0.20 s, 838 en 0.40 s
- 2026-10-24T11:11Z | claude-code | step 2 | started
- 2026-10-24T11:14Z | claude-code | step 2 | done | `pytest tests/test_job_offers_pipeline.py -q` exit 0 (29 passed) ; -k company_variant 1 passed ; `import re` et import `normalize_company` retirés (plus aucun usage)
- 2026-10-24T11:14Z | claude-code | step 3 | started
- 2026-10-24T11:17Z | claude-code | step 3 | done | -k pick_survivor 2 passed ; `"--apply"` = 1, `user_interactions"` = 0 ; simulation locale exit 0 : 380 offres, 8 paires (Crédit Agricole ×2, JEMS ×2, Néosoft, Orange, EPSA, BackMarket), aucune autre, 0 sautée
- 2026-10-24T11:17Z | claude-code | step 4 | started
- 2026-10-24T11:18Z | claude-code | step 4 | done | `grep -c 'company_match_strength' docs/JOB_INGESTION_AND_NORMALIZATION.md` = 1
- 2026-10-24T11:18Z | claude-code | step 5 | started
- 2026-10-24T11:25Z | claude-code | step 5 | done | grep orphelins dans les collecteurs exit 1 (0 ligne) ; grep de code mort 0/0 ; pyflakes exit 0
- 2026-10-24T11:25Z | claude-code | close out | done | DoD relancé à 11:23Z, tout vert. Build exit 0 ; 56 passed. Sélections : company_variant 5, apostrophe 1, city_region 1, pick_survivor 2, pipeline company_variant 1. `"--apply"` = 1 ; `user_interactions"` = 0 ; doc = 1. test_duplicate_cleaning 1 passed. Simulation locale exit 0 : 380 offres, 8 paires inter-entreprises attendues, 0 sautée. semgrep 0 finding.

## Notes
- Fichiers de convention lus : `CLAUDE.md` (racine : code-review-graph d'abord, règles de pertinence des tests), `~/.claude/CLAUDE.md`.
- Mesure en prod à faire par l'utilisateur, en lecture seule. `scratchpad/dupes_prod_probe.py` a été testé en local (exit 0) ; il liste les URL fusionnées de Sanofi, les paires non fusionnées par cause et les paires entre variantes de nom. Commande : `ssh sentinel-vps 'docker exec -i -w /app -e PYTHONPATH=/app jobtracker-backend python -' < dupes_prod_probe.py`.
- Après le plan, en prod : l'utilisateur lance `retroactive_dedup_job_offers.py` en simulation. D'après le probe, il doit lister environ 14 paires (Caisse d'Epargne, Crédit Agricole ×2, Devoteam Snowflake, ELCIA, EPSA France, GRAAD, JEMS ×3, Mantu, Néosoft, Nexton, Orange), plus les 2 paires que le probe n'a pas affichées. Il relit cette liste avant de lancer `--apply`.
- Limite connue, acceptée : EPSA contre EPSA Tax (titre 1.00, description 0.29) reste séparé, car la règle faible exige une description ≥ 0.5. Un doublon raté coûte moins cher qu'une fusion à tort.
- Limite connue, hors périmètre : une ville voisine (Villeurbanne contre Lyon, Akkodis) reste un rejet dur. Un seul cas local, d'ailleurs incertain (description 0.29) : pas de règle de proximité géographique sans plus de données.
- Préflight 2026-10-24 :
  - Fichiers de convention relus : `CLAUDE.md`, `AGENTS.md` et `GEMINI.md` (identiques), `.cursorrules` (consignes code-review-graph seulement).
  - Le conteneur local monte `backend/` sur `/app` : la simulation locale tourne sur le code modifié. L'import de `retroactive_dedup_job_offers` n'exécute rien (garde `__main__`).
  - Autres appelants de `deduplicate_and_merge_offers`, hors périmètre et non modifiés : `clean_job_offer_duplicates_optimized` (`services/job_offers.py:97`), utilisé par `remove_similarity_duplicates` (`tasks/clean_job_offers.py:233`). Le DAG Airflow `clean_job_offers` force `enable_global_similarity=True`, qui passe par `fast_similarity_check` et non par cette fonction. Le changement ne déclenche donc aucune fusion automatique des offres déjà en base.
  - Test de régression hors DoD, à relancer en fin de plan : `cd backend && uv run pytest app/tasks/tests/test_duplicate_cleaning.py -q`. Baseline : 1 passed.
- Baseline du DoD, avant tout changement :
  - build exit 0 ;
  - tests : 46 passed ;
  - `-k company_variant`, `apostrophe`, `city_region` et `pick_survivor` : 0 test sélectionné (attendu) ;
  - `"--apply"` = 0 et `user_interactions"` = 2 (attendu avant l'étape 3) ;
  - `company_match_strength` dans la doc = 0 ;
  - grep de code mort : `job_offers_collectors.py` = 2, `normalization.py` = 3 ;
  - pyflakes 3.3.2 disponible.
