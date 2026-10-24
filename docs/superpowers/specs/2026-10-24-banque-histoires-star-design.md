# Banque d'histoires STAR+R commune à toutes les offres — Design

**Date** : 2026-10-24
**Statut** : proposé

## Contexte

Le kit de préparation d'entretien est un onglet de la page d'une offre
(`frontend/src/app/offers/[id]/page.tsx`, composant `InterviewPrepTab`). Pour
chaque offre, `generate_star_stories` (`backend/app/services/interview_prep_service.py`)
fait écrire par l'IA 3 à 5 histoires STAR+R à partir du profil. Elles sont
stockées dans le kit lui-même, `interview_preps.stories` (modèle `StarRStory`
dans `backend/app/models.py`).

Conséquences actuelles :
- Une même expérience vécue est réécrite à chaque offre, parfois avec des
  chiffres différents d'un kit à l'autre.
- Quand le candidat corrige un chiffre dans un kit, la correction reste dans ce
  kit. Les autres kits et les kits suivants gardent l'erreur.
- Chaque kit paie la rédaction complète de 3 à 5 histoires, même quand les
  mêmes histoires existent déjà ailleurs.

Liens existants à préserver :
- `AnticipatedQuestion.mapped_story_id` relie une question anticipée à une
  histoire.
- `PracticeAttempt.question_id` relie un essai d'entraînement à une question.
  `evaluate_practice_answer` lit l'histoire liée pour noter la réponse.
- `export_interview_prep_markdown` exporte les histoires du kit.

Ce travail est la « piste 2 » du kit d'entretien. La préparation par
entretien successif (RH, manager, technique) viendra après et s'appuiera
sur cette banque. Elle est hors du périmètre de ce document.

## Intention

Le candidat veut **une seule version de ses histoires**. Il les enrichit au fil
des offres, et chaque kit puise dedans au lieu de tout réécrire.

Le partage entre la banque et le kit est confirmé par le candidat :
- **Les faits vivent dans la banque et suivent partout** : chiffres,
  contexte, ce que le candidat a fait lui-même.
- **Le récit reste propre à chaque offre** : l'exigence visée, ce qu'on met
  en avant, le vocabulaire.

## Objectifs

1. **Une banque d'histoires par utilisateur**, indépendante des offres.
2. **Une correction de fait faite dans un kit apparaît dans tous les kits** qui
   utilisent cette histoire, y compris ceux déjà générés, sans relancer de
   génération payante. Les kits référencent donc les faits de la banque, ils
   ne les recopient pas.
3. **Remplissage initial à partir des histoires des kits existants.**
4. **Doublons tranchés une fois.** Quand deux kits racontent la même
   expérience avec des chiffres différents, le candidat voit les deux
   versions côte à côte et choisit.
5. **Une nouvelle offre puise d'abord dans la banque.** Le kit affiche un
   tableau « exigence de l'offre → histoire de la banque → adéquation (forte,
   partielle ou manque) ». L'IA n'écrit une nouvelle histoire que pour un
   manque, et cette histoire entre dans la banque.
6. **Le kit ne garde que l'angle propre à l'offre** : exigence visée, ce
   qu'on met en avant, adéquation.

## Interface (validée sur maquettes le 2026-10-24)

Maquette de référence : `2026-10-24-banque-histoires-star-maquette.html`, à
côté de ce document. C'est un fragment HTML du compagnon de brainstorming, et
ses classes de cadre (`mockup`, `section`) ne sont pas stylées hors de ce
contexte. Le texte ci-dessous fait foi.

- **Aucune nouvelle entrée dans le menu principal.** Une page « Mes
  histoires » a été proposée puis écartée par le candidat. On pourra
  l'ajouter plus tard si elle manque.
- **La section Histoires du kit** devient le tableau « Ce que l'offre demande
  / Ton histoire / Adéquation ». Une ligne en « manque » propose « Écrire
  avec l'IA ».
- **Sous le tableau**, l'histoire sélectionnée montre son angle pour cette
  offre et ses faits.
  - Le bouton « Modifier » des faits porte la mention « corrige aussi dans
    les N autres kits qui utilisent cette histoire ».
- **Un bouton « Toute ma banque (N) »** ouvre un panneau latéral à côté du kit.
  - Les histoires y sont groupées par expérience du profil, avec une
    recherche.
  - Chaque histoire montre son résultat chiffré et le nombre de kits qui
    l'utilisent.
  - Une histoire déjà utilisée dans ce kit est marquée « ✓ dans ce kit ».
  - Les autres proposent « Utiliser pour… », qui l'affecte à une ligne du
    tableau.
- **Un doublon s'affiche dans le kit qui contient l'histoire concernée**
  (bandeau « racontée avec −45 % dans un autre kit et −60 % ici »). Il
  s'ouvre sur une vue côte à côte pour trancher.

## Non-objectifs

- Une page dédiée à la banque dans le menu.
- La préparation par entretien successif. C'est le projet suivant.
- Les autres modules du kit : packs d'audience, questions inversées, mode
  entraînement. Ils sont inchangés, sauf pour lire les faits depuis la banque.
- Partager des histoires entre utilisateurs.
- Retirer l'ancien champ `interview_preps.stories`. Ce sera une étape
  séparée, une fois le remplissage vérifié en production.
- Fusionner des doublons automatiquement.

## Anti-objectifs (dans l'ordre d'importance donné par le candidat)

1. **Perdre une histoire d'un kit existant**, au remplissage ou à cause d'un
   doublon tranché. C'est l'échec le plus grave.
2. **Laisser l'IA modifier des chiffres** en rédigeant l'angle propre à une
   offre.
3. Rendre un kit plus cher qu'aujourd'hui (voir [Coût](#coût)).

## Contraintes

- **Isolation par utilisateur** : chaque lecture et chaque écriture de la
  banque est filtrée par `user_id`. Le code existant accepte un `user_id`
  stocké en chaîne ou en `ObjectId` (motif `$or` de
  `backend/app/routers/interview_prep.py`).
- **Quota** : tout appel à l'IA passe par `require_user_quota(...,
  ApiUsageAction.INTERVIEW_PREP)` et `record_api_usage`, avec un
  `sub_action` distinct pour chaque nouvel appel.
- **Annulation** : les nouveaux appels à l'IA respectent le motif
  `_generation_cancelled`. Un résultat qui arrive après une annulation
  n'écrit rien.
- **Garde anti-hallucination** : tout texte rédigé par l'IA à partir d'une
  histoire passe par `_mask_invented_numbers`, avec les faits de l'histoire
  comme sources.
- **Exécution en production** : lancer le remplissage sur les données de
  production revient au candidat. On fait une sauvegarde avant.
- **Tests** : selon les règles du `CLAUDE.md` du projet. Ils portent sur les
  invariants métier, l'isolation entre utilisateurs et les gardes de l'IA,
  pas sur la configuration de mocks.

## Décisions prises par le candidat

- Les faits sont partagés et le récit reste propre à l'offre (voir
  Intention).
- Une correction s'applique aussi aux kits déjà générés, sans génération
  payante.
- La banque est remplie au départ avec les histoires des kits existants.
- Les doublons sont tranchés une fois, sur une vue côte à côte.
- On puise d'abord dans la banque, et l'IA n'écrit que pour les manques.
  L'histoire écrite entre dans la banque.
- Le kit pointe vers la banque et ne garde que l'angle.
- La banque s'ouvre dans un panneau du kit, sans entrée de menu.
- Ces points de la dernière restitution ont été validés tels quels
  (« rien » à corriger) :
  - le remplissage ne détruit rien ;
  - une version écartée lors d'un doublon reste récupérable ;
  - l'historique d'entraînement est conservé ;
  - supprimer une histoire utilisée exige une confirmation qui liste les kits
    concernés, et ces lignes passent en « manque » ;
  - l'IA ne modifie jamais les faits.
- Une exigence que le profil ne couvre pas reçoit une histoire transférable
  quand une expérience voisine existe. Sinon, elle est marquée « pas
  d'expérience dans ton profil », sans génération (voir [Exigences non
  couvertes par le profil](#exigences-non-couvertes-par-le-profil)).

## Choix de conception (faits par moi, modifiables par le constructeur s'il a mieux)

### Données

- **Nouvelle collection `star_stories`**, avec un document par histoire :
  - `id` : chaîne UUID ;
  - `user_id` ;
  - les faits : `title`, `theme`, `situation`, `task`, `action`, `result`,
    `reflection`, `key_tags` ;
  - `experience` : instantané `{company, role, start}` ou `null` ;
  - `origin` : `{kind: "migrated" | "generated" | "manual", offer_id}` ;
  - `discarded_versions` : une liste d'instantanés de faits écartés lors d'un
    doublon, chacun avec sa date et l'id de l'histoire d'origine ;
  - `not_duplicate_of` : la liste des ids que le candidat a déclarés
    différents ;
  - `created_at`, `updated_at`.
- **Dans le kit, un nouveau champ `interview_preps.story_slots`**, une liste
  de lignes :
  - `id` ;
  - `requirement` : l'exigence de l'offre ;
  - `story_id` : un id de la banque, ou `null` pour un manque ;
  - `fit` : l'adéquation, dont la liste complète des valeurs est dans
    [Exigences non couvertes par le
    profil](#exigences-non-couvertes-par-le-profil) ;
  - `angle_edited` : vrai si le candidat a rédigé l'angle à la main ;
  - `angle` : le texte de ce qu'on met en avant pour cette offre.
- **`target_requirement` sort des faits** et devient `story_slots[].requirement`.
- **L'ancien champ `interview_preps.stories` n'est ni lu ni modifié** par le
  nouveau code, une fois le kit migré. Il reste la copie de sûreté.
- **Les ids sont conservés au remplissage** : une histoire de kit garde son
  `id` dans la banque. Les `mapped_story_id` des questions restent ainsi
  valides sans réécriture.
- **Le profil n'a pas d'identifiant d'expérience**
  (`CandidateExperience` est une liste sans id). Le rattachement passe donc
  par l'instantané `experience`.
  - L'affichage regroupe une histoire sous l'expérience du profil courant
    dont l'entreprise et le poste correspondent, une fois normalisés.
  - Sans correspondance, l'histoire va dans un groupe « Sans expérience
    rattachée ».
  - Depuis ce groupe, le candidat peut rattacher l'histoire à une expérience
    de son profil.

### Remplissage depuis les kits existants

- **Un script `backend/migrate_star_stories_to_bank.py`** fait le
  remplissage. Il suit le style de `backend/backfill_contract_types.py` :
  - simulation par défaut, `--apply` pour écrire ;
  - idempotent : relancé, il ne crée rien en double ;
  - rapport par utilisateur : nombre d'histoires dans les kits, nombre
    d'histoires dans la banque, nombre de kits avec des `story_slots`.
- **Pour chaque histoire de kit**, le script :
  - crée l'entrée de banque avec le même `id` et `origin.kind = "migrated"` ;
  - crée la ligne du kit, avec
    `requirement = target_requirement`, `story_id = id`, `fit = strong` et
    `angle` vide.
- **Le script vérifie l'invariant et s'arrête en erreur s'il est violé** :
  chaque `id` d'histoire de kit existe dans la banque, et chaque kit a autant
  de lignes que d'histoires d'origine.
- **Rattachement à une expérience au remplissage** : l'histoire est rattachée
  si exactement une entreprise du profil apparaît dans `situation`. Sinon elle
  reste « Sans expérience rattachée ». Aucun appel à l'IA.
- **Aucun doublon n'est fusionné au remplissage.** Le script détecte
  seulement les doublons possibles, que le kit affichera.

### Doublons

- **Détection sans IA** : deux histoires du même utilisateur, rattachées à la
  même expérience ou sans rattachement, avec des titres proches ou des
  résultats qui se recoupent. L'heuristique exacte revient au constructeur.
  - Un faux positif coûte un clic au candidat (« ce sont deux histoires
    différentes »).
  - Un faux négatif laisse deux histoires côte à côte.
  - Aucune des deux erreurs ne perd de données. On penche donc vers
    proposer plus.
- **Trancher « même histoire, je garde A »** :
  - les faits de B rejoignent `A.discarded_versions` ;
  - toutes les lignes de kit et toutes les questions qui pointaient vers B
    pointent vers A ;
  - B est retiré de la banque.
- **Trancher « histoires différentes »** : chacune enregistre l'autre dans
  `not_duplicate_of`, et la paire n'est plus jamais proposée.
- **Une version écartée se restaure depuis l'histoire** : ses faits
  remplacent les faits actuels, et ces derniers passent à leur tour dans
  `discarded_versions`.

### Génération pour une offre

1. **Exigences** : celles du Bloc B de l'évaluation de l'offre, quand elle
   existe.
   - Aujourd'hui, l'IA écrit 3 à 5 histoires et chacune choisit sa propre
     exigence. Il n'y a pas de tableau d'exigences.
   - Le Bloc B, lui, est exhaustif (règle d'exhaustivité de
     `backend/app/services/evaluation/evaluator.py`) et peut lister plus de
     10 exigences.
   - **Plafond : 5 lignes.** Elles sont choisies par poids (`critical`, puis
     `high`, puis `meaningful`), et l'ordre du Bloc B départage les
     ex æquo.
   - Le traitement des `missing_requirements` (exigences que le profil ne
     couvre pas) est décrit plus bas, dans [Exigences non couvertes par le
     profil](#exigences-non-couvertes-par-le-profil).
   - Sans évaluation, l'appel d'association de l'étape 2 extrait au plus 5
     exigences clés de la description.
2. **Association (un appel à l'IA, `sub_action = "story_match"`)** :
   - entrées : les exigences, plus un résumé court de chaque histoire de la
     banque (id, titre, expérience, résultat, tags) ;
   - sortie, pour chaque exigence : un `story_id` ou `null`, une adéquation
     et un angle ;
   - l'angle passe par `_mask_invented_numbers` contre les faits de
     l'histoire.
   - **Banque vide** : l'appel est sauté et toutes les exigences sont des
     manques.
3. **Manques (un appel à l'IA, `sub_action = "stories"`)** :
   - le prompt `star_stories.md` est adapté pour recevoir la liste des
     exigences sans histoire ;
   - toutes les nouvelles histoires sont écrites en un seul appel ;
   - le prompt demande aussi l'expérience du profil d'où vient chaque
     histoire, ce qui remplit `experience` ;
   - les nouvelles histoires entrent dans la banque avec
     `origin.kind = "generated"`.
4. **Relancer la génération des histoires d'un kit** refait les étapes 1 à 3.
   Elle remplace les lignes du kit et **ne supprime jamais une histoire de la
   banque**. Comme aujourd'hui, les questions qui pointaient vers une histoire
   absente des nouvelles lignes perdent leur `mapped_story_id`.
   - **Un angle rédigé à la main est conservé** si la nouvelle génération
     produit une ligne avec la même exigence et la même histoire. La ligne
     porte un indicateur `angle_edited`.
   - **Dans les autres cas, l'angle est perdu.** La confirmation qui existe
     déjà avant de régénérer un kit modifié doit alors citer les angles
     rédigés à la main.
5. **« Écrire avec l'IA » sur une ligne en manque** fait l'étape 3 pour cette
   seule exigence.
6. **« L'écrire moi-même » sur une ligne en manque** ouvre un formulaire vide,
   sans appel payant. L'histoire entre dans la banque avec
   `origin.kind = "manual"`.
7. **« Utiliser pour… » depuis le panneau** affecte l'histoire à la ligne
   choisie, avec `fit = manual` et un angle vide que le candidat peut
   rédiger. Aucun appel à l'IA.
8. **`generate_all_endpoint`** utilise le même enchaînement pour la partie
   histoires.

### Exigences non couvertes par le profil

C'est une exigence du Bloc B classée en `missing_requirements` : le profil ne
la couvre pas. L'IA ne peut pas écrire d'histoire vraie dessus sans inventer,
ce qui va contre l'anti-objectif 2 et la règle anti-hallucination de
`star_stories.md`. Le candidat a validé ce traitement le 2026-10-24 :

- **Le profil contient une expérience voisine** (par exemple AWS pour une
  exigence GCP) :
  - l'IA écrit une histoire vraie sur cette expérience, qui entre dans la
    banque comme toute autre histoire ;
  - la ligne du kit est marquée `fit = transferable` et l'interface affiche
    « transférable » ;
  - l'angle explique le pont entre l'expérience vécue et l'exigence ;
  - les faits restent ceux de l'expérience vécue, jamais ceux de l'exigence.
- **Rien d'approchant dans le profil** :
  - la ligne affiche « pas d'expérience dans ton profil », avec
    `story_id = null` et `fit = no_experience` ;
  - il n'y a pas de bouton « Écrire avec l'IA » ;
  - le candidat prépare une réponse franche sur cet écart ;
  - « L'écrire moi-même » reste proposé, sans appel payant, pour le cas où le
    profil serait incomplet (mon choix).
- **C'est l'appel d'écriture des manques (étape 3) qui tranche**, pour chaque
  exigence non couverte : il renvoie soit une histoire transférable, soit
  rien.
- Le plafond de 5 lignes s'applique à l'ensemble des exigences, couvertes ou
  non. Une exigence non couverte mais de poids `critical` peut donc occuper
  une ligne.
- La maquette montre « Expérience cloud GCP → manque → Écrire avec l'IA ».
  Cet exemple est remplacé par cette section.

Valeurs complètes de `story_slots[].fit` : `strong`, `partial`,
`transferable`, `gap` (exigence couverte par le profil mais pas encore par une
histoire), `no_experience` et `manual`.

### Modifications et suppression

- **Modifier des faits** écrit dans `star_stories`. Tous les kits qui
  référencent l'histoire affichent la modification au prochain chargement.
- **Modifier l'angle ou l'exigence** n'écrit que dans la ligne du kit.
- **Supprimer une histoire de la banque** :
  - une lecture préalable renvoie la liste des kits qui l'utilisent (offre,
    entreprise) pour la confirmation ;
  - après confirmation, les lignes concernées passent en `story_id = null`
    et `fit = gap` ;
  - les questions qui pointaient vers l'histoire perdent leur
    `mapped_story_id`.
- **Supprimer une ligne du kit** ne supprime pas l'histoire de la banque.

### Lecteurs existants

- **`GET /offers/{offer_id}/interview-prep`** renvoie les lignes du kit avec
  les faits de chaque histoire joints depuis la banque, plus les doublons
  possibles qui concernent ce kit.
- **`evaluate_practice_answer`** et **`export_interview_prep_markdown`**
  lisent les faits depuis la banque, via la ligne du kit ou via
  `mapped_story_id`.
- **`generate_anticipated_questions`** reçoit les histoires des lignes du kit.
- **Les essais d'entraînement ne changent pas.** Ils restent rattachés à leur
  question.

### Fichiers concernés (indicatif)

- **Backend** :
  - `backend/app/models.py`
  - `backend/app/services/interview_prep_service.py`
  - `backend/app/routers/interview_prep.py`, ou un routeur
    `star_stories` séparé pour les opérations sur la banque
  - `backend/app/llm/prompts/interview/star_stories.md`
  - un nouveau prompt d'association
  - `backend/migrate_star_stories_to_bank.py`
- **Frontend** :
  - `frontend/src/types/interview.ts`
  - `frontend/src/lib/api.ts`
  - `frontend/src/components/interview/InterviewPrepTab.tsx`
  - `frontend/src/components/interview/StarStoryCard.tsx`
  - `frontend/src/components/interview/AnticipatedQuestionsViewer.tsx`
  - un nouveau composant de panneau de banque

## Coût

Aujourd'hui, chaque kit fait un appel qui écrit 3 à 5 histoires complètes.
Après le changement :
- **Premier kit, banque vide** : même coût qu'aujourd'hui, avec un appel
  d'écriture.
- **Kits suivants** : un appel d'association court, plus un appel d'écriture
  réduit aux seuls manques. Il n'y a parfois aucun manque.

**Critère** : sur les premières générations après livraison, comparer dans
`api_usage` les tokens par kit (`sub_action` `story_match` et `stories`) à la
moyenne des kits d'avant. On attend une baisse dès que la banque contient
quelques histoires. C'est à mesurer, pas acquis.

## Tests attendus

- **Isolation** : la banque d'un utilisateur n'est ni lisible, ni
  modifiable, ni supprimable par un autre. Une ligne de kit ne peut pas
  pointer vers l'histoire d'un autre utilisateur.
- **Remplissage sans perte** :
  - chaque `id` d'histoire de kit se retrouve dans la banque, et chaque kit
    a ses lignes ;
  - `interview_preps.stories` est inchangé ;
  - relancer le script ne crée rien de plus ;
  - les `mapped_story_id` restent valides.
- **Propagation** : modifier un fait dans un kit change ce que renvoient les
  autres kits qui utilisent l'histoire, sans aucun appel à l'IA.
- **Doublon tranché** :
  - la version écartée se retrouve dans `discarded_versions` ;
  - les lignes et les questions sont redirigées ;
  - restaurer la version écartée remet ses faits.
- **Suppression** : les lignes passent en manque, les questions perdent leur
  lien, et les autres histoires sont intactes.
- **Garde des chiffres** : un angle qui contient un nombre absent des faits
  est masqué en `[à chiffrer]`.
- **Génération** :
  - banque vide : pas d'appel d'association ;
  - aucun manque : pas d'appel d'écriture ;
  - relancer la génération ne supprime aucune histoire de la banque ;
  - une exigence sans expérience voisine donne une ligne `no_experience`,
    sans histoire créée ;
  - un angle rédigé à la main survit à la régénération quand la paire
    exigence + histoire est conservée.
- **Entraînement** : la notation lit les faits à jour depuis la banque.

## Laissé au constructeur

- L'heuristique exacte de détection des doublons, dans les limites fixées
  plus haut.
- Le découpage des routes : routeur séparé ou non, PATCH ou PUT.
- Le moment du remplissage pour les kits non encore migrés au déploiement.
  Deux options : migration paresseuse au premier accès, idempotente, ou script
  lancé au déploiement. Condition : aucun kit ne doit s'afficher vide parce
  qu'il n'a pas encore été migré.
- Le format exact du prompt d'association et la limite de taille du résumé
  de la banque qu'on lui envoie.
- La découpe en composants frontend et le détail visuel, dans le respect de
  la maquette validée.
