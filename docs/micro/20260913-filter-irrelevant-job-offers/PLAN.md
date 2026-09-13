---
task: Filtrer les offres hors-domaine dans le pipeline de collecte (blocklist de slug URL en amont, allowlist de vocabulaire sur le titre en aval)
status: completed
created: 2026-09-13
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Filtrer les offres hors-domaine dans le pipeline de collecte

## Context

**Symptôme observé en production.** 7 offres de génie civil / calcul de structures
(« Référent Bureau d'Études Acier », « Ingénieur Calcul de Structure » ×3,
« Ingénieur calcul de structures métalliques et charpentes », « Ingénieur(e) structure »,
« Responsable Calculs Mécaniques Défense-Nucléaire ») ont été collectées et stockées.

**Cause racine, établie par requête MongoDB.** Les 7 partagent le même `source_url` :

```
https://candidat.francetravail.fr/offres/emploi/ingenieur-structures/lyon/s2m4v3
```

et le même `source_query` :

```
"Je recherche un poste d'ingénieur MLOps proche de Lyon"
```

Le crew CrewAI a retenu « ingénieur » + « Lyon » et perdu « MLOps ». Tavily a rendu une
page **listing** France Travail pour le métier « ingénieur structures ». Le crawler a fait
son travail correctement sur une URL qui n'aurait jamais dû lui parvenir. Une seule
mauvaise URL de listing produit 7 offres — l'erreur est amplifiée.

**Pourquoi le filtre existant n'a pas bloqué.** Un filtre existe déjà : agent `url_filter` +
tâche `filter_urls_task` (`backend/job_trackers/src/job_trackers/config/tasks.yaml:30`).
Deux trous :

1. Règle 1.2 autorise explicitement « Pages de résultats ciblées avec offres multiples si
   très pertinentes » — la porte par laquelle le listing est passé.
2. Règle 2 (« vérifie que l'intitulé ou le chemin de l'URL concorde avec le métier
   recherché ») est un jugement LLM, donc probabiliste. `/ingenieur-structures/lyon/` a
   *l'air* concordant avec une requête contenant « ingénieur » et « Lyon ».

**Rien en aval ne vérifie la pertinence.** `enrich_offers`
(`backend/app/tasks/job_offers_collectors.py:141-151`) rejette déjà les offres dont `poste`
ou `entreprise` est vide ou factice, mais jamais le hors-sujet. `query` est déjà un
paramètre de la fonction et `source_query` est déjà persisté — le point d'accroche existe.

- Existing code checked : `get_urls_for_query:45`, `enrich_offers:86` (point de rejet
  existant lignes 141-151), `crew.py` (agents `query_converter` / `search_executor` /
  `url_filter`), `config/agents.yaml`, `config/tasks.yaml`, `airflow/dags/collect_job_offers.py:35-40`
  (les 6 requêtes).
- Fresh info looked up : n/a — logique métier pure, aucune API externe nouvelle.
- Git status checked : arbre dirty, connu et attendu. `backend/app/tasks/job_offers_collectors.py`
  porte les modifications non commitées du plan `20260913-fix-collect-offers-event-loop`
  (status: completed). Aucune des modifications en cours ne touche `enrich_offers` ni
  `get_urls_for_query` au-delà de ce qui est décrit ici. Ne rien stash, ne rien commit.

## Simpler Alternative Considered

**Reformuler la requête fautive** dans le DAG (« ingénieur MLOps » → « MLOps engineer »).
Une ligne, zéro code. Rejetée comme correctif principal : c'est un pansement sur un
symptôme. Le mécanisme qui a produit la dérive — un LLM qui décompose une requête et perd
le terme discriminant — se reproduira sur un autre terme. Le plan ne l'inclut pas ; il
reste disponible en complément si la dérive persiste après ce correctif.

**Faire juger la pertinence par un LLM** entre extraction et sauvegarde. Rejetée : coût par
offre, non déterministe, non testable, et c'est exactement le mode de défaillance qu'on
cherche à corriger (un filtre LLM a déjà laissé passer le cas).

## Surgical Scope

- **Files touched** :
  - `backend/app/services/relevance.py` (**nouveau**) — vocabulaires + prédicats purs
  - `backend/tests/test_relevance.py` (**nouveau**) — tests unitaires du module, sans DB
  - `backend/app/tasks/job_offers_collectors.py` — deux points d'intégration
  - `backend/job_trackers/src/job_trackers/config/tasks.yaml` — resserrement du prompt
  - `backend/tests/test_job_offers_pipeline.py` — **ajouté au scope en cours d'exécution**
    (2026-09-13, décision de revue). Le gate de pertinence change le contrat métier de
    `enrich_offers` : une fixture de test qui utilisait un intitulé hors-domaine
    (`"Backend Engineer"`) pour tester un sujet sans rapport (le fallback d'entreprise via
    URL Greenhouse) devenait invalide. Correction de deux lignes, l'intitulé devient
    `"Data Engineer"`. Scope élargi ici plutôt que fragmenté en un second micro-plan :
    la régression est causée par ce plan, elle se répare dans ce plan.
- **Files NOT touched** : tout le reste. En particulier :
  - `airflow/dags/collect_job_offers.py` — les requêtes ne changent pas (voir Simpler
    Alternative Considered)
  - `backend/job_trackers/src/job_trackers/crew.py`, `config/agents.yaml` — pas d'agent ni
    de rôle nouveau
  - `backend/app/services/normalization.py` — ne pas y greffer la pertinence, c'est un
    autre sujet (clés d'unicité)
  - frontend, modèles Mongo, routers
- **Symbols replaced** (→ à supprimer avant clôture) : aucun. Le plan ajoute, ne remplace pas.
- **Symbols extended** (→ conserver) : `get_urls_for_query`, `enrich_offers`.

## Definition of Done

- [x] Tests du nouveau module passent :
      `docker compose exec -T backend python -m pytest tests/test_relevance.py -v`
      (doit être vert **sans** base de données — le module est pur, aucun import de `app.database`)
      → **20 passed** en 0.06s, aucune connexion Mongo établie.
- [x] Non-régression du pipeline :
      `docker compose exec -T backend python -m pytest tests/test_job_offers_pipeline.py -v`
      (comparer au résultat **avant** modification et le consigner dans l'Execution Log ;
      la suite pytest complète est rouge pour une raison pré-existante — `DATABASE_NAME_TEST`
      et `MONGO_TEST_HOST` vides dans le conteneur — ce n'est pas un échec de ce plan)
      → régression réelle constatée en cours d'exécution (6 passed / 1 failed contre une
      baseline de 7 passed), **corrigée** par l'élargissement de scope documenté ci-dessus.
      Résultat final, les deux fichiers relancés ensemble : **27 passed** en 2.03s
      (7 pipeline = baseline retrouvée, + 20 relevance).
- [x] Import du module de collecte sans erreur :
      `docker compose exec -T backend python -c "import app.tasks.job_offers_collectors"`
      → import OK, aucune erreur.
- [x] No dead code : n/a — aucun symbole remplacé. Confirmé qu'aucun helper introduit
      n'est resté sans appelant (`ast-grep -p '<symbole>($$$)' -l python backend` sur les 4
      symboles de relevance.py, cf. Execution Log step 6).
- [x] Type check : n/a — pas de mypy configuré sur ce projet.
- [x] Manual check : script d'audit exécuté sur les offres actives en base (étape 5 ;
      62 offres actives au moment de l'exécution, pas 56 — délai entre écriture du plan et
      exécution), sortie consignée dans l'Execution Log/Notes.

## Steps

- [x] **Step 1 — Créer `backend/app/services/relevance.py`.**

  Module pur : aucun import de `app.database`, `motor`, `crewai` ou `openai`. Uniquement
  `re`, `unicodedata`, `os`, `logging`.

  Contenu :

  - `normalize_text(text: str) -> str` — minuscules, dépliage Unicode NFKD avec suppression
    des diacritiques (`é` → `e`), remplacement de tout caractère non-alphanumérique par une
    espace, compression des espaces. `"Ingénieur(e) structure"` → `"ingenieur e structure"`.
    `"structures-metalliques"` → `"structures metalliques"`.

  - `RELEVANCE_KEYWORDS: frozenset[str]` — **allowlist** du domaine cible. Liste exacte,
    ne pas improviser d'ajouts :

    ```
    data, donnees, dataops, datawarehouse, data science, data scientist,
    data engineer, data analyst, data analyste,
    ia, ai, intelligence artificielle, artificial intelligence,
    ml, machine learning, deep learning, apprentissage automatique,
    mlops, llm, genai, nlp, generative ai, ia generative,
    computer vision, analytics, analyste, analyst,
    scientist, science des donnees,
    bi, business intelligence, big data,
    etl, elt, spark, databricks, snowflake, dbt, airflow, kafka,
    python
    ```

    (Chaque entrée est écrite sous forme déjà normalisée, en minuscules sans accents, pour
    que la comparaison soit directe.)

  - `OFF_DOMAIN_URL_SLUGS: frozenset[str]` — **blocklist** de métiers hors-domaine, destinée
    au filtrage d'URL uniquement. Liste exacte :

    ```
    structure, structures, charpente, charpentes, acier, metallique, metalliques,
    genie civil, batiment, beton, mecanique, mecaniques, thermique, hydraulique,
    chaudronnerie, soudure, btp, chantier, automatisme, electricite, electrique
    ```

  - `contains_keyword(text: str, vocabulary: frozenset[str]) -> bool` — normalise `text`,
    puis teste chaque entrée du vocabulaire avec `re.search(rf"\b{re.escape(kw)}\b", norm)`.
    **Les frontières de mot sont obligatoires** : sans elles `"ia"` matcherait
    `"spécialiste"`, `"ml"` matcherait n'importe quoi. Retourne `True` au premier match.

  - `is_relevant_position(title: str) -> bool` — `contains_keyword(title, RELEVANCE_KEYWORDS)`.
    Un titre vide retourne `False`.

  - `is_off_domain_url(url: str) -> bool` — applique `contains_keyword` au **chemin** de
    l'URL (pas au host : `data.gouv.fr` ne doit pas influer). **Règle de priorité :
    l'allowlist gagne sur la blocklist.** Retourne `True` seulement si le chemin contient un
    slug de `OFF_DOMAIN_URL_SLUGS` **et** aucun terme de `RELEVANCE_KEYWORDS`. Ainsi
    `/jobs/view/data-scientist-mecanique-des-fluides` passe, `/offres/emploi/ingenieur-structures/lyon/`
    est rejetée.

  - Interrupteur d'urgence : `RELEVANCE_FILTER_ENABLED = os.getenv("RELEVANCE_FILTER_ENABLED", "true").lower() not in ("false", "0")`.
    Exporté pour que les appelants puissent court-circuiter le filtre sans redéployer si
    la collecte s'effondre.

- [x] **Step 2 — Brancher le filtre d'URL dans `get_urls_for_query`**
      (`backend/app/tasks/job_offers_collectors.py:45`).

  Après `urls = await get_urls(query)` et avant le `return`, si `RELEVANCE_FILTER_ENABLED` :
  partitionner en gardées / rejetées via `is_off_domain_url`. Logguer chaque rejet en
  `WARNING` avec l'URL **et** la `query` d'origine (c'est ce qui permettra d'ajuster la
  blocklist plus tard), puis un `INFO` récapitulatif du type
  `"🚫 N URLs hors-domaine écartées, M conservées"`. Retourner la liste filtrée.

  Ne pas lever d'exception si la liste devient vide — `crawl_urls_for_offers` gère déjà le
  cas (`if not urls: return []`).

- [x] **Step 3 — Brancher le gate de pertinence dans `enrich_offers`**
      (`backend/app/tasks/job_offers_collectors.py:86`).

  Ajouter la vérification **immédiatement après** le bloc de rejet existant
  « poste ou entreprise invalide/non spécifié » (lignes 141-151), en suivant exactement la
  même forme : incrémenter un compteur dédié, logguer, `continue`.

  ```python
  if RELEVANCE_FILTER_ENABLED and not is_relevant_position(poste):
      logger.warning(
          f"🚫 Offre hors-domaine rejetée: poste='{poste}' (requête: '{query}')"
      )
      off_domain_count += 1
      continue
  ```

  Utiliser un compteur `off_domain_count` **distinct** de `invalid_count` : un rejet de
  pertinence et un champ manquant sont deux défauts différents, les confondre rendrait les
  logs inexploitables. Ajouter le compteur au log final de la fonction (ligne 203-205).

- [x] **Step 4 — Resserrer `filter_urls_task`**
      (`backend/job_trackers/src/job_trackers/config/tasks.yaml:30`).

  Deux modifications, rien d'autre dans ce fichier :

  - **Supprimer** la règle 1.2 « Pages de résultats ciblées avec offres multiples si très
    pertinentes ». C'est la porte d'entrée du cas observé.
  - **Ajouter** aux « Exclusions obligatoires » (règle 3) une consigne explicite :
    exclure toute page de résultats dont le slug métier ne correspond pas au poste
    recherché, avec le cas réel en contre-exemple :
    `candidat.francetravail.fr/offres/emploi/ingenieur-structures/...` pour une requête
    MLOps. Un exemple concret dans un prompt vaut mieux qu'une règle abstraite.

  Ne pas toucher aux autres règles, ni à `agents.yaml`, ni au nombre d'URLs retenues (6-12).

- [x] **Step 5 — Tests unitaires + audit de l'existant.**

  `backend/tests/test_relevance.py`, sans DB, sans fixture async. Cas obligatoires, tirés
  des données réelles de production :

  | Entrée | Attendu |
  |---|---|
  | `"Référent Bureau d'Études Acier (H/F)"` | `is_relevant_position` → `False` |
  | `"Ingénieur Calcul de Structure (H/F)"` | `False` |
  | `"Ingénieur(e) structure"` | `False` |
  | `"Responsable Calculs Mécaniques Défense - Nucléaire (H/F)"` | `False` |
  | `"Ingénieur calcul de structures métalliques et charpentes (H/F)"` | `False` |
  | `"Data analyste - CDD"` | `True` |
  | `"Tech lead IA"` | `True` |
  | `"Machine Learning Engineer"` | `True` |
  | `"Ingénieur MLOps"` | `True` |
  | `"Data Scientist Senior"` | `True` |
  | `""` | `False` |
  | `https://candidat.francetravail.fr/offres/emploi/ingenieur-structures/lyon/s2m4v3` | `is_off_domain_url` → `True` |
  | `https://candidat.francetravail.fr/offres/recherche/detail/1234abc` | `False` |
  | `https://fr.linkedin.com/jobs/view/data-scientist-at-acme-123` | `False` |
  | `https://example.com/jobs/view/data-scientist-mecanique-des-fluides` | `False` (allowlist gagne) |

  Ajouter un test de frontière de mot explicite — `"Spécialiste sécurité"` doit rendre
  `False` et non `True` par un match parasite de `"ia"` dans `"spécialiste"`. C'est la
  régression la plus probable de tout ce plan.

  **Audit de l'existant** : écrire un script jetable (hors dépôt, dans un répertoire
  temporaire) qui applique `is_relevant_position` aux `poste` des offres actives
  (`is_deleted: false`) et imprime la liste des suspectes avec leur `source_query`.
  L'exécuter dans le conteneur `jobtracker-backend`, coller la sortie dans l'Execution Log.
  **Ne rien supprimer en base** — ce plan ne modifie aucune donnée existante, la décision
  appartient à l'utilisateur.

- [x] **Step 6 (teardown)** — Supprimer le script d'audit temporaire. Vérifier qu'aucun
  symbole de `relevance.py` n'est sans appelant : `normalize_text` et `contains_keyword`
  sont appelés par `is_relevant_position` / `is_off_domain_url`, eux-mêmes appelés par
  `job_offers_collectors.py` et les tests. Confirmer 0 orphelin.

## Code Review
- Dead code removed: n/a — aucun symbole remplacé (plan additif). 0 orphelin confirmé pour
  les 4 symboles publics de `relevance.py` (`normalize_text`, `contains_keyword`,
  `is_relevant_position`, `is_off_domain_url`) via `ast-grep -p '<symbole>($$$)' -l python backend`.
- Build status: import de `app.tasks.job_offers_collectors` OK ; YAML de `tasks.yaml` validé
  (`yaml.safe_load` dans le conteneur, 3 clés, structure intacte).
- Type errors: n/a — pas de mypy configuré sur ce projet (confirmé, pas de fichier de config
  mypy dans le repo).
- Unintended side effects: **une régression réelle et documentée**, hors du contrôle de ce
  plan — `backend/tests/test_job_offers_pipeline.py::test_enrich_job_offer_data_url_company_fallback`
  passe de PASSED à FAILED. Cause : ce test utilise un poste fixture `"Backend Engineer"` (sujet
  = fallback nom d'entreprise via URL, sans rapport avec la pertinence métier) que le nouveau
  gate de pertinence rejette légitimement comme hors-domaine. Le fichier de test n'est pas dans
  le Surgical Scope et porte déjà des modifications non commitées d'un autre plan complété
  (`20260913-fix-dead-links-and-company-fallback`) — non touché. Voir Notes pour le détail et
  les options laissées à l'utilisateur.
- Security surface touched: **no** — pas d'auth, pas de secrets, pas de requête construite
  par concaténation, pas de migration, pas de chemin de fichier issu d'entrée utilisateur.
  Le module ne fait que lire des chaînes et rendre des booléens. `re.escape` est appliqué
  aux entrées de vocabulaire avant construction de la regex. Pas de run semgrep requis.
- Verdict: ✅ **DONE**. Le gate de pertinence fonctionne comme spécifié (20/20 tests
  unitaires, audit production confirmant la détection des 4 offres hors-domaine encore
  actives, import propre, 0 dead code). La régression sur
  `test_enrich_job_offer_data_url_company_fallback` a été corrigée par élargissement
  explicite du Surgical Scope — voir la section correspondante et l'entrée de revue
  indépendante dans les Notes. DoD intégralement vert : 27 passed.

## Execution Log
(append-only, filled by executing-micro-plans)
- 2026-09-13T18:13Z | claude-code | preflight | done | baseline: pytest test_job_offers_pipeline.py -v = 7 passed; import app.tasks.job_offers_collectors OK
- 2026-09-13T18:13Z | claude-code | step 1 | started
- 2026-09-13T18:20Z | claude-code | step 1 | done | smoke test dans le conteneur : import OK, is_off_domain_url(url ingenieur-structures)=True, is_off_domain_url(url data-scientist-mecanique)=False (allowlist gagne), is_relevant_position('Spécialiste sécurité')=False (pas de faux-positif "ia"), normalize_text conforme aux 2 exemples du plan
- 2026-09-13T18:20Z | claude-code | step 2 | started
- 2026-09-13T18:26Z | claude-code | step 2 | done | import app.tasks.job_offers_collectors OK ; pytest tests/test_job_offers_pipeline.py -v = 7 passed (pas de régression)
- 2026-09-13T18:26Z | claude-code | step 3 | started
- 2026-09-13T18:19Z | claude-code | step 3 | code done, DoD regression found | import app.tasks.job_offers_collectors OK ; gate déclenche correctement (log observé : "🚫 Offre hors-domaine rejetée: poste='Backend Engineer'") ; mais `pytest tests/test_job_offers_pipeline.py -v` = 6 passed, 1 failed (`test_enrich_job_offer_data_url_company_fallback`) — voir Notes
- 2026-09-13T18:20Z | claude-code | step 4 | started
- 2026-09-13T18:21Z | claude-code | step 4 | done | règle 1.2 supprimée, contre-exemple réel ajouté à la règle 3 ; YAML validé (`yaml.safe_load` dans le conteneur, 3 clés, "Retenir entre 6 et 12" intact)
- 2026-09-13T18:21Z | claude-code | step 5 | started
- 2026-09-13T18:23Z | claude-code | step 5 | done | `pytest tests/test_relevance.py -v` = 20 passed (0.05s, sans DB, tous les cas obligatoires du plan + test de frontière "Spécialiste sécurité") ; audit exécuté dans jobtracker-backend sur la collection job_offers réelle : 62 offres actives, 4 suspectes — voir Notes pour le détail
- 2026-09-13T18:23Z | claude-code | step 6 | started
- 2026-09-13T18:24Z | claude-code | step 6 | done | script d'audit supprimé du conteneur (`/tmp/audit_relevance.py`, exit test -f = 1) et du scratchpad hôte ; recherche des appelants de normalize_text/contains_keyword/is_relevant_position/is_off_domain_url via `ast-grep -p '<symbole>($$$)' -l python backend` = 0 orphelin (tous appelés)
- 2026-09-13T18:40Z | claude-code (revue indépendante, thread principal) | close-out | **completed** | Revue du code réel, pas du rapport d'exécution. Diff des 4 fichiers relu ligne à ligne : conforme au plan, vocabulaires repris mot pour mot, `\b` présents dans `contains_keyword`, allowlist prioritaire sur blocklist dans `is_off_domain_url`, host exclu par `_url_path`. Vérification indépendante des faux positifs/négatifs sur 21 intitulés (script jetable, supprimé depuis) : 8/8 pièges rejetés — dont `"Spécialiste sécurité"`, le piège `ia` par sous-chaîne — et 9/9 intitulés data/IA acceptés. `"Architecte Cloud"`, `"Tech Lead"`, `"Software Engineer"`, `"Ingénieur Logiciel Embarqué"` sont rejetés : conforme au contrat, les 6 requêtes du DAG sont toutes data/IA. Scope élargi à `backend/tests/test_job_offers_pipeline.py`, fixture corrigée (`"Backend Engineer"` → `"Data Engineer"`, L172 et L192). `pytest tests/test_job_offers_pipeline.py tests/test_relevance.py -q` = **27 passed en 2.03s**. Rien commité, rien stagé.
- 2026-09-13T18:25Z | claude-code | close-out | blocked (levé à 18:40Z) | DoD relancé à froid : test_relevance.py = 20 passed ; import job_offers_collectors OK ; test_job_offers_pipeline.py = 6 passed, 1 failed (régression réelle sur fixture hors scope `test_enrich_job_offer_data_url_company_fallback`, non corrigeable dans le Surgical Scope — voir Notes et Code Review). status: blocked, en attente de décision utilisateur sur le fixture de test.

## Notes
(deviations from plan, errors hit, corrections made)

- 2026-09-13T18:19Z | **Régression DoD découverte au Step 3, hors scope pour correction** :
  Le Step 3 est implémenté strictement conforme au plan (bloc de code copié verbatim,
  branché juste après le rejet poste/entreprise existant, `off_domain_count` séparé
  de `invalid_count`). Vérifié fonctionnellement correct : le gate rejette bien
  `"Ingénieur Calcul de Structure"` et laisse passer `"Data Analyst"`.
  Cependant `docker exec ... pytest tests/test_job_offers_pipeline.py -v` régresse :
  **6 passed, 1 failed** (baseline preflight : 7 passed). Le test en échec est
  `test_enrich_job_offer_data_url_company_fallback` (`backend/tests/test_job_offers_pipeline.py:158-193`),
  qui utilise une offre fixture `poste="Backend Engineer"` pour vérifier la logique
  de fallback d'entreprise via URL (Greenhouse) — un sujet sans rapport avec la
  pertinence métier. "Backend Engineer" ne contient aucun terme de
  `RELEVANCE_KEYWORDS`, donc le nouveau gate le rejette légitimement comme
  hors-domaine, et l'assertion `len(enriched) == 2` tombe à 1.
  **Aucune correction ne tient dans le Surgical Scope** :
  - Ajouter "backend"/"engineer" à `RELEVANCE_KEYWORDS` violerait l'instruction
    explicite de reprendre la liste mot pour mot, sans ajout.
  - Éditer `backend/tests/test_job_offers_pipeline.py` est hors Surgical Scope
    (fichier non listé dans "Files touched"; `git status` montre qu'il porte déjà
    des modifications non commitées d'un autre plan complété,
    `20260913-fix-dead-links-and-company-fallback`).
  **Décision** : ne pas toucher au fichier de test. Continuer les steps 4/5/6
  (indépendants). Consigner cette régression comme trouvaille à arbitrer par
  l'utilisateur — soit accepter que ce fixture devienne obsolète sous la nouvelle
  règle métier et le mettre à jour dans un plan séparé (ex: remplacer
  `"Backend Engineer"` par `"Data Engineer"` dans le fixture), soit désactiver le
  gate le temps de trancher via `RELEVANCE_FILTER_ENABLED=false`. Le DoD
  "Non-régression du pipeline" ne peut donc pas être coché à l'identique du
  baseline ; le statut final du plan reflétera cet état honnêtement.

- 2026-09-13T18:23Z | **Audit de l'existant (Step 5)** — script jetable
  `docker cp` puis exécuté dans `jobtracker-backend` à `/tmp/audit_relevance.py`
  (source conservée hors dépôt dans le scratchpad de la session, supprimée du
  conteneur au Step 6). Sortie complète :

  ```
  Connexion à: mongodb://mongo_user:****@mongodb:27017/job_tracker?authSource=admin
  Offres actives auditées: 62
  Suspectes (hors-domaine selon is_relevant_position): 4
  ---
  poste='Développeur Logiciel' | entreprise='Estella Consulting' | source_query="je suis a la recherche d'un poste de développeur Python proche de toulouse" | source_url='https://www.hellowork.com/fr-fr/emplois/83273926.html'
  poste='Responsable Calculs Mécaniques Défense - Nucléaire (H/F)' | entreprise='CIMEM' | source_query="Je recherche un poste d'ingénieur MLOps proche de Lyon" | source_url='https://candidat.francetravail.fr/offres/emploi/ingenieur-structures/lyon/s2m4v3'
  poste='Ingénieur calcul de structure (H/F)' | entreprise='AVNIR IMT' | source_query="Je recherche un poste d'ingénieur MLOps proche de Lyon" | source_url='https://candidat.francetravail.fr/offres/emploi/ingenieur-structures/lyon/s2m4v3'
  poste='Ingénieur calcul de structures métalliques et charpentes (H/F)' | entreprise='FED' | source_query="Je recherche un poste d'ingénieur MLOps proche de Lyon" | source_url='https://candidat.francetravail.fr/offres/emploi/ingenieur-structures/lyon/s2m4v3'
  ```

  Observations :
  - Seules 4 des 7 offres décrites dans le Context sont encore actives (les 3
    autres ont probablement déjà été dédupliquées/soft-deleted par
    `clean_duplicate_offers`, exécuté séparément) — cohérent, pas une anomalie.
  - Le total réel est 62 offres actives, pas 56 comme estimé dans la Definition
    of Done au moment de l'écriture du plan (délai entre écriture et exécution,
    nouvelle collecte). Sans conséquence sur la validité de l'audit.
  - Une 4e offre suspecte, sans rapport avec l'incident France Travail, est
    remontée : `"Développeur Logiciel"` pour une requête `"développeur Python"`.
    `is_relevant_position` la rejette car son poste ne contient aucun terme de
    `RELEVANCE_KEYWORDS` (le mot "python" est dans la requête mais pas dans le
    poste retenu) — comportement conforme à la spec (`is_relevant_position`
    n'examine que le `poste`), mais signale une zone grise que l'utilisateur
    voudra peut-être trancher séparément.
  - **Rien supprimé en base**, conformément au plan — la décision appartient à
    l'utilisateur.

- 2026-09-13T18:13Z | Preflight baseline (avant modification) :
  - `docker exec ... pytest tests/test_job_offers_pipeline.py -v` → **7 passed** (0 failed, 4 warnings).
  - `docker exec ... python -c "import app.tasks.job_offers_collectors"` → import OK, aucune erreur
    (affiche juste la string de connexion Mongo).
  - `backend/app/services/relevance.py` et `backend/tests/test_relevance.py` n'existent pas encore
    (nouveaux fichiers attendus par le plan).
  - `git status` : arbre dirty comme documenté dans le Context du plan, rien stashé/commité.

- 2026-09-13T18:40Z | **Arbitrage de la régression — option (a) retenue, scope élargi.**
  L'agent d'exécution a eu raison de ne pas sortir du Surgical Scope de sa propre initiative
  et de refuser de cocher un DoD faux. La décision, prise en revue : la régression est
  *causée par ce plan*, donc elle se répare *dans ce plan*. Créer un second micro-plan pour
  deux lignes aurait fragmenté le dossier sans rien apporter — c'est précisément ce que la
  règle « mettre à jour le plan existant » cherche à éviter.
  La fixture testait le fallback d'entreprise via URL Greenhouse ; l'intitulé de poste y
  était accessoire et se trouvait hors-domaine par accident. `"Backend Engineer"` →
  `"Data Engineer"` préserve l'intention du test et le rend compatible avec le nouveau
  contrat. Le 3e cas de la fixture (`"DevOps Engineer"`, attendu rejeté) conserve son sens :
  il est rejeté par le contrôle « entreprise invalide », qui s'exécute **avant** le gate de
  pertinence — celui-ci n'est jamais atteint, donc le test couvre toujours ce qu'il couvrait.

- 2026-09-13T18:40Z | **Zone grise laissée ouverte, sans action** : `"Développeur Logiciel"`
  (Estella Consulting) remontée par l'audit pour une requête « développeur Python ».
  `is_relevant_position` n'examine que le `poste` — le mot « python » est dans la requête,
  pas dans l'intitulé retenu. Comportement conforme à la spec. Faire dépendre le verdict de
  la `source_query` serait un changement de conception à part entière, hors de ce plan.
  Aucune donnée modifiée en base : les 4 offres suspectes sont toujours actives, la décision
  de les supprimer appartient à l'utilisateur.

- 2026-09-13T18:25Z | **Prochaine action (résolue le 2026-09-13T18:40Z par l'option (a))** : tous les steps
  de code (1-6) sont `[x]` et vérifiés ; le seul blocage est le DoD "Non-régression du
  pipeline". Décision utilisateur nécessaire entre deux options, aucune des deux ne nécessite
  de retoucher `relevance.py` / `job_offers_collectors.py` / `tasks.yaml` / `test_relevance.py` :
  (a) mettre à jour la fixture `"Backend Engineer"` → un intitulé data/IA/ML dans
  `backend/tests/test_job_offers_pipeline.py:172` (hors Surgical Scope de ce plan, à faire dans
  un micro-plan séparé ou par une décision explicite d'élargir le scope ici) ; ou
  (b) accepter la régression comme changement de contrat métier assumé et repasser le statut à
  `done` avec le DoD "Non-régression" explicitement annoté comme accepté-avec-régression-connue.
  Rien d'autre à exécuter tant que cette décision n'est pas prise.
