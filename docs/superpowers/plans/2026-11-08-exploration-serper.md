# Plan : banc de comparaison Serper / Tavily

**Statut** : terminé — décision documentée : maintien de Tavily en production, Serper non retenu pour l'usage actuel  
**Design** : [exploration Serper](../specs/2026-11-08-exploration-serper-design.md)  
**Remédiation** : [remediation bench Serper](./2026-11-08-remediation-bench-serper.md)  
**Décision finale** :
- **Tavily maintenu en production** : 0,00 $/mois (< 250 requêtes/mois grâce aux 1 000 crédits gratuits récurrents) avec 3× à 4× plus d'offres pertinentes découvertes lors des tests réels (13 offres pertinentes vs 4 pour Serper sur la même requête).
- **Serper non retenu pour l'usage actuel** : Coût plancher de 50 $/6 mois (~8,33 $/mois) sans quota gratuit récurrent, avec un volume d'offres inférieur. Seuil de rentabilité fixé à 510 requêtes complètes/mois. Le code du banc reste archivé sur la branche `feature/exploration-serper`.
- **Améliorations intégrées au projet** : Filtrage anti-bruit des ATS (sous-domaines support, vitrines marketing d'éditeurs ATS, listings génériques Taleo) intégré directement dans `custom_tool.py` pour Tavily, et directives d'hygiène des tests renforcées dans `AGENTS.md`.

**Objectif :** préparer une expérience reproductible, limitée et isolée pour mesurer le gain et le coût des deux moteurs dans le contexte JobTracker.

**Architecture :** un script autonome dans `backend/scripts/`, des adaptateurs de recherche normalisant les résultats, des données de run locales et un rapport agrégé. Le banc réutilise les fonctions de qualification et de déduplication lorsqu'elles sont utilisables sans écriture ; les adaptations nécessaires restent isolées. Aucun branchement du DAG pendant l'expérience.

## Task 1 — Définir les entrées, les structures et les limites (`backend/scripts/bench_serper_tavily.py`)

- [x] Créer un jeu de 10 à 20 requêtes synthétiques, avec profils fictifs, association requête–profil et paramètres pays/langue (`gl="fr"`, `hl="fr"`). Documenter les critères de pertinence et la référence JobSpy.
- [x] Définir les structures de données typées (`RunManifest`, `SearchAttempt`, `NormalizedHit`, `CostProjection`) : version du code, date, liste de requêtes figée, paramètres de chaque passe, nombre maximal de tentatives et budget estimé par fournisseur.
- [x] Prévoir un mode préparation (`--dry-run`) sans réseau par défaut ; les appels réels exigent une activation explicite (`--live`) et des plafonds renseignés (`--max-calls`, `--max-credits`). Ne jamais récupérer les clés dans les arguments CLI ou les fichiers de résultats.

## Task 2 — Collecter et normaliser

- [x] Implémenter deux adaptateurs isolés renvoyant URL, titre, extrait, rang, fournisseur, passe et crédits consommés, plus statut, paramètres et erreurs. Conserver les réponses brutes utiles avant filtrage.
- [x] **Tavily (référence)** : reproduire les deux passes `advanced` de `TavilyJobBoardSearchTool` (Passe 1 : `preferred_job_boards` en mode `prefer`, `max_results=20`, 2 crédits ; Passe 2 : `company_ats_domains` en mode `restrict`, `max_results=10`, 2 crédits — soit 4 crédits/requête).
- [x] **Serper (traduction réaliste)** :
  - Appliquer `excluded_domains` et `excluded_paths` en post-filtrage Python (et non via 19 opérateurs `-site:` qui tronquent la requête Google).
  - Passe 1 (Web + Job boards FR, `tbs="qdr:m"`, `num=20` → **2 crédits** Serper).
  - Passe 2 (ATS directs) : découper les 15 domaines de `company_ats_domains` en 2 sous-requêtes `site:a OR site:b ...` (`num=10` chacune → **2 × 1 crédit**) pour éviter la troncature silencieuse des opérateurs booléens Google.
  - Compter chaque tentative (y compris les reprises) et les crédits exacts facturés par passe. Ne pas convertir silencieusement un échec en résultat vide.
- [x] Tester hors réseau (`backend/tests/test_bench_serper_tavily.py`) les réponses valides, le décompte exact des crédits (`num=20` = 2 crédits chez Serper), les doublons entre passes, le résultat vide, l'erreur partielle et l'arrêt sur plafond. Ne pas modifier le comportement du collecteur existant.

## Task 3 — Qualifier, annoter et comparer les coûts selon le volume

- [x] Enregistrer les provenances avant déduplication ; appliquer les mêmes règles aux deux fournisseurs et extraire chaque URL commune une seule fois via `route_and_extract`. Classer chaque étape et conserver les échecs.
- [x] Exporter une table d'évaluation pré-annotée (JSONL/CSV) à partir des briques existantes (`domain_relevance.py` + statut d'extraction ATS) avec une colonne `human_label` (`pertinent` | `non_pertinent` | `incertain`) à compléter sur l'échantillon de contrôle, face à un jeu de référence JobSpy figé.
- [x] Modéliser deux scénarios financiers dans le rapport pour éviter le biais du coût unitaire facial :
  - **Scénario A — Faible volume / Usage actuel (< 250 requêtes/mois, soit ≤ 1 000 crédits Tavily)** :
    - *Tavily* : **0 $/mois** grâce au quota gratuit mensuel renouvelable de 1 000 crédits (ou surplus en Pay-As-You-Go à 0,008 $/crédit sans engagement).
    - *Serper* : 0 $ uniquement pendant l'essai unique de 2 500 crédits à l'inscription (non renouvelable), puis coût plancher de **50 $ tous les 6 mois (~8,33 $/mois)** lié à l'expiration des packs prépayés de 50 000 crédits, même si seule une fraction est consommée.
  - **Scénario B — Passage à l'échelle (Volume mensuel > 1 000 crédits)** :
    - Coût marginal par requête complète (~0,030 $–0,032 $ chez Tavily vs ~0,003 $–0,004 $ chez Serper au tarif Starter de 1 $/1 000 crédits) et coût marginal par offre pertinente unique.
    - Calculer le **seuil de rentabilité (break-even)** en nombre de requêtes mensuelles à partir duquel le pack Serper à 50 $/6 mois devient moins cher que le quota gratuit + dépassement Tavily (~2 040 crédits Tavily/mois, soit ~510 requêtes complètes/mois).
- [x] Produire un rapport par fournisseur et par requête : appels, crédits, coûts (Scénario A, Scénario B et break-even), domaines, extraction, doublons, expirations, offres pertinentes, communes et supplémentaires, avec dénominateurs et nombre d'annotations.
- [x] Tester avec des données locales que les URL communes restent attribuées aux deux moteurs, qu'un échec est visible, que le coût par offre est absent lorsque le dénominateur est nul et que la projection distingue bien le quota mensuel gratuit Tavily du pack prépayé périssable Serper.

## Task 4 — Vérification et décision

- [x] Lancer les tests ciblés du banc sans réseau et vérifier que le mode préparation ne modifie pas la base et n'appelle aucun fournisseur.
- [x] Vérifier les tarifs et renseigner une fenêtre et des plafonds avant tout run réel. Exécuter uniquement sur autorisation et configuration disponibles, sans collecte massive.
- [x] Examiner les résultats et leurs limites ; décider de garder Tavily, de tester Serper plus longtemps ou de préparer une intégration. Documenter cette décision séparément.

## Points d'intégration à vérifier lors de l'implémentation

- `backend/job_trackers/src/job_trackers/tools/custom_tool.py` : deux passes Tavily et filtrage d'URL.
- `backend/job_trackers/src/job_trackers/main.py` : reformulation, replis et filtre LLM, à figer pour le banc.
- `backend/app/tasks/job_offers_collectors.py` : construction partagée des requêtes et pipeline avec écritures, à éviter dans le banc.
- `backend/app/services/ats/router.py`, `normalization.py` et `sources/jobboards.py` : extraction, déduplication et référence JobSpy.
- `backend/app/services/usage_tracker.py` : suivi orienté actions utilisateur et tokens ; ajouter au banc son propre journal d'appels de recherche.
