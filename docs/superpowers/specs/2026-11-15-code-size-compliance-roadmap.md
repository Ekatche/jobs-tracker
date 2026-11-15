# Feuille de Route — Mise en Conformité Taille & Modularité du Code

Date : 2026-11-15  
Statut : Audit initial & cadrage des lots (sous-projet dédié)  
Cible architecturale : **≤ 300 lignes par fichier** (cible), **≤ 500 lignes** (plafond strict), fonctions ≤ 50 lignes, séparation Schémas / Logique pure / Adaptateurs I/O.  

---

## 1. État des lieux (Audit `wc -l` au 2026-11-15)

### Fichiers Frontend > 500 lignes (20 fichiers)
| Lignes | Fichier | Problème principal |
|---|---|---|
| 1687 | `frontend/src/components/profile/CandidateProfileSection.tsx` | Formulaire complet + CRUD expériences/projets/diplômes/certifications/styles |
| 1620 | `frontend/src/app/offers/page.tsx` | Page complète, OfferCard, pagination, filtres avancés, modals |
| 1145 | `frontend/src/lib/api.ts` | Client HTTP, auth refresh + tous les endpoints + toutes les interfaces |
| 999 | `frontend/src/components/profile/TargetingPreferencesSection.tsx` | Formulaire préférences multi-sections |
| 920 | `frontend/src/components/applications/ApplicationDetails.tsx` | Détails candidature + évaluation + notes + relances + actions |
| 876 | `frontend/src/app/admin/page.tsx` | Tableau admin users/usage/actions |
| 872 | `frontend/src/app/applications/page.tsx` | Kanban + liste + détails + modals + transitions |
| 854 | `frontend/src/app/offers/[id]/page.tsx` | Détail offre + onglets Bloc A/B/G + description + prep |
| 828 | `frontend/src/components/applications/CoverLetterPanel.tsx` | Éditeur lettre + historique versions + réécriture partielle + rapport garde |
| 681 | `frontend/src/components/dashboard/EditApplicationModal.tsx` | Formulaire modal complet |
| 612 | `frontend/src/app/settings/usage/page.tsx` | Quotas + paliers + journal d'appels |
| 609 | `frontend/src/app/resumes/page.tsx` | Liste CV + générateur + modale |
| 607 | `frontend/src/app/page.tsx` | Landing page multi-sections |
| 586 | `frontend/src/app/profile/page.tsx` | Orchestration page profil |
| 571 | `frontend/src/app/onboarding/page.tsx` | Wizard multi-étapes |
| 554 | `frontend/src/components/resumes/ResumePreviewModal.tsx` | Aperçu + customisation thème + éditeur contenu |
| 542 | `frontend/src/app/tasks/page.tsx` | Liste tâches + création/édition |
| 540 | `frontend/src/components/dashboard/NewApplicationModal.tsx` | Modale création candidature |
| 520 | `frontend/src/app/guide/page.tsx` | Données FAQ + rendu page |
| 503 | `frontend/src/components/interview/InterviewPrepTab.tsx` | Préparation d'entretien complète |

*(Note : `StorySlotsTable.tsx` à 497 et `Header.tsx` à 475 sont en zone d'alerte 400–500.)*

### Fichiers Backend > 500 lignes (17 fichiers)
| Lignes | Fichier | Problème principal |
|---|---|---|
| 1305 | `backend/app/routers/job_offers.py` | Catalogue + interactions + filtres + stats + évaluation + nettoyage |
| 1066 | `backend/app/models.py` | Tous les schémas Pydantic mélangés dans un fichier unique |
| 967 | `backend/app/routers/applications.py` | CRUD Kanban + génération background + cover letters + analytics |
| 961 | `backend/app/services/interview_prep_service.py` | Génération multi-modules + practice feedback + garde-fous |
| 943 | `backend/app/services/cv_guards.py` | Extraction métriques + garde ancienneté + audit expériences/compétences |
| 939 | `backend/app/services/normalization.py` | Nettoyage HTML + déduplication + contrats + clés d'identité |
| 927 | `backend/app/services/ats/router.py` | Extracteurs par plateforme + JSON-LD + curl_cffi + marqueurs non-contenu |
| 923 | `backend/app/services/evaluation/evaluator.py` | Prompts + two-pass + gating + Bloc B/G/H + orchestration DB |
| 852 | `backend/app/tasks/job_offers_collectors.py` | Génération requêtes + collecte structurée/Tavily + persistance |
| 846 | `backend/app/tasks/verify_job_offers.py` | Checks HTTP + JSON-LD + redirections + Crawl4AI liveness |
| 799 | `backend/app/routers/interview_prep.py` | Endpoints kit + practice + streaming/annulation |
| 784 | `backend/app/services/cv_parser.py` | PDF/VLM transcription + nettoyage + parsing structuré |
| 784 | `backend/app/routers/cover_letters.py` | CRUD lettres + régénération + réécriture partielle + PDF |
| 773 | `backend/app/services/profile/merge.py` | Fusion multi-sources + arbitrage + déduplication |
| 754 | `backend/app/routers_legacy.py` | Anciens routeurs à auditer / archiver ou scinder |
| 644 | `backend/app/tasks/clean_job_offers.py` | Pipeline nettoyage nocturne |
| 537 | `backend/app/services/letter_guards.py` | Règles anti-hallucination + critique déterministe |

*(Zone d'alerte 400–500 : `company_profiles.py` 457, `star_bank.py` 438, `resumes.py` 432, `llm/utils.py` 430.)*

---

## 2. Stratégie de découpage en 6 lots autonomes (Zéro régression)

Chaque lot préserve strictement les imports existants via un fichier baril (`__init__.py` ou ré-exports `ts`) puis migre progressivement, avec passage complet des tests (`pytest` côté backend, `npm run build` / `lint` côté frontend) à chaque étape :

1. **Lot 1 — Socle Frontend (`api.ts` & `offers/page.tsx`)**
   - Scinder `frontend/src/lib/api.ts` en `frontend/src/lib/api/{client.ts,auth.ts,offers.ts,applications.ts,resumes.ts,profile.ts,interview.ts,usage.ts,index.ts}` avec ré-export strict dans `lib/api.ts`.
   - Extraire `OfferCard.tsx`, `OffersFiltersBar.tsx`, `OffersPagination.tsx` de `frontend/src/app/offers/page.tsx`.
2. **Lot 2 — Profil & Modales Frontend (`CandidateProfileSection.tsx`, `TargetingPreferencesSection.tsx`, `ApplicationDetails.tsx`)**
   - Découper `CandidateProfileSection.tsx` par section métier (`ProfileIdentityCard`, `ProfileExperiencesEditor`, `ProfileProjectsEditor`, `ProfileEducationCertsEditor`, `ProfileSourcesPanel`).
   - Découper `ApplicationDetails.tsx` et `CoverLetterPanel.tsx` (éditeur vs historique/rapport qualité).
3. **Lot 3 — Pages Secondaires Frontend (`applications/page.tsx`, `offers/[id]/page.tsx`, `admin/page.tsx`, `resumes/`, `onboarding/`)**
   - Extraire les sections d'onglets et cartes de détail dans des sous-composants ≤ 300 lignes.
4. **Lot 4 — Schémas & Routeurs Backend (`models.py`, `job_offers.py`, `applications.py`, `interview_prep.py`, `cover_letters.py`, `routers_legacy.py`)**
   - Scinder `backend/app/models.py` en package `backend/app/models/{common.py,users.py,offers.py,evaluation.py,applications.py,profile.py,resumes.py,usage.py,__init__.py}` (100 % rétrocompatible via `__init__.py`).
   - Extraire helpers DB/filtres de `routers/job_offers.py` et `routers/applications.py` vers `app/services/`.
5. **Lot 5 — Services IA & Garde-fous Backend (`evaluator.py`, `cv_guards.py`, `letter_guards.py`, `interview_prep_service.py`, `cv_parser.py`, `profile/merge.py`)**
   - Appliquer la séparation stricte 3 couches : constantes/règles (`rules.py`) vs logique pure (`metrics.py`, `scoring.py`) vs adaptateurs LLM/DB.
6. **Lot 6 — Collecte, ATS & Tâches Airflow (`ats/router.py`, `normalization.py`, `job_offers_collectors.py`, `verify_job_offers.py`, `clean_job_offers.py`)**
   - Séparer `ats/router.py` en un module par famille ATS (`ats/boards_api.py`, `ats/regional.py`, `ats/jsonld.py`, `ats/non_content.py`, `ats/router.py`).
   - Extraire des sous-modules spécialisés pour `normalization.py` et les tâches Airflow.

---

## 3. Règle d'enchaînement recommandée

1. Terminer et déployer d'abord le sous-projet **Intégration Frontend Career-Ops v1.32+**.
2. Exécuter ensuite cette feuille de route **lot par lot** (`Lot 1` → `Lot 6`), chaque lot faisant l'objet d'un plan dédié (`writing-plans` / `executing-plans`), d'un contrôle `wc -l` automatisé et d'une passe complète de tests sans régression.
