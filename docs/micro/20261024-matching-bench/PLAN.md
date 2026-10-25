---
task: Banc de mesure du matching (spec matching hybride, étape 1b) — export de prod, juge LLM, classements chronologique et Two-Pass
description: Banc de mesure 1b de la spec matching hybride — scripts/export_matching_bench.py (export Mongo en lecture seule lancé par l'utilisateur sur le VPS, échantillon seedé de 100 offres rattachées et non rattachées pour les profils actifs, interactions applied/hidden, comptages de publication, bson json_util) ; scripts/matching_bench.py (BenchDatabase en mémoire en lecture seule pour compute_offer_evaluation, juge LLM openai/gpt-6.1-sol via litellm acompletion avec cache, Two-Pass calcul pur, dry-run d'estimation de coût par défaut et --confirm pour dépenser, classements chronologique created_at et Two-Pass, Precision@10/@20, taux de faux positifs Top 20, cohérence du juge sur les interactions, accord juge/humain sur 20 paires CSV, coût et latence réels) ; résultats versionnés scripts/matching_bench_results.json sans données de profil ; tests sans réseau
status: blocked
created: 2026-10-24
---

# Banc de mesure du matching (étape 1b)

## Context
- Existing code checked:
  - `compute_offer_evaluation(db, user_id, offer_id, model=None) -> OfferEvaluationRun` (`backend/app/services/evaluation/evaluator.py:221`, livré par le plan archivé `20261024-twopass-pure-evaluation-compute`) fait trois lectures en base : `job_offers.find_one({"_id": oid})`, `candidate_profile.find_one({"$or": [{"user_id": str}, {"user_id": ObjectId}]})`, et `job_offers.count_documents({"entreprise": {"$regex": "^<entreprise échappée>$", "$options": "i"}, "canonical_title": ...})` si l'offre a `entreprise` et `canonical_title` (`:530`).
  - Hors base, il appelle `compute_domain_relevance` (embedding `text-embedding-3-small`, coût négligeable) et deux fois `acompletion` via `_acompletion_with_fallback`. Il lève `HTTPException` 404 (offre absente) ou 400 (ni description ni `competences_cles`).
  - Ce qu'un utilisateur connecté voit dans la liste d'offres (`backend/app/routers/job_offers.py`) : offres non supprimées (`is_deleted` absent ou faux, `:379`), rattachées à son profil (`matched_user_ids` contient son id en str, `restrict_to_profile_offers`, `:228-241`), offres masquées exclues (`:331-335`), tri `created_at` décroissant puis `_id` décroissant (`:436`). C'est la référence « chronologique » du §6.2.
  - Modèles et prix (`backend/app/services/usage_tracker.py:55-90`, `estimate_llm_cost`) : `gpt-6.1-sol` à 2 $ en entrée et 10 $ en sortie par M tokens (doc OpenAI vérifiée le 2026-09-30) ; `gemini-3.7-flash` et `gemini-3.8-flash` à 0,75 $ et 3,75 $.
  - `build_candidate_context(profile)` (`backend/app/services/profile/context.py:11`) est une projection pure du profil, celle que reçoit le Two-Pass.
  - Conventions des scripts : `backend/scripts/` est un package (`__init__.py`), et les tests importent `from scripts.<module> import ...` (`tests/test_profile_seed.py:2`). Squelette argparse et logging, plus `sys.path.insert(0, parent.parent)` (`scripts/backfill_matched_user_ids.py`). Le banc existant `scripts/letter_bakeoff.py` estime son coût avec une table de prix.
  - `backend/scripts/data/` est ignoré par git (`.gitignore:97`) ; `backend/scripts/matching_bench_results.json` ne l'est pas, il sera versionné.
  - `backend/app/database.py:30` écrit sur stdout à l'import (« Connexion à: … »). L'export ne peut donc pas sortir sur stdout : il écrit un fichier dans le conteneur, que l'utilisateur récupère ensuite.
  - Prod : conteneur `jobtracker-backend`, `WORKDIR /app` (`backend/Dockerfile:3`), joint par `ssh sentinel-vps`. Le script d'export n'est pas déployé : il est envoyé sur l'entrée standard (`python -`, où `__file__` vaut `'<stdin>'` et `sys.path[0]` vaut le répertoire courant, vérifié en local). En local, `./backend` est monté sur `/app` (`docker-compose.yml:11`).
  - `tests/conftest.py:13` charge `.env` sans `override` : des clés API invalides passées dans l'environnement y restent, et tout appel réseau réel échoue.
- Fresh info looked up: grille de prix OpenAI déjà relevée dans `usage_tracker.py` le 2026-09-30, aucune recherche supplémentaire. Juge : `openai/gpt-6.1-sol`, déjà utilisé pour les lettres et la préparation d'entretien, d'une autre famille que le Two-Pass (gemini), plus capable que `gpt-5-nano` (spec §6.1).
- Git status checked: périmètre propre. Aucun des fichiers à créer n'existe, `backend/scripts/` n'a aucune modification en cours. Les fichiers des autres sessions (`routers/`, `models.py`, `frontend/`) sont seulement lus.

## Simpler Alternative Considered
1. Lancer tout le banc en prod (`docker exec` sur le VPS), directement sur la base de prod, sans export. Rejeté : l'étape 3 relance le banc à chaque réglage de l'hybride. Un export figé rend les mesures reproductibles (le stock de prod bouge : offres archivées, nouvelles collectes) et permet de le relancer en local sans toucher à la prod.
2. Un seul script (export + banc). Rejeté : l'export tourne sur la base de prod. Un script court, en lecture seule et sans appel LLM, se relit d'un coup d'œil avant d'être lancé là-bas.
3. Versionner les annotations complètes (justifications du juge, évaluations Two-Pass). Rejeté : elles citent le parcours des candidats. Seuls les labels, scores, tokens et latences sont versionnés ; le détail reste dans `scripts/data/` (ignoré par git).

## Surgical Scope
- **Files touched**:
  - `backend/scripts/export_matching_bench.py` (nouveau)
  - `backend/scripts/matching_bench.py` (nouveau)
  - `backend/tests/test_matching_bench.py` (nouveau)
  - `backend/scripts/matching_bench_results.json` (nouveau, versionné, produit par le run de l'étape 7)
  - Fichiers générés, ignorés par git, dans `backend/scripts/data/matching_bench/` : `export.json`, `judge_cache.json`, `twopass_cache.json`, `validation.csv`
- **Files NOT touched**: tous les autres, en particulier tout `backend/app/` (dont `evaluator.py`, `models.py`, `routers/`), `frontend/` et `.gitignore`.
- **Symbols replaced** (→ to delete before done): none.
- **Symbols extended** (→ keep): none. `compute_offer_evaluation`, `build_candidate_context` et `estimate_llm_cost` sont seulement appelés.
- **Nouveaux symboles** :
  - `export_matching_bench.py` :
    - `select_sample(candidates, user_ids, excluded_ids, seed, per_profile=30, unmatched=40) -> List[str]` (pur) ;
    - `assign_aliases(interaction_counts) -> Dict[str, str]` (pur, A, B, … par nombre d'interactions décroissant, puis par user_id) ;
    - `build_export(db, user_ids, seed) -> dict` (async, lecture seule) ;
    - `main()`.
  - `matching_bench.py` :
    - `BenchDatabase` (lecture seule : `find_one` et `count_documents` seulement, aucune méthode d'écriture) ;
    - `JUDGE_MODEL`, `JUDGE_PROMPT_VERSION`, `LABELS`, `build_judge_messages`, `parse_judge_label` ;
    - `run_judge` et `run_twopass` (dry-run par défaut, `--confirm` pour dépenser) ;
    - `rank_chronological` et `rank_twopass` ;
    - `precision_at_k`, `false_positive_rate_at_k`, `judge_coherence`, `agreement` ;
    - `select_validation_pairs` et `build_results_payload` ;
    - sous-commandes `judge`, `twopass`, `validation-sheet`, `report`.

## Definition of Done
- [ ] Build passes: `cd backend && uv run python -c "import scripts.export_matching_bench, scripts.matching_bench"` exit 0
- [ ] Tests pass: `cd backend && uv run pytest tests/test_matching_bench.py -q` exit 0, au moins 10 tests passés
- [ ] Tests sans réseau : `cd backend && OPENAI_API_KEY=invalid GEMINI_API_KEY=invalid uv run pytest tests/test_matching_bench.py -q` exit 0
- [ ] Export et banc en lecture seule sur la base : `grep -cE '\.(insert_|update_|replace_|delete_|bulk_write|drop\(|find_one_and_)' backend/scripts/export_matching_bench.py backend/scripts/matching_bench.py` donne 0 pour chaque fichier, et `cd backend && uv run pytest tests/test_matching_bench.py -q -k bench_database` exit 0. Ce test fait tourner `compute_offer_evaluation` sur `BenchDatabase` avec le LLM simulé, vérifie que le comptage de publication exporté est bien rendu, et que les collections n'ont aucune méthode d'écriture.
- [ ] Calcul pur seulement, ni quota ni consommation enregistrée : `grep -cE 'evaluate_offer_two_pass|record_api_usage|require_user_quota' backend/scripts/matching_bench.py` = 0, et `grep -c 'compute_offer_evaluation' backend/scripts/matching_bench.py` ≥ 1
- [ ] Juge d'une autre famille que le Two-Pass : `grep -c 'JUDGE_MODEL = "openai/gpt-6.1-sol"' backend/scripts/matching_bench.py` = 1
- [ ] Aucune dépense sans `--confirm` : `cd backend && uv run pytest tests/test_matching_bench.py -q -k dry_run` exit 0, au moins 2 tests sélectionnés (juge et Two-Pass, LLM patché pour lever s'il est appelé)
- [ ] Échantillon conforme au §6.1 (mêmes offres pour tous les profils, rattachées et non rattachées, déterministe, sans offre ayant déjà une interaction) : `cd backend && uv run pytest tests/test_matching_bench.py -q -k select_sample` exit 0
- [ ] Données personnelles hors git : `git check-ignore -q backend/scripts/data/matching_bench/export.json` exit 0, et `cd backend && uv run pytest tests/test_matching_bench.py -q -k results_payload` exit 0 (le contenu versionné ne contient ni user_id, ni champ de profil, ni justification)
- [ ] Bout en bout sur la base locale, lecture seule et sans dépense : `docker exec jobtracker-backend python scripts/export_matching_bench.py --out scripts/data/matching_bench/export_local.json` exit 0, puis `docker exec jobtracker-backend python scripts/matching_bench.py judge --export scripts/data/matching_bench/export_local.json` et `... twopass --export ...` exit 0, avec le nombre d'appels et le coût estimé affichés
- [ ] Banc mesuré sur l'export de prod (étapes 5 à 7) : `cd backend && uv run python -c "import json; r=json.load(open('scripts/matching_bench_results.json')); m=r['meta']; assert r['metrics'] and len(r['twopass'])==m['n_profiles']*m['n_sample'] and len(r['judge'])==m['n_profiles']*m['n_sample']+m['n_interactions'] and r['human']"` exit 0
- [ ] No dead code: aucun symbole remplacé. `cd backend && uvx pyflakes scripts/export_matching_bench.py scripts/matching_bench.py tests/test_matching_bench.py` sans sortie
- [ ] Type check: n/a — ni mypy ni pyright configurés dans `backend/pyproject.toml`
- [ ] Manual check: étapes 5 à 7, observées par l'utilisateur (export de prod, accord sur la dépense, validation de 20 paires)

## Steps
- [x] Step 1: Écrire `backend/tests/test_matching_bench.py` d'abord, sans réseau ni base (LLM et embedding patchés sur `app.services.evaluation.evaluator.acompletion` et `compute_domain_relevance`, ou sur `scripts.matching_bench.acompletion` pour le juge). Tests prévus :
  - `select_sample` : déterministe, mêmes offres pour tous les profils, 30 offres par profil et 40 non rattachées, ids exclus absents, aucun doublon ; si une réserve est trop petite, prendre tout ce qu'elle contient sans planter ;
  - `assign_aliases` ;
  - `BenchDatabase` faisant tourner `compute_offer_evaluation` (`-k bench_database`) ;
  - `rank_chronological` : offres rattachées d'abord, les plus récentes en tête ;
  - `rank_twopass` : score décroissant, échecs en dernier ;
  - `precision_at_k` et `false_positive_rate_at_k` ;
  - `parse_judge_label` (label inconnu rejeté) ;
  - dry-run du juge et du Two-Pass sans appel LLM, cache inchangé (`-k dry_run`) ;
  - `build_results_payload` sans donnée de profil (`-k results_payload`) ;
  - `judge_coherence` et `agreement` ;
  - `select_validation_pairs` : 20 paires, réparties entre profils, déterministe.

  Vérification : `cd backend && uv run pytest tests/test_matching_bench.py -q` échoue, et uniquement sur `ModuleNotFoundError: No module named 'scripts.export_matching_bench'`.
- [x] Step 2: Écrire `backend/scripts/export_matching_bench.py`, en lecture seule.
  - Profils actifs : utilisateurs qui ont au moins une interaction `applied` ou `hidden` dans `user_offer_interactions` et un `candidate_profile` (`--user-id` répétable pour forcer la liste).
  - Offres candidates : non supprimées, `pipeline_stage` ≠ `"expired"`, avec une description non vide ou des `competences_cles`, sans interaction d'un profil actif. Seuls `_id` et `matched_user_ids` sont projetés, puis `select_sample` tire l'échantillon avec la graine `20261024`.
  - Contenu exporté :
    - documents complets de l'échantillon et des offres des interactions ;
    - `publication_counts`, calculés avec le filtre exact de l'évaluateur ;
    - profils ;
    - interactions ;
    - nombre d'offres d'interaction introuvables (offer_id morts après la restauration du 5 octobre).
  - Écriture avec `bson.json_util` dans `--out` (défaut : `scripts/data/matching_bench/export.json`). Journal sur stderr.

  Vérification : `cd backend && uv run pytest tests/test_matching_bench.py -q -k "select_sample or aliases"` exit 0, et la commande d'export local du Definition of Done exit 0, avec les comptages journalisés.
- [x] Step 3: Écrire `backend/scripts/matching_bench.py`.
  - `BenchDatabase` est construite depuis l'export.
  - Juge `openai/gpt-6.1-sol` : `temperature=0`, `response_format` JSON, `drop_params=True`. Le profil (`build_candidate_context`) est placé en tête du message utilisateur pour bénéficier du cache de prompt OpenAI, et la description est tronquée à 8000 caractères. Labels : `relevant`, `partial`, `irrelevant`, plus une justification courte.
  - Paires jugées : échantillon × profils, plus les interactions pour le seul profil concerné.
  - Two-Pass : `compute_offer_evaluation` sur échantillon × profils. Modèle par `--model`, par défaut `DEFAULT_EVALUATION_MODEL`.
  - Caches incrémentaux dans `scripts/data/matching_bench/` (clé : modèle | version | alias | offer_id ; écriture atomique). Seules les erreurs déterministes (`HTTPException`) entrent en cache ; les autres seront retentées au run suivant.
  - Sans `--confirm`, le script affiche le nombre d'appels restants et le coût estimé : pour le juge, prompt / 4 tokens et 200 tokens de sortie via `estimate_llm_cost` ; pour le Two-Pass, 0,0176 $ par paire, mesure du §6.2.
  - `--concurrency` : 8 par défaut pour le juge, 4 pour le Two-Pass.
  - `validation-sheet` écrit `validation.csv` : 20 paires à l'aveugle, sans le label du juge, 10 par profil, réparties par label du juge. Il refuse d'écraser un fichier existant.
  - `report` lit les caches et les labels humains du CSV, imprime les métriques par profil et par classement, puis écrit `scripts/matching_bench_results.json`. Métriques :
    - P@10, P@20 et taux de faux positifs dans le Top 20 ;
    - coût, latence moyenne et p90, et erreurs du Two-Pass ;
    - cohérence du juge sur les interactions ;
    - accord juge/humain, exact et binaire.

  Vérification : `cd backend && uv run pytest tests/test_matching_bench.py -q` exit 0, et les deux dry-runs locaux du Definition of Done exit 0.
- [x] Step 4 (teardown): aucun symbole remplacé, donc pas de scan d'orphelins.
  - `uvx pyflakes` sur les 3 fichiers, sans sortie.
  - Les `grep -c` de lecture seule, de calcul pur et de modèle juge donnent les valeurs attendues.
  - Supprimer `backend/scripts/data/matching_bench/export_local.json`, un artefact de vérification qui contient le profil local.
  - Vérification : les commandes ci-dessus et `test ! -e backend/scripts/data/matching_bench/export_local.json`.
- [x] Step 5 (utilisateur) : export de prod, en lecture seule, lancé par l'utilisateur. Depuis la racine du dépôt :
  `mkdir -p backend/scripts/data/matching_bench`
  `ssh sentinel-vps 'docker exec -i jobtracker-backend python - --out /tmp/matching_bench_export.json' < backend/scripts/export_matching_bench.py`
  `ssh sentinel-vps 'docker exec jobtracker-backend cat /tmp/matching_bench_export.json' > backend/scripts/data/matching_bench/export.json`
  `ssh sentinel-vps 'docker exec jobtracker-backend rm /tmp/matching_bench_export.json'`

  L'utilisateur donne aussi le modèle d'évaluation de prod : `ssh sentinel-vps 'docker exec jobtracker-backend printenv EVALUATION_MODEL'`, un nom de modèle et pas un secret.

  Vérification : `cd backend && uv run python -c "from bson import json_util; e=json_util.loads(open('scripts/data/matching_bench/export.json').read()); print(len(e['profiles']), len(e['sample_offer_ids']), len(e['interactions']))"` exit 0. Comptages notés dans `## Notes` et comparés aux chiffres annoncés par la spec : 2 profils, 41 interactions (30 `applied`, 11 `hidden`).
- [~] Step 6 (après accord de l'utilisateur sur la dépense) : afficher les dry-runs `judge` et `twopass` sur `export.json` et donner le coût estimé à l'utilisateur. Lancer ensuite, seulement après son accord, `docker exec jobtracker-backend python scripts/matching_bench.py judge --confirm` et `... twopass --confirm --model <modèle de prod>`.

  Vérification : un second dry-run des deux sous-commandes affiche 0 appel restant, hors erreurs déterministes listées. Coût réel relevé dans `## Notes`.
- [ ] Step 7 (utilisateur) : `docker exec jobtracker-backend python scripts/matching_bench.py validation-sheet`. L'utilisateur remplit la colonne `human_label` des 20 lignes de `backend/scripts/data/matching_bench/validation.csv`. Puis `docker exec jobtracker-backend python scripts/matching_bench.py report`.

  Vérification : la commande « Banc mesuré » du Definition of Done exit 0. Métriques recopiées dans `## Notes` : P@10, P@20 et faux positifs par profil et par classement, coût et latence du Two-Pass, accord du juge.

## Code Review
- Dead code removed:
- Build status:
- Type errors:
- Unintended side effects:
- Security surface touched:
- Verdict:

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-10-24T16:10Z | claude-code | preflight | done | baseline : build exit 1 (ModuleNotFoundError), pytest exit 4, check-ignore exit 0, pyflakes et conteneur local disponibles
- 2026-10-24T16:10Z | claude-code | step 1 | started
- 2026-10-24T16:14Z | claude-code | step 1 | done | `pytest tests/test_matching_bench.py -q` exit 2, seule erreur : `ModuleNotFoundError: No module named 'scripts.export_matching_bench'`
- 2026-10-24T16:14Z | claude-code | step 2 | started
- 2026-10-24T16:17Z | claude-code | step 2 | done | export local exit 0 par `python -` sur stdin (commande de prod) et par fichier : 1 profil, 380 offres candidates, échantillon de 70 (30 rattachées + 40 non rattachées), 1 interaction, 0 introuvable ; `-k "select_sample or aliases"` reporté à l'étape 3 (voir Notes)
- 2026-10-24T16:17Z | claude-code | step 3 | started
- 2026-10-24T16:23Z | claude-code | step 3 | done | `OPENAI_API_KEY=invalid GEMINI_API_KEY=invalid pytest tests/test_matching_bench.py -q` exit 0, 15 passed ; dry-run local `judge` exit 0 (71 paires, 0,88 $ estimés), `twopass` exit 0 (70 paires, 1,23 $ estimés), aucun cache créé
- 2026-10-24T16:23Z | claude-code | step 4 | started
- 2026-10-24T16:24Z | claude-code | step 4 | done | `uvx pyflakes` 3 fichiers sans sortie exit 0 ; écritures 0/0 ; quota 0 ; `compute_offer_evaluation` 4 ; `JUDGE_MODEL` 1 ; build exit 0 ; `git check-ignore` exit 0 ; `export_local.json` supprimé, `test ! -e` exit 0
- 2026-10-24T16:24Z | claude-code | step 5 | blocked | en attente de l'export de prod, lancé par l'utilisateur
- 2026-10-24T20:49Z | claude-code | step 5 | done | vérification exit 0 : 1 profil, 70 offres d'échantillon, 41 interactions (30 applied, 11 hidden, toutes du profil A), 11 offres d'interaction introuvables ; EVALUATION_MODEL prod = gemini/gemini-3.8-flash
- 2026-10-24T20:52Z | claude-code | step 6 | started
- 2026-10-24T20:53Z | claude-code | step 6 | dry-run | juge openai/gpt-6.1-sol 100 paires 1,33 $ ; Two-Pass gemini/gemini-3.8-flash 70 paires 1,23 $ ; total 2,56 $ sous le plafond de 7 $, --confirm lancés en arrière-plan (logs scratchpad bench_judge.log et bench_twopass.log)
- 2026-10-24T20:57Z | claude-code | step 6 | failure 1/2 | `judge --confirm` exit 0 mais 0 paire jugée sur 100 : `BadRequestError ... 'temperature' does not support 0 with this model. Only the default (1) value is supported.` Hypothèse : retirer `temperature=0` de `run_judge`. Two-Pass toujours en cours
- 2026-10-24T20:58Z | claude-code | step 6 | fix 1/2 ok | `temperature=0` retiré (`matching_bench.py`, commentaire), `pytest tests/test_matching_bench.py -q` 15 passed ; une paire jugée à la main : `partial`, 5 665 tokens en entrée, 67 en sortie, 0 de raisonnement ; `judge --confirm` relancé
- 2026-10-24T21:00Z | claude-code | step 6 | blocked | Two-Pass `twopass exit 0`, 70 évaluées, dry-run 0 restante ; juge `judge exit 0`, 93 jugées, dry-run 7 restantes (0,09 $) : `RateLimitError ... You have no credits remaining` (compte OpenAI à sec, erreur externe, pas déterministe)

## Notes
- Étape 6 (2026-10-24T21:00Z) :
  - premier `judge --confirm` : 0 paire jugée sur 100, `gpt-6.1-sol` refuse `temperature=0` et litellm ne le sait pas (`drop_params` ne retire rien). Correctif : paramètre retiré. Aucun coût, les 400 ne sont pas facturés ;
  - second `judge --confirm` : 93 paires jugées (18 `relevant`, 48 `partial`, 27 `irrelevant`), 7 en échec sur `You have no credits remaining` ;
  - coût réel calculé depuis les caches avec `estimate_llm_cost` : juge 1,10 $ (514 850 tokens en entrée, 6 931 en sortie), Two-Pass 1,30 $ (514 846 en entrée, 244 590 en sortie), paire de test 0,012 $, soit 2,41 $ au total, sous le plafond de 7 $ ;
  - prochaine action : l'utilisateur recharge le compte OpenAI, puis `docker exec jobtracker-backend python scripts/matching_bench.py judge --confirm` (7 paires, 0,09 $ estimés, dans l'accord déjà donné), puis second dry-run à 0 et étape 7.
- Conventions lues (Phase 3) : `CLAUDE.md`, identique à `AGENTS.md` et `GEMINI.md` (graphe de code, directives sur les tests : logique métier, contrats, pas de sur-mocking ni de réseau) ; `.cursorrules` (graphe de code).
- Baseline (Phase 3, 2026-10-24) :
  - build : exit 1, `ModuleNotFoundError: No module named 'scripts.export_matching_bench'` ;
  - pytest : exit 4, aucun test collecté, fichier absent, y compris le run sans réseau ;
  - `git check-ignore` : exit 0 ;
  - `uvx pyflakes` disponible ;
  - conteneur local `jobtracker-backend` en marche, l'évaluateur s'y importe ;
  - les `grep -c` sur les scripts échouent faute de fichier.
- Coût attendu (mémoire `llm-cost-sensitivity`) :
  - juge `gpt-6.1-sol` : environ 0,012 $ par paire avant cache de prompt (environ 5 000 tokens en entrée à 2 $ par M, environ 150 en sortie à 10 $ par M), soit environ 2,9 $ pour environ 241 paires ;
  - Two-Pass : 0,0176 $ par paire, soit environ 3,5 $ pour 200 paires ;
  - total : environ 6,4 $ pour un passage complet.

  Le dry-run donne l'estimation tirée des prompts réels avant toute dépense. Si `gpt-6.1-sol` produit des tokens de raisonnement, facturés en sortie, le coût réel du juge peut dépasser l'estimation : il est relevé à l'étape 6.
- Écart de modèle à trancher à l'étape 5 : le `.env` local fixe `EVALUATION_MODEL=gemini/gemini-3.7-flash`, alors que le défaut du code est `gemini/gemini-3.8-flash`. Le banc mesure le modèle de prod, passé par `--model`.
- Sécurité : l'export lit la base de prod (profils, interactions). Il ne contient aucun secret, mais il contient des données personnelles, d'où son dépôt dans `scripts/data/` (ignoré par git) et sa suppression du conteneur de prod juste après récupération. Les clés API ne sont jamais affichées. Aucun fichier de la surface sécurité (auth, injection, migration, upload) n'est touché : pas de semgrep requis.
- Le classement hybride sera branché sur ce banc à l'étape 3 de la spec, avec la garde de rappel (aucune offre `applied` sous `FLOOR`) ; il n'existe pas encore. L'export inclut les offres des interactions pour cette garde.
- La garde de rappel ne s'applique pas ici : elle ne vaut que pour l'hybride.
- Écart à l'étape 2 : sa vérification `-k "select_sample or aliases"` ne peut pas passer avant l'étape 3, car `tests/test_matching_bench.py` importe les deux modules en tête (exit 2, `No module named 'scripts.matching_bench'`). Ces tests sont couverts par la vérification complète de l'étape 3. La commande d'export de prod par stdin (`python -`, où `__file__` vaut `'<stdin>'`) a été validée en local, fichier temporaire supprimé du conteneur.
- Étape 5 (2026-10-24T20:49Z) : l'export de prod compte 1 profil, pas 2 comme l'annonçait la spec. Les 41 interactions (30 `applied`, 11 `hidden`) appartiennent toutes au même utilisateur ; aucun autre utilisateur n'a d'interaction `applied`/`hidden` avec un `candidate_profile`. Échantillon : 70 offres (30 rattachées et 40 non rattachées). 11 offres d'interaction sont introuvables (offer_id morts après la restauration du 5 octobre). Le banc reste valable, avec moins de puissance statistique : 70 paires au lieu de 200.
- Modèle Two-Pass de prod : `gemini/gemini-3.8-flash`, égal au défaut du code. L'écart avec le `.env` local (`gemini-3.7-flash`) est tranché : `--model gemini/gemini-3.8-flash` à l'étape 6.
- Accord de dépense donné par l'utilisateur le 2026-10-24 vers 20:33Z (« je te donne mon accord pour le banc de mesure »). Plafond retenu : 7 $ pour le passage complet, d'après l'estimation de 6,4 $. Si le dry-run sur l'export de prod dépasse 7 $, revenir vers l'utilisateur avant tout `--confirm`.
- Décision 2 de la spec tranchée le même jour : le Two-Pass est réservé aux meilleures offres. Le banc garde sa mesure du Two-Pass, qui sert désormais à dimensionner N (coût et latence), plus à décider de l'existence du Lot 2.
- Prochaine action : l'utilisateur lance les commandes de l'étape 5 (export de prod et `printenv EVALUATION_MODEL`). Ensuite, dry-run `judge` et `twopass` sur l'export de prod (dry-run local : juge 0,88 $ et Two-Pass 1,23 $ pour 70 offres et 1 profil), puis `--confirm` sans nouvelle question si le total reste sous le plafond.
