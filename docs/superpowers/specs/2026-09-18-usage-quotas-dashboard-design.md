# Design Spec: Phase 7 — Usage Tracking, Quotas & Monétisation UI

## 1. Contexte & Objectif
La Phase 7 apporte la couche transverse indispensable pour piloter la consommation des tokens LLM, faire respecter les limites par niveau d'abonnement (*Free*, *Advanced*, *Pro*) et offrir une interface limpide permettant aux utilisateurs de suivre leur quota restant et de changer de plan.

Le backend de tracking et d'application des quotas (`usage_tracker.py`, `usage.py`) étant déjà opérationnel, cette spécification formalise l'endpoint de changement de palier et la construction de l'interface complète `/settings/usage`.

---

## 2. Piliers Fonctionnels & Architecture

### 2.1 Backend (`app/routers/usage.py`)
- `GET /usage/me/summary` : Récupère la synthèse mensuelle (`UserQuotaSummary`), les jauges par action (`ActionQuotaUsage`) et le tier actif.
- `GET /usage/me` : Liste paginée des logs d'utilisation `ApiUsageRecord`.
- `GET /usage/tiers` : Configuration publique des paliers et tarifs.
- `PUT /usage/me/tier` : Changement de palier utilisateur (persistance dans `users.tier`).

### 2.2 Frontend (`/settings/usage`)
- Types TypeScript dans `frontend/src/types/usage.ts`.
- Client `usageApi` dans `frontend/src/lib/api.ts`.
- Page principale `/settings/usage/page.tsx` :
  1. **Header & Tier Actuel** : Badge distinctif (Free, Advanced, Pro), date de cycle, tokens consommés totaux.
  2. **Cartes de Quotas Mensuels** : Jauges visuelles animées avec statut vert/orange/rouge pour les 6 actions (Interview Prep, CV Tailoring, Lettres, Évaluations, Parsing CV, Résumés).
  3. **Grille Tarifaire Interactive** : Sélecteur de formule à 3 colonnes avec comparatif des plafonds et bouton d'upgrade/sélection.
  4. **Journal d'Activité Récent** : Tableau dynamique affichant les derniers appels IA (date, action, modèle, tokens, coût estimé).
- Liens de navigation dans le menu utilisateur du `Header.tsx`.

---

## 3. Stratégie de Tests
1. **Backend Tests** :
   - `test_usage_tier_api.py` : Test de `PUT /usage/me/tier`, vérification du recalcul des limites et de la persistance.
2. **Frontend Build** :
   - `npm run build` propre avec toutes les routes statiques et dynamiques.
