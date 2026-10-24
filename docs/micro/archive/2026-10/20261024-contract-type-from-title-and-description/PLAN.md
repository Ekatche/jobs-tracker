---
task: Déduire le type de contrat (stage, alternance…) de l'intitulé brut et de la description, pour que le filtre « Mes contrats ciblés » écarte les stages
description: type_contrat jamais déduit à la collecte — enrich_offers garde la valeur source et clean_job_title_syntax efface « Stage » de l'intitulé ; detect_contract_type (intitulé brut, marqueurs forts de description, valeur source canonisée Permanent→CDI) dans normalization.py, branché dans enrich_offers, remplace l'étape 0 morte de normalize_offer_fields ; script backfill_contract_types.py en simulation / --apply ; filtre _build_contract_type_filter stage|alternance
status: done
created: 2026-10-24
---

# Déduire le type de contrat de l'intitulé brut et de la description

## Context
- Existing code checked:
  - Exemple de l'utilisateur : https://www.linkedin.com/jobs/view/4481312374/ (Solvay).
    - Sur LinkedIn, l'intitulé est « Stage Data Science (F/H/X) », avec le niveau « Stagiaire / Alternant », le type d'emploi « Temps plein », et dans le texte « stage de 3 à 4 mois » et « Gratification de stage ».
    - En base locale : `poste` vaut « Data Science », `raw_poste` vaut « Stage Data Science (F/H/X) » et `type_contrat` vaut « Non spécifié ». La description dit « Le stagiaire Data Scientist… ». L'offre est rattachée au profil (`matched_user_ids`).
  - Cause : `enrich_offers` (`backend/app/tasks/job_offers_collectors.py:297`, `:364`) enregistre `type_contrat` tel que la source le donne, puis `clean_job_title_syntax` (`:336`) retire « Stage » de l'intitulé.
    - jobspy ne donne « Stage » que si `job_type` vaut « internship » (`sources/jobboards.py:22`). Ici, LinkedIn donne « fulltime ».
    - La seule déduction depuis l'intitulé est l'étape 0 de `normalize_offer_fields` (`normalization.py:525-538`), et cette fonction n'est appelée que par les tests.
  - Le filtre existe déjà et marche :
    - `_build_contract_type_filter` (`routers/job_offers.py:200`) exclut les `type_contrat` qui contiennent `stage|alternance` pour une recherche CDI/CDD/Freelance ;
    - la page Offres applique « Mes contrats ciblés » par défaut (`frontend/src/app/offers/page.tsx:781`) ;
    - le profil local cible `['CDI', 'CDD', 'Freelance / Prestation']`.
    
    Seul l'étiquetage manque.
  - Mesure en base locale, en lecture seule :
    - 380 offres, dont 299 en « Non spécifié » ;
    - parmi elles, 10 ont « stage » et 8 « alternance » dans `raw_poste` ;
    - les marqueurs forts de description en ajoutent quelques-unes ;
    - aucune des 61 offres CDI ou CDD ne contient ces marqueurs ;
    - 4 offres ont une valeur source anglaise ou composée (« Permanent », « Permanent contract ») que le filtre CDI ne reconnaît pas.
  - Le badge du frontend (`frontend/src/lib/contractBadge.ts`) affiche déjà « 🎓 Stage » ou « 📚 Alternance » dès que la valeur contient le mot. Rien à changer côté frontend.
  - Plans précédents : `docs/micro/plans/20261002-keep-unspecified-contracts-in-filter.md` (un « Non spécifié » reste visible : l'utilisateur écarte lui-même) et `archive/2026-10/20261002-offer-ux-tab-order-and-contract-filtering`.
- Fresh info looked up : jobspy LinkedIn remonte aussi `job_level` (« Seniority level »). Il n'est pas utilisé ici, car LinkedIn y confond stage et alternance (« Stagiaire / Alternant »).
- Git status checked : les fichiers du périmètre portent les changements du plan dédup du 2026-10-24 (terminé, archivé) et de plans antérieurs déjà terminés. Aucune session en cours dessus.

## Simpler Alternative Considered
- Exclure les offres de stage dès le matching (`offer_profile_matcher`) : rejeté. Le filtre d'affichage existe déjà, et il laisse l'utilisateur voir les stages s'il choisit « Tous les contrats ». L'étiquetage est la seule pièce manquante.
- Demander le contrat au LLM du crawler : il le fait déjà et a répondu « Non spécifié » ici. Les sources jobspy, elles, ne passent pas par le LLM. Une déduction déterministe, gratuite, couvre toutes les sources et la base existante.

## Surgical Scope
- **Files touched** :
  - `backend/app/services/normalization.py`
  - `backend/app/tasks/job_offers_collectors.py`
  - `backend/backfill_contract_types.py` (nouveau)
  - `backend/tests/test_normalization_and_dedup.py`
  - `backend/tests/test_job_offers_pipeline.py`
  - `docs/JOB_INGESTION_AND_NORMALIZATION.md`
- **Files NOT touched** : tous les autres, en particulier `backend/app/routers/job_offers.py` (autre session), `frontend/`, `backend/app/services/sources/jobboards.py`, `backend/job_crawler/crawler1.py` et `backend/app/services/offer_profile_matcher.py`
- **Symbols replaced** (→ to delete before done) : l'étape 0 en ligne de `normalize_offer_fields` (« Extraction préventive du type de contrat depuis le poste »), remplacée par un appel à `detect_contract_type`
- **Symbols extended** (→ keep) : `enrich_offers` (valeur de `type_contrat`), `normalize_offer_fields`

## Definition of Done
- [x] Build passes : `cd backend && uv run python -c "import app.tasks.job_offers_collectors, app.services.normalization, backfill_contract_types"` exit 0
- [x] Tests pass : `cd backend && uv run pytest tests/test_normalization_and_dedup.py tests/test_job_offers_pipeline.py -q` exit 0
- [x] Contrat déduit de l'intitulé brut (« Stage Data Science (F/H/X) » donne Stage, « Alternance - Data scientist » donne Alternance, « (stage ou alternance) » donne « Stage / Alternance », « Stage - … » avec une source CDI donne Stage — amendé, voir Notes) : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k contract_from_title` exit 0, au moins 3 tests sélectionnés
- [x] Contrat déduit des marqueurs forts de description (« Le stagiaire… », « stage de 3 à 4 mois », « contrat d'apprentissage ») : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k contract_from_description` exit 0, au moins 2 tests sélectionnés
- [x] Pas de faux stage, pour ne jamais masquer un CDI. Trois cas restent « Non spécifié » : une mention optionnelle (« éventuellement sous la forme d'un stage de fin d'études ou d'une alternance »), « Early-stage » dans l'intitulé, et un CDI qui parle d'« encadrer des stagiaires ». Commande : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k contract_not_inferred` exit 0, au moins 3 tests sélectionnés
- [x] Valeur source : « Permanent contract » est canonisé en CDI ; un « CDI » de la source l'emporte sur « Freelance » dans l'intitulé, mais pas sur « Stage » (amendé, voir Notes) ; « Temps partiel » reste tel quel quand rien d'autre n'est trouvé. Commande : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q -k contract_source` exit 0, au moins 3 tests sélectionnés
- [x] Collecte : `enrich_offers_sync` enregistre « Stage » pour l'intitulé « Stage Data Science (F/H/X) » sans contrat source : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q -k contract` exit 0, au moins 1 test sélectionné
- [x] Backfill en simulation par défaut : `grep -c '"--apply"' backend/backfill_contract_types.py` >= 1
- [x] Rejeu local en simulation, sans écriture : `docker exec -w /app -e PYTHONPATH=/app jobtracker-backend python backfill_contract_types.py` exit 0. L'offre Solvay passe de « Non spécifié » à Stage, au moins 15 offres « Non spécifié » passent à Stage ou Alternance, et aucune offre CDI ou CDD ne passe à Stage ou Alternance, sauf si son intitulé brut contient Stage ou Alternance (amendé, voir Notes).
- [x] Doc à jour : `grep -c 'detect_contract_type' docs/JOB_INGESTION_AND_NORMALIZATION.md` >= 1
- [x] No dead code : `grep -c 'Extraction préventive du type de contrat' backend/app/services/normalization.py` = 0 ; `cd backend && uv run python -m pyflakes app/services/normalization.py app/tasks/job_offers_collectors.py backfill_contract_types.py` exit 0
- [x] Type check : n/a — ni mypy ni ruff configurés dans `backend/pyproject.toml`
- [x] Manual check : n/a pour ce plan. Le backfill en prod (`--apply`) est lancé par l'utilisateur après relecture de la simulation, après déploiement.

## Steps
- [x] Step 1 : dans `normalization.py`, ajouter `detect_contract_type(source_contract, raw_title, description) -> str`. Ordre de décision :
  1. une valeur source reconnue est canonisée (Stage, Alternance, Freelance, CDI, CDD, Intérim) ;
  2. sinon, l'intitulé brut (« stage » précédé d'un tiret exclu, pour « early-stage ») ; stage et alternance ensemble donnent « Stage / Alternance » ;
  3. sinon, les marqueurs forts de la description seulement ;
  4. sinon, la valeur source non vide d'origine, ou « Non spécifié ».
  
  Remplacer l'étape 0 en ligne de `normalize_offer_fields` par un appel à cette fonction. Ajouter dans `test_normalization_and_dedup.py` les tests `contract_from_title`, `contract_from_description`, `contract_not_inferred` et `contract_source`. Vérif : `cd backend && uv run pytest tests/test_normalization_and_dedup.py -q` exit 0.
- [x] Step 2 : dans `enrich_offers`, `"type_contrat": detect_contract_type(type_contrat, poste, description)`, avec `poste` brut, avant nettoyage. Ajouter l'import et le test pipeline `contract`. Vérif : `cd backend && uv run pytest tests/test_job_offers_pipeline.py -q -k contract` exit 0.
- [x] Step 3 : créer `backend/backfill_contract_types.py`.
  - Toutes les offres non supprimées sont lues ; le nouveau contrat vaut `detect_contract_type(type_contrat, raw_poste or poste, description)`.
  - Le script affiche chaque changement et un décompte par transition.
  - Il écrit `type_contrat` seulement avec `--apply`.
  
  Vérif : grep `"--apply"` >= 1, puis la simulation locale (commande du DoD) exit 0, avec les transitions lues.
- [x] Step 4 : `docs/JOB_INGESTION_AND_NORMALIZATION.md`, section « Normalisation des offres entrantes » : décrire `detect_contract_type`, son ordre de décision, le filtre « Mes contrats ciblés » qui en dépend, et le backfill. Vérif : `grep -c 'detect_contract_type' docs/JOB_INGESTION_AND_NORMALIZATION.md` >= 1.
- [x] Step 5 (teardown) : scan d'orphelins borné à l'étape 0 remplacée (texte « Extraction préventive du type de contrat », regex en ligne de contrat dans `normalize_offer_fields`). Confirmer 0 orphelin, pyflakes exit 0, puis relancer tout le DoD.

## Code Review
- Dead code removed: yes — étape 0 en ligne de `normalize_offer_fields` supprimée (grep « Extraction préventive du type de contrat » = 0), pyflakes exit 0 sur les 3 fichiers
- Build status: pass — import des 3 modules exit 0 ; `pytest tests/test_normalization_and_dedup.py tests/test_job_offers_pipeline.py -q` exit 0, 71 passed
- Type errors: none — pas de type checker configuré (n/a) ; pyflakes propre
- Unintended side effects: none attendu. Effet voulu : une offre dont l'intitulé brut contient Stage ou Alternance est étiquetée ainsi, même si la source dit CDI (1 cas en base locale : Sopra Steria via SmartRecruiters). `normalize_offer_fields` canonise désormais aussi la valeur source (« Permanent » → CDI), sans appelant en prod
- Security surface touched: yes (script d'écriture en base `backfill_contract_types.py`, simulation par défaut) — semgrep local p/python + p/secrets sur les 3 fichiers : 0 finding, 0 erreur
- Verdict: ✅ DONE

## Execution Log
- 2026-10-24T11:49Z | claude-code | preflight | done | baseline DoD lu (voir Notes)
- 2026-10-24T11:49Z | claude-code | step 1 | started
- 2026-10-24T11:51Z | claude-code | step 1 | done | `uv run pytest tests/test_normalization_and_dedup.py -q` exit 0, 40 passed (27 + 13 nouveaux)
- 2026-10-24T11:51Z | claude-code | step 2 | started
- 2026-10-24T11:52Z | claude-code | step 2 | done | `uv run pytest tests/test_job_offers_pipeline.py -q -k contract` exit 0, 1 passed, 29 deselected
- 2026-10-24T11:52Z | claude-code | step 3 | started
- 2026-10-24T11:54Z | claude-code | step 1 | reopened | simulation step 3 : stage Sopra Steria (SmartRecruiters) étiqueté CDI par la source reste CDI — règle de priorité amendée, voir Notes
- 2026-10-24T11:54Z | claude-code | step 1 | done (re-vérifié après amendement) | `uv run pytest tests/test_normalization_and_dedup.py -q` exit 0, 41 passed
- 2026-10-24T11:54Z | claude-code | step 3 | done | grep `"--apply"` = 1 ; simulation locale exit 0, 43 changements : Solvay NS→Stage, 17 NS→Stage/Alternance, seul CDI→Stage = Sopra Steria « Stage - IA… » (intitulé)
- 2026-10-24T11:56Z | claude-code | step 4 | started
- 2026-10-24T11:56Z | claude-code | step 4 | done | `grep -c 'detect_contract_type' docs/JOB_INGESTION_AND_NORMALIZATION.md` = 2
- 2026-10-24T11:56Z | claude-code | step 5 | started
- 2026-10-24T12:06Z | claude-code | step 5 | done | grep étape 0 = 0 ; pyflakes exit 0 ; DoD complet relancé, tout exit 0
- 2026-10-24T12:08Z | claude-code | close-out | done | DoD frais (build 0, tests 71 passed, sélections -k 4/3/4/3/1, --apply 1, doc 2, orphelin 0, pyflakes 0) ; simulation 43 changements ; diff relu ; test pipeline 0,01 s sans Mongo ; semgrep 0

## Notes
- Fichiers de convention relus en préflight : `CLAUDE.md` (racine ; `AGENTS.md` et `GEMINI.md` identiques, `diff -q` vide) et `.cursorrules` (outils code-review-graph). Pas d'autre fichier de convention sous `backend/`.
- Baseline DoD (avant tout changement) :
  - build exit 1 (`backfill_contract_types` absent) ;
  - tests exit 0, 56 passed ;
  - les sélections `-k contract_*` et `-k contract` donnent exit 5 (aucun test) ;
  - `--apply` absent ; doc 0 ;
  - texte de l'étape 0 présent (1) ;
  - pyflakes exit 1 (fichier absent seulement).
- Valeurs `type_contrat` en base locale : Non spécifié 299, CDI 57, Stage 13, CDD 3, Permanent 3, Freelance 2, « CDD / Temporaire » 1, Alternance 1, « Permanent contract » 1.
- Le filtre « Mes contrats ciblés » envoie la regex `CDI|CDD|Freelance` (`frontend/src/app/offers/page.tsx:569-570`). Les libellés canoniques CDI, CDD et Freelance restent donc compatibles.
- Garde-fous ajoutés à la conception :
  - « early/seed/late/growth stage » (stade de startup) n'est pas un stage ;
  - « apprentissage automatique/profond… » (machine learning) n'est pas une alternance ;
  - « le/la stagiaire » ne compte qu'en début de phrase, sinon un CDI qui « encadrera le stagiaire » serait masqué ;
  - « votre stage » est exclu (un CDI junior peut écrire « votre stage de fin d'études »).
- Hors périmètre, à signaler :
  - le prompt du crawler (`crawler1.py:255`) pourrait demander de déduire le contrat du contenu ;
  - `job_level` de jobspy n'est pas exploité ;
  - les offres d'un contrat non ciblé restent rattachées au profil (`matched_user_ids`) : elles sont seulement masquées par le filtre par défaut.
- **Amendement (2026-10-24, trouvé par la simulation de l'étape 3)** :
  - Constat : l'offre Sopra Steria « Stage - IA et management opérationnel en ingénierie… » (`ats_platform: smartrecruiters`) a `type_contrat` CDI, alors que sa description dit « le stage vise à… ». Avec la règle d'origine (la source l'emporte toujours), ce stage restait visible en CDI.
  - Nouvelle règle : « Stage » ou « Alternance » dans l'intitulé brut l'emporte sur la valeur de la source ; pour les autres contrats, la source garde la priorité.
  - Conséquences sur les tests :
    - le test `contract_source` « CDI source vs Stage titre » devient `contract_from_title_stage_overrides_source` ;
    - un test `contract_source` CDI source vs « Freelance » dans le titre est ajouté ;
    - `TestNormalizeOfferFields.test_preserve_existing_contract_if_present` passe de « Développeur Stage Master » à « Développeur Python Freelance », pour garder son intention (une valeur source reconnue est conservée).
- Clôture : le test `test_enrich_infers_contract_from_raw_title` attendait 30 s le timeout de sélection Mongo dans `normalize_role` (via `get_database`), avant de retomber sur l'intitulé nettoyé. `normalize_role` est maintenant patché avec `monkeypatch` (convention du fichier) : le test passe en 0,01 s, sans service. Les tests `enrich` existants gardent ce délai de 30 s par offre ; c'est hors périmètre, à signaler.
