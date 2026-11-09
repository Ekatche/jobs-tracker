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
  `scripts/reference_dataset.py` (`load_reference`, `validate_reference`, `coverage_report`).
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
#   cos = cached_hybrid_cos_records(export); assessed = hybrid_scores(export, cos)
#   rattachée = not _is_detached(assessed[offer_id], FLOOR)
git worktree remove --force <tmp>/before
```

Sont comparés, par profil : offres rattachées (échantillon plus offres d'interaction, soit les ids de
`_hybrid_assessment_ids`) avant et après, ajoutées, retirées, répartition par label du juge en cache,
faux négatifs (offres `relevant` détachées), P@10, P@20, FP@20 du classement hybride, candidatures
(`applied`) et interactions sous le plancher.

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
| Candidatures (20) sous le plancher | 2 | 2 |
| Offres d'interaction (30) sous le plancher | 7 | 7 |

Limites.

- L'export ne contient qu'un profil et 100 paires : l'absence d'effet est observée, pas démontrée. Elle
  s'explique si le profil n'est pas juridique et n'a pas de rôle à acronyme ; le chemin modifié est
  actif (`title_matches_roles("Legal Counsel", role_terms(["juriste"]))` passe de faux à vrai), mais
  l'export ne l'exerce pas. Les ajouts attendus (groupe juridique FR/EN, jetons bruts et développés)
  restent donc non mesurés en volume réel.
- Export figé à sa date : le stock d'offres de production a changé depuis. Ce n'est pas un échantillon
  représentatif de la production.
- Labels du juge LLM (modèle de repli compris), pas humains ; accord juge/humain limité à la feuille de
  validation.
- 4 paires sur 100 ont un vecteur d'offre en cache périmé (texte d'embedding modifié depuis) : elles sont
  scorées avec `cos=None`, de façon identique avant et après, donc sans effet sur la comparaison, mais les
  chiffres absolus sont légèrement biaisés tant que `embed --confirm` n'a pas été relancé (dépense, à
  l'utilisateur).
- La garde d'interaction (candidature ou interaction conservée sous le plancher) n'est pas simulée sur
  l'export : `rematch_user` n'y tourne pas. Elle est couverte par `tests/test_offer_profile_matcher.py`.
