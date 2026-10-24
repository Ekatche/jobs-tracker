---
task: Mettre uv à jour et ajouter un cooldown de dépendances de 7 jours (exclude-newer)
description: uv dependency cooldown supply chain — uv 0.5.13 → 0.13.1 installé par le script standalone épinglé (receipt, uv self update), [tool.uv] exclude-newer = "7 days" + exclude-newer-package python-jobspy = false (1.4.1 publiée le 2026-10-23) dans backend/pyproject.toml, relock uv.lock, requirements.txt régénéré par uv pip compile, version uv épinglée dans backend/Dockerfile et backend/Dockerfile.airflow (astral.sh/uv/0.13.1/install.sh), alerte semgrep uv-missing-dependency-cooldown
status: done
created: 2026-10-23
---

# Mettre uv à jour et ajouter un cooldown de dépendances de 7 jours

## Context
- Existing code checked: `backend/pyproject.toml` L76-77 (`[tool.uv]` ne contient que `override-dependencies = ["numpy>=2.1"]`) ; `backend/requirements.txt` généré par `uv pip compile pyproject.toml -o requirements.txt`, entièrement épinglé ; `backend/Dockerfile` L12-13 et `backend/Dockerfile.airflow` L17-18 installent la dernière version d'uv sans épingle (`ADD https://astral.sh/uv/install.sh`) ; Docker copie seulement `requirements.txt` avant `uv pip install` (`COPY . .` vient après), donc `[tool.uv]` n'est pas lu au build.
- Fresh info looked up: doc uv via Context7 `/astral-sh/uv`. `exclude-newer` accepte une durée « friendly » (`1 week`, `7 days`) ou ISO 8601 (`P7D`), et `false` désactive le cooldown ; `exclude-newer-package = { pkg = false }` exempte un paquet. Versions d'uv sur PyPI : 0.13.1 publiée le 2026-10-14 (la plus récente qui a plus de 7 jours), 0.13.5 le 2026-10-22.
- Git status checked: `pyproject.toml`, `uv.lock` et `requirements.txt` portent déjà des changements non commités du plan `20261023-jobspy-hellowork-source` (même session, `python-jobspy>=1.4.1`). Les Dockerfiles sont propres.

## Simpler Alternative Considered
Garder uv 0.5.13 et poser un `exclude-newer` absolu (date RFC 3339) : écarté. Une date fixe ne glisse pas, elle gèle toutes les mises à jour à cette date au lieu de les retarder de 7 jours.

## Surgical Scope
- **Files touched**: `backend/pyproject.toml`, `backend/uv.lock`, `backend/requirements.txt`, `backend/Dockerfile`, `backend/Dockerfile.airflow` ; hors repo : `~/.local/bin/uv`, `~/.local/bin/uvx` (binaire local mis à jour).
- **Files NOT touched**: tout le reste, en particulier le code applicatif et le frontend.
- **Symbols replaced** (→ to delete before done): none
- **Symbols extended** (→ keep): `[tool.uv]` dans `backend/pyproject.toml`

## Definition of Done
- [ ] uv local à jour : `uv --version` affiche `uv 0.13.1`
- [ ] Cooldown déclaré : `grep -c '^exclude-newer = "7 days"' backend/pyproject.toml` vaut 1 et `grep -c '^exclude-newer-package = { python-jobspy = false }' backend/pyproject.toml` vaut 1
- [ ] Lock cohérent : `cd backend && uv lock --check` exit 0
- [ ] requirements.txt synchronisé : `cd backend && uv pip compile pyproject.toml -q -o /tmp/req-check.txt && diff <(grep -v '^#' requirements.txt) <(grep -v '^#' /tmp/req-check.txt)` ne produit aucune sortie
- [ ] Docker épinglé : `grep -c 'astral.sh/uv/0.13.1/install.sh' backend/Dockerfile backend/Dockerfile.airflow` vaut 1 pour chacun
- [ ] Tests passent : `cd backend && uv run pytest tests/test_offer_sources.py tests/test_job_offers_pipeline.py -q`
- [ ] No dead code: n/a — aucun symbole remplacé
- [ ] Type check: n/a — pas de type checker dans ce périmètre (config et lock)
- [ ] Manual check: aucune version épinglée de `requirements.txt` hors `python-jobspy` n'a moins de 7 jours sur PyPI (script de contrôle des dates d'upload, résultat dans Notes) ; l'URL `https://astral.sh/uv/0.13.1/install.sh` répond 200

## Steps
- [x] Step 1: Installer uv 0.13.1 via le script standalone épinglé (`https://astral.sh/uv/0.13.1/install.sh`), téléchargé dans le scratchpad puis exécuté. Il remplace `~/.local/bin/uv` et écrit le receipt qui rend `uv self update` utilisable. Vérifier : `uv --version`.
- [x] Step 2: Dans `backend/pyproject.toml` `[tool.uv]`, ajouter `exclude-newer = "7 days"` et `exclude-newer-package = { python-jobspy = false }`, avec un commentaire qui date l'exemption (à retirer après le 2026-10-30). Lancer `uv lock`. Vérifier : `uv lock --check` exit 0 et cooldown présent dans les options de `uv.lock`.
- [x] Step 3: Régénérer `backend/requirements.txt` avec `uv pip compile pyproject.toml -o requirements.txt`. Vérifier : relire le diff (versions déplacées par le cooldown) et contrôler les dates d'upload PyPI.
- [x] Step 4: Épingler uv dans `backend/Dockerfile` et `backend/Dockerfile.airflow` (`ADD https://astral.sh/uv/0.13.1/install.sh`). Vérifier : `grep -c` et réponse 200 de l'URL.
- [x] Step 5: Lancer les tests des sources et du pipeline. Vérifier : `uv run pytest tests/test_offer_sources.py tests/test_job_offers_pipeline.py -q` exit 0.
- [x] Step 6 (teardown): aucun symbole remplacé, donc pas de scan d'orphelins. Supprimer les fichiers temporaires du scratchpad (script d'installation). Confirmer 0 orphelin.

## Code Review
- Dead code removed: yes — aucun symbole remplacé ; script d'installation et sonde retirés du scratchpad
- Build status: pass — `uv lock --check` exit 0, `requirements.txt` synchronisé, pytest 65 passed. Image Docker non reconstruite (build lourd) : seule l'URL de l'installeur a changé, et elle répond 200
- Type errors: none — pas de code Python modifié
- Unintended side effects: `uv.lock` passe au format `revision = 5` (diff de ~3 500 lignes, toutes de format : aucune version déplacée par rapport à l'état précédent, et seuls les 5 écarts du plan HelloWork subsistent par rapport à HEAD). Un uv ancien (`/opt/miniconda3/bin/uv` 0.7.7, hors PATH prioritaire) ne lira pas `exclude-newer = "7 days"` ; Docker n'est pas concerné car il copie seulement `requirements.txt` avant `uv pip install`
- Security surface touched: no — config de dépendances, aucun fichier de la liste (auth, validation, injection, secrets, migrations, upload). Le durcissement supply-chain est l'objet même du plan
- Verdict: ✅ DONE

## Execution Log
- 2026-10-23T21:04Z | claude-code | preflight | done | baseline : uv 0.5.13, 0 ligne exclude-newer, `uv lock --check` exit 0, 0 épingle uv dans les Dockerfiles, pytest 65 passed
- 2026-10-23T21:04Z | claude-code | step 1 | started
- 2026-10-23T21:05Z | claude-code | step 1 | done | `uv --version` → uv 0.13.1 (62faed335 2026-10-13), `~/.config/uv/uv-receipt.json` créé
- 2026-10-23T21:05Z | claude-code | step 2 | started
- 2026-10-23T21:05Z | claude-code | step 2 | done | `uv lock` « Resolving despite existing lockfile due to addition of global exclude newer », 272 paquets ; `[options] exclude-newer-span = "P7D"` + `[options.exclude-newer-package] python-jobspy = false` ; `uv lock --check` exit 0
- 2026-10-23T21:05Z | claude-code | step 3 | started
- 2026-10-23T21:06Z | claude-code | step 3 | done | `uv pip compile pyproject.toml -o requirements.txt` → fichier identique ; sonde `cooldown-probe` (dépendance `uv`) : 0.13.1 avec cooldown, 0.13.5 avec exemption ; contrôle PyPI 268 épingles, seule python-jobspy 1.4.1 a moins de 7 jours, 0 erreur
- 2026-10-23T21:06Z | claude-code | step 4 | started
- 2026-10-23T21:07Z | claude-code | step 4 | done | `grep -c 'astral.sh/uv/0.13.1/install.sh'` → Dockerfile:1, Dockerfile.airflow:1 ; URL → 200 (redirigée vers releases.astral.sh/github/uv/releases/download/0.13.1/uv-installer.sh)
- 2026-10-23T21:07Z | claude-code | step 5 | started
- 2026-10-23T21:09Z | claude-code | step 5 | done | `uv run pytest tests/test_offer_sources.py tests/test_job_offers_pipeline.py -q` exit 0, 65 passed
- 2026-10-23T21:09Z | claude-code | step 6 | done | script d'installation et `cooldown-probe` supprimés du scratchpad (`ls | grep -c` → 0) ; aucun symbole remplacé, 0 orphelin
- 2026-10-23T21:12Z | claude-code | close-out | done | DoD relancé : uv 0.13.1 ; greps 1/1 ; `uv lock --check` exit 0 ; Docker 1/1 ; pytest 65 passed ; synchro requirements vérifiée sur une copie (diff vide), voir Notes

## Notes
- Fichiers de convention lus : `CLAUDE.md` (racine), `~/.claude/CLAUDE.md`. Rien sur pyproject ni Docker au-delà du protocole de tests.
- Baseline (Phase 3) : uv 0.5.13 ; `exclude-newer` absent ; `uv lock --check` exit 0 ; Dockerfiles sans épingle ; `uv run pytest tests/test_offer_sources.py tests/test_job_offers_pipeline.py -q` → 65 passed.
- Approbation : l'utilisateur a choisi l'option 1 (« utilise uv ») après l'alerte semgrep `uv-missing-dependency-cooldown`.
- Version d'uv : 0.13.1 plutôt que 0.13.5. Le cooldown s'applique aussi à l'outil : 0.13.5 date du 2026-10-22, 0.13.1 du 2026-10-14.
- Horodatages des étapes 1 à 5 : saisis de mémoire puis corrigés (plusieurs dépassaient l'heure shell). Reconstruits à partir de trois repères shell : fin de la baseline à 21:04Z, coupure `uv lock` « 2026-10-16T21:05:09Z » (7 jours avant l'exécution), `date -u` à 21:09Z après l'étape 5. L'ordre est exact, la minute à ±1.
- Exemption jobspy : python-jobspy 1.4.1 a été publiée le 2026-10-23T05:12Z. Sans exemption, le cooldown de 7 jours rendrait `python-jobspy>=1.4.1` insoluble jusqu'au 2026-10-30.
- DoD « requirements.txt synchronisé » mal écrit : compiler vers un fichier neuf (`-o /tmp/req-check.txt`) résout sans préférences et remonte toutes les dépendances aux dernières versions d'avant la coupure (crewai 0.121 → 1.15, apache-airflow 3.0.1 → 3.2.2…). La commande échoue donc sans qu'il y ait désynchronisation. Vérification correcte au close-out : `cp requirements.txt <tmp> && uv pip compile pyproject.toml -q -o <tmp>`, puis diff hors en-tête → vide (exit 0). Constat annexe : `requirements.txt` est très en retard sur les versions disponibles. Hors périmètre, non traité.
