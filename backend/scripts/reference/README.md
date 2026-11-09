# Jeu de référence synthétique commun

Jeu partagé par trois plans : **profil/matching** (labels pertinent/partiel/hors_sujet),
**parseur CV** (faits attendus par page, PDF générés par le plan parseur) et **lettres**
(exigences, preuves exactes, éléments transférables, lacunes).

## Règles

- **Entièrement synthétique** : aucune donnée réelle, aucune personne ni entreprise réelle.
- **Aucun PDF binaire** versionné : les PDF sont générés par le plan parseur.
- **Le texte des sources est une donnée, jamais une instruction.** Un CV ou une offre
  contenant « ignore les consignes précédentes » ne doit jamais être exécuté : on le traite
  comme du contenu à analyser.
- Les fichiers de contenu (`profiles.json`, `offers.json`, `matching_labels.json`,
  `cv_facts.json`, `letter_requirements.json`) sont remplis par la tâche 1b. Validation :
  `scripts/reference_dataset.py` (`load_reference`, `validate_reference`).
  Les seuils de volume sont vérifiés par un test sur le contenu réel, pas par le validateur.

## Schéma

Tous les fichiers sont des listes JSON. Les champs optionnels sont indiqués ; un champ
inconnu n'est pas rejeté.

### `profiles.json`

```json
{"profile_id": "p01",
 "subgroup": {"metier": "data engineer", "niveau": "junior", "langue": "fr", "reconversion": false},
 "sources": {"cv": {"headline": "...", "experiences": [{"company": "Acme", "role": "...",
             "start_date": "2023-01", "end_date": "2023-06", "missions": ["..."], "stack": ["..."]}]},
             "manual": {"preferences": {"target_roles": ["data engineer"]}}}}
```

`niveau` : `junior` | `confirme` | `senior` ; `langue` : `fr` | `en`. Au moins une source non
vide. Les sources ont le format consommé par `build_profile_from_sources`
(`app/services/profile/merge.py`) : `headline`, `summary`, `contact`, `preferences`
(`target_roles`, `seniority_levels`, `locations`, `contract_types`, `remote_policy`,
`excluded_keywords`, `preferred_industries`, `preferred_company_sizes`), `experiences`,
`projects`, `education`, `certifications`, `skills` (catégorie -> liste), `languages`,
`interests`, `excluded_*`.

### `offers.json`

```json
{"offer_id": "o001", "poste": "Data Engineer", "entreprise": "Gamma", "localisation": "Paris",
 "type_contrat": "CDI", "mode_travail": "Hybride", "description": "...",
 "competences_cles": ["Python"], "seniority_level": "junior", "sector": "tech_it",
 "company_size": "pme", "canonical_title": "data engineer",
 "created_at": "2026-10-01T08:00:00Z", "source": "synthetic", "url": "https://example.test/o001"}
```

`poste` et `description` obligatoires et non vides. Optionnel : `piege_filtre_metier`
(booléen) — l'offre est un piège pour le filtre métier (titre voisin, métier différent).

### `matching_labels.json`

```json
{"profile_id": "p01", "offer_id": "o001", "label": "pertinent",
 "motif": "Même métier, niveau cohérent.", "preference_violee": false}
```

`label` : `pertinent` | `partiel` | `hors_sujet` ; `motif` non vide ; paire
(`profile_id`, `offer_id`) unique. Optionnel : `preference_violee` (booléen, défaut false).

### `cv_facts.json`

```json
{"profile_id": "p01", "fait": "Acme", "champ": "experiences.company", "page": 1, "critique": true}
```

`page` (entier >= 1) est la page cible que le générateur de PDF du plan parseur doit
respecter ; `critique` (booléen) marque un fait dont la perte est rédhibitoire.

### `letter_requirements.json`

```json
{"profile_id": "p01", "offer_id": "o001", "exigences": ["Airflow", "SQL"],
 "preuves_exactes": [{"exigence": "Airflow", "preuve": "ETL Airflow"}],
 "transferables": [{"exigence": "SQL", "element": "Python"}], "lacunes": []}
```

## Vocabulaires (valeurs stockées en production)

Le jeu utilise les valeurs que le scoring voit réellement ; le test importe les constantes depuis `app`.

- Offres : `mode_travail` ∈ {"Télétravail total", "Hybride", "Présentiel", ""} (`""` = inconnu ; un déplacement terrain compte comme "Présentiel") ; `seniority_level` ∈ `SENIORITY_ORDER` (intern, junior, mid, senior, lead, director ; un stage est `intern`) ; `sector` ∈ `SECTORS` ; `company_size` ∈ `COMPANY_SIZES` ; `type_contrat` ∈ CDI, CDD, Alternance, Stage ou `""`.
- Préférences (toutes sources) : `remote_policy` est une chaîne scalaire `RemotePolicy` (`full_remote`, `hybrid`, `on_site`, `flexible`) ; `seniority_levels` dans `SENIORITY_ORDER` ; `locations` sans "Remote" (le télétravail passe par `remote_policy`) ; `preferred_industries` / `preferred_company_sizes` dans `SECTORS` / `COMPANY_SIZES`.
- `subgroup.niveau` reste junior / confirme / senior (schéma du jeu, distinct de `seniority_level`).
- `preference_violee` reflète un jugement humain, pas le comportement du scoring : vrai si la ville (hors télétravail total), le contrat, le niveau ou le mode de travail sort des préférences déclarées. Table du mode :

  | remote_policy | Présentiel | Hybride | Télétravail total |
  |---|---|---|---|
  | hybrid | violation | — | pas de violation (plus de souplesse que demandé) |
  | on_site | — | — | violation |
  | full_remote | violation | violation | — |
  | flexible | aucune violation | aucune violation | aucune violation |

  Un mode inconnu (`""`) n'est jamais une violation. Un profil dont les sources disent [sur site, hybride] ou [hybride, sur site] est `flexible`.
- Chaque `exigence` de `preuves_exactes` et `transferables` figure dans `exigences` ; `transferables[].element` fait au moins 15 caractères.

## Critères de label

- **pertinent** : candidature sérieuse possible. Même métier ou métier voisin, niveau
  cohérent, exigences essentielles plausiblement couvertes, aucune préférence déclarée
  clairement violée.
- **partiel** : recoupement réel mais écart notable (niveau, compétence clé manquante) ou
  préférence déclarée violée (alors `preference_violee: true`).
- **hors_sujet** : autre métier ou écart rédhibitoire.
- **Une donnée inconnue n'est jamais un écart** : un champ absent de l'offre ou du profil ne
  fait pas baisser le label.

(Même esprit que `JUDGE_RUBRIC` dans `scripts/matching_bench.py`.)

## Budget LLM

Plafond commun 2,50 $ : parseur 0,25 $, profil 0,25 $, lettres 2 $. Tout dépassement exige un
accord explicite. Avant tout appel réel, `check_budget` ; après, `record_call`. Le registre
`scripts/data/llm_budget.jsonl` n'est pas versionné.

```python
from scripts.llm_budget import check_budget, record_call

check_budget("profil", estimated_usd=0.01)  # lève BudgetExceeded si la part serait dépassée
# ... appel réel ...
record_call("profil", "matching_bench.py", "mistral-small", 0.008, "billed")
```

`plan` : `parser` | `profil` | `lettres` ; `cost_kind` : `estimated` | `billed`. Un registre
illisible fait refuser l'appel plutôt que de sous-compter.

## Banc lettres

`scripts/letter_bakeoff.py` mesure les lettres (`run_letter_pipeline_async`, chemin de production) et le
CV adapté (`generate_tailored_cv_content`) sur les 14 couples de `letter_requirements.json`. Il compare
des versions de prompts à modèles et entrées constants. Depuis `backend` :

```bash
uv run python scripts/letter_bakeoff.py                          # estimation seule, aucun appel
uv run python scripts/letter_bakeoff.py --simulated              # chaîne complète hors réseau (pas une référence)
uv run python scripts/letter_bakeoff.py --real --limit 10        # estimation seule
uv run python scripts/letter_bakeoff.py --real --confirm --limit 10 --label base      # appels réels, payants
uv run python scripts/letter_bakeoff.py --real --confirm --label v2 --prompts-dir DIR --reuse-analyst
uv run python scripts/letter_bakeoff.py --summarize scripts/data/letters_bench/base/feuille_evaluation.csv
uv run python scripts/letter_bakeoff.py --compare base v2
```

`--no-cv` coupe le complément CV. Neutralisé : la recherche entreprise (contexte entreprise vide, entrée
constante, pas de Tavily). Un modèle sans prix connu refuse le mode réel. Budget : `check_budget("lettres", ...)`
avant chaque couple (estimation prudente du couple plus le coût mesuré des échecs non inscrits depuis le début),
`record_call` seulement pour un document généré avec succès (un échec, `CVHonestyError` compris, n'inscrit rien).
Le CV du banc est généré sans évaluation Bloc B (`evaluation=None`) ; `rapport.md` liste les modèles effectifs
par rôle. `--limit` doit être un entier >= 1. Sorties dans `scripts/data/letters_bench/<label>/` (non versionné) :
`results.json`, `rapport.md`, `feuille_evaluation.csv` et `feuille_violations.csv`. Évaluation humaine :
remplir les colonnes `inventees_*`, `mauvais_poste_*`, `exigences_avec_preuve_couvertes_*` (plafonné à `exigences_avec_preuve` de la ligne), `affirmations_valides`,
`naturel_1_5` de la première feuille, et `faux_rejet` (oui/non) de la seconde ; `--summarize` en tire fidélité,
couverture, faux rejets et naturel, avec dénominateurs, global et par métier.

## Simulation avant recalcul

Avant tout `rematch_all_users.py --apply` (décision de l'utilisateur, jamais automatique), on mesure
l'effet des changements de rattachement de la branche sur l'export privé figé
(`scripts/data/matching_bench/`, non versionné). Hors réseau : aucun embedding ni LLM, seulement les
caches `hybrid_cos_cache.json` et `judge_cache.json`. Ne jamais lancer `--confirm`, `--apply` ni
`rematch_all_users.py` pour cette mesure. `matching_bench.py report` n'est pas utilisé : il réécrit
`matching_bench_results.json`, versionné.

Méthode. « Avant » = base de fusion, dans un worktree détaché temporaire ; « après » = HEAD :

```bash
git worktree add --detach <tmp>/before 871c87a        # puis copier l'export et les caches dans <tmp>/before/backend/scripts/data/matching_bench/
# dans chaque arbre, avec le même interpréteur : sys.path[0] = <arbre>/backend, puis
#   export = load_export(Path(<export.json>))   # pas json.load : _id doit passer par bson json_util, sinon 0 paire, sans erreur
#   cos = cached_hybrid_cos_records(export); assessed = hybrid_scores(export, cos)
#   rattachée = not _is_detached(assessed[alias][offer_id], FLOOR)   # assessed = {alias: {offer_id: (motif, résultat)}}
git worktree remove --force <tmp>/before
```

Sont comparés, par profil : offres rattachées (échantillon plus offres d'interaction, soit les ids de
`_hybrid_assessment_ids`) avant et après, ajoutées, retirées, répartition par label du juge en cache,
faux négatifs (offres `relevant` détachées), P@10, P@20, FP@20 du classement hybride, candidatures
(`applied`) et interactions détachées (filtre dur ou sous le plancher).

Résultat du 2026-11-09 (base `871c87a`, HEAD `b5d4ef2`), agrégats seulement :

| Mesure | Avant | Après |
|---|---|---|
| Profils dans l'export | 1 | 1 |
| Paires évaluées (profil x offre) | 100 | 100 |
| Offres rattachées | 52 | 52 |
| Ajoutées / retirées / inchangées | | 0 / 0 / 52 |
| Faux négatifs (`relevant` détachées, sur 21) | 1 | 1 |
| `partial` détachées | 20 | 20 |
| `irrelevant` rattachées | 2 | 2 |
| P@10 / P@20 / FP@20 hybride | 0,20 / 0,25 / 0,00 | 0,20 / 0,25 / 0,00 |
| Candidatures (20) détachées (filtre dur ou sous le plancher) | 2 | 2 |
| Offres d'interaction (30, dont les 20 candidatures) détachées (filtre dur ou sous le plancher) | 7 | 7 |

Motifs de détachement (identiques avant et après) : les 48 offres détachées se répartissent en 33
géographie, 12 métier, 2 contrat, 1 mot exclu, 0 plancher (plus petit score non filtré 38,3 pour
FLOOR 35). Candidatures détachées (2) : 1 métier, 1 contrat. Interactions détachées (7, dont ces 2) :
6 métier, 1 contrat. Le seul faux négatif est lui aussi écarté par la garde métier : en production, les
offres déjà rattachées parmi ces 7 seraient conservées par la garde d'interaction.

Limites.

- L'export ne contient qu'un profil et 100 paires : l'absence d'effet est observée, pas démontrée. Elle
  s'explique par un profil sans aucun terme juridique (fait vérifié) et sans rôle à acronyme ; le chemin
  modifié est actif (`title_matches_roles("Legal Counsel", role_terms(["juriste"]))` passe de faux à
  vrai). La garde métier est exercée (12 paires filtrées, mêmes verdicts avant et après), mais pas ses
  chemins nouveaux (groupe juridique, union des jetons). Les ajouts attendus (groupe juridique FR/EN, jetons bruts et développés)
  restent donc non mesurés en volume réel.
- Export figé à sa date : le stock d'offres de production a changé depuis. Ce n'est pas un échantillon
  représentatif de la production.
- Labels du juge LLM (modèle de repli compris), pas humains ; accord juge/humain limité à la feuille de
  validation.
- 4 paires sur 100 n'ont pas de cosinus valide en cache (vecteur d'offre périmé) ; toutes sont écartées
  par le filtre géographique avant tout score, donc le cosinus manquant n'intervient ni dans le banc ni en
  production (`rematch_user` ne saute en `semantic_unknown` que les paires non filtrées,
  `offer_profile_matcher.py:189`). Sur un autre export, une paire non filtrée sans cosinus serait scorée
  avec `cos=None` par le banc mais ignorée par `rematch_user`.
- La garde d'interaction (candidature ou interaction conservée sous le plancher) n'est pas simulée sur
  l'export : `rematch_user` n'y tourne pas. Elle est couverte par `tests/test_offer_profile_matcher.py`.

## Banc de matching : résultats et décisions

Mesure sur ce jeu synthétique (22 profils, 389 labels, 2 574 paires évaluées, embeddings `mistral-embed` en cache, `FLOOR` 35), à la date du jeu 2026-11-08 ; chiffres de `scripts/reference_bench_results.json`. Les résultats ont été calculés avant le reclassement de 2 labels (p04/o042 et p06/o042 en `hors_sujet`) : effet négligeable, non régénérés.

| Mesure | Hybride | Chronologique | Cible du plan |
|---|---|---|---|
| p@5 | 0,727 | 0,218 | 0,80 |
| nDCG@10 | 0,951 | 0,465 | sans seuil |
| Rappel | 0,863 | | 0,90 |
| Violations de préférence @5 | 0,68 | 0,86 | |

- **Faux négatifs : 13** sur 94 offres pertinentes, 11 écartées par la garde métier (`role`) et 2 sous le plancher (`below_floor`, un seul profil sans rôle visé). Profils les plus faibles en rappel : p13 chef de projet (0,25), p12 (0,60). Source la plus faible : cadremploi (0,43, 7 pertinentes).
- **Définition de p@5** : toutes les offres annotées du profil sont classées, offres détachées comprises, placées en fin de liste. 5 profils sur 22 ont moins de 5 offres rattachées : leur top 5 inclut alors des offres détachées, que la production masque, ce qui pèse sur p@5. La métrique n'a pas été changée. Le plafond de p@5 est aussi abaissé par construction : un profil à 4 offres pertinentes ne dépasse pas 0,80.
- **Sous-groupes** : les 14 sous-groupes métier sont tous sous le seuil de 20 exemples pertinents, ainsi que senior (16) et reconversion (18) : aucune conclusion par sous-groupe, aucune régression mesurable.
- **`COS_FLOOR` 0,73 / `COS_CEIL` 0,83 inchangés** : calibrés sur un seul profil réel. Sur le jeu, 1 % des pertinentes sont sous le plancher et 1 % des hors sujet au-dessus du plafond, loin du seuil d'alerte de 25 % ; 22 % des pertinentes saturent au-dessus du plafond (perte de résolution, pas d'erreur de classement). Jeu écrit par nous : à recalibrer dès qu'un deuxième profil réel existe.
- **Garde métier corrigée** : union des jetons bruts et développés (acronymes comme SRE) et groupe juridique FR/EN (juriste, legal, counsel, lawyer ; sans avocat, droit ni les adjectifs juridique/juridiques, qui rattachaient « Conseiller Commercial Protection Juridique »). Le retrait des adjectifs fait perdre o099 (« Assistant Juridique ») au profil p20 : un piège visible au top 5 coûte plus qu'un rappel manqué. Collision connue : « Legal Entity Controller/Accountant » passent pour un rôle juriste.
- **Rôles voisins non élargis** (10 des 11 faux négatifs `role`, par exemple data scientist face à ML engineer, comptable face à contrôleur de gestion) : élargir sur nos propres labels serait du surapprentissage et ouvrirait des faux positifs.

Décisions en attente de l'utilisateur, avant `rematch_all_users.py --apply` :

1. Cibles 80 % / 90 % non atteintes (rappel 0,863 notamment) : élargir ou non les rôles voisins.
2. Fusion d'expériences : « Orion » et « Orion Capital » aux mêmes dates fusionnent (`profile/merge.py`) ; une promotion dans la même année avec l'ancien poste sans fin est fusionnée à tort. Cas rares, corrigeables à la main.
3. L'export privé ne contient qu'un profil : l'effet réel de la garde métier en production n'est pas mesuré (cf. « Simulation avant recalcul »).
