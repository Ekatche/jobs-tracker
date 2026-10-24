---
task: Conserver l'offre, l'évaluation et le kit d'entretien d'une candidature quand l'offre source disparaît
description: "Offre non trouvée 404 sur offre postulée — DELETE /job-offers/{id} et PATCH soft-delete sans auth ni garde candidature (job_offers.py, get_current_admin_user, safe_delete_or_expire_offer), _ensure_offer_for_application qui relie un nouvel offer_id sans migrer offer_evaluations ni interview_preps (applications.py), liens Offre scrapée / Préparer l'entretien / Analyse complète vers un offer_id mort (ApplicationDetails.tsx, link-offer, useRouter)"
status: done
created: 2026-10-23
---

# Conserver les données d'une offre postulée

## Context
- Existing code checked :
  - Cause racine du « Offre non trouvée » (voir mémoire `orphan-offer-ids-after-oct5-restore`) : la restauration du 2026-10-05 (`backend/scripts/restore_to_db.py`) a recréé candidatures et évaluations, pas les `job_offers`. En base locale, 11 candidatures sur 12 pointent vers une offre absente ; 6 d'entre elles ont une évaluation indexée sur cet `offer_id` mort. Une offre seulement expirée reste lisible (soft-delete).
  - `backend/app/routers/job_offers.py:794-804` `delete_job_offer` : `delete_one` physique, **sans authentification**, sans vérifier les candidatures liées. `job_offers_router` est monté sans dépendance (`main.py:96`).
  - `backend/app/routers/job_offers.py:756-791` `soft_delete_job_offer` : **sans authentification** non plus.
  - Aucun appelant frontend : `offerApi.permanentDelete` et `offerApi.softDelete` (`frontend/src/lib/api.ts:674-696`) ne sont appelés nulle part dans `frontend/src`.
  - `backend/app/auth.py:151-160` `get_current_admin_user` existe déjà (403 si `role != admin`), utilisé par `routers/admin.py`.
  - `backend/app/tasks/clean_job_offers.py:23-75` : `is_offer_referenced_by_application` + `safe_delete_or_expire_offer(offer_id, collection, db)`, qui renvoie `"expired"`, `"deleted"` ou `"error"`. C'est le motif retenu par le plan `archive/2026-09/20260916-zero-token-ats-and-offer-cleaning-alignment`.
  - `backend/app/routers/applications.py:706-796` `_ensure_offer_for_application` : quand l'`offer_id` est mort, il retrouve l'offre (url, puis `unique_key`) ou en insère une nouvelle, puis réécrit `applications.offer_id`. L'évaluation (`offer_evaluations`) et le kit (`interview_preps`) restent sur l'ancien id : `GET /applications/{id}/evaluation` renvoie `None` et le kit semble vide.
  - Formes stockées : `offer_evaluations` écrit `{"user_id": str, "offer_id": str}` (`evaluator.py:555`) ; `interview_preps` est lu en acceptant `str` ou `ObjectId` pour les deux champs (`interview_prep.py:45-51`). Aucun index unique sur ces deux collections (vérifié en local) : la migration doit elle-même éviter de créer un doublon `(user_id, offer_id)`.
  - `resumes.py` ne stocke rien par `offer_id` (il lit l'offre et l'évaluation) : rien d'autre à migrer. Les `user_offer_interactions` de l'ancien id restent orphelines sans effet ; `link_application_offer` crée déjà l'interaction « applied » sur le nouvel id.
  - `frontend/src/components/applications/ApplicationDetails.tsx` : `handleLinkOffer` (L179-195) appelle `POST /applications/{id}/link-offer` (sans LLM) et renvoie le nouvel `offer_id`. Trois `<Link href={`/offers/...`}>` (L384 « Offre scrapée », L559 « Préparer l'entretien », L567 « Analyse complète ») utilisent l'`offer_id` stocké sans le réparer. `handleOpenTailoredResumeWithAutoLink` (L198-209) ne lie que si aucun id n'existe et garde donc un id mort.
  - Tests existants : `tests_for` ne renvoie aucun test direct pour `delete_job_offer`, `_ensure_offer_for_application` ou `link_application_offer`.
- Fresh info looked up : n/a (FastAPI `Depends`, Motor et `next/navigation` sont déjà utilisés tels quels dans le dépôt).
- Git status checked : `job_offers.py`, `applications.py` et `ApplicationDetails.tsx` sont propres. `tests/test_interview_prep_api.py` (plan A) et `tests/test_verify_job_offers.py` (autre session) sont modifiés : ils ne sont pas touchés, les nouveaux tests vont dans un fichier neuf.

## Simpler Alternative Considered
1. **Script ponctuel qui recrée les 11 offres et réécrit les ids.** Il répare les données locales du 5 octobre, mais pas la cause : le `DELETE` ouvert peut recréer des orphelins, et la prochaine réparation par `link-offer` perdrait encore l'évaluation. Écarté comme solution unique. Le flux réparé par ce plan rend ce script inutile : un clic suffit à réparer chaque candidature.
2. **Supprimer `DELETE` et `soft-delete`, qui n'ont aucun appelant frontend.** Plus radical, mais le nettoyage reste l'affaire des tâches Airflow, et un admin peut avoir besoin de la route. Retenu à la place : les garder, mais les réserver aux admins et rendre `DELETE` non destructif pour une offre liée.
3. **Afficher seulement un message plus clair sur `/offers/[id]`.** Ne rend ni l'évaluation ni le kit. Écarté.

## Surgical Scope
- **Files touched** :
  - `backend/app/routers/job_offers.py` (`delete_job_offer`, `soft_delete_job_offer`, import)
  - `backend/app/routers/applications.py` (`_ensure_offer_for_application` + nouvelle fonction privée `_migrate_user_offer_data`)
  - `frontend/src/components/applications/ApplicationDetails.tsx` (`handleLinkOffer` réutilisé, nouveau `handleOpenOffer`, `handleOpenTailoredResumeWithAutoLink`, 3 liens convertis en boutons)
  - `backend/tests/test_applied_offer_retention.py` (nouveau)
- **Files NOT touched** : `backend/app/tasks/clean_job_offers.py` (réutilisé tel quel), `frontend/src/lib/api.ts`, `frontend/src/app/offers/[id]/*`, `backend/app/routers/interview_prep.py`, `backend/tests/test_interview_prep_api.py`, `backend/tests/test_verify_job_offers.py`, `backend/app/tasks/verify_job_offers.py`, la documentation. Tout le reste.
- **Symbols replaced** (→ to delete before done) : les 3 `<Link href={`/offers/${...}`}>` de `ApplicationDetails.tsx`, remplacés par des `<button onClick={() => handleOpenOffer(...)}>`. Le corps de `delete_job_offer` (`delete_one` direct), remplacé par `safe_delete_or_expire_offer`.
- **Symbols extended** (→ keep) :
  - `job_offers.py::delete_job_offer` : `Depends(get_current_admin_user)`, 404 si absente, puis `safe_delete_or_expire_offer`. Message distinct si l'offre est conservée (`"expired"`), 500 si `"error"`.
  - `job_offers.py::soft_delete_job_offer` : `Depends(get_current_admin_user)`. Pas d'autre changement.
  - `applications.py::_ensure_offer_for_application` : mémorise l'`offer_id` d'origine ; s'il diffère de l'id final, appelle `_migrate_user_offer_data(user_id, old, new, db)`.
  - `applications.py::_migrate_user_offer_data` (nouveau) : pour `offer_evaluations` puis `interview_preps`, déplace les documents `(user_id, old)` vers `str(new)`, seulement si aucun document `(user_id, new)` n'existe déjà. Accepte `str` et `ObjectId` pour `user_id` et `offer_id`.
  - `ApplicationDetails.tsx::handleOpenOffer(suffix)` (nouveau) : `(await handleLinkOffer()) || application.offer_id || evaluation?.offer_id`, puis `router.push(`/offers/${id}${suffix}`)`.
  - `ApplicationDetails.tsx::handleOpenTailoredResumeWithAutoLink` : appelle `handleLinkOffer()` d'abord, l'id stocké sert de repli.

## Definition of Done
- [x] Lint backend : `cd backend && uv run ruff check app/routers/job_offers.py app/routers/applications.py tests/test_applied_offer_retention.py` (exit 0)
- [x] Nouveaux tests : `cd backend && uv run pytest tests/test_applied_offer_retention.py -v` (tous verts, au moins 5 tests)
- [x] Régression backend : `cd backend && uv run pytest tests/test_applications.py tests/test_interview_prep_api.py tests/test_clean_and_verify_alignment.py tests/test_job_offers_pipeline.py -q` (aucun nouvel échec par rapport à la baseline)
- [x] Type check frontend : `cd frontend && npx tsc --noEmit` (exit 0)
- [x] Lint frontend : `cd frontend && npm run lint` (aucune nouvelle erreur sur `ApplicationDetails.tsx`)
- [x] Build frontend : `cd frontend && npm run build` (exit 0)
- [x] Sécurité : `semgrep scan --config p/python --config p/secrets --metrics=off backend/app/routers/job_offers.py backend/app/routers/applications.py` (aucun nouveau finding par rapport à la baseline)
- [x] Routes de suppression réservées aux admins : `grep -c "Depends(get_current_admin_user)" backend/app/routers/job_offers.py` vaut 2
- [x] Plus de suppression physique directe dans la route : `awk '/^async def delete_job_offer/,/^@job_offers_router/' backend/app/routers/job_offers.py | grep -c "delete_one"` vaut 0
- [x] Plus de lien direct vers un `offer_id` non réparé : `grep -c 'href={`/offers/' frontend/src/components/applications/ApplicationDetails.tsx` vaut 0
- [x] No dead code : `Link` toujours importé seulement s'il reste utilisé (`grep -c "<Link" frontend/src/components/applications/ApplicationDetails.tsx` ≥ 1 ou import retiré) ; aucun import inutilisé signalé par ruff ou eslint
- [x] Manual check (observateur : l'utilisateur, stack locale) : sur une candidature à offre disparue avec évaluation (par exemple « Ingénieur Ia Agentique (h/f) »), cliquer « Préparer l'entretien » ouvre `/offers/<nouvel id>?tab=interview` sans « Offre non trouvée », et l'évaluation reste affichée sur la candidature après rechargement

## Steps
- [x] Step 1 : `backend/tests/test_applied_offer_retention.py` (rouge d'abord). Cas :
  - (a) `DELETE /job-offers/{id}` sans token renvoie 401 ou 403 ;
  - (b) avec un utilisateur non-admin, 403 ;
  - (c) en admin, une offre liée à une candidature survit avec `is_deleted=True` et `pipeline_stage="expired"` ;
  - (d) en admin, une offre non liée est supprimée physiquement ;
  - (e) `POST /applications/{id}/link-offer` sur une candidature dont l'offre a disparu rattache l'évaluation et le kit de l'utilisateur au nouvel `offer_id` ;
  - (f) la migration n'écrase pas un document existant pour le nouvel id et ne touche pas aux documents d'un autre utilisateur.

  Vérification : `cd backend && uv run pytest tests/test_applied_offer_retention.py -v`. Attendu : (a), (b), (c) et (e) échouent, (d) peut passer.
- [x] Step 2 : `job_offers.py`. Ajouter `Depends(get_current_admin_user)` sur `delete_job_offer` et `soft_delete_job_offer`. `delete_job_offer` : 400 si l'id est invalide, 404 si l'offre est absente, puis `safe_delete_or_expire_offer(offer_id, db["job_offers"], db)`. Réponses : `"expired"` → message « offre liée à une candidature, conservée et marquée expirée » ; `"error"` → 500. Vérification : pytest cas (a) à (d) verts, plus ruff.
- [x] Step 3 : `applications.py`. Ajouter `_migrate_user_offer_data` et l'appeler à la fin de `_ensure_offer_for_application` quand l'id d'origine diffère de l'id final. Vérification : pytest cas (e) et (f) verts, plus ruff.
- [x] Step 4 : `ApplicationDetails.tsx`. Importer `useRouter` depuis `next/navigation` et ajouter `handleOpenOffer(suffix)`. Convertir les 3 `<Link href={`/offers/...`}>` en `<button type="button">` avec les mêmes classes et le même contenu, désactivés pendant `isLinkingOffer`. `handleOpenTailoredResumeWithAutoLink` appelle d'abord `handleLinkOffer()`, en gardant l'ouverture d'onglet synchrone pour Safari. Vérification : `npx tsc --noEmit`, plus le grep `href={`/offers/` qui doit valoir 0.
- [x] Step 5 : contrôle manuel par l'utilisateur, sur la candidature « Ingénieur Ia Agentique (h/f) » (offre disparue, 1 évaluation, stack locale). Observer : la navigation vers `/offers/<nouvel id>?tab=interview` et l'évaluation toujours visible après rechargement de `/applications`. Vérification : log backend `POST /applications/<id>/link-offer` 200 puis `GET /job-offers/<nouvel id>` 200 (`docker compose logs -t backend --since <ts>`), plus la confirmation de l'utilisateur.
- [x] Step 6 (teardown) : orphan scan limité aux symboles remplacés. `<Link href={`/offers/` absent, `delete_one` absent de la route, import `Link` utilisé ou retiré. Puis semgrep, lint et build frontend. Confirmer 0 orphelin.

## Code Review
- Dead code removed : yes. Les 4 `<Link>` et l'import `next/link` sont retirés (`grep -c '<Link\|next/link'` vaut 0, `href={`/offers/` vaut 0) ; `delete_one` n'est plus dans la route (0) ; `handleOpenOffer` a 3 appelants, `_migrate_user_offer_data` 1, `safe_delete_or_expire_offer` 1.
- Build status : pass (`npm run build` exit 0, `npm run lint` exit 0).
- Type errors : none (`npx tsc --noEmit` exit 0 ; ruff exit 0).
- Unintended side effects : none relevé à la lecture du diff (81 lignes ajoutées, 26 retirées, 3 fichiers + 1 test neuf). Les boutons font un `POST link-offer` (sans LLM) avant chaque navigation, ce qui est voulu. Les nouveaux tests exigent `mongo_test` (port 27018), comme le reste des tests API du projet.
- Security surface touched : yes (authentification sur `DELETE /job-offers/{id}` et `PATCH /job-offers/{id}/soft-delete`), semgrep run : pass (p/python + p/secrets, 187 règles, 0 finding).
- Verdict : ✅ DONE

## Execution Log
- 2026-10-23T18:47Z | claude-code | plan | written | en attente d'approbation
- 2026-10-23T18:56Z | claude-code | plan | approved | « ok pour le plan » ; baseline dans Notes
- 2026-10-23T18:56Z | claude-code | step 1 | started
- 2026-10-23T18:57Z | claude-code | step 1 | done | `pytest tests/test_applied_offer_retention.py` 2 passed (d,f) 4 failed (a: DELETE anonyme 200, b: 200 au lieu de 403, c: offre liée effacée, e: évaluation non migrée) — rouge attendu
- 2026-10-23T18:57Z | claude-code | step 2 | started
- 2026-10-23T18:58Z | claude-code | step 2 | done | `pytest -k delete` 4 passed (a,b,c,d) ; ruff exit 0
- 2026-10-23T18:58Z | claude-code | step 3 | started
- 2026-10-23T18:59Z | claude-code | step 3 | done | `pytest tests/test_applied_offer_retention.py -v` 6 passed ; ruff exit 0
- 2026-10-23T18:59Z | claude-code | step 4 | started
- 2026-10-23T19:00Z | claude-code | step 4 | done | `npx tsc --noEmit` exit 0 ; eslint ApplicationDetails.tsx exit 0 ; grep href offers 0, <Link/next/link 0, href resumes 0
- 2026-10-23T19:00Z | claude-code | step 5 | started | en attente du contrôle utilisateur
- 2026-10-23T19:07Z | claude-code | step 5 | done | logs 19:04:06Z `POST /applications/6aaa4437…/link-offer` 200 puis `GET /job-offers/6adbafa6…` 200, `/evaluation` 200, `GET /offers/6adbafa6…/interview-prep` 200 ; DB : candidature `offer_id` = 6adbafa6…, offre 1, évaluation 1, kit 4 histoires ; capture utilisateur sur l'onglet « Préparation Entretien », sans « Offre non trouvée »
- 2026-10-23T19:08Z | claude-code | step 6 | started
- 2026-10-23T19:12Z | claude-code | step 6 | done | greps orphelins : href offers 0, `<Link`/next/link 0, delete_one route 0 ; semgrep 0 finding ; `npm run lint` exit 0 ; `npm run build` exit 0
- 2026-10-23T19:12Z | claude-code | plan | done | DoD complet relancé : ruff exit 0 ; pytest nouveaux 6 passed ; régression 40 passed ; tsc exit 0 ; lint exit 0 ; build exit 0 ; semgrep 0 ; admin 2 ; diff relu

## Notes
- Surface de sécurité : passer les 2 routes en admin-only ferme une suppression anonyme du catalogue partagé `job_offers`. Aucun appelant frontend n'existe : rien ne casse côté UI. Le DAG Airflow ne passe pas par l'API, il appelle `clean_job_offers` directement.
- Hors périmètre, observé, non changé : `soft_delete_job_offer` ne pose pas `pipeline_stage: "expired"`, contrairement aux tâches alignées par le plan du 2026-09-16. À traiter séparément si besoin.
- Les tests API du projet dépendent de `mongo_test` (port 27018, `conftest.py`). Les nouveaux tests suivent cette convention. Ils ne passent donc pas sans ce service, comme `test_applications.py` aujourd'hui.
- `link-offer` ne consomme aucun token LLM. L'appeler avant chaque navigation coûte un aller-retour DB, sans coût IA.
- La réparation des 11 candidatures locales du 5 octobre se fait au premier clic sur chacune, sans script. L'état de la prod reste inconnu : la lecture n'est pas autorisée.
- Conventions lues (phase 3) : `CLAUDE.md` racine, identique à `AGENTS.md`. Directives retenues : tests à forte valeur (contrats d'API, sécurité, ségrégation des accès, intégrité des données partagées) et `tests_for` avant de toucher aux tests.
- `_ensure_offer_for_application` a 6 appelants, tous dans `applications.py` : `_generate_description_bg`, `create_application`, `update_application`, `regenerate_application_description`, `link_application_offer` et `evaluate_application_offer`. La migration s'applique donc partout où l'id change, ce qui est voulu.
- Baseline 2026-10-23T18:56Z, avant tout changement :
  - ruff : 0 erreur ;
  - pytest (régression) : 40 passés ;
  - `npx tsc --noEmit` : 0 erreur ;
  - `npm run lint` : 0 erreur, avertissements `exhaustive-deps` préexistants (par exemple `ResumePreviewModal.tsx`), eslint propre sur `ApplicationDetails.tsx` ;
  - `npm run build` : exit 0 ;
  - semgrep : 0 finding sur 187 règles ;
  - greps : admin 0 (cible 2), `delete_one` dans la route 1 (cible 0), `href={`/offers/` 3 (cible 0), `<Link` 4.
- `/app/.next` est un volume anonyme du conteneur frontend : `npm run build` sur l'hôte n'écrase pas le serveur de dev.
- Écart de l'étape 4, dans le même fichier et dans l'intention approuvée (« les 4 boutons réparent l'offre ») : quand un `offer_id` existe, « CV Adapté » était un `<Link href={`/resumes?generate_offer_id=...`}>` (L391), pas `handleOpenTailoredResumeWithAutoLink`. Il est converti en `<button>` qui appelle ce handler, sinon l'id mort restait utilisé. Les 4 `<Link>` ayant disparu, l'import `next/link` est retiré (`grep -c '<Link\|next/link'` vaut 0).
- Clôturé 2026-10-23T19:12Z. Reste hors plan : commit et déploiement, à la demande de l'utilisateur. En prod, chaque candidature à offre disparue se répare au premier clic (aucun script à lancer).
