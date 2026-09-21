# Filtrage "Selon mon profil" basé sur matching persistant — Design

**Date** : 2026-09-22
**Statut** : proposé

## Contexte

Le bouton "Selon mon profil" (page `/offers`) filtre actuellement les offres en
construisant côté frontend une chaîne `keywords` (rôles cibles joints par `|`)
et `location` (villes jointes par `|`), envoyée à `GET /job-offers`. Le
backend fait un matching regex tolérant (stemming, mots génériques) sur
`poste`/`description`/`competences_cles`.

Ce mécanisme a deux défauts :
1. **Trop large** : les offres sont collectées globalement (mutualisées entre
   profils — `build_search_queries` déduplique les requêtes identiques entre
   utilisateurs), donc le regex peut faire remonter des offres collectées pour
   le profil d'un autre utilisateur, simplement parce que le texte matche.
2. **Pas de traçabilité** : rien ne relie une offre aux profils dont elle
   satisfait réellement les critères. Chaque affichage refait un matching
   texte à la volée, sans jamais persister le résultat.

Chaque offre porte déjà un `canonical_title` (normalisé via `normalize_role`,
la même taxonomie `role_aliases` que celle utilisée pour construire les
requêtes de collecte) et une `localisation` normalisée (`normalize_city`). Ces
deux champs permettent un matching précis et déterministe entre une offre et
les préférences d'un profil (`target_roles`, `locations`, `remote_policy`).

Échelle actuelle (2026-09-22) : 123 offres, 11 users, 2 profils avec
préférences renseignées. Un recalcul synchrone en tâche de fond est largement
suffisant ; pas besoin de file de tâches dédiée (aucune infra Celery dans ce
repo — seulement `BackgroundTasks` FastAPI, déjà utilisé dans
`cover_letters.py`/`applications.py`, et Airflow pour le cycle quotidien de
collecte).

## Objectif

Remplacer le filtrage texte à la volée par un champ persistant
`matched_user_ids` sur chaque offre, tenu à jour par un moteur de matching
unique invoqué à trois moments :

1. Après chaque cycle de collecte, pour les offres nouvellement
   sauvegardées (tague contre tous les profils existants).
2. Immédiatement après modification des préférences d'un profil (tague ce
   user contre tout le stock actif).
3. Une fois, via script de backfill, pour rattraper le stock déjà en base.

Le bouton "Selon mon profil" devient un simple filtre `matched_user_ids ==
current_user.id`, réutilisant le pipeline d'agrégation existant de
`GET /job-offers` (dédup, pagination, interactions multi-tenant).

## Non-objectifs

- Ne remplace pas le filtre "mots-clés" libre existant (recherche manuelle) —
  seul le comportement du bouton "Selon mon profil" change.
- Ne modifie pas `contract_types` dans le matching (le bouton actuel ne les
  utilise pas non plus — hors scope, cohérent avec le comportement existant).
- Ne construit pas de file de tâches distribuée — hors de propos à cette
  échelle (YAGNI).

## Architecture

Un module de service unique porte toute la logique de matching, appelé
depuis trois points d'entrée distincts. Aucun des trois points d'entrée ne
réimplémente la logique de comparaison — ils diffèrent seulement par "quels
users" et "quelles offres" ils passent en entrée.

```
┌─────────────────────────┐   ┌──────────────────────────┐   ┌────────────────────┐
│ Cycle de collecte        │   │ PUT /profile/candidate    │   │ Script backfill     │
│ (Airflow, quotidien)     │   │ (préférences modifiées)   │   │ (one-shot, manuel)  │
└────────────┬─────────────┘   └─────────────┬──────────────┘   └─────────┬──────────┘
             │ tag_new_offers(offer_ids)      │ rematch_user(user_id)      │ rematch_user(user_id)
             │                                │  (BackgroundTasks)         │  (pour chaque profil)
             └────────────────┬───────────────┴────────────────┬──────────┘
                               ▼                                ▼
                    offer_profile_matcher.py
                    - get_normalized_profile_criteria(prefs, db)
                    - offer_matches_criteria(offer, roles, locations, remote_policy)
                               │
                               ▼
                    job_offers.matched_user_ids: [str]  (indexé)
                               │
                               ▼
                    GET /job-offers?profile_only=true
                    → match_filter["matched_user_ids"] = current_user.id
```

## Composants

### 1. Schéma — `job_offers.matched_user_ids`

Nouveau champ `list[str]` (convention `str(user_id)`, cohérente avec
`offer_evaluations.user_id` déjà stocké en string dans ce projet). Absent par
défaut sur les offres existantes (traité comme liste vide par le matching —
`$in`/`$addToSet` fonctionnent sur un champ absent).

Index simple (non unique) sur `matched_user_ids` pour que le filtre
`GET /job-offers?profile_only=true` reste performant sur `$eq`/`$in` d'un
tableau, à mesure que le volume d'offres grandit.

### 2. `backend/app/services/offer_profile_matcher.py` (nouveau)

```python
async def get_normalized_profile_criteria(
    prefs: dict, db
) -> tuple[set[str], set[str], str]:
    """Normalise target_roles (normalize_role, async, caché via role_aliases)
    et locations (normalize_city, sync). Retourne (roles, locations, remote_policy)."""

def offer_matches_criteria(
    offer: dict,
    normalized_roles: set[str],
    normalized_locations: set[str],
    remote_policy: str,
) -> bool:
    """Pure, sans I/O.
    role_match = not normalized_roles or offer["canonical_title"].lower() in normalized_roles
    loc_match = (
        not normalized_locations
        or offer["localisation"].lower() in normalized_locations
        or (remote_policy == "full_remote" and offer["mode_travail"] == "Télétravail total")
    )
    return role_match and loc_match
    """

async def rematch_user(user_id: str, db) -> None:
    """Recalcule le matching d'UN user contre tout le stock actif.
    $addToSet sur les offres qui matchent désormais, $pull sur celles qui
    ne matchent plus. Utilisé par le hook profil ET le script de backfill."""

async def tag_new_offers(offer_ids: list[ObjectId], db) -> None:
    """Recalcule le matching de TOUS les profils contre un lot d'offres
    fraîchement sauvegardées. Utilisé en fin de cycle de collecte."""
```

Cas `target_roles` vide **et** `locations` vide (profil sans aucune
préférence) : traité comme "aucun critère exploitable" → `offer_matches_criteria`
retourne toujours `False` (pas de tag). Décision explicite (validée) : mieux
vaut ne rien taguer que tout taguer, pour que le bouton "Selon mon profil"
n'affiche jamais silencieusement le stock entier comme s'il était filtré.

### 3. `job_offers_collectors.save_offers_to_database`

Modification minimale : retourne en plus la liste des `_id` des offres
créées ou mises à jour dans ce cycle (actuellement seulement `{"saved":
int, "updated": int}` → devient `{"saved": int, "updated": int, "offer_ids":
list[ObjectId]}`). Le merge multi-diffusion existant
(`merge_multidiffusion_offers`) part d'une copie de `existing_doc` puis
n'écrase que des champs nommément listés (`url`, `alternative_urls`,
`salaire`, `type_contrat`, `localisation`, `poste`) — `matched_user_ids`
n'est jamais dans cette liste, donc il survit à une re-collecte sans
modification supplémentaire.

`collect_and_save_offers` appelle ensuite
`tag_new_offers(result["offer_ids"], db)` après la sauvegarde.

### 4. Hook profil — `backend/app/routers/cover_letters.py`

Dans le handler `PUT /profile/candidate` : si `preferences.target_roles` ou
`preferences.locations` ou `preferences.remote_policy` diffèrent entre
l'ancien et le nouveau document, `background_tasks.add_task(rematch_user,
str(current_user.id), db)`. Suit le même pattern que
`_generate_cover_letter_bg` déjà présent dans ce fichier (tâche de fond
FastAPI existante, pas de nouvelle dépendance).

### 5. Filtrage — `backend/app/routers/job_offers.py`

`GET /job-offers` gagne un paramètre `profile_only: bool = Query(False)`.
Si `True` et `current_user` présent : `match_filter["matched_user_ids"] =
str(current_user.id)`. Réutilise tel quel le pipeline d'agrégation existant
(dédup par `unique_key`, tri, pagination, `apply_user_interaction_filters`,
scores d'évaluation par user). Si `current_user` absent, `profile_only` est
ignoré silencieusement (comportement identique à un utilisateur anonyme
aujourd'hui — pas de préférences à appliquer).

### 6. Frontend — `frontend/src/app/offers/page.tsx`

`handleApplyProfileCriteria` : au lieu de dériver `searchTerm`/`locationFilter`
à partir du profil, passe `profile_only=true` au fetch. Garde l'appel à
`getCandidateProfile()`/`getSuggestedRoles()` uniquement pour affichage
("Filtré selon : Data Engineer, Lyon"), plus pour construire la requête.

Si le profil n'a ni `target_roles` ni `locations` : afficher un message
invitant à compléter le profil au lieu d'appeler l'API avec `profile_only`
(cohérent avec la décision "profil vide → rien ne matche" côté backend —
évite un aller-retour réseau pour un résultat vide prévisible).

### 7. Script de backfill — `backend/scripts/backfill_matched_user_ids.py`

Même convention que `backend/scripts/backfill_canonical_titles.py` déjà
présent dans ce repo (`--dry-run`, exécution via `docker exec
jobtracker-backend python scripts/...`). Boucle sur chaque document
`candidate_profile`, appelle `rematch_user(str(prof["user_id"]), db)` (ou
une variante dry-run qui logue sans écrire).

## Tests

- `offer_matches_criteria` : cas rôle seul, localisation seule, les deux,
  aucun des deux (profil vide → False), full_remote avec offre télétravail,
  insensibilité à la casse.
- `rematch_user` : offre qui devient matchée (`$addToSet`), offre qui cesse
  de matcher après changement de préférences (`$pull`), idempotence (deux
  appels consécutifs sans changement de préférences → pas de duplication
  dans `matched_user_ids`).
- `tag_new_offers` : une offre nouvellement collectée taguée pour plusieurs
  profils qui matchent simultanément (mutualisation).
- `save_offers_to_database` : vérifie que `matched_user_ids` existant sur
  `existing_doc` survit à une mise à jour (merge multi-diffusion) et que
  `offer_ids` retournés couvrent bien créations et mises à jour.
- `GET /job-offers?profile_only=true` : retourne uniquement les offres où
  `matched_user_ids` contient `current_user.id` ; ignoré si non authentifié.
- Hook profil : modification de `target_roles` déclenche bien
  `background_tasks.add_task(rematch_user, ...)` ; pas de déclenchement si
  seuls des champs non pertinents changent (ex. `headline`).

## Migration

Le script de backfill doit tourner une fois manuellement après déploiement
pour rattraper les 123 offres et 2 profils déjà en base. Pas de migration
automatique au démarrage de l'app (cohérent avec la convention déjà en place
pour `backfill_canonical_titles.py`, lancé à la main via `docker exec`).
