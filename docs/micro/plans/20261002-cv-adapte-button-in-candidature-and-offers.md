---
task: Bouton CV Adapté disponible dans la fiche candidature et les pages d'offre
status: completed
created: 2026-10-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Bouton CV Adapté disponible dans la fiche candidature et les pages d'offre

## Context
- L'utilisateur souhaite avoir accès au bouton « CV Adapté » directement depuis sa fiche candidature lors de la navigation sur les pages d'offres.
- Actuellement, le bouton existe sur la barre supérieure de la page de détail d'offre (`/offers/[id]`), mais :
  1. La modal de candidature (`NewApplicationModal`) ouverte depuis une offre n'affiche pas de lien direct vers la génération du CV adapté.
  2. Le tiroir latéral `ApplicationDetails` (« Fiche Candidature ») n'affiche qu'un lien vers l'offre scrapée, sans bouton rapide vers `/resumes?generate_offer_id=...`.
  3. Les cartes d'offres sur `/offers` n'ont pas de raccourci direct « CV Adapté » (seulement Détails, Offre, Postuler).

## Simpler Alternative Considered
- Ajouter uniquement le bouton sur la page `/offers/[id]` : rejeté car l'utilisateur a spécifié le vouloir dans sa fiche candidature et ses pages d'offre.

## Surgical Scope
- **Files touched**:
  - `frontend/src/components/dashboard/NewApplicationModal.tsx`
  - `frontend/src/components/applications/ApplicationDetails.tsx`
  - `frontend/src/app/offers/page.tsx`
- **Files NOT touched**: backend files, other frontend pages
- **Symbols extended**:
  - `NewApplicationModal` header / banner with CV Adapté action
  - `ApplicationDetails` meta chips with CV Adapté button
  - `OfferCard` action bar in `offers/page.tsx` with CV Adapté button

## Definition of Done
- [x] Dans `NewApplicationModal`, lorsque `prefilledData.offer_id` est présent, un bouton distinct « CV Adapté » permet d'ouvrir directement `/resumes?generate_offer_id=${prefilledData.offer_id}` (dans un nouvel onglet pour ne pas perdre la saisie de candidature).
- [x] Dans `ApplicationDetails` (« Fiche Candidature »), lorsque `application.offer_id` ou `evaluation.offer_id` existe, un bouton « CV Adapté » est présent dans les actions rapides.
- [x] Dans `frontend/src/app/offers/page.tsx`, chaque carte d'offre dispose d'un bouton raccourci « CV Adapté » stylisé en indigo menant à `/resumes?generate_offer_id=${offer.id}`.
- [x] Le build frontend `npm --prefix frontend run build` passe avec code 0.

## Steps
- [x] Step 1: Mettre à jour `NewApplicationModal.tsx` pour inclure le bouton « CV Adapté » lorsque `prefilledData.offer_id` existe.
- [x] Step 2: Mettre à jour `ApplicationDetails.tsx` pour ajouter le bouton « CV Adapté » dans le bloc d'en-tête / meta chips.
- [x] Step 3: Mettre à jour `frontend/src/app/offers/page.tsx` pour ajouter le bouton « CV Adapté » sur les cartes d'offre.
- [x] Step 4: Valider avec `npm --prefix frontend run build`.
- [x] Step 5: Mettre à jour `docs/micro/DAILY_LOG-2026-10-02.md` et finaliser le plan.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-02 22:07: Plan authored and approved for micro-dev execution.
- 2026-10-02 22:08: Added CV Adapté button in `NewApplicationModal.tsx` prefilled banner.
- 2026-10-02 22:08: Added CV Adapté button in `ApplicationDetails.tsx` quick meta chips.
- 2026-10-02 22:09: Added CV Adapté shortcut button in `offers/page.tsx` offer cards.
- 2026-10-02 22:09: Next.js production build succeeded (`npm --prefix frontend run build` exit code 0).

## Notes
- `resumes/page.tsx` gère déjà nativement le paramètre de requête `?generate_offer_id=<id>` pour ouvrir automatiquement la modale de génération avec l'offre pré-sélectionnée.
