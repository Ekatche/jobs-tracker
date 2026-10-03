---
target: frontend/src/app/offers/page.tsx
total_score: 20
max_score: 40
na_heuristics: 0
p0_count: 1
p1_count: 3
target_identity: "file:/Users/elielkatche/job-tracker/frontend/src/app/offers/page.tsx"
target_fingerprint: "sha256:8a384a4fc32dbfd6771df8eac8a2fb407c068e060ff8eb9d09c5b44ab106330b"
target_path: /Users/elielkatche/job-tracker/frontend/src/app/offers/page.tsx
timestamp: 2026-10-03T09-14-40Z
slug: frontend-src-app-offers-page-tsx
---
Method: dual-agent (A: a355bd3d5d41fb9c6 · B: a0bb041f95d7dab2b)

## Design Health Score

| # | Heuristique | Score | Point clé |
|---|-----------|-------|-----------|
| 1 | Visibilité du statut système | 1/4 | Filtre "contrats ciblés" activé automatiquement au montage, aucun indicateur visible hors d'un dropdown replié |
| 2 | Correspondance système/monde réel | 3/4 | Badges Nouveau/Évaluée/Match clairs, vocabulaire métier correct |
| 3 | Contrôle et liberté utilisateur | 2/4 | Pas d'état d'URL : retour arrière ou rafraîchissement perd la page courante |
| 4 | Cohérence et standards | 2/4 | Deux champs de description différents (brut vs nettoyé) selon le point d'entrée |
| 5 | Prévention des erreurs | 2/4 | Rien n'empêche un total "Statistiques" et une liste filtrée de raconter deux histoires différentes |
| 6 | Reconnaissance plutôt que rappel | 2/4 | Filtre actif invisible tant que le panneau "Filtres avancés" n'est pas ouvert |
| 7 | Flexibilité et efficacité | 3/4 | Filtres riches (contrat, mode, ancienneté, favoris) une fois le panneau ouvert |
| 8 | Esthétique et minimalisme | 3/4 | Grille de cartes propre, hiérarchie des badges lisible |
| 9 | Diagnostic/récupération d'erreurs | 2/4 | Erreur de régénération affichée via `alert()` navigateur, pas de bannière cohérente avec le reste |
| 10 | Aide et documentation | 2/4 | Aucune mention de "Mes contrats ciblés" en dehors du select replié |
| **Total** | | **20/40** | **Faible** |

## Design Specificity Verdict

**LLM**: La grille de cartes et les badges (Nouveau/Évaluée/Match) montrent un vrai effort de hiérarchisation visuelle propre au produit — mais la logique de filtrage par défaut est invisible à l'utilisateur, ce qui rend l'écran "liste d'offres" générique et peu digne de confiance : rien ne distingue à l'œil nu "il n'y a pas d'offre" de "il n'y a pas d'offre qui correspond à un filtre que je n'ai pas choisi".

**Scan déterministe**: 4 findings sur `page.tsx` + `[id]/page.tsx`, dont 3 probables faux positifs (état hover et spinner mal interprétés comme anti-patterns) et 1 plausible mais mineur : un bloc citation `border-l-4 border-blue-500` (`[id]/page.tsx:593`) au style "callout IA générique" — isolé, pas un problème structurel.

**Overlay navigateur**: injection échouée (même blocage mixed-content que les deux autres zones) — aucun overlay visible. Le compte de test ne contenait qu'une seule offre fantôme (description vide), empêchant de rejouer "voir plus" et la pagination en direct ; confirmé plutôt par lecture exacte du code source (voir ci-dessous), méthode explicitement déclarée comme telle plutôt que présentée comme testée en direct.

**Correction factuelle importante**: contrairement au signalement initial ("obligé de cliquer sur Postuler pour voir le résumé"), le code actuel de `page.tsx` affiche `cleanedDescription` directement sur la carte, sans action requise (`page.tsx:410, 543-576`). Si ce comportement persiste en production sur le VPS, c'est un problème de déploiement à vérifier, pas un défaut de ce code source. Le vrai mécanisme en jeu est différent et plus profond — voir P0 ci-dessous.

## Overall Impression

L'écran a l'ossature d'un bon produit (badges, filtres riches, nettoyage de texte) mais le filtrage automatique silencieux casse la confiance : un total "Statistiques" et une liste "Offres" peuvent raconter deux histoires différentes sans qu'aucune UI ne le signale, et "voir plus" ouvre une boîte non bornée dans une grille qui s'étire. Le produit sait filtrer intelligemment ; il ne sait pas encore le dire.

## What's Working

1. **Nettoyage de texte des descriptions** (`cleanDescriptionPreview`, `page.tsx:39-51`) — retire les artefacts markdown bruts du scraping (listes numérotées, gras, puces) avant affichage, un vrai souci du détail.
2. **Badges de fraîcheur et de score** — "Nouveau (< 24h)", "Match X/5", type de contrat : hiérarchie visuelle cohérente par couleur.
3. **Filtre "Mes contrats ciblés"** — l'intention (pré-positionner la recherche sur le profil du candidat) est une bonne idée produit ; c'est l'absence de visibilité qui la casse, pas l'idée elle-même.

## Priority Issues

**[P0] Le total "Statistiques" et la liste "Offres" peuvent diverger sans aucune explication visible**
Pourquoi: `fetchStats` (:198-201) appelle `jobOffersApi.getStats()` sans aucun filtre — total brut de la base. `fetchOffers` (:176-195) applique toujours `currentFilters`, qui inclut par défaut `contract_type = "profile_targeted"` dès que le profil a des préférences de contrat (:321-322, appliqué silencieusement au montage via `handleApplyProfileCriteria`, :301-333). Résultat possible et confirmé en direct par l'agent B : liste à 0 offre, onglet Statistiques à 1 offre, au même instant sur le même compte — parce que l'unique offre ne correspond pas au type de contrat ciblé du profil.
Fix: appliquer le même filtre aux deux appels, ou afficher un badge explicite "Filtré sur vos contrats ciblés — X offres au total" à côté du compteur de la liste.
Commande: **harden**

**[P1] Filtre par défaut invisible — contredit l'intention de transparence**
Pourquoi: `setContractTypeFilter((prev) => (prev === "" ? "profile_targeted" : prev))` (:322) s'exécute automatiquement au premier rendu (:330-333), sans toast ni pastille sur la barre de recherche. Le seul endroit où ce filtre apparaît est l'option `🎯 Mes contrats ciblés (...)` du select "Contrat" (:1118-1134), lui-même caché dans le panneau "Filtres avancés" fermé par défaut (`showFilters` initialisé à `false`, :121).
Fix: afficher une pilule active fermable ("🎯 Filtré sur vos contrats ciblés ×") sur la barre principale dès qu'un filtre de profil est appliqué automatiquement.
Commande: **clarify**

**[P1] "Voir plus" étire toute la rangée de la grille, pas seulement la carte**
Pourquoi: la description perd son `line-clamp-3` à l'expansion (:560-562) sans aucune limite de hauteur de remplacement ; la grille (`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-4 gap-6`, :742/:1240) n'a pas de `items-start`, donc l'`align-items: stretch` par défaut de CSS Grid étire toutes les cartes de la même rangée à la hauteur de celle qui vient de s'ouvrir — y compris des offres sans aucun rapport.
Fix: ajouter `items-start` à la grille et/ou plafonner la description ouverte avec `max-height` + défilement interne.
Commande: **layout**

**[P1] Changement de page démonte toute la liste et perd la position de défilement utile**
Pourquoi: `fetchOffers()` appelé sans `silent` sur changement de page (:177, :343-349) passe `loading=true`, ce qui remplace entièrement grille + pagination par un spinner centré (:1212-1218) — la liste et les boutons de pagination disparaissent pendant le chargement. `handlePageClick` (:664-667) déclenche en parallèle un `window.scrollTo({behavior:"smooth"})` vers le haut, donc l'utilisateur voit la page défiler puis tout le contenu disparaître puis réapparaître. Aucun état de page n'est reflété dans l'URL (pas de `useSearchParams`/`router.push` dans ce fichier) : un retour arrière ou un rafraîchissement retombe toujours en page 1.
Fix: garder la grille montée pendant le chargement de page suivante (griser + spinner en overlay, comme le fait déjà `fetchOffers(true)` en mode silencieux ailleurs) ; synchroniser `currentPage` dans l'URL.
Commande: **harden**

**[P2] Message d'erreur de régénération via `alert()` natif**
Pourquoi: `handleRegenerateDescription` (catch, :269-275) retombe sur `alert()` navigateur alors que le reste de l'écran utilise des bannières stylées cohérentes (`error`, :1219-1228).
Fix: remplacer par la même bannière inline que les autres erreurs de la page.
Commande: **harden**

## Persona Red Flags

**Riley (stress testeur)**: Change de page plusieurs fois rapidement → liste entière disparaît et réapparaît à chaque clic, aucun repère de continuité. Le total "Statistiques" ne correspondra jamais aux offres réellement listées si un filtre de profil est actif — de quoi douter de la fiabilité des chiffres du produit entier.

**Jordan (débutant confus)**: Arrive sur `/offers`, voit "0 offre trouvée" ou une liste très courte, sans savoir qu'un filtre a été choisi à sa place. Doit découvrir par hasard le panneau "Filtres avancés" puis repérer l'option `profile_targeted` pour comprendre pourquoi.

**Casey (mobile distrait)**: Sur `grid-cols-1` mobile, l'étirement de "voir plus" est moins visible (une carte par ligne) mais le remontage complet au changement de page reste identique — pire sur une connexion lente où le spinner plein écran dure plus longtemps.

## Minor Observations

- Pagination déjà partiellement durcie côté backend en 2026-09-17 (`docs/micro/archive/.../20260917-stabilize-pagination-and-new-offers-highlight/PLAN.md`) : tiebreaker de tri déterministe, dédoublonnage aligné count/liste. Le ressenti "instable" actuel vient du remontage visuel décrit en P1, pas d'un retour aux doublons/offres manquantes d'avant ce correctif.
- Le bloc citation `border-l-4 border-blue-500` (`[id]/page.tsx:593`) a un style "callout" isolé — à surveiller s'il se répète ailleurs, pas un problème en soi aujourd'hui.
- Compte de test limité à une offre fantôme (description vide) : la reproduction live de "voir plus"/pagination n'a pas pu être rejouée à l'écran, confirmée uniquement par lecture exacte du code ci-dessus.

## Questions to Consider

- Le filtrage automatique sur "contrats ciblés" doit-il rester activé par défaut, ou seulement proposé comme suggestion explicite au premier chargement ?
- Le total affiché dans l'onglet "Statistiques" doit-il toujours représenter la base entière, ou se filtrer lui aussi selon ce que l'utilisateur voit dans la liste ?
- Le remontage complet pendant la pagination était-il un choix volontaire (éviter un état transitoire incohérent), ou un oubli du mode silencieux déjà utilisé ailleurs dans ce même fichier ?
