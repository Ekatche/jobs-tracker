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
 "type_contrat": "CDI", "mode_travail": "hybride", "description": "...",
 "competences_cles": ["Python"], "seniority_level": "junior", "sector": "tech",
 "company_size": "50-200", "canonical_title": "data engineer",
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
