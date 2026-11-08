# Design : comparaison Serper et Tavily

**Date** : 2026-11-08  
**Statut** : proposé — expérience à préparer  
**Périmètre** : découverte d'offres et mesure, sans intégration en production

## Contexte

Le projet collecte des offres structurées avec JobSpy et recherche en parallèle des URL avec Tavily. `TavilyJobBoardSearchTool` effectue deux recherches `advanced` par requête : une passe privilégiant des job boards et une passe ciblant les ATS. `run_crew` optimise d'abord la requête par LLM, puis filtre les URL par LLM et peut utiliser des requêtes alternatives. La collecte complète déduplique, enrichit et enregistre les offres.

Au commit `871c87a`, les changements locaux mentionnés dans le document de reprise ne sont pas présents : notamment, il n'y a ni troisième passe Tavily ni connecteur Workday dédié dans le routeur ATS. Greenhouse, Lever, Workable et SmartRecruiters disposent d'extracteurs directs ; Workday peut passer par les mécanismes génériques. La construction des requêtes partage déjà les chaînes identiques entre profils au sein d'un run, avec un maximum de huit requêtes.

## Objectif

Mesurer, sur les mêmes requêtes et dans une fenêtre rapprochée, la contribution de Serper et de Tavily en offres accessibles, pertinentes et uniques, ainsi que leur coût. L'expérience doit permettre de décider si Serper mérite une intégration ultérieure. Elle ne valide pas les améliorations des lettres ou du matching.

## Protocole

- Constituer 5 à 10 profils fictifs ou anonymisés, couvrant métiers, niveaux et zones. Figer 2 à 3 requêtes par profil et mutualiser les requêtes identiques. Conserver les associations requête–profils.
- Utiliser les mêmes requêtes figées, sans nouvelle reformulation LLM ni replis différents selon le moteur. Conserver les paramètres effectifs, les différences de ciblage et les limites de résultats : les capacités et les deux passes Tavily (`include_domains_mode="prefer"` en Passe 1, liste de 15 domaines ATS en Passe 2) n'ont pas d'équivalent exact chez Serper, où `num=20` consomme 2 crédits et où les 15 domaines ATS doivent être répartis en 2 sous-requêtes `site:... OR site:...` avec post-filtrage Python des domaines exclus.
- Réaliser deux lectures techniques et deux lectures financières :
  1. *Technique* : comparaison par requête de chaque stratégie complète, puis comparaison à budget d'appels fixé.
  2. *Financière* : **Scénario A (Faible volume / < 250 requêtes complètes par mois)** où Tavily coûte **0 $/mois** grâce à ses 1 000 crédits gratuits renouvelés mensuellement (et 0,008 $/crédit en Pay-As-You-Go au-delà), contre **50 $ tous les 6 mois (~8,33 $/mois plancher)** chez Serper une fois les 2 500 crédits d'essai uniques épuisés (packs prépayés expirant à 6 mois) ; et **Scénario B (Passage à l'échelle > 510 requêtes/mois)** où le coût marginal unitaire de Serper (~0,003 $–0,004 $ par requête complète au tarif Starter de 1 $/1k crédits) devient ~8 à 10 fois inférieur à celui de Tavily (~0,030 $–0,032 $ par requête complète de 4 crédits).
- Enregistrer avant filtrage : identifiant du run et de la requête, fournisseur, passe, date, paramètres, crédits consommés, URL, titre, extrait, rang, statut et erreur éventuelle. Les doublons conservent toutes leurs provenances. Une passe en échec produit un résultat partiel explicite.
- Appliquer les mêmes règles de qualification et extraire une seule fois chaque URL commune, puis attribuer les résultats à toutes ses provenances. Classer liens inutilisables, offres expirées, extraction impossible et offres extraites. La déduplication intersites existante est une aide, à contrôler par sondage humain.
- Évaluer la pertinence par profil à partir d'un export CSV/JSONL pré-annoté (`domain_relevance.py` + statut d'extraction ATS) et d'un contrôle humain avec labels `pertinent` / `non_pertinent` / `incertain`. Calculer séparément les offres communes, propres à chaque moteur et supplémentaires par rapport à un échantillon JobSpy comparable. Définir « nouvelle » par rapport à ce jeu de référence figé, pas à une base de production mouvante.
- Rapporter appels tentés et réussis, crédits, coût estimé selon les Scénarios A et B (ainsi que le seuil de rentabilité mensuel en volume de requêtes), coûts de récupération, embeddings et LLM séparés ; domaines, doublons, expirations, erreurs et offres pertinentes uniques. Indiquer les dénominateurs, tailles d'échantillon et incertitudes. Un coût par offre est indéfini si le nombre d'offres pertinentes est nul.

## Isolation et limites

Le banc fonctionne hors DAG et n'appelle pas `collect_and_save_offers`, qui écrit en base. Les fichiers bruts et annotations restent dans `backend/scripts/data/` ignoré par Git ; ne versionner que requêtes synthétiques et résultats agrégés sans données personnelles. Aucun appel payant par défaut : un plafond d'appels par fournisseur et un budget explicites doivent être fixés avant exécution. Clés uniquement dans l'environnement sécurisé ; aucun secret dans les journaux.

Le budget mesure les coûts estimés à partir de tarifs configurés et ne garantit pas la facturation fournisseur ; limiter les appels avant envoi, y compris tentatives et reprises. Vérifier les prix et conditions sur les pages officielles avant le run. L'accès à JobSpy et aux pages cibles peut varier selon le serveur ; signaler les échecs au lieu de conclure à une absence d'offres.

## Critères de décision

Comparer couverture incrémentale, pertinence, coût par offre pertinente unique, fiabilité et diversité des domaines. Un petit échantillon ne suffit pas à établir une supériorité durable : si les résultats sont proches ou incomplets, prolonger la mesure. Une intégration au pipeline, une politique de cache et un éventuel changement de fournisseur feront l'objet d'un plan distinct après décision.
