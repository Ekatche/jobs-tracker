---
title: Rechargement automatique et visibilité immédiate du CV après génération sur la page /resumes
status: done
---

## User intent
Lorsque l'utilisateur génère un CV adapté depuis la modale ou via un lien direct d'offre (`/resumes?generate_offer_id=...`), la liste des CVs sur la page `/resumes` doit se recharger automatiquement depuis le serveur pour que le nouveau CV apparaisse immédiatement visible dans la grille, sans nécessiter de rafraîchissement manuel du navigateur.

## Surgical Scope
- `frontend/src/app/resumes/page.tsx`:
  - Dans `handleGenerateSubmit`, déclenchement de `await fetchResumes()` dès la confirmation de génération.
  - Réinitialisation des filtres `searchQuery` ("") et `templateFilter` ("all") pour garantir que le CV nouvellement généré ne soit pas masqué par d'anciens filtres.
  - Dans `handleRegenerateResume`, synchronisation immédiate via `await fetchResumes()`.
  - Sécurisation du filtrage dans `filteredResumes` (`(r.target_role || "")`, `(r.target_company || "")`) contre d'éventuelles valeurs nulles/indéfinies.

## Steps
- [x] 1. Mettre à jour `handleGenerateSubmit` et `handleRegenerateResume` dans `frontend/src/app/resumes/page.tsx`.
- [x] 2. Sécuriser `filteredResumes` contre les valeurs nulles.
- [x] 3. Valider la compilation TypeScript avec `npx tsc --noEmit`.
- [x] 4. Vérifier le comportement et clôturer le plan micro-dev.

## Definition of Done
- [x] Après génération d'un CV, `fetchResumes` est exécuté et la liste serveur est rafraîchie.
- [x] Les filtres sont réinitialisés pour positionner le nouveau CV en haut de la grille.
- [x] `npx tsc --noEmit` passe sans aucune erreur.

## Code Review
- **Synchronisation Serveur:** `fetchResumes()` garantit que les données affichées dans la grille proviennent directement de la base MongoDB sans divergence de state.
- **Filtres & Ergonomie:** La remise à zéro des filtres à la génération évite l'effet "CV introuvable" si une recherche textuelle était active.
- **Robustesse:** Protection contre les `TypeError` si un rôle ou une entreprise est absent dans un document de CV ancien ou partiel.
- Verdict: ✅ DONE

## Execution Log
- 20:39 : Initialisation du plan micro-dev et journal quotidien.
- 20:39 : Modification de `frontend/src/app/resumes/page.tsx` (`fetchResumes`, reset filtres, sécurisation search).
- 20:40 : Validation TypeScript (`npx tsc --noEmit` sans erreur).
