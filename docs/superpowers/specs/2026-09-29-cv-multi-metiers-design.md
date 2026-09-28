# CV adapté multi-métiers : RH, Marketing, métiers opérationnels

Date : 2026-09-29

## Contexte

La généralisation multi-métiers du 2026-09-19
(`2026-09-19-generalisation-multi-metiers-design.md`) a rendu la collecte,
l'évaluation et les catégories de compétences du CV adapté indépendantes du
métier. Le CV adapté garde pourtant des biais tech qui le rendent peu
crédible pour un profil RH, Marketing ou opérationnel (cariste, préparateur
de commandes, agent logistique…) :

- `executive_minimalist.html:201` titre « Compétences Techniques » en dur.
- `tailor_prompt.md` §4 : exemples de métriques « ROI, latence, volume de
  données » et consigne « vocabulaire technique ». §6 impose « 1 à 3 projets »
  même quand le candidat n'en a aucun de pertinent.
- `CandidateProject.context` n'accepte que `perso | client | recherche |
  consortium`. Le champ est saisi en **texte libre** dans l'UI profil et le
  validateur ramène silencieusement toute valeur inconnue à `perso` : un
  projet « associatif » saisi aujourd'hui est enregistré comme perso.
- Le portfolio (`contact.website`) et les centres d'intérêt
  (`profile.interests`) existent dans le profil mais n'atteignent jamais le
  rendu du CV (`routers/resumes.py:217` ne les transmet pas).
- Rien ne guide le parseur de CV pour classer CACES, permis, SST ou
  habilitations dans `certifications`.
- Le profil n'a aucun champ pour la mobilité (« véhiculé ») ni les
  disponibilités horaires (« 2x8, nuit, week-end »), informations attendues
  en tête d'un CV de métier opérationnel en France.

## Objectifs

- Un profil RH, Marketing ou opérationnel obtient un CV adapté dont les
  libellés, les métriques et les sections correspondent à son métier.
- Le métier est **déduit par le LLM** à partir du profil et de l'offre :
  aucun champ « famille métier », aucune branche de code par métier.
- Aucune régression pour les profils tech.

## Non-objectifs

- Nouveaux modèles visuels (« Classique », « Créatif ») : sous-projet B,
  spec séparé après livraison de celui-ci.
- Section « Bénévolat / Engagements » distincte des projets : le bénévolat
  passe par le contexte de projet `associatif`.
- Choix des centres d'intérêt par le LLM selon l'offre : ils sont affichés
  tels que saisis dans le profil.
- Regroupement des missions d'intérim courtes sous une seule entrée :
  demande une évolution du contrôle anti-invention sur les entreprises.
- Évaluation et collecte d'offres pour les métiers opérationnels.
- Aucun changement de `TailoredCVSchema`, aucune migration de base.

## Design

### 1. Textes neutres

**Modèles** (`backend/app/templates/cv/`)
- `executive_minimalist.html` : « Compétences Techniques » → « Compétences ».
- Relecture des deux modèles : tout libellé visible « Technologies » ou
  « Stack » devient « Outils ».

**Prompt** (`backend/app/llm/prompts/cv/tailor_prompt.md`)
- §4 Expériences : « vocabulaire technique » → « vocabulaire métier ».
  Les exemples de résultats quantifiés couvrent plusieurs familles, et le
  LLM retient ceux qui correspondent au métier réel du candidat :
  - tech : latence, volume de données, disponibilité ;
  - RH : délai de recrutement, nombre de recrutements, turnover ;
  - marketing : taux de conversion, audience, coût d'acquisition ;
  - logistique / terrain : cadence (colis ou lignes par heure), taux
    d'erreur, jours sans accident, tonnage.
  Rappel explicite : ne jamais inventer un chiffre absent du profil.
- `relevant_technologies` décrit comme « outils, logiciels, engins ou
  méthodes réellement utilisés ».
- Style : pour un métier opérationnel, phrases simples et concrètes, sans
  jargon de bureau.
- §6 Projets : « 1 à 3 » → « 0 à 3 ; liste vide si aucun projet n'est
  pertinent pour l'offre ».
- §7 Certifications : si l'offre exige une habilitation (CACES, permis,
  SST, habilitation électrique, FIMO/FCO) que le candidat possède, la
  citer dans l'accroche et en tête des certifications.

### 2. Contextes de projet

- `CandidateProject.context` (`models.py:500`) accepte en plus
  `associatif` et `evenement`. Le validateur `normalize_context` mappe les
  synonymes : `associatif`, `association`, `asso`, `bénévolat`,
  `benevolat`, `volunteer` → `associatif` ; `evenement`, `événement`,
  `event`, `salon` → `evenement`. Le repli sur `perso` reste pour les
  valeurs inconnues.
- Mêmes valeurs reportées dans : `cv_parser.py` (description du schéma
  ligne 49, normalisation ligne 139), `profile/collectors/website.py`
  (`_VALID_PROJECT_CONTEXTS` ligne 52, prompt ligne 220),
  `frontend/src/types/coverLetter.ts:22`.
- UI profil (`CandidateProfileSection.tsx`, champ « Contexte ») : le champ
  texte devient un `<select>` à 6 options (Perso, Client, Recherche,
  Consortium, Associatif, Événement).

### 3. Mobilité et disponibilités

Deux clés texte libre ajoutées au dictionnaire `contact` (déjà
`Dict[str, Optional[str]]`, donc sans changement de schéma) :
- `mobility` — ex. « Permis B, véhiculé », « Mobile en Île-de-France » ;
- `availability` — ex. « Disponible immédiatement · 2x8, nuit, week-end ».

- **UI profil** : deux champs dans le bloc coordonnées, à côté de
  téléphone et site web. Ils sont chargés depuis `data.contact` et
  **inclus dans l'objet `contact` envoyé à la sauvegarde** (ligne ~380),
  sinon la sauvegarde les effacerait.
- **Parseur de CV** : le schéma de sortie gagne
  `"contact": {"mobility": "...", "availability": "..."}`, renseigné
  seulement si le CV le mentionne. `merge.py:526` fusionne déjà
  `src_payload["contact"]`, rien à changer côté fusion.

### 4. Habilitations dans le parseur

Consigne ajoutée au prompt de `cv_parser.py` : CACES (avec les
catégories, ex. « CACES R489 cat. 1, 3, 5 »), permis de conduire (B, C,
CE…), SST, habilitations électriques, FIMO/FCO et autres titres
réglementaires vont dans `certifications`, pas dans `skills`.

### 5. Rendu du CV

**Données** — `routers/resumes.py` : la construction du dictionnaire
`candidate` (aujourd'hui en ligne dans la route, ligne 217) est extraite
dans une fonction pure `_build_candidate(profile_doc, user)` pour être
testable, puis enrichie :
- `website_url` : `contact.website`, mis à `None` s'il est identique à
  `github_url` (évite le doublon, cas du profil actuel) ;
- `mobility`, `availability` : depuis `contact` ;
- `interests` : `profile_doc.get("interests") or []`.

Lus au moment du rendu, comme les coordonnées actuelles : les CV déjà
générés en profitent à leur prochain affichage.

**Modèles** — les deux modèles :
- lien 🌐 portfolio si `website_url` ;
- ligne sous le nom et le titre avec `mobility` et `availability`,
  séparés par « · », si au moins un est renseigné ;
- section « Centres d'intérêt » si `interests` n'est pas vide
  (Sidebar Elegance : colonne latérale, en dernier ; Executive Minimalist :
  après Langues) ;
- `Certifications` devient « Certifications & habilitations » et remonte
  juste après les compétences. Sidebar Elegance : Compétences Clés →
  Certifications & habilitations → Langues → Formation. Executive
  Minimalist : la section « Langues & Certifications » est scindée ; la
  nouvelle section « Certifications & habilitations » suit « Compétences »,
  « Langues » reste en fin.

Ce réordonnancement s'applique aussi aux CV tech : la section y est courte,
l'impact est jugé acceptable.

## Tests

- `tests/test_cv_templates.py`, pour chacun des deux modèles :
  - « Compétences Techniques » absent du HTML ;
  - « Centres d'intérêt » présent si `interests` non vide, absent sinon ;
  - lien portfolio affiché ; absent quand `website_url` vaut `None` ;
  - ligne mobilité / disponibilités présente si l'un des deux est
    renseigné, absente sinon ;
  - « Certifications & habilitations » précède « Formation ».
- Test de la construction de `candidate` : `website_url` à `None` quand il
  est identique au GitHub.
- Tests de `CandidateProject.normalize_context` : nouvelles valeurs,
  synonymes, repli `perso` inchangé.
- Tests de normalisation du contexte dans `cv_parser.py` et `website.py`.
- Frontend : `tsc --noEmit` et lint sur les fichiers touchés.
- Validation manuelle : génération d'un CV adapté pour un profil
  préparateur de commandes (CACES, permis B, aucun projet) sur une offre
  logistique, et pour un profil tech existant (non-régression).

## Risques

- Le prompt est une consigne, pas une garantie : le LLM peut encore
  produire une métrique inadaptée. Le contrôle anti-invention
  (`verify_cv_honesty`) reste le filet contre les faits inventés, pas
  contre le mauvais vocabulaire. Mitigation : validation manuelle sur les
  deux profils de référence ci-dessus.
- Liste vide de projets : les deux modèles masquent déjà la section
  (`{% if cv.featured_projects %}`), à confirmer par test.
