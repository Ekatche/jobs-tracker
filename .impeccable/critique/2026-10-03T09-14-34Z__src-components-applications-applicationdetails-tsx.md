---
target: src/components/applications/ApplicationDetails.tsx
total_score: 23
max_score: 40
na_heuristics: 0
p0_count: 1
p1_count: 2
target_identity: "file:/Users/elielkatche/job-tracker/src/components/applications/ApplicationDetails.tsx"
timestamp: 2026-10-03T09-14-34Z
slug: src-components-applications-applicationdetails-tsx
---
Method: dual-agent (A: ab4e8ced1481f9af0 · B: a682e27e596faaf31)

## Design Health Score

| # | Heuristique | Score | Point clé |
|---|-----------|-------|-----------|
| 1 | Visibilité du statut système | 2/4 | Changement d'état (offre liée) après scoring IA invisible hors couleur du bouton Enregistrer |
| 2 | Correspondance système/monde réel | 4/4 | Vocabulaire métier précis et calibré (Écart significatif, Relance due) |
| 3 | Contrôle et liberté utilisateur | 3/4 | `confirm()` navigateur natif non stylé pour les modifs non enregistrées |
| 4 | Cohérence et standards | 1/4 | Boutons dupliqués, dialog natif au milieu d'une UI custom |
| 5 | Prévention des erreurs | 1/4 | Scoring IA note avec pleine confiance une URL factice, sans garde-fou |
| 6 | Reconnaissance plutôt que rappel | 3/4 | Labels de section clairs ; 3 premiers champs sans label visible une fois remplis |
| 7 | Flexibilité et efficacité | 3/4 | Édition inline efficace, pas de raccourcis au-delà d'Échap |
| 8 | Esthétique et minimalisme | 2/4 | Jusqu'à 5 chips d'action qui wrap sur 2 lignes |
| 9 | Diagnostic/récupération d'erreurs | 2/4 | Bannière d'erreur stylée pour le scoring, mais "Régénérer par IA" avale ses erreurs en silence |
| 10 | Aide et documentation | 2/4 | Rien de contextuel sur le "Two-Pass" ou les bornes de score |
| **Total** | | **23/40** | **Acceptable** |

## Design Specificity Verdict

**LLM**: Vocabulaire et scoring métier (matched/missing requirements, red flags) montrent une vraie pensée produit pour la recherche d'emploi — mais l'architecture d'interaction (formulaire unique à défilement) est interchangeable avec n'importe quel panneau CRM, et la fonctionnalité la plus "produit" (accès à l'offre) est verrouillée derrière une fonctionnalité annexe (le scoring).

**Scan déterministe**: 0 finding sur les 5 fichiers (ApplicationDetails.tsx, ApplicationCard.tsx, KanbanColumn.tsx, KanbanBoard.tsx, pipeline/page.tsx) — confirmé non cassé (l'outil remonte des findings ailleurs dans le repo). Les problèmes de cette zone sont d'ordre interaction/logique, pas des anti-patterns visuels détectables mécaniquement — le détecteur ne s'applique simplement pas ici, pas de désaccord.

**Overlay navigateur**: injection échouée (mixed content HTTP→HTTPS, requête `detect.js` restée `pending`), pas d'overlay visible dans un onglet. Inspection manuelle confirmée à la place : fiche candidature ouverte en live, scoring IA réellement déclenché sur une URL factice.

**Note repo**: KanbanBoard.tsx/KanbanColumn.tsx/ApplicationCard.tsx ne correspondent plus au rendu réel de `/applications` (vue groupée en 6 colonnes avec boutons rapides absents de ces fichiers) — fichiers probablement obsolètes, à vérifier côté hygiène de repo.

## Overall Impression

Le vocabulaire est juste, mais la fiche confond "fonctionnalité annexe" (scoring IA) et "prérequis d'accès" (voir l'offre) — un verrouillage non intentionnel qui casse le parcours principal. Combiné à des boutons dupliqués et une charge cognitive critique, l'ensemble se lit comme assemblé fonctionnalité-par-fonctionnalité plutôt que pensé de bout en bout.

## What's Working

1. **Vocabulaire et scoring métier** — matched/missing requirements, red flags, directement adressés à l'anxiété réelle de la recherche d'emploi.
2. **Édition inline sans mode dédié** — cliquer un champ et taper directement, sans bouton "Modifier" préalable.
3. **Typographie de section cohérente** — micro-labels uppercase systématiques, rythme lisible sur un panneau dense.

## Priority Issues

**[P0] Accès à l'offre verrouillé derrière le scoring IA, avec risque de perte de lien silencieuse**
Pourquoi: `ApplicationDetails.tsx:333` n'affiche "Offre scrapée"/"CV Adapté" que si `application.offer_id || evaluation?.offer_id` existe ; `evaluation` démarre `null`. Confirmé en live : candidature neuve avec URL → aucun accès à `/offers/*` avant de cliquer "Lancer le scoring IA". Ce clic lie silencieusement `offer_id` (:183-185) et passe `hasUnsavedChanges=true` sans bannière visible — seul un `confirm()` natif au moment de fermer protège ce lien.
Fix: découpler la création/consultation de l'Offre du scoring (réutiliser la plomberie de "Régénérer par IA" qui sait déjà fetcher le contenu à l'URL, :567-578) ; remplacer le signal de sauvegarde en attente par une bannière visible.
Commande: **clarify**

**[P1] Boutons dupliqués — même destination, styles différents (confirme le signalement utilisateur)**
Pourquoi: "Voir annonce" (:321-331) et "Ouvrir le lien" (:545-555) pointent vers le même href externe. "Offre scrapée" (:335-341) et "Analyse complète" (:475-481) pointent vers exactement la même URL `/offers/{id}`. Jusqu'à 3 liens visibles simultanément vers "voir le poste" une fois scoré.
Fix: un seul contrôle par destination — lien URL brute au niveau du champ "Lien vers l'annonce", un seul accès à l'Offre interne dans la carte scoring.
Commande: **distill**

**[P1] Scoring IA note avec pleine confiance un contenu non vérifiable**
Pourquoi: testé en live avec une URL factice (example.com) → "2.5/5.0, Écart significatif, 1 red flag" rendu sans aucun avertissement sur la fiabilité de l'extraction. Un score faux mais visuellement autoritaire peut faire abandonner ou poursuivre une piste pour de mauvaises raisons.
Fix: détecter un scrape vide/suspect, refuser de scorer ou badger "contenu non vérifié / score peu fiable".
Commande: **harden**

**[P2] Surcharge de la rangée de chips d'en-tête, hiérarchie de poids incohérente**
Pourquoi: jusqu'à 5 chips/liens dans la même rangée sans priorité ; "CV Adapté" (:342-351, fond indigo plein) a le même poids visuel que le vrai CTA primaire "Enregistrer".
Fix: repasser "CV Adapté" en style outline, plafonner la rangée à ≤4 éléments.
Commande: **quieter**

**[P3] Boutons Archiver/Supprimer icône-seule sur mobile**
Pourquoi: `hidden sm:inline` (:757-759, :768-770) fait disparaître le libellé sous ~640px — action destructive réduite à une icône sans hover tactile.
Fix: garder un libellé visible à tous les breakpoints au moins pour "Supprimer".
Commande: **harden**

## Persona Red Flags

**Riley (stress testeur)**: URL factice au scoring → score "2.5/5.0" rendu avec pleine autorité, zéro garde-fou. Fermer le tiroir après scoring déclenche un `confirm()` natif qui casse le chrome custom. Le scoring flip silencieusement `hasUnsavedChanges` sans trace lisible de pourquoi Enregistrer est actif.

**Jordan (débutant confus)**: Trois liens bleus différents peuvent tous se lire "voir le poste", seule la forme d'icône les distingue. Avant tout scoring, aucun chemin vers l'offre n'existe — doit découvrir que "Lancer le scoring IA" est en fait le prérequis caché. Nom de modèle interne ("Gemini 3.7 Flash") exposé sans explication.

**Casey (mobile distrait)**: "Archiver"/"Supprimer" perdent leur libellé à 390px. La rangée de chips passe sur 2 lignes une fois scorée, repoussant la carte de score plus bas.

## Minor Observations

- `pipeline/page.tsx` ne fait qu'une redirection vers `/applications` (5 lignes) — le kanban n'est plus hébergé à `/pipeline`.
- "Régénérer par IA" (description) avale ses erreurs en silence (:162-167, `console.error` seul, aucune bannière contrairement au scoring).
- Fichiers Kanban fournis désynchronisés du rendu live réel de `/applications` — hygiène de repo à vérifier, hors scope strict.

## Questions to Consider

- Si "Offre scrapée" et "Analyse complète" pointent vers exactement la même URL, doublon accidentel ou intention perdue en route ?
- "Lancer le scoring IA" doit-il vraiment noter ET lier silencieusement une offre en un seul clic, ou ces deux effets devraient-ils être séparés et visibles ?
- "Régénérer par IA" sait déjà fetcher le contenu à l'URL collée — qu'est-ce qui empêche de créer la fiche Offre dès cette étape, avant même de payer un scoring ?
