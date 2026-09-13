# Génération de lettres de motivation — design

Date : 2026-09-13
Statut : validé section par section, prêt pour plan d'implémentation

## Objectif

Générer une lettre de motivation quand une candidature passe au statut « En
étude », à partir d'un profil candidat structuré et de la description de
l'offre. La lettre doit être crédible, spécifique à l'offre, et ne contenir
aucune expérience, compétence ou chiffre absent du profil.

Le critère de réussite n'est pas « la meilleure lettre possible » mais « une
lettre qu'un recruteur ne classe pas comme générée ». Ce critère n'est pas
mesurable par un test automatique. Il est approché par trois moyens de nature
différente : des garde-fous en code pour tout ce qui se compte, un critique sur un
autre modèle que le rédacteur pour l'impression d'ensemble, et la relecture humaine
qui décide.

## Décisions de cadrage

| Question | Décision |
|---|---|
| Déclenchement | Passage au statut `ETUDE` (« En étude ») |
| Exécution | Asynchrone, `BackgroundTasks` FastAPI + polling côté client |
| Profil | Un profil complet unique, sélection des expériences par le LLM |
| Sortie | Texte éditable, régénérable, versions historisées |
| Moteur LLM | Les trois fournisseurs déjà configurés — Gemini, OpenAI, Mistral. Un modèle par rôle, choisi sur la nature de la tâche |
| Rédacteur | Départagé par un bake-off à l'implémentation, pas par hypothèse |
| Critique | Obligatoirement sur un fournisseur différent du rédacteur |
| Passes LLM | Trois au cas nominal, une quatrième si le critique ou un garde-fou bloquant l'exige |
| Orchestration | Crew CrewAI dédié, séparé de `JobTrackers` |

Le choix du moteur est indépendant de CrewAI : un service Python simple aurait
utilisé le même sélecteur. CrewAI est un choix explicite de cohérence avec
l'existant.

Critère qui gouverne les arbitrages de cette spec : le résultat, pas le coût. Le
volume est de l'ordre de quelques lettres par semaine, donc un écart de prix au
token entre deux modèles représente des centimes par mois et ne doit jamais
trancher un choix de qualité. Le coût n'est chiffré que pour vérifier qu'aucune
option ne dérape, pas pour départager.

## Approches écartées

**Service Python direct sans CrewAI.** Techniquement équivalent et un peu plus
léger, mais ne réutilise pas l'infrastructure d'agents en place. Écarté sur
préférence explicite.

**Agents ajoutés au crew `JobTrackers` existant.** `JobTrackers` fait de la
collecte et du filtrage d'URL. Y greffer de la rédaction mélange deux
responsabilités dans un même `agents.yaml`. Le nouveau crew vit dans un fichier
séparé du même package et reprend ses conventions de configuration, avec son
propre sélecteur de modèle.

**Un seul appel LLM avec le prompt complet.** Plus simple, mais le rédacteur voit
alors tout le profil et peut mélanger deux expériences ou inventer un chiffre.

**Une auto-critique par le rédacteur lui-même.** Un modèle ne voit pas ses propres
tics : il relit sa prose, la trouve correcte, et l'« améliore » vers du poli
générique — exactement ce que la spec de style interdit. Remplacée par un critique
sur un autre fournisseur, qui n'a pas les mêmes réflexes et voit donc ceux du
rédacteur.

**Un critique qui réécrit.** Mélanger juger et rédiger dans un même appel produit
une lettre à deux voix. Le critique rend un verdict et une liste de défauts ; la
réécriture revient à `reviser`, sur le modèle du rédacteur.

**Un seul modèle pour tout le crew.** Les quatre rôles ne font pas le même métier :
extraction sur gros contexte, rédaction française, jugement stylistique, correction
sous contrainte. Aucun modèle n'est le meilleur des quatre.

## Architecture

### Collection `candidate_profile`

Un document par utilisateur. Source de vérité unique après amorçage.

```
user_id
headline
summary
contact: { email, phone, github, website, linkedin }
experiences[]: {
  company, role, location, contract,     # VIE, CDI, consultant, stage…
  start, end,                            # end = null → en poste
  sector,                                # biopharma, santé, industrie, conseil…
  missions[],                            # phrases factuelles validées
  achievements[]: { text, metric },      # metric = null si aucun chiffre réel
  stack[]                                # sert de pré-filtre, pas de tag à maintenir
}
projects[]: {
  name, description, stack[], url, year,
  context                                # perso | client | recherche | consortium
}
education[]:      { school, degree, years, topics[] }
certifications[]: { name, issuer, year, topics[] }
languages[]
skills: { langages, cloud, bases, mlops, frameworks, data_eng, viz }
provenance[]:     { field_path, source }  # cv | site | saisie
updated_at
```

Trois points de conception :

`achievements` est séparé de `missions` parce que la spec de fond demande de
privilégier les réalisations concrètes. Mélangés, l'agent d'extraction ne sait
pas lesquelles sont des preuves.

`metric` est explicitement nullable. Pas de chiffre réel, champ vide : le
rédacteur ne voit aucun nombre et ne peut donc pas en inventer un.

`context` sur les projets est obligatoire. Sans lui, un projet personnel se lit
comme une mission salariée dans la lettre. Le rédacteur doit énoncer le statut
naturellement (« un projet perso », « pour un client »).

`provenance` existe parce que le CV et le site divergeaient réellement lors du
cadrage (Odoo côté CV, Sylob côté site, les deux vrais). Quand deux sources se
contredisent, il faut savoir laquelle disait quoi sans relire le PDF.

### Amorçage du profil

Script one-shot, exécuté à la main, jamais appelé à l'exécution normale :

1. lit `data/profile/cv.md` (CV Canva converti en markdown, dossier ignoré par
   git) et les pages déjà récupérées du site personnel ;
2. fusionne les expériences par (entreprise, dates) ;
3. marque les conflits au lieu de les résoudre seul ;
4. produit un JSON que l'utilisateur relit et corrige ;
5. insère en base.

Après l'amorçage, ni le PDF ni le site ne sont relus. Le site personnel est une
amorce, pas une dépendance d'exécution.

Sources disponibles à l'amorçage : 8 postes, 12 projets répartis en 3 groupes,
5 formations, 4 certifications. Le CV omet 3 postes que le site contient
(bioMérieux, Nodya, un Bimedoc plus détaillé) et 2 certifications (RNCP Big Data
M2i RS 3299, RNAseq/Galaxy CNRS). Le site omet Odoo. La fusion doit donc être une
union avec signalement, pas un choix de source prioritaire.

### Collection `cover_letters`

```
user_id, application_id
status                                   # pending | ready | failed
versions[]: {
  n, body, origin,                       # generated | edited
  models,                                # un identifiant par rôle : analyst, writer, critic, reviser
  prompt_version, guard_report,
  critic_verdict,                        # pass | revise + défauts relevés
  revised,                               # booléen : reviser est-il passé
  created_at
}
current_version
error
created_at, updated_at
```

Collection séparée de `applications`, pas sous-document : l'historique grossit à
chaque régénération, et l'affichage de la liste des candidatures n'a aucune
raison de charger le texte des lettres.

### Crew `cover_letter`

Fichier séparé dans le package `job_trackers`, mêmes conventions que
`crew.py` (`agents.yaml`, `tasks.yaml`), avec `get_letter_llm()` au lieu de
`get_crew_llm()` (voir Configuration LLM).

| Agent | Entrée | Sortie | Quand |
|---|---|---|---|
| `offer_analyst` | description de l'offre + profil complet | JSON : missions réelles du poste, 2-3 expériences ou projets retenus, preuve justifiant chaque choix | toujours |
| `writer` | le JSON seulement | lettre de 250 à 400 mots | toujours |
| `critic` | la lettre seulement, plus les missions du poste | JSON : verdict `pass` / `revise`, liste de défauts localisés | toujours |
| `reviser` | lettre + JSON d'analyse + défauts du critique + rapport de garde-fous | lettre corrigée | verdict `revise`, ou garde-fou bloquant |

Contrainte structurante : `writer` ne reçoit jamais le profil complet. Il ne
peut pas citer une expérience que `offer_analyst` n'a pas retenue, ni un chiffre
absent du JSON. L'anti-hallucination est une propriété de l'architecture, pas
une consigne de prompt.

Fusionner `offer_analyst` et `writer` en un seul appel détruirait cette
garantie : le rédacteur verrait tout le profil.

**Le critique tourne obligatoirement sur un autre fournisseur que le rédacteur.**
C'est ce qui rend la passe utile : un modèle relisant sa propre prose la valide et
la polit, alors qu'un modèle d'une autre famille reconnaît les tics de celle du
rédacteur — structures tripartites, connecteurs systématiques, symétrie je/vous. Le
contrat d'implémentation est explicite : si `writer` et `critic` résolvent le même
fournisseur, la construction du crew échoue au démarrage plutôt que de tourner avec
une critique inutile.

Il ne voit que la lettre et les missions du poste, jamais le profil ni le JSON
d'analyse. Deux raisons : un juge qui connaît la sélection retenue justifie ce
qu'il lit au lieu de le juger, et le recruteur réel, lui non plus, n'a que la lettre
et l'offre. Ses critères sont exactement ceux que le code ne sait pas mesurer.

Il juge, il ne réécrit pas. Sortie limitée à un verdict et à des défauts localisés :
mélanger juger et rédiger dans le même appel produit une lettre à deux voix. La
réécriture est le métier de `reviser`, qui tourne sur le modèle du rédacteur pour
que la voix reste la même.

`reviser` reçoit le cumul — défauts du critique et rapport de garde-fous — et ne
passe qu'une fois. Après lui, la lettre part en `ready` avec son rapport, quel que
soit l'état des contrôles.

Réversible à peu de frais : `guard_report` et le verdict du critique sont stockés
sur chaque version. Après une vingtaine de lettres, le taux réel de `revise` est
connu. S'il est très bas, le critique devient un luxe et peut être coupé ; s'il est
très haut, ce sont les prompts de `writer` qu'il faut corriger, pas une passe qu'il
faut ajouter.

Les expériences et les projets sont sélectionnables au même titre : sur une
offre où le salariat est mince, les projets portent la candidature (Sentinel sur
une offre quantitative, FilialeAgents sur une offre agents/LLM, DeepOS ou NGS
Pipeline sur une offre biotech).

### Prompts

Fichiers markdown versionnés dans `backend/app/llm/prompts/cover_letter/` :

- `01_fond.md` — règles de fond, interdits, structure, longueur
- `02_style.md` — ton, vocabulaire, ponctuation, rythme, paragraphes
- `03_critique.md` — grille de jugement du critique : les signes d'une rédaction générée, formulés comme des questions de recruteur et non comme des règles à appliquer
- `04_revision.md` — consignes de correction, utilisées uniquement par `reviser`

`03_critique.md` ne reprend pas les listes d'interdits de `01` et `02` : le code les
vérifie déjà mieux qu'un modèle, et les redonner au critique le pousserait à
signaler du lexique au lieu de juger l'impression d'ensemble, seul point qu'il est
là pour couvrir.

Pas dans les `backstory` de `agents.yaml` : les deux specs font environ
2500 mots, noyées dans du YAML elles deviennent illisibles et indiffables, et
elles seront itérées souvent. Chaque version de lettre stocke le
`prompt_version` qui l'a produite.

### Garde-fous en code

Module `backend/app/services/letter_guards.py`, fonctions pures, exécutées sur la
sortie de `writer`, en parallèle de `critic`.

**Niveau bloquant, déterministe.** Violation → un appel à `reviser` avec le
rapport d'échec en entrée. Un seul.

| Contrôle | Règle initiale |
|---|---|
| Ponctuation interdite | aucun `!`, aucun `...`, aucun `—`, au plus 1 `;`, pas de parenthèses |
| Lexique banni | listes des deux specs (« forte appétence », « solide expertise », « je suis convaincu que mon profil »…) |
| Ouvertures interdites | « Je vous adresse ma candidature », « Actuellement à la recherche », « Titulaire de », « Fort de », « C'est avec grand intérêt » |
| Connecteurs en tête de phrase | « De plus », « Par ailleurs », « En outre », « Enfin », « De même », « En effet », « Ainsi », « Dans ce contexte », « À ce titre », « Fort de cette expérience » — au plus 1 dans toute la lettre |
| Compliments génériques | « entreprise leader », « entreprise innovante », « acteur majeur », « entreprise reconnue », « culture d'innovation », « excellence », « forte croissance » |
| Paragraphes | entre 3 et 5 |
| Longueur | entre 250 et 400 mots |
| Répétitions plafonnées | « mon parcours », « mon expérience », « mes compétences » : 1 chacun ; « je souhaite », « je suis », « je serais » : 1 chacun ; nom de l'entreprise : 2 |
| Ouverture de paragraphe | pas tous les paragraphes commençant par « Je » |
| Énumérations | au plus 3 technologies dans une même phrase |
| Recouvrement avec l'offre | aucune séquence de 8 mots consécutifs commune à la lettre et à la description de l'offre |
| Entités | toute entreprise, technologie ou chiffre de la lettre doit exister dans le JSON produit par `offer_analyst` |

**Niveau avertissement, jamais de relance.** Reporté dans `guard_report`, visible
dans l'interface, replié par défaut.

| Contrôle | Règle initiale |
|---|---|
| Variance de longueur de phrase | écart-type des longueurs sous 4 mots → signalé |
| Phrase extrême | au-delà de 40 mots → signalé |
| Accumulation d'adjectifs | 3 adjectifs consécutifs → signalé |
| Uniformité syntaxique | plus de 3 phrases consécutives de même construction → signalé |

**Niveau non mesurable en code** : « trop parfait », interchangeable avec une autre
candidature, motivation déclarée au lieu d'expliquée, symétrie je/vous trop
régulière. C'est le domaine de `critic`, pas du code — aucune expression régulière ne
décide si une lettre sonne générée. Son verdict rejoint le rapport des garde-fous et
déclenche `reviser` de la même manière.

Après la passe `reviser`, la lettre passe en `status: ready` même si des contrôles
bloquants sautent encore, avec son `guard_report` et le verdict du critique visibles.
Pas de seconde relance. Une mauvaise lettre lisible et corrigeable vaut mieux qu'un
échec muet, et une boucle de relance ne converge pas : elle tourne sur les mêmes
faiblesses du même modèle.

Les seuils vivent en constantes d'un seul module pour être ajustés à l'usage.

**Deux tensions arbitrées.** La spec de style demande de couper les phrases
longues et, ailleurs, d'en garder quelques-unes quand elles viennent
naturellement. Coder « coupe les phrases longues » en règle bloquante
aplatirait le rythme réclamé : d'où plafond dur sur l'extrême seulement, et
plancher de variance en simple avertissement. La même spec interdit d'introduire
des imperfections artificielles — raison supplémentaire pour que la variance ne
déclenche jamais de relance, sinon le modèle rallonge une phrase courte pour
passer le contrôle.

Un contrôle statistique qui déclenche une relance boucle sur ses faux positifs
et consomme le crédit pour rien. La relance reste réservée au déterministe.

### Déclenchement

Dans `update_application` ([applications.py:149](../../../backend/app/routers/applications.py#L149)),
après le `update_one` : ancien statut différent de `ETUDE` et nouveau statut égal
à `ETUDE`.

Trois gardes :

**Idempotence** — pas de génération si une lettre existe déjà pour cette
candidature. Sans elle, un aller-retour `ETUDE → APPLIED → ETUDE` écrase le
travail en cours.

**Description présente** — la tâche relit la candidature à son démarrage. Si la
description manque alors qu'une URL existe, elle génère la description d'abord
puis enchaîne ; le cas se produit réellement quand le passage en `ETUDE` suit de
peu la création de la candidature, pendant que `_generate_description_bg` tourne
encore. Sans URL ni description : échec `description_missing` explicite, avec
réessai proposé par l'interface.

**Profil présent** — pas de profil en base, échec explicite indiquant d'amorcer
le profil.

### Exécution asynchrone

`run_crew` est synchrone ([main.py:22](../../../backend/job_trackers/src/job_trackers/main.py#L22),
`kickoff()`). Appelé tel quel dans une `BackgroundTask`, il bloque la boucle
d'événements 40 à 120 secondes et gèle toute l'API, pas seulement la génération.
Il doit passer par `asyncio.to_thread`.

Corollaire : le thread du crew ne touche pas MongoDB. Un client Motor est lié à
sa boucle d'événements — c'est la cause racine documentée dans
[docs/micro/20260913-fix-collect-offers-event-loop/PLAN.md](../../micro/20260913-fix-collect-offers-event-loop/PLAN.md),
d'où `_get_client()` dans [database.py](../../../backend/app/database.py). Le
crew calcule, l'écriture se fait au retour dans le contexte asynchrone.

### API

Nouveau routeur `backend/app/routers/cover_letters.py` :

```
GET    /applications/{id}/cover-letter             # cible du polling
POST   /applications/{id}/cover-letter/regenerate  # nouvelle version générée
PATCH  /applications/{id}/cover-letter             # édition manuelle → version origin=edited
GET    /profile/candidate
PUT    /profile/candidate
```

Contrôle d'accès identique à l'existant : la candidature doit appartenir à
l'utilisateur authentifié, sinon 403.

### Frontend

Composant dédié `CoverLetterPanel.tsx`, pas de logique ajoutée dans
[ApplicationDetails.tsx](../../../frontend/src/components/applications/ApplicationDetails.tsx) —
ce fichier fait déjà 19,5 Ko et y greffer du polling le rend ingérable.

Quatre états : absent, en cours, prête, échouée. En état « prête » : textarea
éditable, bouton de régénération, historique des versions, `guard_report` et verdict
du critique repliés par défaut. L'historique affiche le modèle rédacteur de chaque
version : c'est ce qui rend une régénération comparable à la précédente.

Polling toutes les 3 secondes tant que `status = pending`, arrêt sur `ready` ou
`failed`, abandon au bout de 3 minutes avec message — quatre appels LLM dont un sur un
gros modèle tiennent mal dans deux.

Appels regroupés dans `coverLetterApi`, sur le modèle de `applicationApi`
([api.ts:434](../../../frontend/src/lib/api.ts#L434)).

### Configuration LLM

Sélecteur dédié `get_letter_llm()`, distinct de `get_crew_llm()`
([crew.py:42](../../../backend/job_trackers/src/job_trackers/crew.py#L42)). La
collecte d'offres fonctionne aujourd'hui avec sa propre sélection ; changer son
moteur pour servir les lettres ferait régresser une chaîne qui marche. Deux
fonctions, deux jeux de variables d'environnement, aucun couplage.

Signature : `get_letter_llm(role)`. Les trois clés sont déjà présentes dans le `.env`
du projet — `GEMINI_API_KEY`, `OPENAI_API_KEY`, `MISTRAL_API_KEY` — et chaque rôle
résout vers le fournisseur qui sert le mieux son métier. Une variable
d'environnement par rôle (`LETTER_MODEL_ANALYST`, `LETTER_MODEL_WRITER`,
`LETTER_MODEL_CRITIC`) permet de forcer un modèle sans toucher au code ; c'est ce que
le bake-off utilise.

**Un modèle par rôle, pas un modèle pour le crew.** Extraire sur gros contexte,
écrire du français, juger un style, corriger sous contrainte : quatre métiers, aucun
modèle n'est le meilleur des quatre. Le pattern existe déjà dans le code — `llm=` est
passé agent par agent
([crew.py:64](../../../backend/job_trackers/src/job_trackers/crew.py#L64)).

| Agent | Modèle | Température | Pourquoi |
|---|---|---|---|
| `offer_analyst` | `gemini/gemini-3.8-flash` | 0.1 | ~12 000 tokens d'entrée pour une sortie JSON courte. Long contexte, raisonnement interne, et le seul des trois fournisseurs à garder un palier gratuit sur sa génération courante — or c'est l'appel le plus gourmand en entrée. Aucune créativité attendue : le livrable est une sélection justifiée, pas de la prose |
| `writer` | départagé par bake-off | 0.7 | C'est le livrable, et aucune documentation ne dit qui écrit le meilleur français non-formaté. Voir le protocole ci-dessous. La température basse du sélecteur existant serait contre-productive : à 0.1 la prose devient plate et répétitive, exactement ce que le contrôle de variance signale |
| `critic` | un autre fournisseur que `writer` | 0.2 | Juge, ne réécrit pas. Température basse : on veut un verdict reproductible, pas une lecture inspirée |
| `reviser` | le modèle de `writer` | 0.5 | Corrige la prose en gardant la voix. Température plus basse que `writer` : correction ciblée, pas réécriture libre |

**Résolution du critique.** Règle en deux cas, dérivée du gagnant du bake-off :
`writer` chez OpenAI donne `critic` sur `gemini/gemini-3.8-flash` ; `writer` chez
Mistral ou Google donne `critic` sur `openai/gpt-5.6-sol`. Sol plutôt qu'un modèle
d'entrée de gamme parce que juger « est-ce que cette lettre sonne générée » demande
plus de finesse que d'en écrire une correcte, et parce que l'entrée est une lettre de
350 mots : le coût reste au centime. Si les deux rôles résolvent le même fournisseur
— override mal posé — la construction du crew échoue au démarrage, avec un message
nommant les deux modèles en conflit.

**Protocole du bake-off.** Une étape du plan d'implémentation, pas un chantier
séparé. Trois candidats : `openai/gpt-5.6-sol`, `mistral/mistral-large-3`,
`gemini/gemini-3.8-flash`. Même offre réelle, même profil, même JSON d'analyse en
entrée — donc `offer_analyst` ne tourne qu'une fois et les trois lettres sont
comparables. Sortie : trois lettres numérotées sans nom de modèle, dans un fichier du
répertoire de travail, accompagnées de leur `guard_report`. Deux mesures se
superposent : le nombre de violations, qui est objectif, et le classement à l'aveugle,
qui est le seul juge du style. Le gagnant devient le défaut en dur ; le fichier de
comparaison n'est pas committé, la décision l'est.

**Versions épinglées, pas d'alias.** Les trois fournisseurs font dériver leurs alias,
chacun à sa façon, et la spec de style dépend du modèle exact :

- Mistral documente qu'un alias bascule vers un nouveau modèle dès son passage en
  disponibilité générale, avec changement silencieux de comportement *et de prix*.
  Épingler sur major.minor (`mistral-large-3-0`) ou sur l'identifiant daté.
- Google hot-swap `-latest` à chaque release, préavis de deux semaines par courriel
  en cas de rupture, et applique des limites plus serrées aux modèles en preview. Le
  catalogue courant est `gemini-3.8-flash` ; `gemini-3.1-pro-preview` est en preview
  et sans palier gratuit, donc écarté.
- OpenAI : épingler l'identifiant exact du modèle retenu au bake-off, sinon le
  gagnant mesuré n'est plus celui qui tourne.

Un test refuse tout identifiant contenant `latest` ou `preview`.

Tarifs relevés le 2026-09-13 sur `docs.mistral.ai/inference/pricing`,
`platform.openai.com/docs/pricing` et `ai.google.dev/gemini-api/docs/pricing`, par
million de tokens, contexte court :

| Modèle | Entrée | Entrée en cache | Sortie | Palier gratuit |
|---|---|---|---|---|
| Gemini 3.8 Flash | 0,75 $ | 0,075 $ | 3,75 $ | oui |
| Gemini 3.5 Flash-Lite | 0,30 $ | 0,03 $ | 2,50 $ | oui |
| Gemini 3.1 Pro (preview) | 2,00 $ | 0,20 $ | 12,00 $ | non |
| Mistral Small 4 | 0,15 $ | 0,015 $ | 0,60 $ | crédits du plan Free |
| Mistral Large 3 | 0,50 $ | 0,05 $ | 1,50 $ | crédits du plan Free |
| GPT-5.6 Luna | 0,40 $ | 0,04 $ | 2,40 $ | non |
| GPT-5.6 Terra | 4,00 $ | 0,40 $ | 24,00 $ | non |
| GPT-5.6 Sol | 8,00 $ | 0,80 $ | 40,00 $ | non |
| GPT-6 Astra | 20,00 $ | 2,00 $ | 100,00 $ | non |

Trois pièges dans ce tableau. Les tarifs Gemini 3.8 Flash **doublent le
1er janvier 2027** — c'est un prix promotionnel, à revoir à cette date. Mistral
Medium 3.5 (1,50 $ / 7,50 $) coûte trois fois Large 3 en entrée et cinq fois en
sortie : c'est un modèle agentique et multimodal, pas un palier intermédiaire, et il
n'a aucun intérêt ici. GPT-6 Astra est décrit par OpenAI comme destiné au travail de
raisonnement le plus dur, ce qu'écrire 350 mots n'est pas : il entre au bake-off
seulement si les trois candidats déçoivent tous.

## Exclusions assumées

**Pas d'éditeur de profil complet en v1.** 8 expériences, 12 projets, 5
formations avec tableaux imbriqués : un formulaire représente plusieurs jours de
frontend pour un contenu modifié deux à trois fois par an. En v1, le JSON amorcé
est édité à la main et envoyé via `PUT`. À reconsidérer si l'usage le réclame.

**Pas d'export PDF ou DOCX.** Ajouterait une dépendance de rendu et des
questions de mise en page. La lettre est du texte à copier.

**Pas de génération pour les offres non retenues.** Seul le passage en `ETUDE`
déclenche.

**`summarize_chunks` garde son OpenAI en dur.**
[llm/utils.py:179](../../../backend/app/llm/utils.py#L179) exige `OPENAI_API_KEY` et
retourne un message d'erreur sans elle. Ce n'est plus un problème de coût puisque la
clé OpenAI est assumée, mais ça reste un sélecteur de modèle dupliqué qui échappe à
`get_letter_llm`. Chantier distinct, hors périmètre ici.

## Tests

Développement piloté par les tests, garde-fous d'abord puisque ce sont des
fonctions pures.

`test_letter_guards.py` — un cas passant et un cas fautif par règle bloquante,
plus les quatre contrôles d'avertissement. Aucun LLM, aucune base. Fichier de
test le plus rentable du lot : c'est lui qui tient réellement la qualité.

`test_cover_letter_trigger.py` — `ETUDE` déclenche, les autres statuts non, un
second passage ne duplique pas, description manquante enchaîne au lieu
d'échouer, profil absent échoue explicitement.

`test_profile_seed.py` — la fusion CV + site par (entreprise, dates) produit une
union et signale les conflits sans trancher. Le cas Odoo / Sylob sert de fixture.

`test_letter_llm.py` — `get_letter_llm` rend un modèle distinct par rôle, `critic`
résout toujours sur un fournisseur différent de `writer`, un override qui les mettrait
sur le même fournisseur lève une erreur nommant les deux modèles, une clé manquante
lève une erreur explicite, et aucun identifiant ne contient `latest` ni `preview`. Les
deux derniers cas attrapent les dérives que rien d'autre ne voit : une lettre générée
par un modèle qui n'est pas celui mesuré au bake-off, et une critique qui se juge
elle-même.

Le crew n'est pas testé contre un LLM réel : non déterministe, et la suite
appellerait quatre modèles à chaque exécution. La couture est `run_letter_crew`, que
les tests remplacent par un double retournant un texte fixe.

Aucun test n'affirme que la lettre est bonne. Ce n'est pas testable.

## Risques

**Qualité rédactionnelle.** Aucun modèle n'écrit spontanément la prose que la spec de
style réclame ; tous tendent vers le template. Trois lignes de défense, chacune sur un
type de défaut différent : la séparation `offer_analyst` / `writer` empêche
l'invention, les garde-fous attrapent le mesurable, le critique inter-modèle attrape
l'impression d'ensemble. Ce qui reste : un défaut que le rédacteur produit et que le
critique ne voit pas non plus. Conséquence à accepter, inchangée — la relecture
humaine est la dernière étape, et la lettre est éditable pour cette raison.

**Coût par lettre.** Trois appels au nominal, quatre avec `reviser`. Chiffrage aux
tarifs relevés, avec `writer` sur l'hypothèse la plus chère des trois candidats
(GPT-5.6 Sol) : `offer_analyst` environ 12 000 tokens d'entrée sur Gemini Flash, soit
0,01 $ ou rien du tout dans le palier gratuit ; `writer` environ 5 000 d'entrée et 600
de sortie, soit 0,064 $ ; `critic` environ 1 000 d'entrée et 300 de sortie, soit
0,02 $. Entre 0,03 et 0,10 $ la lettre selon le gagnant du bake-off. À quelques
lettres par semaine, c'est un ou deux dollars par mois : le coût n'est pas un risque,
il est chiffré ici pour établir qu'il ne contraint aucun choix.

**Dérive des tarifs et des paliers.** Deux échéances connues. Les tarifs Gemini 3.8
Flash doublent le 1er janvier 2027 — rien à faire aujourd'hui, tout à relire à cette
date. Et le plan Free de Mistral a déjà changé de forme une fois : la page d'aide
décrivant l'ancien « Experiment plan » rend 404, l'offre actuelle est un crédit
mensuel. Deux points à vérifier dans Mistral Studio si le bake-off désigne Mistral —
carte bancaire exigée ou non, report ou expiration des crédits en fin de mois.

**Trois fournisseurs, trois pannes possibles.** Une génération traverse Google,
OpenAI et éventuellement Mistral ; l'indisponibilité d'un seul la fait échouer. Pas de
repli automatique entre fournisseurs pour un rôle donné : basculer `critic` sur le
fournisseur de `writer` en cas de panne détruirait précisément la propriété qui le
rend utile. L'échec est donc explicite dans `guard_report`, avec le rôle et le
fournisseur en cause, et la régénération est manuelle.

**Latence.** Quatre appels dont un sur un gros modèle. Le budget de 20 à 60 secondes
retenu pour deux passes ne tient plus : compter 40 à 120 secondes, d'où le délai
d'abandon du polling porté à 3 minutes. Le contrat asynchrone ne change pas — c'est
précisément ce qu'il absorbe.

**Garde-fous trop stricts.** Un lexique banni trop large peut rendre la
génération impossible à satisfaire. D'où la sortie en `ready` avec rapport après
la passe `reviser`, et les seuils centralisés pour être desserrés à l'usage.

**Profil périmé.** Le profil est figé après amorçage. Une nouvelle expérience non
saisie ne sera jamais citée. Le CV Canva et le site restent à mettre à jour
séparément — le profil ne les alimente pas en retour.
