# Tavily : job boards en mode `prefer` pour tous les profils

## Problème

Passe 1 de `TavilyJobBoardSearchTool._run` = 3 appels `include_domains` en
mode `restrict` (défaut) sur des boards cadres/tech (WTTJ, APEC, Cadremploi,
Free-Work, LesJeudis). Tavily renvoie toujours `max_results` pages de ces
sites, même hors sujet : pour un métier non couvert (animation, social,
fonction publique), 100 % de bruit, rejeté par l'agent `url_filter`.
Coût : 4 appels advanced = 8 crédits par requête.

## Doc Tavily (vérifiée le 2026-10-27, docs.tavily.com, endpoint search + best practices)

- `include_domains_mode` : `restrict` (défaut, filtre dur) ou `prefer`
  (cherche aussi le reste du web) ; 400 sans `include_domains`.
- `country` : booste un pays, seulement avec `topic="general"` (défaut) ;
  valeur `france` dans l'enum.
- `exclude_domains` max 150, `include_domains` max 300, `max_results` max 20.
- `score` par résultat ; la doc conseille de filtrer par score, seuil
  dépendant du cas d'usage.
- advanced = 2 crédits, basic = 1, quel que soit `max_results`.
- SDK tavily-python 0.7.2 (uv.lock backend) : `search(**kwargs)` relayé, `data.update(kwargs)` dans `_search`.

## Décision (accord utilisateur du 2026-10-27)

- Passe 1 : un seul appel `prefer`, `country="france"`, `max_results=20`,
  domaines préférés = WTTJ, APEC, Cadremploi, Free-Work, LesJeudis,
  choisirleservicepublic.gouv.fr (JSON-LD JobPosting, reprend
  emploi-territorial), planetanim.fr.
- Exclus : agrégateurs spam + Indeed, LinkedIn, HelloWork (jobspy) +
  France Travail (source abandonnée), dans `exclude_domains` et dans
  `_is_valid_job_url`.
- Passe 2 ATS inchangée.
- Score de chaque résultat journalisé, aucun seuil (à calibrer sur logs).
- Coût : 2 appels = 4 crédits par requête (au lieu de 8).
- Pas de test Tavily payant : jugement sur la collecte du lendemain 07:00 UTC.

## Étapes

- [x] Test rouge `tests/test_crew_models_and_tools.py` (un appel prefer, exclusions)
- [x] Implémentation `job_trackers/src/job_trackers/tools/custom_tool.py`
- [x] Motif choisirleservicepublic dans `config/tasks.yaml` (filter_urls_task)
- [x] Suite `uv run pytest tests` (depuis backend/) : 1435 passed
- [x] Commit 2669bcf, déployé le 2026-10-27 (backend reconstruit, Airflow par volume ; /docs 200, mongodb résolu, tavily-python 0.7.2 dans les deux conteneurs)
- [x] Lecture logs du run manuel 2026-10-27 09:44 UTC (23 min, 24 créées / 4 mises à jour, ~20 crédits) :
  domaines pertinents en hausse (Animateur Lyon : centres-sociaux.fr 0.86, nostalentsnosemplois 0.83,
  fr.trabajo.org 0.77), APEC sature 10/20 places sur FP&A et Data Analyst, Finance PM 0 résultat board.
  Seuil 0.5 envisagé (couperait instagram 0.35, apec 0.30-0.05, disney 0.41) : non décidé.
- [ ] Problème distinct : l'agent de recherche n'appelle pas Tavily sur 3/8 requêtes (URLs inventées,
  2 essais gâchés) ; Data Scientist Lyon en échec car 0 offre structurée nouvelle (53/55 connues).
