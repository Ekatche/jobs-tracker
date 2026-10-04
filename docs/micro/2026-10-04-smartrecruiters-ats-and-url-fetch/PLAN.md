---
title: Support SmartRecruiters Zero-Token, intégration ATS prioritaire dans fetch_documents et auto-liaison offer_id
status: done
---

## User intent
L'utilisateur souhaite pouvoir générer un CV adapté sur n'importe quelle offre/candidature ajoutée via une URL (comme le lien SmartRecruiters testé), fiabiliser l'extraction pour obtenir une description systématiquement sans blocage anti-bot/SPA, lier automatiquement l'offre à la candidature, et afficher des indications claires sur la page si une action manuelle est requise.

## Surgical Scope
- `backend/app/services/ats/router.py`:
  - Implémenté `extract_smartrecruiters_job(url, client)` via l'API publique `api.smartrecruiters.com/v1/companies/{company}/postings/{id}`.
  - Intégré SmartRecruiters dans `extract_ats_or_jsonld_offer(url, client)`.
- `backend/app/llm/utils.py`:
  - Mis à jour `fetch_documents(url)` pour appeler `extract_ats_or_jsonld_offer(url)` en première intention (Zero-Token, ~150ms).
  - Appliqué `optimize_crawl_url(url)` avant d'appeler `get_filtered_markdown(url)` pour débloquer les URLs LinkedIn (guest API) et Indeed (vue mobile).
  - Rendu l'import de `get_filtered_markdown` paresseux pour éviter les plantages au chargement si Crawl4AI n'est pas sollicité.
- `backend/app/routers/applications.py`:
  - Appelé systématiquement `_ensure_offer_for_application` dans `create_application` et `_generate_description_bg` pour associer l'`offer_id` en base dès que la description ou l'URL est prête.
  - Dans `update_application`, synchronisation immédiate de la description de la candidature vers `job_offers`.
  - Dans `regenerate_application_description`, liaison de l'offre si elle ne l'était pas encore.
- `frontend/src/components/applications/ApplicationDetails.tsx`:
  - Rendu le bouton « CV Adapté » résilient et explicite :
    - Si `offer_id` présent : redirection directe vers `/resumes?generate_offer_id=...`.
    - Si pas d'`offer_id` mais description présente : bouton actif avec auto-liaison transparente (`handleLinkOffer`) puis ouverture de la génération de CV.
    - Si aucune description : bouton désactivé (grisé) avec libellé explicite `CV Adapté (Description requise)`.
  - Bannière d'aide sous le champ description invitant à coller le texte de l'annonce si l'extraction d'URL a échoué.
- `backend/tests/test_ats_parsers.py`:
  - Ajouté 3 tests unitaires pour SmartRecruiters (succès avec sections et contrat, 404/offre expirée, routage ATS).

## Steps
- [x] 1. Ajouter le parseur SmartRecruiters dans `backend/app/services/ats/router.py`.
- [x] 2. Mettre à jour `fetch_documents` dans `backend/app/llm/utils.py` avec la cascade ATS & `optimize_crawl_url`.
- [x] 3. Assurer la liaison automatique `_ensure_offer_for_application` dans `backend/app/routers/applications.py`.
- [x] 4. Mettre à jour `ApplicationDetails.tsx` pour l'auto-liaison du bouton CV Adapté et le message d'aide.
- [x] 5. Écrire et exécuter les tests dans `backend/tests/test_ats_parsers.py` (17 tests validés).
- [x] 6. Tester directement avec l'URL SmartRecruiters de l'utilisateur (succès en 0.15s, 2288 caractères).

## Definition of Done
- [x] L'URL SmartRecruiters est extraite avec succès en ~150ms avec toutes ses sections (Ingénieur IA, ASI, Lyon, 2288 caractères).
- [x] L'extraction de candidatures par URL lie automatiquement une entrée `job_offers`.
- [x] Le bouton « CV Adapté » est disponible dès qu'une description est présente, ou affiche un message d'aide clair si manquante.
- [x] Tous les tests unitaires ATS passent sans régression (17 passed).

## Code Review
- **Performance & Zero-Token**: SmartRecruiters est traité en requête HTTP directe REST (150ms, 0 token) évitant l'échec sur SPA et anti-bot.
- **Auto-link & Synchronisation**: Toute description de candidature se synchronise dans `job_offers`, garantissant le déblocage du CV sur-mesure.
- **Frontend UX**: Le bouton "CV Adapté" ne disparaît plus silencieusement, il indique son état et permet l'auto-liaison en 1 clic.
- **Type Safety**: `npx tsc --noEmit` passe avec 0 erreur, `py_compile` validé sur tous les modules modifiés.
- Revue Claude (2026-10-04) — trois défauts corrigés avant commit :
  - `update_application` écrasait la description de l'offre liée dans `job_offers`, collection partagée entre utilisateurs. La synchronisation passe désormais par `_ensure_offer_for_application`, qui ne remplit qu'une description vide. Test `test_update_description_never_overwrites_shared_offer` (rouge sur l'ancien code, vert après).
  - `create_application` remplaçait un `offer_id` fourni par l'appelant lorsqu'il était absent de `job_offers` (`test_create_and_get_application_with_offer_id` échouait). L'auto-liaison n'a lieu que sans `offer_id`.
  - `window.open` après un `await` était bloqué par Safari : l'onglet est ouvert pendant le clic, puis redirigé une fois l'offre liée.
- Verdict: ✅ DONE

## Execution Log
- 19:37 : Initialisation du plan micro-dev et diagnostic de l'URL SmartRecruiters.
- 19:39 : Implémentation du connecteur SmartRecruiters et enregistrement dans `extract_ats_or_jsonld_offer`.
- 19:40 : Intégration de la cascade ATS Zero-Token et `optimize_crawl_url` dans `fetch_documents`.
- 19:41 : Mise à jour de `backend/app/routers/applications.py` avec auto-liaison systématique et propagation de description.
- 19:42 : Mise à jour de `ApplicationDetails.tsx` avec bouton CV Adapté résilient, auto-liaison au clic et banner d'aide.
- 19:43 : Validation TypeScript (`tsc --noEmit`) et exécution des tests unitaires (`test_ats_parsers.py` : 17 passed).
- 19:43 : Test d'intégration en direct sur l'URL SmartRecruiters fournie par l'utilisateur avec succès.
- 20:10 : Revue, correction des trois défauts ci-dessus ; 147 tests backend liés passent, tsc et ESLint propres.
