---
task: Implement multi-step onboarding wizard page (/onboarding) with targeting, CV upload, and external sources
status: completed
created: 2026-09-16
---

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-micro-plans` to execute this plan — never `superpowers:executing-plans`, which does not know this file's `[~]` marker, Execution Log format, or evidence rule.

# Multi-Step Onboarding Wizard Page

## Context
- Existing code checked (inventaire complet de la plateforme) :
  - `TargetingPreferencesSection.tsx` : existe déjà et est 100% fonctionnel (postes, remote, séniorité, salaires, devises, contrats, préavis, keywords bannis, industries). Il sauvegarde directement via `coverLetterApi.updateCandidatePreferences()`.
  - `CvDropzone.tsx` : existe déjà et est 100% fonctionnel (drag-and-drop PDF, parsing VLM/LLM instantané, mise à jour du profil via `coverLetterApi.importCv()`).
  - Collecteurs de sources externes : `coverLetterApi.importGithub()` et `coverLetterApi.importWebsite()` sont déjà implémentés et testés dans l'API (`/profile/candidate/sources/github`, `/profile/candidate/sources/website`).
  - Backend models : `CandidateProfile` et `CandidatePreferences` sont déjà en production avec toutes les méthodes de merge multi-sources.
  - Auth et User models : `UserModel` et `UserResponse` gèrent déjà le compte mais n'ont pas d'indicateur d'état d'onboarding (`onboarding_completed`).
- Fresh info looked up:
  - Next.js App Router : création de la page `/onboarding` avec composant client (`"use client"`) protégé par `ProtectedRoute`.

## Simpler Alternative Considered
- Refaire de nouveaux formulaires pour le wizard : **REJETÉ** pour éviter la duplication de code et garantir la cohérence absolue avec la page `/profile`.
- **Approche retenue** : Orchestrer et composer les briques existantes (`TargetingPreferencesSection`, `CvDropzone`, imports de sources) au sein d'un Stepper moderne (3 étapes + récapitulatif) avec progression persistée et transition vers le dashboard.

## Surgical Scope
- **Files touched**:
  - `backend/app/models.py` (extension de `UserModel` et `UserResponse` avec `onboarding_completed: Optional[bool] = False`)
  - `backend/app/routers/users.py` (ajout endpoint `POST /users/complete-onboarding`)
  - `backend/tests/test_onboarding.py` (nouveaux tests du statut et de l'endpoint)
  - `frontend/src/lib/api.ts` (ajout de `onboarding_completed` dans `User` et méthode `userApi.completeOnboarding()`)
  - `frontend/src/app/onboarding/page.tsx` (nouvelle page d'orchestration du wizard)
- **Files NOT touched**:
  - `TargetingPreferencesSection.tsx` (réutilisé tel quel via ses props)
  - `CvDropzone.tsx` (réutilisé tel quel via ses props)
  - Tous les services de parsing, crawling, normalisation existants
- **Symbols replaced**: none.
- **Symbols extended**:
  - `UserModel`, `UserResponse` (`backend/app/models.py`) : `onboarding_completed: Optional[bool] = False`.
  - `userApi` (`frontend/src/lib/api.ts`) : `completeOnboarding(): Promise<User>`.

## Definition of Done
- [x] Build passes: `python3 -m py_compile backend/app/models.py backend/app/routers/users.py`
- [x] Frontend build passes: `npm --prefix frontend run build`
- [x] Tests pass: `.venv/bin/pytest tests/test_onboarding.py -v` (0 failures)
- [x] No dead code: n/a — aucun symbole remplacé
- [x] Zero code duplication: réutilisation à 100% des composants de ciblage, dropzone CV et endpoints existants
- [x] Manual check: la page `/onboarding` guide l'utilisateur à travers les 3 étapes (Ciblage, CV, Sources Web) et le bouton final "Accéder à mon espace" valide l'onboarding et redirige vers `/dashboard`.

## Steps
- [x] Step 1: Dans `backend/app/models.py`, ajouter `onboarding_completed: Optional[bool] = False` à `UserModel` et `UserResponse`.
- [x] Step 2: Dans `backend/app/routers/users.py`, ajouter `POST /users/complete-onboarding` pour passer le drapeau à `True` en base et renvoyer l'utilisateur mis à jour.
- [x] Step 3: Écrire les tests unitaires et d'API dans `backend/tests/test_onboarding.py` pour valider le modèle et l'endpoint.
- [x] Step 4: Dans `frontend/src/lib/api.ts`, déclarer `onboarding_completed?: boolean` sur l'interface `User` et ajouter `completeOnboarding()` dans `userApi`.
- [x] Step 5: Créer `frontend/src/app/onboarding/page.tsx` avec :
  - Barre de progression interactive (Étape 1 : Ciblage → Étape 2 : CV & Expériences → Étape 3 : Liens & Lancement).
  - Étape 1 : Intègre `TargetingPreferencesSection` pour renseigner ou ajuster le ciblage. Bouton "Étape suivante" ou "Passer".
  - Étape 2 : Intègre `CvDropzone` pour l'upload PDF + aperçu instantané du nombre d'expériences et compétences extraites. Boutons "Étape suivante" / "Retour".
  - Étape 3 : Champs d'import pour GitHub et Website/Portfolio utilisant directement `coverLetterApi.importGithub` / `importWebsite`, récapitulatif global et bouton "Lancer mon espace" appelant `completeOnboarding()` et redirigeant vers `/dashboard`.
- [x] Step 6 (teardown): Validation backend (`py_compile` + `pytest`), build frontend (`npm run build`), mise à jour du journal d'exécution et de `DAILY_LOG`.

## Code Review
- Dead code removed: yes
- Build status: pass
- Type errors: none
- Unintended side effects: none
- Security surface touched: no (standard auth-protected endpoints, user_id isolation)
- Verdict: ✅ DONE

## Execution Log
- Step 1 completed: Added `onboarding_completed: Optional[bool] = False` to `UserModel` and `UserResponse` in `backend/app/models.py`. Verified with `python3 -m py_compile backend/app/models.py`.
- Step 2 completed: Added `POST /users/complete-onboarding` endpoint in `backend/app/routers/users.py`. Verified with `python3 -m py_compile backend/app/routers/users.py`.
- Step 3 completed: Wrote tests in `backend/tests/test_onboarding.py` (model default, serialization, endpoint). Verified with pytest (3 passed in 0.06s).
- Step 4 completed: Added `onboarding_completed?: boolean` to `User` interface and `completeOnboarding()` to `userApi` in `frontend/src/lib/api.ts`.
- Step 5 completed: Implemented `frontend/src/app/onboarding/page.tsx` orchestrating Step 1 (TargetingPreferencesSection), Step 2 (CvDropzone + live extracted data preview), and Step 3 (GitHub & Website source imports, summary review, completeOnboarding action).
- Step 6 completed: Built frontend with `next build` (zero errors, `/onboarding` statically optimized), validated 30 backend tests (100% pass), and updated Daily Log.

## Notes
- Stepper design: Clean, modern progress bar with 3 steps: "1. Ciblage", "2. CV & Parcours", "3. Présence Web & Validation".
- Persistence: User can skip optional steps if they want to complete them later in `/profile`.
