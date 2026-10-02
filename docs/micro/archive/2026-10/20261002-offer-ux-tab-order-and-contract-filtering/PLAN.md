---
task: Nettoyage du jargon interne, réorganisation des onglets du détail d'offre et filtrage/distinction des stages
description: "Nettoyage du jargon interne, réorganisation des onglets du détail d'offre et filtrage/distinction des stages — app/offers/[id]/page.tsx, components/interview/InterviewPrepTab.tsx, app/offers/page.tsx, lib/contractBadge.ts, components/applications/ApplicationDetails.tsx, app/settings/usage/page.tsx +2"
status: done
created: 2026-10-02
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Nettoyage du jargon interne, réorganisation des onglets du détail d'offre et filtrage/distinction des stages

## Context
- Existing code checked:
  - `frontend/src/app/offers/[id]/page.tsx` affiche des mentions techniques internes pour l'utilisateur ("Bloc B", "Blocs A & G", "Bloc A", "Bloc G", "Two-Pass"), et commence par l'onglet `matching` au lieu de la description du poste.
  - `frontend/src/components/interview/InterviewPrepTab.tsx` mentionne "exigences du Bloc B" dans la description de la section stories.
  - `frontend/src/app/offers/page.tsx` utilise le même badge neutre gris (`bg-slate-800 text-slate-300`) pour tous les types de contrats (Stage, CDI, etc.), sans distinction visuelle claire, et n'exploite pas les `contract_types` définis dans les préférences du profil candidat (`candidate_profile.preferences.contract_types`) pour pré-positionner le filtre.
  - `backend/app/services/normalization.py` nettoie les mots "stage", "stagiaire", "intern" du titre sans garantir que `type_contrat` soit alimenté si celui-ci était nul ou "Non spécifié".
- Fresh info looked up: n/a
- Git status checked: clean on expected files in scope.

## Simpler Alternative Considered
- Masquer purement et simplement les stages côté backend : rejeté car l'utilisateur souhaite pouvoir afficher tous les contrats à la demande via le sélecteur standard de contrat.

## Surgical Scope
- **Files touched**:
  - `frontend/src/app/offers/[id]/page.tsx`
  - `frontend/src/components/interview/InterviewPrepTab.tsx`
  - `frontend/src/app/offers/page.tsx`
  - `frontend/src/lib/contractBadge.ts`
  - `frontend/src/components/applications/ApplicationDetails.tsx`
  - `frontend/src/app/settings/usage/page.tsx`
  - `backend/app/services/normalization.py`
  - `backend/tests/test_normalization_and_dedup.py`
- **Files NOT touched**: all others
- **Symbols replaced**: none
- **Symbols extended**:
  - `OfferDetailPage` in `frontend/src/app/offers/[id]/page.tsx` (ordre des onglets, onglet par défaut 'job', retrait libellés Blocs)
  - `InterviewPrepTab` in `frontend/src/components/interview/InterviewPrepTab.tsx` (libellé vulgarisé sans Bloc B)
  - `JobOffersPage` in `frontend/src/app/offers/page.tsx` (badges colorés par type de contrat, prise en compte des `contract_types` du profil)
  - `normalize_offer_fields` in `backend/app/services/normalization.py` (détection automatique de `type_contrat` depuis le titre avant nettoyage)

## Definition of Done
- [x] Backend tests pass: `docker exec jobtracker-backend pytest tests/test_normalization_and_dedup.py` (18 passed)
- [x] Frontend build passes: `npm --prefix frontend run build` (Exit code 0)
- [x] No internal jargon in UI: aucune occurrence de "Bloc A", "Bloc B", "Bloc G", ou "Two-Pass" visible par l'utilisateur.
- [x] Tab order: l'onglet "Annonce du Poste" est le 1er onglet et affiché par défaut à l'ouverture de l'offre.
- [x] Contract distinction & filtering:
  - Les badges de contrat sur la liste des offres ont des styles visuels immédiatement reconnaissables (Stage en ambre avec icône 🎓, CDI en émeraude, CDD en bleu ciel, Freelance en violet).
  - La page des offres charge les préférences de contrat du profil et pré-positionne le filtre pour cibler ces contrats par défaut, avec possibilité de sélectionner "Tous les contrats".

## Steps
- [x] Step 1: Mettre à jour `backend/app/services/normalization.py` pour détecter le type de contrat (Stage, Alternance, CDI, CDD) dans le titre avant nettoyage syntaxique si `type_contrat` est vide ou "Non spécifié". Ajouter les tests associés dans `backend/tests/test_normalization_and_dedup.py`.
- [x] Step 2: Mettre à jour `frontend/src/app/offers/[id]/page.tsx` :
  - Définir `activeTab` initial à `"job"`.
  - Réordonner les boutons d'onglets pour mettre "Annonce du Poste" en 1er, suivi de "Adéquation Exigences", "Stratégie & Intégrité", "Préparation Entretien".
  - Retirer toutes les mentions de "Bloc B", "Blocs A & G", "Bloc A", "Bloc G", et remplacer "Two-Pass" par une formulation naturelle d'adéquation IA.
- [x] Step 3: Mettre à jour `frontend/src/components/interview/InterviewPrepTab.tsx` pour remplacer la mention "Bloc B" par un libellé clair ("exigences clés du poste").
- [x] Step 4: Mettre à jour `frontend/src/app/offers/page.tsx` :
  - Créer `frontend/src/lib/contractBadge.ts` et appliquer les styles de badges distinctifs (Stage en ambre 🎓, CDI en émeraude, CDD en bleu ciel, Freelance en violet).
  - Intégrer la lecture de `preferences.contract_types` dans `handleApplyProfileCriteria` et pré-sélectionner le filtre sur les contrats ciblés de l'utilisateur avec option explicite "Tous les contrats" et choix unitaires.
- [x] Step 5: Vérifier les tests backend et le build frontend, vérifier l'absence d'erreurs TypeScript, et consigner l'exécution dans `docs/micro/DAILY_LOG-2026-10-02.md`.

## Code Review
- Dead code removed: yes
- Build status: pass (`npm --prefix frontend run build` et `pytest tests/test_normalization_and_dedup.py` validés à 100%)
- Type errors: none
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE

## Execution Log
- 2026-10-02 11:05: Plan initialized after user grill-me alignment.
- 2026-10-02 11:08: Updated `backend/app/services/normalization.py` to extract contract types from raw title before syntax strip and verified with 18 unit tests in `backend/tests/test_normalization_and_dedup.py`.
- 2026-10-02 11:10: Updated `frontend/src/app/offers/[id]/page.tsx` with default active tab "job", reordered tab bar with "Annonce du Poste" first, and stripped all "Bloc" / "Two-Pass" jargon.
- 2026-10-02 11:12: Created `frontend/src/lib/contractBadge.ts` and enhanced `frontend/src/app/offers/page.tsx` with profile targeted contract pre-selection and vibrant badges (Amber 🎓 Stage, Emerald CDI, Sky CDD, Purple Freelance).
- 2026-10-02 11:13: Cleaned remaining Two-Pass / Blocs mentions in `ApplicationDetails.tsx` and `settings/usage/page.tsx`.
- 2026-10-02 11:14: Verified with `npm --prefix frontend run build` (exit code 0) and updated `docs/micro/DAILY_LOG-2026-10-02.md`.

## Notes
- None.
