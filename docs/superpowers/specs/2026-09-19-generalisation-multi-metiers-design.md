# Généralisation multi-métiers de l'application

Date : 2026-09-19

## Contexte

L'application (MonSuiviJob / Career-Ops) est un produit multi-utilisateurs : chaque
compte a son propre profil, ses propres préférences de ciblage (`target_roles`,
`locations`, etc.) et cherche des offres qui lui correspondent. En pratique
aujourd'hui, elle ne fonctionne correctement que pour des profils tech/data/IA.

Symptôme constaté : un profil "animatrice" reçoit une offre "Data Scientist /
Machine Learning Engineer" évaluée à **4.0/5.0 "Excellent Match"**, alors qu'elle
n'a aucune pertinence.

Deux causes racines distinctes, indépendantes l'une de l'autre :

1. **Collecte** : `backend/app/tasks/job_offers_collectors.py::build_search_queries()`
   génère déjà des requêtes de recherche dynamiques par profil (rôles ciblés +
   localisations, round-robin, fallback `DEFAULT_QUERIES` seulement si aucun
   profil actif n'a de `target_roles`). Donc la collecte est déjà personnalisable.
   Mais `backend/app/services/relevance.py` applique ensuite un filtre global
   (`is_relevant_position`, `is_off_domain_url`) avec une allowlist de mots-clés
   data/IA codée en dur, appelé à deux endroits de
   `job_offers_collectors.py` (`get_urls_for_query` et `enrich_offers`). Ce
   filtre rejette silencieusement toute offre hors data/IA avant même
   l'enregistrement en base — y compris une offre trouvée par une requête
   générée spécifiquement pour un profil animation.

2. **Évaluation** : `backend/app/services/evaluation/evaluator.py` (Two-Pass)
   ne vérifie la cohérence entre le métier de l'offre et le métier du candidat
   nulle part. Le Bloc A ne couvre que geo-mismatch et visa. Le Bloc B matche
   exigence par exigence (diplôme, compétences, langues) sans jamais vérifier
   que le métier global correspond. Un recoupement partiel sur des critères
   génériques (langue parlée, soft-skill) suffit à produire un score élevé même
   sur une offre totalement hors-domaine.

À cela s'ajoutent des couplages tech plus superficiels (wording de prompts,
libellés UI, valeurs par défaut) qui n'empêchent rien fonctionnellement mais
nuisent à l'expérience d'un profil non-tech et doivent être nettoyés pour une
généralisation cohérente de bout en bout.

## Objectifs

- N'importe quel profil (dev, animatrice, tout autre métier) doit pouvoir
  charger un CV, se voir extraire un profil structuré pertinent, éditer ce
  profil, et recevoir des offres réellement collectées et évaluées pour son
  domaine.
- La collecte et l'évaluation restent mutualisées entre tous les
  utilisateurs (une seule base d'offres partagée) — pas de sandboxing par
  utilisateur.
- Aucune régression pour les profils tech existants.

## Non-objectifs (hors scope)

- Pas de migration de renommage de champ en base (`stack` reste `stack` en
  base de données) — uniquement du relabelling côté UI/prompts.
- Pas de nouveaux connecteurs d'import de profil (Behance, ArtStation, etc.) —
  seulement remettre le connecteur générique "Website" au même niveau que
  GitHub dans l'UI existante.
- Pas de refonte de l'internationalisation / multi-langue de l'UI.
- Pas de changement du modèle de données `CandidatePreferences` /
  `CandidateProfile` (déjà génériques, confirmés par l'exploration).

## Design par phase

### Phase 1 — Collecte d'offres

Supprimer le fichier `backend/app/services/relevance.py` dans son intégralité
(`RELEVANCE_KEYWORDS`, `OFF_DOMAIN_URL_SLUGS`, `is_relevant_position`,
`is_off_domain_url`, `RELEVANCE_FILTER_ENABLED`) ainsi que ses deux points
d'appel dans `job_offers_collectors.py` :
- dans `get_urls_for_query` (le bloc `if RELEVANCE_FILTER_ENABLED: ...` qui
  filtre les URLs hors-domaine)
- dans `enrich_offers` (le `if RELEVANCE_FILTER_ENABLED and not
  is_relevant_position(poste): continue`)

`DEFAULT_QUERIES` reste tel quel comme filet de sécurité (cas où aucun profil
actif n'a de `target_roles` renseigné) — son biais tech dans ce cas limite est
accepté, ne pas sur-ingénierer un fallback générique pour un cas qui ne
devrait pas se produire en usage normal.

Le fichier de test `backend/tests/test_relevance.py` est supprimé avec le
module qu'il teste.

Le rejet des offres invalides (poste/entreprise vides ou placeholders,
`enrich_offers` lignes ~296-307) reste en place — c'est un garde-fou qualité,
pas un garde-fou de domaine, il n'est pas concerné par ce changement.

### Phase 2 — Cohérence métier dans l'évaluateur

Deux mécanismes complémentaires, dans `backend/app/services/evaluation/evaluator.py` :

1. **Pré-filtre embedding (avant le Two-Pass complet)** : réutiliser
   l'infrastructure d'embeddings déjà en place dans
   `backend/app/services/role_normalizer.py` pour comparer le
   `canonical_title` de l'offre aux `target_roles`/`headline` du candidat.
   Sous un seuil de similarité (à calibrer, départ conservateur), l'offre est
   marquée directement comme hors périmètre avec un score plancher, sans
   déclencher l'appel LLM Two-Pass complet — ce qui généralise le matching
   *et* réduit le coût sur des offres manifestement non pertinentes.
2. **Garde-fou explicite dans le prompt (filet de sécurité pour les cas
   ambigus)** : ajouter un champ `domain_coherence: "match" | "partial" |
   "mismatch"` à la sortie JSON du Pass 2, avec instruction de comparer le
   métier réel de l'offre au métier réel du candidat (pas seulement les
   compétences isolées). Si `mismatch`, le score final est plafonné bas
   indépendamment des `matched_requirements`.

Neutraliser également le wording biaisé du prompt Pass 2 :
- retirer "technique" de "analyste expert en recrutement technique"
- retirer la mention GitHub-only ("projets concrets/GitHub" → "projets
  concrets/réalisations")
- généraliser la RÈGLE DIPLÔME : au lieu de limiter le full-match automatique
  aux disciplines "informatique, IA, data ou mathématiques appliquées",
  comparer le diplôme du candidat au domaine réellement demandé par l'offre.

### Phase 3 — Profil / merge

Dans `backend/app/services/profile/merge.py` :
- Retirer le fallback de headline codé en dur `"Ingénieur Data & IA"` →
  remplacer par un fallback neutre dérivé du dernier intitulé de poste réel du
  candidat, ou une chaîne vide si aucune expérience n'est disponible.
- Retirer l'heuristique qui ajoute "& AI Specialist" quand des mots-clés IA
  sont détectés dans les compétences.

Pas de renommage du champ `stack` en base (voir Non-objectifs).

### Phase 4 — Frontend : labels et copie

Fichiers concernés : `CandidateProfileSection.tsx`, `CvDropzone.tsx`,
`onboarding/page.tsx`. (`TargetingPreferencesSection.tsx` est déjà générique,
non touché.)

- Renommer les libellés visibles "Stack technique" / "Technologies / Stack" →
  "Outils & compétences" (le champ de données sous-jacent reste `stack`,
  seul le libellé affiché change).
- Neutraliser les placeholders actuellement 100% tech (ex: `"Python, Spark,
  Airflow, Azure"`, `"Senior Data Engineer"`) → exemples neutres ou
  multi-domaines.
- Neutraliser la copie de `CvDropzone.tsx` et de l'onboarding ("stacks
  techniques", "réalisations techniques réelles" → "outils et compétences",
  "réalisations concrètes").
- Mettre le connecteur générique "Website" visuellement au même niveau que le
  connecteur GitHub dans l'onboarding (les deux existent déjà, pas de nouveau
  code de connecteur).

### Phase 5 — CV adapté (tailored CV)

Dans `backend/app/llm/prompts/cv/tailor_prompt.md` ligne 47 : les exemples de
catégories de compétences ("Backend & Microservices", "Cloud & DevOps", "Data
& IA", "Frontend & UI") biaisent le LLM vers des catégories tech même quand le
candidat ne l'est pas. Remplacer par la même consigne déjà utilisée avec
succès dans `cv_parser.py` : catégories dynamiques dérivées du profil réel du
candidat, sans catégorie Data/IA imposée si le candidat exerce un autre
métier.

`frontend/src/types/resume.ts` (`technologies` / `relevant_technologies`) :
les noms de champs TypeScript ne sont pas renommés (changement cosmétique
interne à risque disproportionné pour le bénéfice). Si l'UI qui consomme ces
champs (`ResumePreviewModal.tsx`, `ResumeCard.tsx`) affiche littéralement le
mot "technologies" à l'utilisateur, le libellé affiché sera généralisé au
moment de l'implémentation — à vérifier alors, pas de changement de schéma
prévu a priori.

## Plan de test / validation

- **Scénario bout-en-bout profil animatrice** : profil avec
  `target_roles=["Animatrice 2D"]` → `build_search_queries` génère la requête
  → collecte sans `relevance.py` → offre animation visible en base →
  évaluation avec pré-filtre embedding → score cohérent avec le domaine (plus
  de score "Excellent" sur une offre Data Scientist).
- **Non-régression profil tech existant** : un profil dev avec ses
  `target_roles` habituels continue à matcher normalement — le seuil du
  pré-filtre embedding doit être calibré sur des paires rôle/offre connues
  pour éviter les faux négatifs (offre pertinente écartée à tort).
- Tests unitaires existants qui dépendent de `relevance.py` sont supprimés
  avec le module ; ajouter des tests pour le pré-filtre embedding et le champ
  `domain_coherence`.

## Risques

- Supprimer `relevance.py` peut laisser passer un peu plus de bruit web
  (pages non-emploi mal extraites) que le filtre bloquait accessoirement. La
  validation stricte poste/entreprise déjà présente dans `enrich_offers`
  (rejet des placeholders/valeurs vides) doit suffire à absorber ce bruit ;
  à surveiller après déploiement.
- Seuil du pré-filtre embedding mal calibré → faux négatifs. Mitigation :
  seuil de départ conservateur (biaisé vers laisser passer plutôt que
  rejeter) + logging des offres écartées par le pré-filtre pour audit manuel
  ultérieur.
