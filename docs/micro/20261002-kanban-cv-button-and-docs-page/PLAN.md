---
task: Bouton CV Adapté universel dans le tiroir Kanban et page de Documentation
description: "Ajout du bouton CV Adapté toujours actif dans ApplicationDetails (Kanban) avec endpoint ensure-offer + création de la page /docs et lien Header — applications.py, ApplicationDetails.tsx, resumes/page.tsx, docs/page.tsx, Header.tsx"
status: planned
created: 2026-10-02
---

# Bouton CV Adapté universel dans le tiroir Kanban et page de Documentation

## Context
- L'utilisateur signale que sur la sidebar de ses fiches emploi dans le kanban (`ApplicationDetails`), le bouton menant à la création de CV adapté n'apparaît toujours pas pour ses fiches.
- En inspectant le code, le bouton existant était masqué conditionnellement par `(application.offer_id || evaluation?.offer_id)`. Or, les candidatures créées manuellement ou non encore évaluées ne possèdent pas d'`offer_id` lié, rendant le bouton invisible. De plus, son emplacement était confiné aux petits chips de métadonnées.
- L'utilisateur souhaite également une page de documentation (`/docs`) accessible dans l'application qui explique clairement comment utiliser toutes les fonctionnalités de Job Tracker.

## Simpler Alternative Considered
- Afficher le bouton uniquement si une évaluation a été calculée : rejeté car cela force l'utilisateur à lancer une évaluation avant de pouvoir générer un CV.
- Page d'aide externe ou modale simple : rejeté car une page `/docs` dédiée avec barre de recherche, sommaire et sections détaillées offre une vraie valeur produit et une navigation fluide.

## Surgical Scope
- **Files touched**:
  - `backend/app/routers/applications.py` : ajout de l'utilitaire `ensure_offer_for_application` et du endpoint `POST /applications/{application_id}/ensure-offer`
  - `frontend/src/lib/api.ts` : ajout de `ensureOffer` dans `applicationsApi`
  - `frontend/src/components/applications/ApplicationDetails.tsx` : affichage systématique du bouton « CV Adapté » dans l'en-tête de la fiche candidature (avec création/liaison automatique de l'offre si nécessaire avant redirection)
  - `frontend/src/app/resumes/page.tsx` : fiabilisation du chargement d'offre individuelle lorsque `generate_offer_id` n'est pas dans le top 100
  - `frontend/src/app/docs/page.tsx` : nouvelle page de documentation interactive et complète
  - `frontend/src/components/layout/Header.tsx` : ajout du lien vers `/docs` dans la navigation principale (desktop et mobile)
- **Files NOT touched**:
  - Les modèles de base de données, la logique de génération de CV, les autres composants Kanban
- **Symbols replaced**:
  - Condition restrictive `(application.offer_id || evaluation?.offer_id)` pour le bouton CV dans `ApplicationDetails.tsx`
- **Symbols extended**:
  - `job_router` dans `backend/app/routers/applications.py` (`ensure_offer_for_application`, `ensure_application_offer`)
  - `applicationsApi` dans `frontend/src/lib/api.ts` (`ensureOffer`)
  - `ApplicationDetails` dans `frontend/src/components/applications/ApplicationDetails.tsx`
  - `Header` dans `frontend/src/components/layout/Header.tsx`

## Definition of Done
- [ ] Le backend expose `POST /applications/{application_id}/ensure-offer` qui garantit qu'une offre existe et renvoie `{"offer_id": str}` : `python -c "import ast; ast.parse(open('backend/app/routers/applications.py').read())"`
- [ ] `frontend/src/lib/api.ts` exporte `ensureOffer` : `grep -c 'ensureOffer' frontend/src/lib/api.ts` (attendu >= 1)
- [ ] `ApplicationDetails.tsx` affiche le bouton « CV Adapté » indépendamment de la présence préalable de `offer_id` : `grep -c 'handleOpenCvGenerator' frontend/src/components/applications/ApplicationDetails.tsx` (attendu >= 1)
- [ ] La page `/docs` existe et contient les guides d'utilisation complets : `test -f frontend/src/app/docs/page.tsx` (exit 0)
- [ ] `Header.tsx` inclut un lien de navigation vers `/docs` : `grep -c 'href="/docs"' frontend/src/components/layout/Header.tsx` (attendu >= 2)
- [ ] Le build frontend réussit sans aucune erreur TypeScript ou de syntaxe : `npm --prefix frontend run build`

## Steps
- [ ] Step 1: Ajouter la fonction `ensure_offer_for_application` et l'endpoint `POST /{application_id}/ensure-offer` dans `backend/app/routers/applications.py`.
- [ ] Step 2: Ajouter la méthode `ensureOffer` dans `applicationsApi` (`frontend/src/lib/api.ts`).
- [ ] Step 3: Mettre à jour `ApplicationDetails.tsx` pour afficher un bouton « CV Adapté » visible et actif en permanence avec prise en charge du cas sans `offer_id`.
- [ ] Step 4: Sécuriser `frontend/src/app/resumes/page.tsx` pour récupérer l'offre ciblée par son ID si elle n'est pas dans le top 100 initial.
- [ ] Step 5: Créer la page de documentation `frontend/src/app/docs/page.tsx` (guide interactif, FAQ, sections illustrées).
- [ ] Step 6: Ajouter le lien « Documentation » dans `frontend/src/components/layout/Header.tsx`.
- [ ] Step 7 (teardown): Exécuter le build frontend et vérifier l'absence d'erreurs de type ou d'orphelins.

## Code Review
- Dead code removed: yes / no
- Build status: pass / fail
- Type errors: none / fixed
- Unintended side effects: none
- Security surface touched: no
- Verdict: ✅ DONE / ⚠️ BLOCKED

## Execution Log
(append-only, filled by executing-micro-plans)

## Notes
(deviations from plan, errors hit, corrections made)
