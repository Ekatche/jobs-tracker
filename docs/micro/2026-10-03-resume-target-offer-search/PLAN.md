---
title: Affichage exclusif de l'offre cible et recherche d'offres via API dans la modale CV Adapté
status: done
---

## User intent
1. Lorsque la modale de génération de CV adapté s'ouvre avec une offre présélectionnée (via l'URL `?generate_offer_id=` ou un bouton), afficher UNIQUEMENT cette offre cible sélectionnée de manière claire, sans charger ni afficher une liste arbitraire de 100 offres.
2. Si aucune offre n'est présélectionnée ou si l'utilisateur souhaite changer d'offre, proposer une barre de recherche connectée dynamiquement à l'endpoint de recherche d'offres (`jobOffersApi.getAll({ keywords, limit: 15 })`) avec debouncing au lieu d'un simple filtrage local sur 100 offres pré-téléchargées.

## Surgical Scope
- `frontend/src/app/resumes/page.tsx`:
  - Remplacement du chargement massif de 100 offres par la récupération ciblée via `jobOffersApi.getById(initialOfferId)` si fourni.
  - Ajout d'un état `selectedOffer: JobOffer | null`, `selectedOfferId` et `isSearchingOffer: boolean`.
  - Implémentation d'une recherche serveur debouncée (300ms) connectée à l'API (`jobOffersApi.getAll({ keywords, limit: 15 })`).
  - Affichage exclusif de l'offre sélectionnée dans une carte mise en valeur avec possibilité de basculer en mode recherche ("Changer d'offre").
  - Nettoyage automatique du paramètre d'URL `generate_offer_id` à la fermeture ou fin de génération.

## Steps
- [x] 1. Mettre à jour `openGenerateModal` pour récupérer directement l'offre présélectionnée par son ID (`jobOffersApi.getById`), ou charger les suggestions récentes (limit: 10) si aucune offre n'est fournie.
- [x] 2. Remplacer le filtrage client par une recherche serveur debouncée (300ms) avec indicateur de chargement (`FiRefreshCw animate-spin`).
- [x] 3. Intégrer l'affichage exclusif de l'offre sélectionnée avec badge "Offre sélectionnée" et bouton "Modifier / Changer d'offre".
- [x] 4. Valider le build Next.js (`npm --prefix frontend run build`).

## Definition of Done
- [x] `npm --prefix frontend run build` compile avec succès (19/19 routes générées, code de sortie 0).
- [x] La présélection via `generate_offer_id` affiche directement l'offre ciblée sans être limitée aux 100 dernières offres.

## Code Review
- **Aesthetics & UX:** Interface nette et aérée : l'offre sélectionnée apparaît sous forme d'une belle fiche récapitulative. Recherche fluide avec debounce.
- **Performance:** Fin des 100 offres chargées inutilement. Moins de bande passante et latence réduite.
- Verdict: ✅ DONE

## Execution Log
- 17:40 : Création du plan micro-dev.
- 17:41 : Mise à jour de `frontend/src/app/resumes/page.tsx` (recherche API debouncée + carte exclusive offre cible).
- 17:41 : Validation du build Next.js (succès complet).
- 17:42 : Correction du warning exhaustive-deps sur `useCallback`.
