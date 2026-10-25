# Score de pertinence hybride — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal :** chaque offre du stock reçoit, pour chaque utilisateur, un score de pertinence (0 à 100) qui remplace le rattachement par `source_query` : sous `FLOOR`, l'offre est détachée. Décision de la porte (Task 5) : le score sert de **filtre seul**. La liste reste chronologique par défaut, le tri par pertinence est une option, et aucune offre n'est repliée ni badgée par niveau.

**Architecture :** un paquet `app/services/offer_scoring/` porte les constantes, le score pur, le filtre dur, les conditions géographiques et contractuelles, le référentiel ville → départements et le cache d'embeddings `offer_embeddings`. Le banc de mesure (`scripts/matching_bench.py`) classe d'abord les offres avec ces fonctions ; la porte décide de la suite. Ensuite seulement, `offer_profile_matcher.py` écrit `offer_relevance` et rattache par score, le routeur propose le tri par pertinence et expose les conditions non remplies par un `$lookup`, et `offers/page.tsx` affiche le sélecteur de tri, les conditions non remplies et les filtres secteur et taille.

**Tech Stack :** FastAPI, Motor (MongoDB `mongo:latest`), Pydantic v2, LiteLLM (`aembedding`, `mistral/mistral-embed`), pytest (`asyncio_mode = auto`), Next.js 15 / React / TypeScript, Tailwind.

**Spec :** `docs/superpowers/specs/2026-10-24-matching-hybrid-scoring-and-sectors-design.md`, étapes 3 à 5 du Lot 1 (§7). Sections utiles : §3.2 (`offer_embeddings`, `offer_relevance`), §4.2 à §4.6 (score), §5.2 (UI), §6.2 à §6.4 (critère, métriques, tests).

## Constat du banc (simulation hors réseau du 2026-10-25)

Simulation du score complet (§4.2 à §4.5) sur les 70 offres de l'échantillon, avec les cosinus `mistral-embed` déjà calculés (1 profil, juge `gpt-6.1-sol` sur 93 paires et `mistral-large-2512` sur 7) :

- **Ce qui est fiable : séparer l'adapté du hors-sujet.** FP@20 = 0 ; le Top 20 ne contient que des offres `relevant` ou `partial`. Avec `FLOOR = 30`, 21 offres `irrelevant` sur 26 sont détachées, aucune `relevant` ni aucune offre postulée n'est perdue, une `partial` l'est. Les 20 offres postulées ont toutes un score ≥ 50. AUC du cosinus seul, (`relevant` + `partial`) contre `irrelevant` : 0.957.
- **Ce qui ne l'est pas : classer finement les `relevant` devant les `partial`.** P@10 hybride de 0.10 à 0.20 selon le traitement de la séniorité, contre 0.20 en chronologique ; le critère du §6.2 (chronologique + 0.2, soit 0.40) n'est pas atteint ; le Two-Pass atteint 0.40. Causes : `competences_cles` renseignée sur 3 offres sur 70, la composante de 30 points vaut donc presque toujours 15 ; séniorité connue sur 28 offres sur 70 ; les `partial` sont surtout des postes senior ou lead. Le score tient entre 17.6 et 82.4 : un badge « forte » irait surtout à des `partial`.
- **Puissance statistique faible :** 1 profil, 8 `relevant` dans l'échantillon ; une offre de plus ou de moins déplace P@10 de 0.1. Les 20 labels humains (étape 7 du plan du banc) ne sont pas faits : l'accord du juge n'est pas mesuré.

D'où la Task 5 : une porte à deux niveaux, puis un arrêt pour la décision de l'utilisateur, avant toute exposition du score.

## Global Constraints

- Modèle d'embedding du score : `mistral/mistral-embed`, constante `EMBEDDING_MODEL` du module `offer_scoring/constants.py`. `domain_relevance.EMBEDDING_MODEL` (`text-embedding-3-small`) reste inchangé.
- Bornes sémantiques : `COS_FLOOR = 0.73`, `COS_CEIL = 0.83`. Texte de l'offre : `expand_title_acronyms(poste) + ". " + 1000 premiers caractères de la description` (espaces compressés), sans `competences_cles`. Vecteur profil : `build_candidate_identity(headline, target_roles)` passé par `expand_title_acronyms`.
- Poids : sémantique 45, compétences 30, séniorité 10, secteur 10, taille 5. Seuils : `STRONG_THRESHOLD = 75`, `MEDIUM_THRESHOLD = 60`, `FLOOR = 35` (décision de la porte ; 20 au départ), `CAP_SCORE = MEDIUM_THRESHOLD - 1`. `SCORING_VERSION = "1"`. Toutes ces valeurs vivent dans `offer_scoring/constants.py` et nulle part ailleurs.
- Composante compétences (décision de la porte) : une compétence de l'offre compte si elle apparaît, avec des frontières de mot, dans une compétence du profil (« python » dans « python scikit learn »). Quand l'offre liste des compétences, la composante ne descend jamais sous `W_SKILLS / 2` : un profil incomplet ne pénalise pas une offre.
- Règle unique de l'inconnu (§4.3) : une composante applicable dont l'offre ne renseigne pas la donnée reçoit la moitié de ses points. Une composante dont le candidat n'a pas exprimé la préférence sort du dénominateur.
- Interprétation retenue (spec muette) : un candidat sans `contract_types` n'exclut pas les stages et alternances ; un candidat sans composante applicable (ni identité, ni compétences, ni préférence) ne reçoit aucun score et rien ne lui est rattaché, comme aujourd'hui (`offer_matches_criteria` ne rattachait rien à un profil vide).
- Écart assumé avec le §3.2 : `offer_relevance` porte en plus `unknown_components: List[str]`, sans coder des booléens dans `breakdown`. Ce champ est stocké mais pas affiché dans le Lot 1 (décision de la porte : pas de tooltip de score).
- Écart assumé avec le §5.2 (décision de la porte) : pas de badge de niveau, pas de section repliée, tri chronologique par défaut. Le niveau reste calculé et stocké dans `offer_relevance`.
- Rien de propre à un utilisateur n'est écrit dans `job_offers`, ni score ni embedding.
- Production : aucune écriture par l'implémenteur. `scripts/rematch_all_users.py` se lance en lecture d'abord ; `--apply` en prod revient à l'utilisateur. `MISTRAL_API_KEY` en prod : à vérifier par l'utilisateur (empreinte seulement, jamais la valeur).
- Dépense : tout appel d'embedding réel exige l'accord explicite de l'utilisateur ; le banc appelle l'API seulement avec `--confirm`. Repère : 0,1 $ par million de tokens, environ 0,03 $ pour 1 000 offres.
- Tests sans réseau : embeddings injectés, jamais d'appel LiteLLM réel. Écart assumé avec le §6.4 (« sans base externe ») : les tests d'API de la Task 7 utilisent la base Mongo de test locale (`conftest.py`, port 27018), comme `test_applied_offer_retention.py`, car un `$lookup` ne se simule pas avec une base factice ; ils sont marqués `skipif` quand cette base ne répond pas (ping `pymongo`, 2 s), pour que la suite par défaut passe sans elle. La ségrégation par utilisateur a en plus un test pur, sans base. Commande : `cd backend && uv run pytest tests/<fichier> -v` (jamais `pytest` sans chemin). Frontend : `cd frontend && npm run lint && npm run build`.
- Précondition du §5, avant les Tasks 7 et 8 : `git status --short backend/app/routers/job_offers.py frontend/src/app/offers/page.tsx frontend/src/components/profile/TargetingPreferencesSection.tsx frontend/src/types/coverLetter.ts frontend/src/lib/api.ts` ne liste rien. Sinon : arrêt, demander à l'utilisateur.
- `frontend/src/lib/api.ts` : ne toucher qu'à `JobOffer`, `JobOfferFilter` et `jobOffersApi` (le reste du fichier relève des chemins STAR). Chemins STAR interdits : `interview_prep_service.py`, `routers/interview_prep.py`, `star_*`, `frontend/src/components/interview/*`, `frontend/src/types/interview.ts`.
- Commits : seulement si l'utilisateur les a autorisés pour cette exécution, `git add` avec des chemins explicites.

## Review Focus

1. **Mot exclu court ou accentué** (`excluded_keywords` = « ENS », « Télévente ») : il exclut « Stage ENS Lyon » mais jamais « Ensemble », « sens » ni « Responsable ». Test : Task 3, `test_hard_filter_excluded_keyword_needs_word_boundary`.
2. **API d'embedding indisponible** (clé absente en prod, 429, timeout) pendant un rematch : aucune exception, composante sémantique à la moitié, offres rattachées par les autres composantes, aucun détachement massif. Test : Task 6, `test_rematch_user_embedding_down_detaches_nothing_new`.
3. **Garde d'interaction avec des identifiants hétérogènes** (`applications.user_id` en `str` ou en `ObjectId`, `offer_id` en `str`) : une offre postulée sous `FLOOR` reste rattachée et elle est journalisée. Test : Task 6, `test_rematch_user_keeps_applied_offer_below_floor`.
4. **Vecteurs de modèles différents ou texte modifié** dans `offer_embeddings` : un vecteur d'un autre `model` ou d'un `text_hash` périmé n'est jamais utilisé, l'offre est réembarquée. Test : Task 2, `test_get_offer_vectors_ignores_other_model_and_stale_hash`.
5. **Ville ou zone absente du référentiel** (« La Défense », « St.-Denis », « Remote ») côté offre ou côté profil : pas de plafond (fail-open). Test : Task 3, `test_geo_unresolved_location_never_fails`.

---

## Structure des fichiers

| Fichier | Rôle |
|---|---|
| `backend/app/services/offer_scoring/__init__.py` (créé, vide) | Paquet |
| `backend/app/services/offer_scoring/constants.py` (créé) | Constantes calibrées, `SCORING_VERSION`, modèle d'embedding |
| `backend/app/services/offer_scoring/score.py` (créé) | Composantes, IDF, combinaison, niveaux, `ProfileFeatures` |
| `backend/app/services/offer_scoring/embeddings.py` (créé) | Texte embarqué, cache `offer_embeddings`, vecteur profil |
| `backend/app/services/offer_scoring/geo.py` (créé) | Référentiel ville / département / région → départements |
| `backend/app/services/offer_scoring/assess.py` (créé) | Filtre dur, conditions, `assess_offer` |
| `backend/app/data/communes_departements.json` (créé, généré) | Référentiel statique |
| `backend/scripts/build_communes_index.py` (créé) | Génération du référentiel depuis `geo.api.gouv.fr` |
| `backend/app/services/evaluation/domain_relevance.py` (modifié) | Acronymes |
| `backend/app/database.py`, `backend/main.py` (modifiés) | `create_offer_scoring_indexes` |
| `backend/scripts/matching_bench.py` (modifié) | Classement `hybrid`, commande `embed`, calibrage |
| `backend/app/services/offer_profile_matcher.py` (réécrit) | Rattachement par score, `offer_relevance`, garde d'interaction |
| `backend/scripts/rematch_all_users.py` (créé) | Rattrapage du stock en prod |
| `backend/app/routers/cover_letters.py` (modifié) | Champs qui déclenchent le rematch |
| `backend/app/routers/job_offers.py`, `backend/app/models.py` (modifiés) | Tri optionnel par pertinence, filtres, champs de réponse |
| `frontend/src/lib/companyTaxonomy.ts` (créé) | Options secteurs et tailles partagées |
| `frontend/src/lib/api.ts`, `frontend/src/app/offers/page.tsx`, `frontend/src/components/profile/TargetingPreferencesSection.tsx` (modifiés) | Types, sélecteur de tri, conditions non remplies, filtres |
| `backend/tests/test_hybrid_scoring.py`, `test_offer_scoring_embeddings.py`, `test_offer_scoring_assess.py`, `test_job_offers_relevance_api.py` (créés) ; `test_matching_bench.py`, `test_offer_profile_matcher.py`, `test_domain_relevance.py`, `test_database_indexes.py` (modifiés) | Tests |

---

### Task 1 : Constantes et score pur

**Files:**
- Create: `backend/app/services/offer_scoring/__init__.py`, `backend/app/services/offer_scoring/constants.py`, `backend/app/services/offer_scoring/score.py`
- Test: `backend/tests/test_hybrid_scoring.py`

**Interfaces:**
- Consumes : `SENIORITY_ORDER` (`app/services/evaluation/offer_fit.py:15`), `normalize_text` (`app/services/relevance.py:21`).
- Produces :
  - `constants.py` : `SCORING_VERSION`, `EMBEDDING_MODEL`, `EMBED_BATCH = 16`, `DESCRIPTION_CHARS = 1000`, `COS_FLOOR`, `COS_CEIL`, `W_SEMANTIC = 45`, `W_SKILLS = 30`, `W_SENIORITY = 10`, `W_SECTOR = 10`, `W_SIZE = 5`, `STRONG_THRESHOLD`, `MEDIUM_THRESHOLD`, `FLOOR`, `CAP_SCORE`.
  - `class ComponentPoints(NamedTuple): points: float; max_points: float; known: bool`
  - `@dataclass(frozen=True) class ScoreResult: score: float; raw_score: float; level: str; breakdown: dict[str, float]; unknown_components: list[str]; failed_conditions: list[str]` — `breakdown` a les clés `<composante>` et `<composante>_max` pour chaque composante applicable, plus `raw_score`. Noms de composantes : `semantic`, `skills`, `seniority`, `sector`, `size`.
  - `class SkillIdf` avec `weight(skill: str) -> float` ; `build_skill_idf(skill_lists: Iterable[Sequence[str]]) -> SkillIdf`.
  - `semantic_points(cos: Optional[float]) -> ComponentPoints`
  - `skill_points(offer_skills: Sequence[str], candidate_skills: frozenset[str], idf: SkillIdf) -> Optional[ComponentPoints]`
  - `seniority_points(offer_level: Optional[str], wanted: Sequence[str]) -> Optional[ComponentPoints]`
  - `preference_points(value: Optional[str], preferred: Sequence[str], weight: float) -> Optional[ComponentPoints]`
  - `combine(components: dict[str, Optional[ComponentPoints]], failed_conditions: Sequence[str]) -> Optional[ScoreResult]`
  - `level_for(score: float) -> str`
  - `@dataclass(frozen=True) class ProfileFeatures: identity: str; skills: frozenset[str]; seniority_levels: tuple[str, ...]; preferred_industries: tuple[str, ...]; preferred_company_sizes: tuple[str, ...]; preferences: dict` ; `profile_features(profile: dict) -> ProfileFeatures` (lit `headline`, `skills` aplatis et passés par `normalize_text`, `preferences`).

- [ ] **Step 1 : écrire les tests qui échouent** dans `backend/tests/test_hybrid_scoring.py`

- `test_semantic_points_clamped` : `semantic_points(0.70).points == 0`, `semantic_points(0.78).points == pytest.approx(22.5)`, `semantic_points(0.90).points == 45`, `semantic_points(None) == ComponentPoints(22.5, 45, False)`.
- `test_skill_points_idf_weighted` : `idf = build_skill_idf([["Python", "SQL"], ["python"], ["Python"]])` ; `skill_points(["Python", "SQL"], frozenset({"sql"}), idf).points == pytest.approx(30 * 1.6931 / 2.6931, rel=1e-3)` (IDF = `log((1 + N) / (1 + df)) + 1`, compétences comparées après `normalize_text`).
- `test_skill_points_unknown_and_not_applicable` : offre sans compétences → `ComponentPoints(15, 30, False)` ; candidat sans compétences → `None`.
- `test_seniority_points` : `("senior", ["senior"])` → 10 ; `("lead", ["senior"])` → 6 ; `("junior", ["senior"])` → 0 ; `(None, ["senior"])` → `ComponentPoints(5, 10, False)` ; `("senior", [])` → `None`.
- `test_preference_points` : secteur dans la liste → 10, connu et différent → 0, `None` → 5 (inconnu), liste vide → `None` ; taille : 5 / 0 / 2.5.
- `test_score_normalizes_by_applicable_points` : `combine({"semantic": ComponentPoints(45, 45, True), "skills": ComponentPoints(30, 30, True), "seniority": None, "sector": None, "size": None}, [])` → `score == 100`, `level == "strong"`.
- `test_unknown_components_give_half_score` : les cinq composantes à leur moitié inconnue → `score == 50`, `unknown_components == ["semantic", "skills", "seniority", "sector", "size"]`.
- `test_failed_condition_caps_score` : composantes à 90/100 et `["geo"]` → `score == CAP_SCORE`, `level == "weak"`, `breakdown["raw_score"] == pytest.approx(90)`, `failed_conditions == ["geo"]` ; un score brut de 40 avec `["contract"]` reste 40.
- `test_level_thresholds` : 75 → `strong`, 74.99 → `medium`, 60 → `medium`, 59.99 → `weak`, 0 → `weak`.
- `test_no_applicable_component_returns_none` : toutes les composantes à `None` → `None`.
- `test_profile_features_flattens_skills` : `{"headline": "AI Engineer", "skills": {"langages": ["Python"], "outils": ["Docker"]}, "preferences": {"target_roles": ["ML Engineer"], "seniority_levels": ["senior", "inconnu"]}}` → `skills == frozenset({"python", "docker"})`, `seniority_levels == ("senior",)` (valeurs hors `SENIORITY_ORDER` écartées), `identity` non vide.

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_hybrid_scoring.py -v`
Attendu : FAIL, `ModuleNotFoundError: app.services.offer_scoring`.

- [ ] **Step 3 : implémenter** `constants.py` puis `score.py` avec les signatures ci-dessus. `combine` : `raw = 100 × Σ points / Σ max_points` sur les composantes non `None`, borné à [0, 100] ; `score = min(raw, CAP_SCORE)` si `failed_conditions` est non vide. `profile_features` calcule `identity = expand_title_acronyms(build_candidate_identity(headline, target_roles))` — cet import de `domain_relevance` reste valable après la Task 2.

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_hybrid_scoring.py -v`
Attendu : PASS.

- [ ] **Step 5 : commit** (si autorisé) — `feat(scoring): add hybrid relevance score constants and pure scoring`

---

### Task 2 : Texte embarqué, acronymes et cache `offer_embeddings`

**Files:**
- Modify: `backend/app/services/evaluation/domain_relevance.py:24-32`
- Create: `backend/app/services/offer_scoring/embeddings.py`
- Modify: `backend/app/database.py` (après `create_company_profiles_indexes`, l. 106), `backend/main.py` (imports l. 15-17, appels du lifespan l. 49-61)
- Test: `backend/tests/test_offer_scoring_embeddings.py`, `backend/tests/test_domain_relevance.py`, `backend/tests/test_database_indexes.py`

**Interfaces:**
- Consumes : `EMBEDDING_MODEL`, `EMBED_BATCH`, `DESCRIPTION_CHARS` (Task 1) ; `cosine_similarity` (`app/services/role_normalizer.py`).
- Produces :
  - `offer_embedding_text(offer: dict) -> Optional[str]` : `None` si `poste` est vide ou vaut « Non spécifié » **et** que la description est vide.
  - `text_hash(text: str) -> str` (SHA-256 hexadécimal).
  - `async def embed_texts(texts: list[str]) -> list[list[float]]` : `litellm.aembedding(model=EMBEDDING_MODEL, ...)` par lots de `EMBED_BATCH` ; lève en cas d'erreur.
  - `async def get_offer_vectors(offers: list[dict], db, *, embed=embed_texts, cache: bool = True) -> dict[str, list[float]]` : clé `str(offer["_id"])` ; lit `offer_embeddings` (`{offer_id, model}`), n'utilise que `model == EMBEDDING_MODEL` et `text_hash` identique, embarque le reste, écrit le cache si `cache`. Fail-open : en cas d'erreur d'`embed`, renvoie les vecteurs déjà en cache, journalise un avertissement, ne lève jamais.
  - `async def get_profile_vector(identity: str, *, embed=embed_texts) -> Optional[list[float]]` : `None` si `identity` est vide ou si `embed` échoue.
  - `async def create_offer_scoring_indexes(db) -> None` dans `database.py` : `offer_embeddings` unique `[("offer_id", 1), ("model", 1)]`.

- [ ] **Step 1 : écrire les tests qui échouent**

`test_domain_relevance.py`, `test_expand_title_acronyms_extended` paramétré :

| Entrée | Attendu |
|---|---|
| `"Senior PO"` | `"Senior Product Owner"` |
| `"ML Engineer"` | `"Machine Learning Engineer"` |
| `"Data Analyst BI"` | `"Data Analyst Business Intelligence"` |
| `"SRE / DevOps"` | `"Site Reliability Engineer / DevOps"` |
| `"QA Engineer"` | `"Quality Assurance Engineer"` |
| `"PM Data"` | `"Product Manager Data"` |
| `"DS confirmé"` | `"Data Scientist confirmé"` |
| `"DE Spark"` | `"Data Engineer Spark"` |
| `"Chef de projet"` | inchangé |
| `"CHEF DE PROJET DA"` | inchangé (texte tout en majuscules : aucun acronyme sensible à la casse) |
| `"Développeur Confirmé Ia"` | `"Développeur Confirmé intelligence artificielle"` (comportement actuel conservé) |

`DA` n'est pas développé : en français il désigne souvent un directeur artistique.

`test_offer_scoring_embeddings.py` (base factice : un dict de collections en mémoire avec `find`, `bulk_write` ou `update_one`, sur le modèle de `FakeCollection` de `tests/test_offer_sources.py:332` ; `embed` factice qui compte ses appels) :
- `test_offer_embedding_text_excludes_competences_cles` : offre avec `competences_cles=["Kubernetes"]` absent de la description → `"Kubernetes" not in text`.
- `test_offer_embedding_text_truncates_and_collapses_spaces` : description de 3 000 caractères avec retours à la ligne → texte = `"<poste>. "` + 1 000 caractères, sans `"\n"` ni double espace.
- `test_offer_embedding_text_empty_offer_is_none` : `{"poste": "Non spécifié", "description": None}` → `None` ; `get_offer_vectors` n'appelle pas `embed` pour elle.
- `test_get_offer_vectors_uses_cache_and_embeds_only_missing` : deux offres, une en cache (même modèle, même hash) → `embed` appelé une fois avec un seul texte ; le cache contient ensuite deux documents.
- `test_get_offer_vectors_ignores_other_model_and_stale_hash` : un document `model="text-embedding-3-small"` et un document au `text_hash` différent → les deux offres sont réembarquées ; l'ancien document de l'autre modèle n'est ni lu ni écrasé.
- `test_get_offer_vectors_fail_open` : `embed` lève `RuntimeError` → renvoie seulement les vecteurs en cache, sans exception.
- `test_get_offer_vectors_no_cache_write_when_cache_false`.

`test_database_indexes.py` : `create_offer_scoring_indexes` crée l'index unique `offer_id_1_model_1` (même forme que le test existant de `create_company_profiles_indexes`).

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_domain_relevance.py tests/test_offer_scoring_embeddings.py tests/test_database_indexes.py -v`
Attendu : FAIL (acronymes non développés, module `embeddings` absent).

- [ ] **Step 3 : implémenter**

`ACRONYM_EXPANSIONS` garde l'entrée `ia` insensible à la casse ; une seconde liste `CASE_SENSITIVE_ACRONYMS` porte `PM`, `PO`, `ML`, `QA`, `SRE`, `BI`, `DE`, `DS` (motif `\bXX\b` sans `re.I`) et n'est appliquée que si `not title.isupper()`. `expand_title_acronyms` garde sa signature. Ce changement touche aussi `compute_domain_relevance` (pré-filtre du Two-Pass) : effet attendu, une meilleure similarité sur ces intitulés.

`get_offer_vectors` écrit avec un upsert par `{offer_id, model}` (`$set` de `text_hash`, `vector`, `updated_at`).

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_domain_relevance.py tests/test_offer_scoring_embeddings.py tests/test_database_indexes.py tests/test_hybrid_scoring.py -v`
Attendu : PASS.

- [ ] **Step 5 : commit** (si autorisé) — `feat(scoring): cache offer embeddings and expand common job acronyms`

---

### Task 3 : Filtre dur, conditions et référentiel géographique

**Files:**
- Create: `backend/scripts/build_communes_index.py`, `backend/app/data/communes_departements.json` (généré), `backend/app/services/offer_scoring/geo.py`, `backend/app/services/offer_scoring/assess.py`
- Test: `backend/tests/test_offer_scoring_assess.py`

**Interfaces:**
- Consumes : `contains_keyword`, `normalize_text` (`relevance.py`) ; `detect_contract_type` (`normalization.py:578`), `normalize_city` (`normalization.py:31`) ; `normalize_contract` (`offer_fit.py:28`) ; tout le Task 1 ; `offer_embedding_text` n'est pas utilisé ici.
- Produces :
  - `departments_for_location(text: Optional[str]) -> frozenset[str]` : vide si inconnu.
  - `hard_filter_reason(offer: dict, features: ProfileFeatures) -> Optional[str]` : `"excluded_keyword"`, `"contract"` ou `None`.
  - `failed_conditions(offer: dict, features: ProfileFeatures) -> list[str]` : sous-ensemble ordonné de `["geo", "contract"]`.
  - `assess_offer(offer: dict, features: ProfileFeatures, cos: Optional[float], idf: SkillIdf) -> tuple[Optional[str], Optional[ScoreResult]]` : `(raison du filtre, None)` si filtrée ; sinon `(None, combine(...))`, qui peut valoir `None` (aucune composante applicable). Lit `competences_cles`, `seniority_level`, `sector`, `company_size` sur l'offre.

- [ ] **Step 1 : générer le référentiel**

`build_communes_index.py` lit `https://geo.api.gouv.fr/communes?fields=nom,codeDepartement&format=json` (vérifié le 2026-10-25 : 34 969 communes, sans clé), `https://geo.api.gouv.fr/departements?fields=nom,code,codeRegion` et `https://geo.api.gouv.fr/regions`. Il écrit `{clé normalize_text(nom): [codes départements triés]}` pour les communes (homonymes fusionnés : « saint denis » → `["11", "30", "93", "974"]`), les noms de départements et les noms de régions (« ile de france » → les 8 départements). Données publiques sous Licence Ouverte : mentionner la source et la date dans une clé `_source` du JSON.

Run : `cd backend && uv run python scripts/build_communes_index.py`
Attendu : le fichier existe, `"lyon": ["69"]`, `"paris": ["75"]`, `"auvergne rhone alpes"` liste 12 départements.

- [ ] **Step 2 : écrire les tests qui échouent** dans `backend/tests/test_offer_scoring_assess.py`

`test_departments_for_location` paramétré : `"Lyon"` → `{"69"}` ; `"Lyon, Auvergne-Rhône-Alpes"` → `{"69"}` (premier segment avant la virgule) ; `"69003 Lyon"` → `{"69"}` ; `"Villeurbanne (69)"` → `{"69"}` ; `"Paris 15e"` → `{"75"}` ; `"Île-de-France"` → 8 départements ; `"Ajaccio"` → `{"2A"}` ; `"La Défense"`, `"Remote"`, `"Non spécifié"`, `""`, `None` → vide. Ordre de résolution : code postal à 5 chiffres (2 premiers chiffres, 3 pour `97x`, `{"2A", "2B"}` pour `20`), puis code entre parenthèses, puis nom.

Filtre dur :
- `test_hard_filter_excluded_keyword_needs_word_boundary` : `excluded_keywords=["ENS"]` exclut `"Stage ENS Lyon"`, pas `"Ensemble"`, `"sens du service"` ni `"Responsable"` ; `["Télévente"]` exclut `"Conseiller televente"`.
- `test_hard_filter_internship_without_wish` : offre `type_contrat="Stage"` et candidat `contract_types=["CDI"]` → `"contract"` ; candidat `["CDI", "Stage"]` → `None` ; candidat `[]` → `None`.

Conditions (candidat `locations=["Lyon"]`, `remote_policy="hybrid"`, `contract_types=["CDI"]` sauf mention) :
- `test_geo_same_department_passes` : offre à Villeurbanne → `[]`.
- `test_geo_other_department_fails` : offre à Nantes → `["geo"]`.
- `test_geo_full_remote_offer_passes_unless_on_site` : offre à Nantes en « Télétravail total » → `[]` ; même offre, candidat `on_site` → `["geo"]`.
- `test_geo_full_remote_candidate` : candidat `full_remote`, offre à Lyon en « Présentiel » → `["geo"]` ; offre en « Télétravail total » → `[]` ; offre au mode inconnu → `[]`.
- `test_geo_unresolved_location_never_fails` : offre à « La Défense » → `[]` ; candidat `locations=["St.-Denis"]` (non résolu) face à une offre à Nantes → `[]` ; candidat sans `locations` → `[]`.
- `test_contract_condition` : offre CDD → `["contract"]` ; contrat inconnu → `[]` ; candidat sans `contract_types` → `[]`.

Assemblage :
- `test_assess_offer_capped_offer_keeps_raw_score` : offre adaptée à Nantes (cos 0.83) → `(None, result)` avec `result.failed_conditions == ["geo"]`, `result.score == CAP_SCORE`, `result.breakdown["raw_score"] > CAP_SCORE`.
- `test_assess_offer_filtered_returns_reason` : stage non souhaité → `("contract", None)`.

- [ ] **Step 3 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_offer_scoring_assess.py -v`
Attendu : FAIL, `ModuleNotFoundError: app.services.offer_scoring.geo`.

- [ ] **Step 4 : implémenter** `geo.py` (référentiel chargé une fois, `functools.lru_cache` sur le chargement) et `assess.py`. Condition `geo` : sans `locations`, remplie ; mode de l'offre « Télétravail total » et `remote_policy != "on_site"`, remplie ; candidat `full_remote` : remplie seulement si l'offre est en télétravail total, ou si son mode est inconnu ; départements de l'offre vides ou une location du profil non résolue : remplie ; sinon intersection non vide des départements. Condition `contract` : `normalize_contract(detect_contract_type(type_contrat, poste, description))` non `None` et absent des `normalize_contract(c)` du candidat. L'image embarque déjà `app/data/` (`COPY . .` dans le Dockerfile, rien d'exclu par `.dockerignore`, vérifié le 2026-10-25) : ne pas toucher au Dockerfile.

- [ ] **Step 5 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_offer_scoring_assess.py tests/test_hybrid_scoring.py -v`
Attendu : PASS.

- [ ] **Step 6 : commit** (si autorisé) — `feat(scoring): hard filter, geo and contract conditions with commune index`

---

### Task 4 : Classement hybride sur le banc

**Files:**
- Modify: `backend/scripts/matching_bench.py` (`compute_metrics` l. 443, `report` l. 600, `main` l. 633)
- Test: `backend/tests/test_matching_bench.py`

Précondition : `matching_bench.py` et `test_matching_bench.py` portent des modifications non commitées du plan `docs/micro/20261024-matching-bench/PLAN.md`. Demander à l'utilisateur de les commiter avant cette tâche ; sinon, travailler par-dessus sans rien en retirer.

**Interfaces:**
- Consumes : `profile_features`, `build_skill_idf`, `ScoreResult`, `FLOOR` (Task 1) ; `offer_embedding_text`, `text_hash`, `embed_texts` (Task 2) ; `assess_offer` (Task 3) ; `cosine_similarity`.
- Produces :
  - `HYBRID_COS_CACHE = DATA_DIR / "hybrid_cos_cache.json"`, enregistrements `{alias, offer_id, model, text_hash, identity_hash, cos}`.
  - `async def run_embed(export, cache_path: Path, confirm: bool) -> None` : sans `confirm`, affiche le nombre de paires manquantes et le coût estimé (caractères / 4 × 0,1 $ par million), n'appelle rien.
  - `hybrid_scores(export, cos_records) -> dict[str, dict[str, tuple[Optional[str], Optional[ScoreResult]]]]` par alias puis `offer_id`. IDF : `build_skill_idf` sur les `competences_cles` de toutes les offres de l'export (approximation du stock actif, dite dans le rapport).
  - `rank_hybrid(ids: list[str], assessed: dict[str, tuple]) -> list[str]` : score décroissant, cosinus en départage, puis `offer_id` ; offres filtrées et non scorées en dernier.
  - `compute_metrics(..., hybrid: Optional[dict] = None)` : ajoute `"hybrid"` aux `rankings` et, par profil, un bloc `separation` : `detached_by_label` au `FLOOR` courant, `applied_below_floor` (identifiants des interactions `applied` filtrées ou sous `FLOOR`), `levels_by_label` (`{level: {label: n}}`), `score_range_by_label` (min, médiane, max), `floor_sweep` (`{20|30|35|40: {label: n détachées}}`).

- [ ] **Step 1 : écrire les tests qui échouent**

- `test_rank_hybrid_orders_by_score_with_filtered_last` : trois offres scorées 80, 40, 60 et une filtrée → ordre 80, 60, 40, filtrée.
- `test_compute_metrics_includes_hybrid_and_recall_guard` : banc minuscule (helpers `_offer`, `_export` existants), une interaction `applied` dont le score est sous `FLOOR` → `per_profile["A"]["hybrid"]["p@10"]` présent et `separation["applied_below_floor"] == [<offer_id>]`.
- `test_embed_dry_run_makes_no_api_call` : `embed_texts` remplacé par un faux qui lève ; `run_embed(..., confirm=False)` termine sans l'appeler et sans écrire le cache.
- `test_hybrid_cos_cache_reused_only_for_same_text` : un enregistrement au `text_hash` différent est recalculé par `run_embed(confirm=True)` (faux `embed_texts`).

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_matching_bench.py -v`
Attendu : FAIL sur les quatre nouveaux tests, les anciens passent.

- [ ] **Step 3 : implémenter** ; sous-commande `embed [--confirm]` dans `main` ; `report` affiche la ligne `hybrid` dans le tableau existant, puis le bloc `separation` et le balayage de `FLOOR`. `build_results_payload` inclut ces blocs sans aucun texte de profil (le test `test_results_payload_contains_no_profile_data` doit rester vert).

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_matching_bench.py -v`
Attendu : PASS.

- [ ] **Step 5 : mesurer sur le banc**

Run : `cd backend && uv run python scripts/matching_bench.py embed`
Attendu : nombre de paires et coût estimé (≈ 0,003 $). **Demander l'accord de l'utilisateur**, puis `uv run python scripts/matching_bench.py embed --confirm` et `uv run python scripts/matching_bench.py report`.
Attendu : tableau avec une ligne `hybrid` par profil, bloc `separation`, `scripts/matching_bench_results.json` réécrit.

- [ ] **Step 6 : commit** (si autorisé) — `feat(bench): rank offers with the hybrid score and report separation metrics`

---

### Task 5 : PORTE de fiabilité — arrêt pour décision

Aucun code. Cette tâche s'arrête et attend l'utilisateur : les Tasks 6 à 8 ne commencent pas sans sa décision écrite.

- [ ] **Step 1 : relever les mesures** de `uv run python scripts/matching_bench.py report` et les écrire dans une section `## Décision de la porte` ajoutée en fin de ce plan :

Niveau 1 — critère du §6.2, tel qu'écrit : P@10 hybride ≥ P@10 chronologique + 0.2 sur chaque profil, et garde de rappel respectée. Échec attendu (voir « Constat du banc »).

Niveau 2 — séparation (seuils proposés par le plan, à valider par l'utilisateur) :

| Mesure | Seuil proposé |
|---|---|
| FP@20 hybride, chaque profil | ≤ 0.05 |
| Offres `applied` filtrées ou sous `FLOOR` | 0 |
| Offres `relevant` détachées au `FLOOR` retenu | 0 |
| Offres `irrelevant` détachées au `FLOOR` retenu | ≥ 60 % |
| Accord juge / humain, binaire (20 labels) | ≥ 0.8, ou « non mesuré » écrit en clair |

`FLOOR` retenu : la plus haute valeur du balayage (20, 30, 35, 40) qui ne détache ni `relevant` ni `applied`. Joindre le tableau `levels_by_label` : il dit si « Pertinence forte » désigne surtout des `relevant` ou des `partial`.

- [ ] **Step 2 : STOP — présenter à l'utilisateur** les deux niveaux et trois issues :
  - (i) **adopter l'hybride comme séparateur** (recommandation du §6.2 de la spec) : critère assoupli au niveau 2, constantes éventuellement ajustées (`FLOOR`, seuils de niveau, `SCORING_VERSION` incrémentée), Tasks 6 à 8 telles qu'écrites ;
  - (ii) **option (a)** : corriger les poids ou les composantes, puis remesurer avec la Task 4 ;
  - (iii) **option (b)** : hybride en présélection et Two-Pass automatique sur le Top N. Nouveau plan, accord de dépense (environ 2,6 $ par utilisateur et par mois au plus) ; la Task 6 reste utile telle quelle, les Tasks 7 et 8 passent dans ce nouveau plan.

- [ ] **Step 3 : consigner la décision** dans `## Décision de la porte` (issue choisie, valeurs des constantes, date) et reporter les constantes modifiées dans `constants.py` avec leur test (Task 1, Step 1) mis à jour. Commit si autorisé — `chore(scoring): record reliability gate decision`.

---

### Task 6 : `offer_relevance` et rattachement par score

**Files:**
- Modify: `backend/app/services/offer_profile_matcher.py` (réécriture), `backend/app/database.py` (`create_offer_scoring_indexes`), `backend/app/routers/cover_letters.py:638-645`
- Create: `backend/scripts/rematch_all_users.py`
- Test: `backend/tests/test_offer_profile_matcher.py`, `backend/tests/test_database_indexes.py`

**Interfaces:**
- Consumes : Tasks 1 à 3 (`profile_features`, `SkillIdf`, `build_skill_idf`, `get_offer_vectors`, `get_profile_vector`, `assess_offer`, `FLOOR`, `SCORING_VERSION`).
- Produces :
  - `async def load_skill_idf(db) -> SkillIdf` : agrégation `$unwind` / `$group` des `competences_cles` du stock `{"is_deleted": {"$ne": True}}`.
  - `async def interacted_offer_ids(user_id: str, db) -> set[str]` : `user_offer_interactions` `{user_id: str, status: {"$ne": None}}` ∪ `applications` `{user_id: {"$in": [user_id, ObjectId(user_id)]}, offer_id: {"$ne": None}}`, identifiants rendus en `str`.
  - `@dataclass class RematchSummary: attached: int; detached: int; kept_by_guard: int; applied_below_floor: list[str]; levels: dict[str, int]`
  - `async def rematch_user(user_id: str, db, *, apply: bool = True, embed=embed_texts) -> RematchSummary` (signature compatible avec `_safe_rematch_user`).
  - `async def tag_new_offers(offer_ids: list, db, *, embed=embed_texts) -> None` (signature compatible avec `job_offers_collectors.py:709`).
  - `create_offer_scoring_indexes` crée aussi `offer_relevance` : unique `[("user_id", 1), ("offer_id", 1)]` et `[("user_id", 1), ("score", -1)]`.
- Supprimés : `offer_matches_criteria`, `get_normalized_profile_criteria` et leurs tests. Avant suppression : `query_graph_tool` `callers_of` et `tests_for` sur les deux symboles ; seuls `rematch_user`, `tag_new_offers` et `test_offer_profile_matcher.py` doivent apparaître.

- [ ] **Step 1 : écrire les tests qui échouent** dans `test_offer_profile_matcher.py` (base factice en mémoire ; `embed` factice qui renvoie des vecteurs choisis pour produire des cosinus connus avec le profil)

- `test_rematch_user_attaches_by_score_and_writes_relevance` : offre adaptée (score ≥ `FLOOR`) rattachée par `$addToSet`, offre hors sujet (cos 0.62, compétences absentes) retirée par `$pull` ; `offer_relevance` contient un document par offre scorée avec `user_id` en `str`, `offer_id` en `str`, `level`, `breakdown`, `unknown_components`, `failed_conditions`, `scoring_version == SCORING_VERSION`, `updated_at`.
- `test_rematch_user_capped_offer_stays_attached` : offre adaptée hors zone → rattachée, `level == "weak"`, `failed_conditions == ["geo"]`.
- `test_rematch_user_keeps_applied_offer_below_floor` : offre sous `FLOOR` avec un document `applications` dont `user_id` est un `ObjectId` → pas de `$pull`, `summary.kept_by_guard == 1`, `summary.applied_below_floor == [<offer_id>]`, avertissement journalisé (`caplog`) ; même résultat avec une interaction `hidden` dans `user_offer_interactions`.
- `test_rematch_user_hard_filtered_offer_detached` : stage non souhaité → `$pull`, aucun document `offer_relevance`.
- `test_rematch_user_embedding_down_detaches_nothing_new` : `embed` lève → aucune exception ; une offre adaptée par ses autres composantes reste rattachée ; `breakdown["semantic"] == 22.5`.
- `test_rematch_user_dry_run_writes_nothing` : `apply=False` → aucune écriture sur `job_offers`, `offer_relevance` ni `offer_embeddings` ; le résumé est rempli.
- `test_rematch_user_empty_profile_attaches_nothing` : profil sans identité, compétences ni préférences → aucun `$addToSet`, garde d'interaction toujours appliquée.
- `test_tag_new_offers_scores_batch_for_every_profile` : deux profils, un lot de deux offres → `$addToSet` par profil selon le score, jamais de `$pull`.
- `test_tag_new_offers_empty_list_does_nothing` (conservé).

`test_database_indexes.py` : les deux index `offer_relevance` existent.

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_offer_profile_matcher.py tests/test_database_indexes.py -v`
Attendu : FAIL sur les nouveaux tests.

- [ ] **Step 3 : implémenter.** `rematch_user` : profil `candidate_profile` `{"user_id": ObjectId(user_id)}`, stock actif, IDF, vecteurs (`cache=apply`), vecteur profil, `assess_offer` par offre ; rattachées = non filtrées et `score ≥ FLOOR` ; retirées = le reste moins `interacted_offer_ids` ; upsert `offer_relevance` (`bulk_write` de `UpdateOne(..., upsert=True)`) pour toute offre scorée. `tag_new_offers` : même calcul sur le lot, pour chaque profil, sans `$pull`. Docstring du module réécrite (le rattachement ne passe plus par `source_query`).

Dans `cover_letters.py`, la liste des champs qui déclenchent le rematch devient `target_roles`, `locations`, `remote_policy`, `excluded_keywords`, `contract_types`, `seniority_levels`, `preferred_industries`, `preferred_company_sizes`.

`rematch_all_users.py` : `rematch_user(..., apply=args.apply)` pour chaque profil ; affiche par utilisateur (identifiant tronqué, jamais de texte de profil) `attached`, `detached`, `kept_by_guard`, `levels`, et les offres postulées sous `FLOOR` ; sans `--apply`, n'écrit rien. Il affiche d'abord le nombre d'offres à embarquer et le coût estimé.

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_offer_profile_matcher.py tests/test_database_indexes.py tests/test_hybrid_scoring.py tests/test_offer_scoring_assess.py tests/test_offer_scoring_embeddings.py tests/test_job_offers_pipeline.py -v`
Attendu : PASS (`test_job_offers_pipeline.py` couvre l'appel de `tag_new_offers` à la collecte).

- [ ] **Step 5 : commit** (si autorisé) — `feat(matching): attach offers by hybrid relevance score with interaction guard`

---

### Task 7 : API — tri optionnel par pertinence, conditions non remplies, filtres secteur et taille

Réécrite après la décision de la porte (filtre seul) : aucune offre n'est masquée ni repliée selon son score. Le détachement passe par `matched_user_ids` (Task 6), pas par la liste.

**Files:**
- Modify: `backend/app/routers/job_offers.py` (`restrict_to_profile_offers` l. 228-241, `get_job_offers` l. 356-514, `get_job_offers_count` l. 962), `backend/app/models.py` (`JobOfferResponse` l. 343-367)
- Test: `backend/tests/test_job_offers_relevance_api.py` (base Mongo de test locale)

Précondition : vérification `git status` des Global Constraints.

**Interfaces:**
- Consumes : `offer_relevance` (Task 6) ; `SECTORS`, `COMPANY_SIZES` (`app/services/company_profiles.py:35`, `:52`).
- Produces :
  - `relevance_lookup_stages(user_id: str) -> list[dict]` :
    - `$addFields {_oid_str: {$toString: "$_id"}}` ;
    - `$lookup {from: "offer_relevance", localField: "_oid_str", foreignField: "offer_id", pipeline: [{$match: {user_id}}, {$project: {_id: 0, score: 1, failed_conditions: 1}}], as: "_relevance"}` ;
    - `_relevance` ramené à son premier élément ;
    - `_score_sort = ifNull(score, -1)`.
  - Paramètres de `GET /job-offers/` et `GET /job-offers/count/` :
    - `sort: Literal["relevance", "recent"] = "recent"` ;
    - `sector: Optional[List[Literal[*SECTORS]]] = Query(None)` ;
    - `company_size: Optional[List[Literal[*COMPANY_SIZES]]] = Query(None)`. Une valeur hors taxonomie renvoie 422.
  - Tri :
    - `recent` → `{created_at: -1, _id: -1}`, l'ordre actuel ;
    - `relevance` → `{_score_sort: -1, created_at: -1, _id: -1}`.
    - Le lookup se place après la déduplication (`$replaceRoot`/`$unset`), avant le `$sort` final (l. ~464) et avant `$skip`/`$limit`. Il s'applique pour tout utilisateur connecté, quel que soit `sort`.
  - `GET /job-offers/count/` → `{"total": N}`, format inchangé. Il applique les mêmes filtres secteur et taille que la liste.
  - `JobOfferResponse` : `failed_conditions: List[str] = []`, `sector: Optional[str] = None`, `company_size: Optional[str] = None`. `_relevance`, `_oid_str` et `_score_sort` ne sortent jamais dans la réponse.
  - Utilisateur anonyme : pas de lookup, et `sort=relevance` se comporte comme `recent`.

- [ ] **Step 1 : écrire les tests qui échouent** dans `test_job_offers_relevance_api.py`.
  - Mise en place : seed direct dans la base de test ; utilisateurs A et B surchargés par `get_current_user`, sur le modèle de `test_applied_offer_retention.py`.
  - Le module est marqué `skipif` si la base de test ne répond pas, sauf le premier test, qui est pur.
  - Données : quatre offres rattachées à A.
    - A1 : score 82, la plus ancienne.
    - A2 : score 65.
    - A3 : score 30, `failed_conditions: ["geo"]`.
    - A4 : sans document `offer_relevance`, la plus récente.

  Tests :
  - `test_relevance_lookup_filters_by_current_user` (sans base) : dans `relevance_lookup_stages("u1")`, le `$lookup` sur `offer_relevance` a un sous-pipeline dont le `$match` porte `user_id == "u1"`.
  - `test_list_defaults_to_recent_order` : sans `sort`, la liste renvoie A4, A3, A2, A1. Les quatre offres sont présentes, aucune n'est masquée.
  - `test_sort_relevance_orders_by_score_then_recency` : avec `sort=relevance`, la liste renvoie A1, A2, A3, A4.
  - `test_failed_conditions_exposed` : A3 renvoie `failed_conditions == ["geo"]`, A4 renvoie `[]`.
  - `test_count_returns_total` : `{"total": 4}`, avec ou sans `sort`.
  - `test_relevance_is_per_user` : B est rattaché aux mêmes offres, sans document `offer_relevance`.
    - B reçoit `failed_conditions == []` partout.
    - Avec `sort=relevance`, B obtient l'ordre chronologique.
  - `test_filter_by_sector_and_company_size` :
    - `sector=tech_it&company_size=pme` ne renvoie que l'offre correspondante, et le comptage suit ;
    - `sector=fintech` renvoie 422.
  - `test_response_has_no_internal_fields` : aucune clé commençant par `_` dans les offres renvoyées.

- [ ] **Step 2 : lancer, constater l'échec**

Run : `cd backend && uv run pytest tests/test_job_offers_relevance_api.py -v`
Attendu : FAIL (paramètres inconnus, champs absents).

- [ ] **Step 3 : implémenter.** Les clauses `sector`/`company_size` passent par le même chemin de filtre que la liste et le comptage : un helper partagé, comme `_build_contract_type_filter`.

- [ ] **Step 4 : lancer les tests**

Run : `cd backend && uv run pytest tests/test_job_offers_relevance_api.py tests/test_user_offer_interactions.py tests/test_applied_offer_retention.py tests/test_pipeline_kanban.py -v`
Attendu : PASS.

- [ ] **Step 5 : commit** (si autorisé) — `feat(job-offers): optional relevance sort, failed conditions, sector and size filters`

---

### Task 8 : UI — tri optionnel, conditions non remplies, filtres secteur et taille

Réécrite après la décision de la porte (filtre seul) : pas de badge de niveau, pas de tooltip de score, pas de section repliée.

**Files:**
- Create: `frontend/src/lib/companyTaxonomy.ts`
- Modify :
  - `frontend/src/components/profile/TargetingPreferencesSection.tsx:41-70` (options déplacées) ;
  - `frontend/src/lib/api.ts` (`JobOffer` l. ~369, `JobOfferFilter`) ;
  - `frontend/src/app/offers/page.tsx` : carte d'offre près du badge l. 257-269, états l. 522-557, `currentFilters` l. 562-595, `fetchOffers` l. ~612-628.

Précondition : vérification `git status` des Global Constraints.

**Interfaces:**
- Consumes : contrat d'API de la Task 7.
- Produces :
  - `companyTaxonomy.ts` : `SECTOR_OPTIONS`, `COMPANY_SIZE_OPTIONS`, déplacés tels quels depuis `TargetingPreferencesSection.tsx`, qui les importe.
  - `JobOffer` : `failed_conditions?: string[]`, `sector?: string | null`, `company_size?: string | null`.
  - `JobOfferFilter` : `sort?: "relevance" | "recent"`, `sector?: string[]`, `company_size?: string[]`.
  - `getCount` : inchangé.

- [ ] **Step 1 : implémenter**, avec ces textes exacts :
  - Sur la carte d'offre, une étiquette discrète par condition non remplie :
    - `geo` → « Hors de votre zone géographique » ;
    - `contract` → « Contrat différent de vos préférences ».
    - Rien si `failed_conditions` est vide. Aucun badge de niveau, aucun score de pertinence affiché.
  - Le badge « Match x/5 » (l. 257-269) reste inchangé.
  - Sélecteur de tri « Plus récentes » (par défaut) / « Pertinence ».
  - Filtres déroulants multiples Secteur et Taille d'entreprise, depuis `companyTaxonomy.ts`.
  - Le tri et les deux filtres sont inclus dans `currentFilters`.
  - `offers/page.tsx` n'a pas de vue Kanban (vérifié le 2026-10-25), malgré le titre du §5.2 : rien à faire de ce côté.

- [ ] **Step 2 : vérifier**

Run : `cd frontend && npm run lint && npm run build`
Attendu : 0 erreur.

- [ ] **Step 3 : vérification manuelle**, sur un backend local avec des documents `offer_relevance` de test.
  - Points à contrôler : ordre chronologique par défaut, tri « Pertinence », étiquettes de conditions, filtres secteur et taille.
  - Observateur : l'utilisateur, ou l'implémenteur via `chrome-devtools` avec une capture d'écran jointe au rapport.

- [ ] **Step 4 : commit** (si autorisé) — `feat(offers): relevance sort option, failed condition tags, sector and size filters`

---

## Après le plan (hors exécution)

1. Déploiement : vérifier `MISTRAL_API_KEY` en prod (empreinte), déployer (index créés au démarrage), puis l'utilisateur lance `uv run python scripts/rematch_all_users.py` en lecture, relit le résumé, et lance `--apply`. Coût : environ 0,03 $ pour 1 000 offres à la première passe, une seule fois grâce au cache. Tant que ce rattrapage n'a pas tourné, la liste reste chronologique (aucun document `offer_relevance`, `_score_sort = -1`).
2. Recalibrer `COS_FLOOR`/`COS_CEIL` et les seuils dès qu'un deuxième profil existe (mémoire `mistral-embed-cos-bounds`).
3. Rematch après import de CV (le `headline` et les `skills` changent sans passer par les préférences) : non couvert, à traiter si les scores dérivent.
4. Départements limitrophes : hors Lot 1 (« L'Isle-d'Abeau », Isère, sera plafonnée pour un profil lyonnais).
5. Table de prix de `usage_tracker` : ajouter `mistral-embed` si la dépense d'embedding doit apparaître dans les coûts.

## Décision de la porte

### Mesures (2026-10-25, branche `feat/hybrid-relevance-score` à 9bb1314)

Banc : 1 profil, 70 offres d'échantillon et 30 offres d'interaction (20 `applied`, 10 `hidden`). Cosinus `mistral-embed` calculés sur les 100 paires. Labels donnés par le juge (`gpt-6.1-sol` sur 93 paires, `mistral-large-2512` sur 7) ; aucun label humain.

**Niveau 1 — critère du §6.2 : échec.**

| Profil | P@10 chronologique | P@10 hybride | Seuil (chrono + 0.2) | P@10 cosinus seul | Garde de rappel |
|---|---|---|---|---|---|
| A | 0.20 | 0.10 | ≥ 0.40 | 0.20 | 1 `applied` filtrée |

**Niveau 2 — séparation.**

| Mesure | Seuil proposé | Mesuré |
|---|---|---|
| FP@20 hybride | ≤ 0.05 | 0.00 ✓ |
| `applied` filtrées ou sous `FLOOR` | 0 | 1 filtrée par le filtre dur `contract` (un stage) ; 0 sous `FLOOR` jusqu'à 40 |
| `relevant` détachées au `FLOOR` retenu | 0 | 0 ✓ |
| `irrelevant` détachées au `FLOOR` retenu | ≥ 60 % | 26/26 à 40 ✓ |
| Accord juge / humain, binaire | ≥ 0.8 | non mesuré (0 label humain) |

Balayage du `FLOOR` (offres détachées) :

| `FLOOR` | `relevant` (8) | `partial` (36) | `irrelevant` (26) | `applied` (20) | `hidden` (10) |
|---|---|---|---|---|---|
| 20 | 0 | 0 | 4 (15 %) | 1 (filtrée) | 0 |
| 30 | 0 | 1 | 21 (81 %) | 1 (filtrée) | 0 |
| 35 | 0 | 2 | 24 (92 %) | 1 (filtrée) | 0 |
| 40 | 0 | 3 | 26 (100 %) | 1 (filtrée) | 0 |

Plages de score : `relevant` de 45.4 à 70.4 (médiane 55.8), `partial` de 25.8 à 77.6, `irrelevant` de 17.6 à 39.1, `applied` de 52.7 à 82.4 (médiane 71.9), `hidden` de 43.5 à 69.2 (médiane 56.7).

`FLOOR` donné par la règle : **40**, la plus haute valeur du balayage qui ne détache ni `relevant` ni `applied`. L'offre filtrée est comptée à part : elle est détachée quel que soit le `FLOOR`.

Niveaux par label (`levels_by_label`) :

| Niveau | Échantillon : `relevant` / `partial` / `irrelevant` | `applied` : `relevant` / `partial` | `hidden` : `partial` / `irrelevant` |
|---|---|---|---|
| strong (≥ 75) | 0 / 4 / 0 | 7 / 2 | 0 / 0 |
| medium (≥ 60) | 2 / 7 / 0 | 1 / 3 | 1 / 1 |
| weak | 6 / 25 / 24 | 5 / 1 | 6 / 2 |

### Constats

1. **Le score dépend presque uniquement du cosinus.**
   - `competences_cles` n'est renseignée que sur 7 offres sur 100, et la séniorité de l'offre sur 27 offres sur 68.
   - Le profil n'exprime aucune préférence de secteur ni de taille : ces deux composantes sortent du dénominateur.
   - Quand compétences et séniorité sont inconnues, le score vaut (points sémantiques + 20) / 85. Il reste donc entre 23.5 et 76.5.
   - Un `FLOOR` de 40 revient à un seuil de cosinus d'environ 0.761.
2. **Le cosinus sépare le hors-sujet, pas le `relevant` du `partial`.**
   - Médianes du cosinus : `irrelevant` 0.726, `partial` 0.788, `relevant` 0.795.
   - Classer par le cosinus seul donne P@10 = 0.20. Repondérer les composantes actuelles ne peut donc pas atteindre le niveau 1.
3. **La composante compétences a un défaut.** Le profil écrit ses compétences sous forme d'expressions de plusieurs mots, les offres sous forme de mots isolés. La correspondance exacte ne trouve aucune compétence en commun.
   - Les 2 offres `relevant` qui renseignent leurs compétences (`…1162e4`, `…fa02d9`) reçoivent 0/30. Une offre inconnue reçoit pourtant 15/30.
   - Ces deux offres ont pourtant 5 et 2 compétences présentes, mot pour mot, dans les expressions du profil.
4. **« Pertinence forte » veut dire « proche du poste visé », pas « pertinente ».**
   - Sur l'échantillon : 0 `relevant` et 4 `partial`.
   - Sur les candidatures : 7 `relevant` et 2 `partial`.
5. **La candidature filtrée** (`…dd25e1`, label `partial`) est un stage, alors que les préférences de contrat du profil excluent les stages.
   - La garde d'interaction de la Task 6 la garderait rattachée.
   - Un stage semblable publié plus tard serait en revanche filtré.
6. **Le repli des offres faibles de la Task 7 cacherait la plupart des offres `relevant`.** Par défaut, la Task 7 trie par score et replie les offres de niveau `weak` (score < 60). Au `FLOOR` 40 :

   | Ensemble | Détachées | Plafonnées (`weak`) | `weak` non plafonnées | medium | strong |
   |---|---|---|---|---|---|
   | Échantillon | 3 `partial`, 26 `irrelevant` | 13 `partial` | 6 `relevant`, 9 `partial` | 2 `relevant`, 7 `partial` | 4 `partial` |
   | `applied` | 1 `partial` (filtrée) | 1 `relevant` | 4 `relevant`, 1 `partial` | 1 `relevant`, 3 `partial` | 7 `relevant`, 2 `partial` |

   - Vue principale par défaut, sur l'échantillon : 2 offres `relevant` sur 8 restent visibles.
   - Sur les candidatures : 5 `relevant` sur 13 seraient repliées.
   - Le score est donc fiable pour détacher le hors-sujet, pas pour classer ni pour replier.

### Décision (2026-10-25, utilisateur)

1. **Issue : le score sert de filtre seul.** C'est une variante de l'issue (i), restreinte au détachement.
   - Task 6 inchangée : sous `FLOOR`, l'offre est détachée de `matched_user_ids`, sauf garde d'interaction.
   - Tasks 7 et 8 réécrites :
     - la liste reste chronologique par défaut, le tri par pertinence est une option ;
     - aucune offre n'est repliée ;
     - aucun badge de niveau, aucun tooltip de score ;
     - les conditions non remplies (zone, contrat) sont affichées.
   - Raison : le constat 6. Le score détache bien le hors-sujet, mais il ne classe pas mieux que la date (niveau 1), et le repli `weak` cacherait la plupart des offres `relevant`.
2. **`FLOOR = 35`**, alors que la règle du Step 1 donne 40.
   - À 35, le seuil de cosinus est d'environ 0.752 ; il est de 0.761 à 40.
   - Le minimum des `relevant` (45.4) garde donc 10 points de marge au lieu de 5. Les minima des `hidden` (43.5) et des `applied` scorées (52.7) en gardent aussi.
   - Coût : 2 offres `irrelevant` restent rattachées (24/26 détachées au lieu de 26/26).
   - Pourquoi une marge : le banc compte 1 profil et 8 `relevant`, sans label humain.
3. **Composante compétences : bonus seul.**
   - Une compétence de l'offre compte si elle figure dans `candidate_skills`, ou si elle apparaît, avec des frontières de mot, dans une compétence du profil (`contains_keyword`).
   - Quand l'offre liste des compétences, les points valent `max(W_SKILLS / 2, W_SKILLS × part IDF des compétences trouvées)`.
   - Question de l'utilisateur à l'origine de ce choix : la robustesse face aux compétences que l'utilisateur n'a pas listées.
   - Simulation au `FLOOR` 35 : correspondance exacte, mot à mot, bonus seul et composante retirée donnent les mêmes détachements sur le banc. Seules 7 offres sur 100 listent des compétences.
   - Risque théorique couvert : avec la règle actuelle, une offre qui liste des compétences absentes du profil reçoit 0/30, et son cosinus doit atteindre 0.785 au lieu de 0.752. Le minimum des `relevant` est 0.775.
4. **Stage** : le filtre dur `contract` est inchangé. La candidature `…dd25e1` reste rattachée par la garde d'interaction.
5. **Constantes inchangées** :
   - `STRONG_THRESHOLD = 75`, `MEDIUM_THRESHOLD = 60`, `CAP_SCORE = 59` : le niveau reste calculé et stocké dans `offer_relevance`, mais il n'est pas affiché.
   - `SCORING_VERSION = "1"` : aucun score n'a encore été persisté.
6. **Accord juge / humain** : non mesuré. Il reste à faire avec les 20 labels humains du plan du banc.

### Mesures après correction (2026-10-25, commit 2615ab4)

`FLOOR = 35` et composante compétences en bonus seul. Banc relancé sans appel d'API (caches locaux).

| Mesure (profil A) | Avant (9bb1314) | Après (2615ab4) |
|---|---|---|
| P@10 hybride | 0.10 | 0.20 (= chronologique, seuil du niveau 1 toujours non atteint) |
| P@20 hybride | 0.20 | 0.25 |
| FP@20 hybride | 0.00 | 0.00 |
| Détachées au `FLOOR` courant | 0 / 0 / 4 (à 20) | 0 `relevant` / 2 `partial` / 24 `irrelevant` (à 35) |
| `applied` filtrées ou sous `FLOOR` | `…dd25e1` (filtrée, stage) | `…dd25e1` (filtrée, stage), aucune sous `FLOOR` |
| `relevant` : min / médiane / max | 45.4 / 55.8 / 70.4 | 45.4 / 58.8 / 76.5 |
| `irrelevant` : min / médiane / max | 17.6 / 23.5 / 39.1 | inchangé |
| Niveaux échantillon `relevant` : strong / medium / weak | 0 / 2 / 6 | 1 / 3 / 4 |

- Balayage du `FLOOR` identique avant et après : les offres détachées ne listent pas de compétences, leur score ne bouge pas. La simulation du point 3 est confirmée.
- Marge à 35 : 10.4 points sous le minimum des `relevant`.

