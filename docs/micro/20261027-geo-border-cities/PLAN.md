# Filtre géo : villes frontalières dans le rayon de la ville cible

## Problème

`location_rejection_reason` (`backend/app/services/sources/geo.py`) rejette toute
offre qui cite un pays étranger, sans regarder la distance. Un profil à Annecy
perd les offres de Genève (34 km), un profil à Mulhouse celles de Bâle.

## Décision (accord utilisateur du 2026-10-27 : « on garde tes recommandations »)

- Pas de chantier « étranger » : `country="france"` (Tavily), `country_indeed="france"`
  (jobspy) et les sites préférés français restent tels quels.
- Seule exception : une offre étrangère qui cite une ville frontalière connue
  (table de coordonnées dans `geo.py`) suit la même règle de rayon qu'une commune
  française (`GEO_RADIUS_KM` = 50 km autour de la ville cible).
- Sans ville cible, ou ville cible non résolue : rejet inchangé.
- Pas de collecte réelle ni d'appel payant ; démonstration avec geo.api.gouv.fr
  (API publique gratuite) sur des paires de villes réelles.

## Étapes

- [x] Test rouge `tests/test_offer_sources.py` (Annecy/Genève gardée, Lyon/Genève et Annecy/Zurich rejetées)
- [x] Implémentation `geo.py` (table `BORDER_CITIES`, distance avant rejet)
- [x] `docs/JOB_INGESTION_AND_NORMALIZATION.md` ligne 160
- [x] `uv run pytest tests/test_offer_sources.py` (seulement cette partie, demande utilisateur) : 41 passed
- [x] Démonstration sur paires réelles, résultat à l'utilisateur
- [ ] Commit / déploiement : sur accord explicite
