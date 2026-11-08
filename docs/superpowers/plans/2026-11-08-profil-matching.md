# Profil candidat et matching — plan

**Statut :** proposé, à calibrer avec des mesures.  
**Objectif :** préserver un profil fiable et mesurer le classement des offres sur plusieurs métiers.  
**Architecture :** réutiliser la fusion de profil, les filtres et le scoring existants ; établir d'abord un jeu de référence, puis ne changer que les règles justifiées par les erreurs observées.  
**Technologies :** Python, MongoDB, pytest et interface React.

## Périmètre et contraintes

Examiner `backend/app/services/profile/merge.py`, `profile/context.py`, `offer_scoring/`, `offer_profile_matcher.py` et leurs tests. L'import PDF dépend du [plan parseur](2026-11-08-parser-cv.md) ; les requêtes et sources web sont traitées dans le [plan Serper](2026-11-08-exploration-serper.md). Préserver les interactions et candidatures, la séparation entre utilisateurs et les préférences explicites. Les données inconnues ne sont pas des incompatibilités.

La fusion gère déjà provenance, conflits et priorité `manual > cv > website > github`. Une correction d'expérience est stockée dans `sources.manual` puis refusionnée ; un libellé différent au réimport peut créer un doublon : c'est un risque à reproduire, pas un comportement déjà démontré pour tous les cas. Les tests de fusion et réimport appartiennent à ce plan seul.

Ce plan possède le **jeu synthétique commun** et le **registre de budget** utilisés par les plans parseur et lettres : sa tâche 1 est sur le chemin critique des trois plans et commence par eux.

**Invariant (testé, non négociable) :** aucune perte de candidature ni d'interaction lors d'une fusion ou d'un recalcul ; couvert en tâche 4.

**Budget :** couvre uniquement les appels réels lancés par les scripts de mesure de ces plans ; ni la suite pytest (appels simulés, coût nul), ni l'usage de production (quotas existants). Plafond commun de 2,50 $ : 0,25 $ parseur, 0,25 $ profil, 2 $ lettres. Estimations : parseur ≈ 0,10 $ (20 PDF, deux méthodes), profil ≈ 0,05 $ (embeddings seuls, les labels annotés remplacent le juge LLM), lettres ≈ 0,06 $ par lettre mesuré le 2026-09-30. Tout dépassement exige un accord explicite.

**Cibles proposées pour le pilote, à valider avant mesure :** au moins 20 profils synthétiques, chacun classé sur au moins 15 offres annotées (au moins 300 jugements), incluant des rejets du filtre métier ; précision@5 d'au moins 80 % et rappel d'au moins 90 % sur les offres pertinentes annotées ; nDCG@10 rapporté sans seuil au pilote. Pas plus de 5 points de régression par sous-groupe ayant au moins 20 exemples pertinents ; rapporter les sous-groupes trop petits sans conclure. Les mesures ne valent que sur l'échantillon annoté.

## Tâche 1 — Jeu commun, registre et erreurs de fusion

- [ ] Fixer le jeu commun avant de le remplir. Emplacement : `backend/scripts/reference/`, versionné car entièrement synthétique (aucune donnée réelle, aucun PDF binaire : les PDF sont générés par le plan parseur). Fichiers et schéma minimal :
  - `profiles.json` : `profile_id`, sources par nom (`cv`, `manual`…), sous-groupe (métier, niveau, langue, reconversion) ;
  - `offers.json` : `offer_id`, champs au format des offres stockées ;
  - `matching_labels.json` : `profile_id`, `offer_id`, `label` (`pertinent`, `partiel`, `hors_sujet`), motif ;
  - `cv_facts.json` (parseur) : `profile_id`, fait attendu, page, critique ou non ;
  - `letter_requirements.json` (lettres) : `profile_id`, `offer_id`, exigences, preuves exactes, éléments transférables, lacunes.
  Documenter le schéma et les critères pertinent, partiel et hors sujet dans `backend/scripts/reference/README.md`.
- [ ] Constituer le contenu : juniors, reconversions, rôles voisins, français/anglais, offres rejetées par le filtre métier ; au moins 15 offres annotées par profil, une même offre pouvant servir à plusieurs profils.
- [ ] Créer le registre `backend/scripts/data/llm_budget.jsonl` (non versionné) : une ligne par appel réel (date, plan, script, modèle, coût estimé ou facturé). Fournir une fonction commune sous `backend/scripts/` qui refuse un appel si la part du plan serait dépassée ; les trois plans l'utilisent avant tout appel réel.
- [ ] Étendre `backend/scripts/matching_bench.py` pour lire le jeu commun via un adaptateur vers le format de `load_export` ; réutiliser ses caches et son mode sans `--confirm`. Les labels annotés remplacent le juge LLM sur ce jeu. `export_matching_bench.py` reste une option séparée pour des données réelles : export en lecture seule, fichiers privés dans `backend/scripts/data/`, jamais versionnés ; ne pas le considérer comme anonymisé par défaut.
- [ ] Mesurer précision@5, nDCG@10, rappel sur les exemples annotés, faux négatifs, respect des préférences et résultats par métier et source.
- [ ] Ajouter dans `backend/tests/test_profile_merge.py` des cas de dates et employeurs conflictuels, expérience distincte et correction manuelle suivie d'un réimport avec libellé différent ; éviter doublon et perte de correction sans fusionner deux postes distincts. Depuis `backend`, exécuter `uv run pytest tests/test_profile_merge.py -v`.

## Tâche 2 — Provenance et préférences

- [ ] Partir du contrat existant de provenance et de résolution des conflits ; identifier les limites de granularité pour compétences déclarées, projets, formations et expériences avant toute migration.
- [ ] Tester qu'une compétence issue d'un projet ne devient pas automatiquement une expérience professionnelle et qu'une préférence explicite survit à une fusion. Adapter fusion et contexte uniquement lorsque les tests révèlent un défaut.
- [ ] Depuis `backend`, exécuter `uv run pytest tests/test_profile_merge.py -v` et les tests de contexte concernés ; contrôler que les anciens profils restent lisibles.

## Tâche 3 — Calibrage et explications

- [ ] Rejouer le benchmark avec `backend/app/services/offer_scoring/` et relever les erreurs par sous-groupe avant de proposer des seuils ou poids ; examiner en priorité `COS_FLOOR` et `COS_CEIL`, et vérifier sur quelles données leur calibrage a été établi.
- [ ] Pour chaque règle modifiée, ajouter une régression métier dans `backend/tests/test_offer_scoring_assess.py` ou `test_offer_scoring_role_gate.py` ; vérifier aussi contrat, géographie et inconnues. Depuis `backend`, exécuter `uv run pytest tests/test_offer_scoring_assess.py tests/test_offer_scoring_role_gate.py -v`.
- [ ] Étudier le contrat API et l'interface avant d'exposer raisons du score, préférences insatisfaites et données manquantes ; tester que chaque raison reflète effectivement le calcul.

## Tâche 4 — Simulation avant recalcul

- [ ] Utiliser l'export privé figé pour comparer avant/après en environnement isolé ; adapter si nécessaire le banc au format de l'export. `rematch_all_users.py` opère sur la base configurée, pas sur cet export : sans option il estime seulement, `--confirm` effectue une simulation sans écriture mais peut appeler les embeddings ; ne jamais utiliser `--apply` pour cette mesure.
- [ ] Tester l'invariant dans `backend/tests/test_offer_profile_matcher.py` : candidatures et interactions existantes conservées après rattachement et recalcul. Depuis `backend`, exécuter `uv run pytest tests/test_offer_profile_matcher.py -v`. Documenter ajouts, retraits, faux négatifs et limites avant tout recalcul réel.
