---
target: frontend/src/app/profile/page.tsx
total_score: 18
max_score: 40
na_heuristics: 0
p0_count: 1
p1_count: 2
target_identity: "file:/Users/elielkatche/job-tracker/frontend/src/app/profile/page.tsx"
target_fingerprint: "sha256:6b338845713307925328880ef9380c0ef438221aea99978879605a673846ec8a"
target_path: /Users/elielkatche/job-tracker/frontend/src/app/profile/page.tsx
timestamp: 2026-10-03T09-14-46Z
slug: frontend-src-app-profile-page-tsx
---
Method: dual-agent (A: a079b39b171e37179 · B: a892f14d98346cc35)

## Design Health Score

| # | Heuristique | Score | Point clé |
|---|-----------|-------|-----------|
| 1 | Visibilité du statut système | 2/4 | Badge "CV IA Actif"/"En attente de CV" clair, mais aucun indicateur pendant l'écrasement d'un CV existant |
| 2 | Correspondance système/monde réel | 3/4 | Vocabulaire RH correct (expériences, Voice DNA, préférences de ciblage) |
| 3 | Contrôle et liberté utilisateur | 1/4 | Ré-import de CV remplace tout le profil sans confirmation ni aperçu des changements |
| 4 | Cohérence et standards | 1/4 | Deux paradigmes d'édition coexistent sur la même page (bascule globale vs édition inline toujours visible) |
| 5 | Prévention des erreurs | 1/4 | Aucun garde-fou avant une action destructive (écrasement de profil par import CV) |
| 6 | Reconnaissance plutôt que rappel | 1/4 | ~167 champs mesurés sans divulgation progressive, tout exposé en une seule vue |
| 7 | Flexibilité et efficacité | 2/4 | Import CV rapide pour démarrer, mais aucun raccourci pour corriger seulement un champ erroné après import |
| 8 | Esthétique et minimalisme | 1/4 | Densité maximale mesurée en direct (ex. 33 boutons sur le seul onglet Ciblage) |
| 9 | Diagnostic/récupération d'erreurs | 2/4 | Messages d'erreur d'upload clairs (type de fichier, taille) mais rien sur les données corrompues après import |
| 10 | Aide et documentation | 2/4 | Page Guide/FAQ existe pour Voice DNA, mais rien de contextuel sur place |
| **Total** | | **18/40** | **Faible — le plus bas des 3 zones** |

## Design Specificity Verdict

**LLM**: Le vocabulaire (Voice DNA, préférences de ciblage, archétype) montre une vraie identité produit pensée pour la recherche d'emploi augmentée par IA — mais la page profil traite "tout afficher" comme la seule stratégie de densité, ce qui est l'anti-pattern générique par excès plutôt qu'une absence d'identité.

**Scan déterministe**: 3 findings sur `CandidateProfileSection.tsx`, tous la même règle (soulignement d'onglet actif mal interprété comme un conflit de style) — faux positifs confirmés, aucun defect structurel détecté par le scan. Le vrai problème de cette zone (densité, paradigmes d'édition incohérents) n'est pas du type que le scan déterministe sait repérer.

**Overlay navigateur**: injection échouée (même blocage mixed-content que les deux autres zones), aucun overlay visible dans le navigateur de l'utilisateur. À la place, mesure directe du DOM en direct (`evaluate_script`) : `main.scrollHeight` entre 3× et 4,6× la hauteur de viewport, 33 boutons + 5 champs + 3 selects visibles sur le seul onglet "Ciblage" — chiffres indépendants qui confirment, par une méthode différente, le même constat de surcharge que l'estimation de ~167 champs sur l'onglet "Profil candidat/Expériences".

## Overall Impression

C'est la zone la plus en difficulté des trois : la charge cognitive est au maximum mesuré (8 heuristiques sur 8 en échec sur le critère de densité), deux systèmes d'édition différents coexistent sans raison apparente, et une action à fort impact (remplacer tout son profil par un nouveau CV) ne demande aucune confirmation. Le produit a du bon contenu (Voice DNA, ciblage) mais le présente tout en même temps, sans hiérarchie de divulgation.

## What's Working

1. **Import CV avec retour chiffré** — "X expérience(s) et Y compétence(s) extraites" (`CvDropzone.tsx:62-64`) donne un signal de succès concret, pas un vague "C'est fait !".
2. **Badge d'état CV** — "CV IA Actif" / "En attente de CV" (`CvDropzone.tsx:124-132`) rend l'état du profil lisible en un coup d'œil.
3. **Voice DNA comme concept produit** — extraits d'écriture réelle pour calibrer le style des lettres générées : une vraie différenciation, pas un champ de formulaire générique.

## Priority Issues

**[P0] Ré-import de CV écrase tout le profil sans confirmation ni aperçu**
Pourquoi: `CvDropzone.handleFile` (:31-81) appelle `coverLetterApi.importCv(file)` puis `onProfileUpdated(updatedProfile)` immédiatement, dès qu'un fichier est déposé ou sélectionné — aucun `confirm()`, aucun diff avant/après. La prop `hasCvSource` (:17, :22) ne sert qu'à changer le texte du bouton ("Mettre à jour le CV" vs "Sélectionner un fichier", :148) et le badge (:124-132), jamais à avertir d'un remplacement. Sur un formulaire mesuré à ~167 champs modifiables manuellement, un nouvel import peut silencieusement effacer des corrections déjà faites à la main.
Fix: avant d'appeler `importCv`, afficher un récapitulatif "Ceci remplacera N expériences et M compétences existantes" avec confirmation explicite ; idéalement proposer une fusion plutôt qu'un remplacement total.
Commande: **harden**

**[P1] Données corrompues issues de l'import IA, visibles sans détection ni correction guidée**
Pourquoi: inspection live du compte de test — liens cassés et une certification dupliquée dans les données importées automatiquement par l'IA depuis le CV. Rien dans l'interface ne signale une entrée suspecte (lien mort, doublon) après import ; l'utilisateur doit repérer et corriger manuellement dans un formulaire déjà dense.
Fix: valider les URLs extraites (format + accessibilité) et dédoublonner les entrées structurées (certifications, formations) juste après l'import, avec un badge "à vérifier" sur les entrées suspectes.
Commande: **harden**

**[P1] Deux paradigmes d'édition coexistent sur la même page**
Pourquoi: `isEditing` (:76) bascule l'intégralité du formulaire entre vue lecture et vue édition via le bouton "Modifier manuellement" (:495-499, :518) ; `isEditingStyle` (:83) est un second état totalement indépendant, pour la seule section Voice DNA, explicitement commentée "always visible inline editor" (:539) — elle reste éditable inline que `isEditing` soit actif ou non. Un utilisateur qui a compris le fonctionnement "Modifier puis Enregistrer" pour le reste du profil retrouve un comportement différent, sans transition visuelle, pour cette seule section.
Fix: aligner Voice DNA sur le même mécanisme d'édition que le reste du formulaire, ou si l'édition toujours disponible est un choix délibéré (contenu moins structuré), le signaler visuellement (ex. bordure distincte permanente) plutôt que de le laisser se découvrir par l'usage.
Commande: **clarify**

**[P2] Densité maximale sans divulgation progressive**
Pourquoi: mesure live confirmée indépendamment par les deux canaux — ~167 champs sur l'onglet profil candidat (estimation par lecture), 33 boutons + 5 champs + 3 selects sur le seul onglet Ciblage, hauteur de page 3× à 4,6× la hauteur d'écran (mesure DOM). Tout est visible et modifiable en permanence, sans sections repliables ni progression par étapes.
Fix: regrouper en sous-sections repliables (Expériences / Formation / Compétences / Ciblage), n'ouvrir que la section pertinente par défaut.
Commande: **distill**

## Persona Red Flags

**Riley (stress testeur)**: Dépose un nouveau CV par erreur ou pour tester → profil entier remplacé en un clic, aucune façon de revenir en arrière ni de voir ce qui a changé avant que ce soit fait.

**Jordan (débutant confus)**: Face à ~167 champs sur un seul onglet, ne sait pas par où commencer ni ce qui est obligatoire. Découvre que "Voice DNA" s'édite différemment du reste seulement en cliquant dessus par hasard.

**Sam (utilisateur avancé pressé)**: Veut juste corriger une certification dupliquée après un import CV — doit la retrouver au milieu d'un formulaire dense, sans signal qui la distingue comme suspecte.

## Minor Observations

- Guide/FAQ (`frontend/src/app/guide/page.tsx:253-262`) documente bien le concept Voice DNA — contenu correct, simplement absent du profil lui-même au moment où ça compterait.
- Messages d'erreur d'upload (type de fichier, taille max 10 Mo, `CvDropzone.tsx:34-42`) sont clairs et actionnables — à répliquer sur les autres formulaires de la page.

## Questions to Consider

- Un ré-import de CV doit-il remplacer le profil entièrement, ou fusionner avec ce qui existe déjà en laissant l'utilisateur arbitrer les conflits ?
- Voice DNA doit-il rester éditable en permanence (contenu qui se peaufine au fil du temps) ou rejoindre le même mode d'édition que le reste du profil ?
- La page profil doit-elle rester un formulaire unique à défilement, ou passer à des sous-sections repliables / un flux en étapes ?
