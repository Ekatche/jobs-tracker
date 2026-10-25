# Design Doc: Matching Hybride, Secteurs & Tailles d'Entreprise (Lot 1)

**Date** : 2026-10-24 (révisé le même jour après revue, cf. §9)  
**Statut** : Révisé — décisions 1, 2 et 3 tranchées (§8)  
**Périmètre** : Lot 1 — Mesure & Benchmark + Étage 1 (Filtres durs) + Étage 2 (Score d'adéquation hybride, conditions géographie / contrat) + API & UI Préférences, Niveaux & Tri Pertinence  

---

## 1. Contexte & Problématique

En production, un profil candidat accumule rapidement plus de 200 offres collectées sans hiérarchisation efficace. Quatre limitations majeures ont été identifiées :
1. **Rattachement aveugle par `source_query`** : Toute offre issue d'une requête de recherche (ex: « Data Scientist ») est automatiquement rattachée au profil dans `offer_matches_criteria` (`backend/app/services/offer_profile_matcher.py`), même si le contenu réel de l'offre est un faux positif (ex: stage RH, commercial).
2. **Acronymes mal rapprochés par les embeddings bruts** : Mesuré dans le projet avec `text-embedding-3-small` : « Développeur Confirmé Ia » face à « AI Engineer » donne un cosinus de 0.28, et 0.43 une fois l'acronyme développé. C'est pour cela que `ACRONYM_EXPANSIONS` / `expand_title_acronyms` existent dans `backend/app/services/evaluation/domain_relevance.py` (aujourd'hui pour « IA » seulement). Les acronymes fréquents (*PM, PO, ML, QA, SRE, BI, DA, DE, DS*) sont exposés au même problème. Les embeddings ne le résolvent pas seuls.
3. **Tri chronologique strict (`created_at: -1`)** : Les offres pertinentes sont noyées au milieu d'un flux non trié par adéquation (`$sort {created_at: -1, _id: -1}` dans `backend/app/routers/job_offers.py`).
4. **Absence de filtrage par secteur d'activité et taille d'entreprise** : Le champ `preferred_industries` existe dans le modèle Pydantic `CandidatePreferences` (texte libre) mais n'est ni exposé dans l'interface, ni enrichi sur les offres, ni pris en compte dans le scoring.

### 1.1. Existant à réutiliser (ne pas réimplémenter)

| Brique existante | Emplacement | Usage dans le Lot 1 |
|---|---|---|
| Modèle d'embedding, expansion d'acronymes, identité candidat | `domain_relevance.py` : `EMBEDDING_MODEL`, `expand_title_acronyms`, `build_candidate_identity`, `compute_domain_relevance` (fail-open) | Base du score sémantique (§4.3.1) |
| Ordre de séniorité, écarts contrat / séniorité / salaire | `offer_fit.py` : `SENIORITY_ORDER`, `check_preference_fit`, `normalize_contract` | Séniorité (§4.3.3) et contrat (§4.2, §4.4) |
| Type de contrat canonique à l'ingestion | `normalization.detect_contract_type` + filtre `_build_contract_type_filter` (`routers/job_offers.py`) | Étage 1 contrat (§4.2) |
| Données d'origine rangées par source | `job_offers.raw_data = {<source>: <enregistrement natif>}` (`source_record`, fusion par source à l'étape 13 de `merge_multidiffusion_offers`) | Extraction native secteur / taille (§4.1) |
| Score LLM par utilisateur (Two-Pass) | `evaluator.evaluate_offer_two_pass`, collection `offer_evaluations {user_id, offer_id, score}`, filtre `min_score` | Découpé en calcul pur et enregistrement (§4.7) ; coexistence à trancher (§8, décision 2) |
| Collection par utilisateur plutôt que champ dans le document partagé | `offer_evaluations` ; cf. le `pop("evaluation_score")` de `routers/job_offers.py`, qui corrige une fuite entre utilisateurs causée par un score écrit dans `job_offers` | Modèle suivi par `offer_relevance` (§3.2) |
| Normalisation du nom d'entreprise | `normalization.normalize_company` | Clé de `company_profiles` |

---

## 2. Objectifs & Non-Objectifs (Lot 1)

### Objectifs
* **Mesure & Vérité terrain d'abord** : Disposer d'un jeu de test de référence combinant les interactions de prod existantes (`applied`, `hidden`) et un échantillon évalué par LLM-juge (avec validation croisée manuelle). Ce benchmark est livré **en premier** (§7, étape 1b, juste après la séparation du Two-Pass) : il calibre toutes les constantes du score (§4.6) et décide quelle mesure alimente les niveaux affichés (§6.2).
* **Taxonomie & Profils Entreprise** : Structurer une taxonomie fermée de 12 secteurs (+ `other`) et 4 tailles d'entreprise, stockée dans une collection dédiée `company_profiles` avec cache pour éviter les requêtes redondantes.
* **Scoring Hybride Déterministe & Sémantique** : Remplacer le matching binaire par un score d'adéquation continu de 0 à 100, normalisé par utilisateur, combinant similarité sémantique (embeddings), compétences clés, séniorité et secteur/taille. La géographie et le contrat sont des conditions qui plafonnent ce score, pas des points qui s'additionnent (§4.4).
* **Identifier d'un coup d'œil les offres adaptées au profil** (besoin exprimé par l'utilisateur le 2026-10-24) : offres triées par pertinence par défaut, badge de niveau (forte / moyenne / faible) explicatif, offres de niveau faible reléguées dans une section repliée « Moins pertinentes » sans être supprimées. Cette livraison ne dépend pas du résultat du benchmark : le benchmark choisit la mesure qui alimente les niveaux (§6.2), pas l'existence des niveaux.
* **Préférences utilisateur complètes** : Permettre la sélection de secteurs et tailles d'entreprise dans `TargetingPreferencesSection`.

### Non-Objectifs (Réservés aux Lots 2 et 3)
* Rerank LLM complet à chaque affichage (Lot 2 : limité au Top N, cf. §8 décision 2).
* Ré-apprentissage dynamique des poids par utilisateur via Rocchio / feedback loop (Lot 3).
* Algorithme de diversification MMR (Lot 3).
* Référentiel géographique avec rayon kilométrique (le Lot 1 se limite à ville / département / télétravail, §4.4).

### Anti-objectifs
* Faire disparaître de la liste une offre avec laquelle l'utilisateur a déjà interagi (sauvegardée, postulée, masquée).
* Écrire un score propre à un utilisateur dans le document partagé `job_offers`.
* Pénaliser une offre parce que sa source ne fournit pas une métadonnée.

---

## 3. Architecture & Modèle de Données

### 3.1. Taxonomie Standardisée

#### Secteurs d'activité (12 catégories normalisées + `other`) :
1. `tech_it` : Éditeurs de logiciels, produits et plateformes numériques, Télécoms
2. `finance_insurance` : Banque, Finance, Assurance, Fintech
3. `healthcare_pharma` : Santé, Pharmacie, Biotech, Médical
4. `consulting_services` : Conseil, Audit, ESN, Services B2B
5. `retail_ecommerce` : E-commerce, Retail, Grande Distribution, Mode
6. `industry_aerospace` : Industrie, Aéronautique, Automobile, Défense
7. `energy_environment` : Énergie, Environnement, CleanTech, RSE
8. `media_communication` : Médias, Communication, Divertissement, Jeux vidéo
9. `public_education` : Secteur Public, Administration, Éducation, Recherche
10. `construction_realestate` : Immobilier, Construction, BTP, Urbanisme
11. `logistics_transport` : Transport, Logistique, Supply Chain
12. `agri_food` : Agroalimentaire, Agriculture
13. `other` : aucune des catégories ci-dessus. Valeur de sortie de l'enrichissement uniquement, jamais proposée comme préférence.

**Frontière `tech_it` / `consulting_services`** (choix de rédaction, à confirmer à la relecture) : une ESN ou un cabinet de conseil IT relève de `consulting_services`, même si son code NAF est en 62.0x ; `tech_it` est réservé aux entreprises qui vendent leur propre produit ou plateforme. Cette règle figure telle quelle dans le prompt LLM et dans le mapping natif.

#### Tailles d'entreprise (4 segments normalisés, alignés sur les catégories INSEE) :
1. `startup_tpe` : Startup / TPE (< 20 salariés)
2. `pme` : PME (20 - 249 salariés)
3. `eti` : ETI (250 - 4 999 salariés)
4. `grand_groupe` : Grand Groupe (5 000+ salariés)

---

### 3.2. Modifications de Schéma

#### Collection `company_profiles` (Nouvelle collection MongoDB)
```python
class CompanyProfile(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    company_name_normalized: str  # Index unique (via normalize_company)
    company_name_raw: str
    sector: Optional[str] = None  # Valeur de la taxonomie (dont "other")
    sector_source: Optional[str] = None  # "native_source" | "llm_inferred" | "manual"
    company_size: Optional[str] = None  # Valeur parmi les 4 tailles
    size_source: Optional[str] = None  # "native_source" | "api_entreprises" | "llm_inferred" | "manual"
    siren: Optional[str] = None  # Renseigné quand l'API Recherche d'entreprises a validé la correspondance
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```
*Index :* `{ "company_name_normalized": 1 }` (unique).

Secteur et taille ont chacun leur source : ils ne proviennent pas des mêmes fournisseurs (§4.1).

#### Collection `job_offers` (Enrichissement minimal, partagé entre utilisateurs)
* `sector`: `Optional[str]` (hérité du profil entreprise ou extrait de l'offre)
* `company_size`: `Optional[str]`

Rien de propre à un utilisateur n'est écrit dans `job_offers`. L'embedding n'y est pas stocké non plus (~12 Ko par offre pour 1 536 flottants) : la liste des offres n'a pas à le lire ni à le projeter.

#### Collection `offer_embeddings` (Nouvelle)
```python
class OfferEmbedding(BaseModel):
    offer_id: str
    model: str  # EMBEDDING_MODEL au moment du calcul
    text_hash: str  # Hash du texte embeddé : recalcul seulement si le texte change
    vector: List[float]
    updated_at: datetime
```
*Index :* `{ "offer_id": 1, "model": 1 }` (unique).  
Texte embeddé : `expand_title_acronyms(poste)` + début de description, calculé une seule fois par offre et par modèle. `competences_cles` en est volontairement exclu : les compétences sont mesurées par la composante lexicale (§4.3.2), pas deux fois.

#### Collection `offer_relevance` (Nouvelle, par utilisateur — stockée et affichée, cf. §8 décision 1)
```python
class OfferRelevance(BaseModel):
    user_id: str
    offer_id: str
    score: float  # Entre 0 et 100 : score d'adéquation (§4.3), plafonné si une condition échoue (§4.4)
    level: Literal["strong", "medium", "weak"]  # Niveau affiché (§4.5)
    breakdown: Dict[str, float]  # Points obtenus et points applicables par composante, score avant plafonnement
    failed_conditions: List[str]  # "geo", "contract" : conditions non remplies (§4.4), vide sinon
    scoring_version: str  # Version des constantes calibrées (§4.6)
    updated_at: datetime
```
*Index :* `{ "user_id": 1, "offer_id": 1 }` (unique), `{ "user_id": 1, "score": -1 }`.  
Même modèle que `offer_evaluations`. Le tri par pertinence de la liste passe par un `$lookup` filtré sur `user_id`, appliqué à un ensemble déjà restreint par `matched_user_ids`.

#### Modèle `CandidatePreferences` (`backend/app/models.py` & `frontend/src/types/coverLetter.ts`)
* `preferred_industries: List[str]` (existant, désormais branché, valeurs attendues : la taxonomie hors `other`)
* `preferred_company_sizes: List[str] = Field(default_factory=list)` (nouveau)

**Migration des valeurs existantes de `preferred_industries`** (texte libre aujourd'hui) : un script fait correspondre chaque valeur à la taxonomie. Les valeurs sans correspondance sont conservées dans le champ (aucune perte de données), ignorées par le score et listées dans la sortie du script. Le script est lancé en mode lecture d'abord, puis avec `--apply` par l'utilisateur.

---

## 4. Pipeline d'Enrichissement & Scoring

### 4.1. Enrichissement des Entreprises

L'enrichissement écrit `sector` et `company_size` sur l'offre **au moment de l'ingestion**, à partir de l'enregistrement natif disponible à cet instant. Raison : la fusion de `raw_data` remplace l'enregistrement entier d'une même clé de source (`{**ancien, **entrant}` par clé, étape 13 de `merge_multidiffusion_offers`). Un enregistrement JSON-LD HelloWork, issu du routeur ATS, peut donc remplacer l'enregistrement jobspy qui portait `company_industry`. Même risque pour la clé `indeed` entre jobspy et GraphQL. Règle : une valeur `sector` ou `company_size` connue n'est jamais écrasée par `None`.

Ordre de résolution, du moins cher au plus cher :

1. **Extraction native depuis `raw_data`** (mapping statique libellé source → taxonomie, avec la règle ESN du §3.1) :

   | Source (clé `raw_data`) | Secteur | Taille | Observé sur échantillon |
   |---|---|---|---|
   | `hellowork` (jobspy) | `company_industry` | — | secteur sur 25 offres sur 25 |
   | `indeed` (jobspy) | `company_industry` | `company_num_employees` (format texte à observer, puis à mapper) | secteur sur 4 sur 25 |
   | `linkedin` (jobspy) | — | — | apporte `job_level` (séniorité), pas de secteur |
   | `france_travail` (API) | `secteurActiviteLibelle` | `trancheEffectifEtab` | indisponible tant que l'OAuth France Travail est en panne (depuis le 2026-10-04) |

   jobspy n'expose pas de champ `company_size` : la taille ne vient nativement que d'Indeed et de France Travail. Les offres antérieures au stockage par source n'ont pas d'enregistrement d'origine : elles passent directement aux étapes 2 à 4.
2. **Cache `company_profiles`** sur `normalize_company(entreprise)`.
3. **Taille via l'API publique Recherche d'entreprises** (`recherche-entreprises.api.gouv.fr/search`, gratuite, sans clé) :
   - `categorie_entreprise` (`PME` / `ETI` / `GE`) donne la taille au niveau du groupe. Pour `PME`, `tranche_effectif_salarie` (codes INSEE ≤ `11`, soit moins de 20 salariés) sépare `startup_tpe` de `pme`.
   - Garde de correspondance : le premier résultat n'est retenu que si son nom normalisé correspond au nom de l'entreprise de l'offre. Sinon, rien n'est écrit. Exemple observé : « sanofi » renvoie 182 résultats.
   - Le code NAF (`activite_principale`) **n'est pas** utilisé pour le secteur : il décrit l'unité légale, pas le groupe. Exemple observé : Sanofi sort en `70.10Z` (sièges sociaux), avec une tranche d'effectif de 10 à 19 salariés pour l'entité siège, alors que `categorie_entreprise` vaut correctement `GE`.
   - La limite de débit de l'API est à vérifier dans sa documentation officielle avant implémentation ; les appels se font une fois par entreprise grâce au cache.
4. **Repli LLM avec cache** : si le secteur, ou la taille, reste inconnu, un appel structuré léger (`gpt-5-nano`, JSON schema contraint sur la taxonomie, `other` et `null` autorisés) déduit la valeur manquante à partir du nom de l'entreprise et du contexte de l'offre. Le résultat est stocké dans `company_profiles` avec `*_source = "llm_inferred"`. Le volume (~300 entreprises uniques, chiffre à confirmer en prod) rend le coût marginal.

### 4.2. Étage 1 : Filtrage Éliminatoire (Hard Filter)

Appliqué **avant** tout calcul d'embedding : chaque offre éliminée ici est un appel économisé.

Une offre est exclue du matching pour un utilisateur si :
- Elle contient un mot-clé de `excluded_keywords` (intitulé ou description).
- Le contrat est incompatible de manière rédhibitoire : l'offre est un stage ou une alternance (valeur canonique de `detect_contract_type`) et les `contract_types` du candidat n'en contiennent aucun. Les autres écarts de contrat ne sont pas des exclusions : ils relèvent de la condition contrat du §4.4, qui plafonne le score.

### 4.3. Étage 2 : Score d'Adéquation (0 - 100 points, normalisé par utilisateur)

Le score d'adéquation mesure à quel point l'offre correspond au profil. Ce qui la rend possible ou non (lieu, contrat) n'y entre pas : c'est l'objet des conditions du §4.4. Une addition laisserait un point fort compenser un critère rédhibitoire. Exemple : une offre à Lyon avec des compétences parfaites atteindrait 85/100, donc « pertinente », pour un candidat qui ne travaille qu'en présentiel à Paris.

$$\text{Score} = 100 \times \frac{\sum \text{points obtenus}}{\sum \text{points applicables}}$$

Une composante n'est **applicable** que si le candidat a exprimé la préférence correspondante (ex : pas de `preferred_company_sizes`, donc les 5 points de taille sortent du dénominateur). Ainsi, 100 reste atteignable pour tous les utilisateurs et un seuil a le même sens d'un utilisateur à l'autre.

**Règle unique pour les métadonnées absentes** : quand l'offre ne renseigne pas une composante applicable (secteur inconnu, séniorité non spécifiée, compétences vides), la composante reçoit la **moitié** de ses points. Pas de malus, pas de bonus : une offre n'est ni punie ni favorisée par le silence de sa source.

**Pas de double comptage** : la composante sémantique compare des identités de rôle (intitulés, description), la composante lexicale compare des compétences. `competences_cles` n'entre que dans la seconde.

Poids de départ (total 100, à recalibrer, §4.6) :

1. **Proximité Sémantique (Poids : 45 pts)** :
   - Cosinus entre le vecteur profil (`build_candidate_identity(headline, target_roles)`, sans les compétences) et le vecteur de l'offre (`offer_embeddings` : intitulé et début de description, sans `competences_cles`), avec `EMBEDDING_MODEL`.
   - Normalisation : $\text{clamp}\left(\frac{\cos - \text{COS\_FLOOR}}{\text{COS\_CEIL} - \text{COS\_FLOOR}}, 0, 1\right) \times 45$.
   - Valeurs de départ, **à recalibrer sur le benchmark** : `COS_FLOOR = 0.25`, `COS_CEIL = 0.55`. Repères mesurés : un vrai match (« Développeur Confirmé IA » face à « AI Engineer », acronyme développé) donne 0.43, et le seuil projet actuel est `DOMAIN_RELEVANCE_THRESHOLD = 0.30`. La formule initiale `(cos - 0.5) / 0.5` aurait donné 0 point à ce vrai match.
   - Limite connue : l'embedding sépare bien les domaines (une offre RH est loin d'un profil IA) mais distingue mal les offres d'un même domaine, dont les cosinus tiennent dans une bande étroite. L'ordre fin entre offres d'un même domaine relève d'une lecture LLM (§8, décision 2), pas de ce score.
   - Acronymes : `ACRONYM_EXPANSIONS` est étendu aux acronymes listés au §1, et appliqué des deux côtés (intitulé de l'offre et rôles cibles).
   - Fail-open comme `compute_domain_relevance` : embedding indisponible, composante traitée comme inconnue (moitié des points).
2. **Recouvrement Lexical & Compétences Clés (Poids : 30 pts)** :
   - Recouvrement entre `competences_cles` de l'offre et les compétences du profil (`CandidateProfile.skills`, toutes catégories aplaties), pondéré par l'IDF.
   - IDF calculé sur les `competences_cles` du stock actif (`is_deleted: false`), recalculé à chaque passage de rematch complet.
   - Taux de remplissage de `competences_cles` à mesurer au benchmark ; vide, la composante est traitée comme inconnue.
3. **Adéquation Séniorité (Poids : 10 pts)**, selon `SENIORITY_ORDER` d'`offer_fit.py` :
   - 10 pts si niveau identique à l'un des `seniority_levels` du candidat.
   - 6 pts si 1 niveau d'écart.
   - 0 pt au-delà.
   - Séniorité de l'offre non spécifiée : moitié des points (règle unique ci-dessus).
4. **Secteur & Taille (Poids : 15 pts)** :
   - **Secteur (10 pts)** : 10 si le `sector` de l'offre fait partie des `preferred_industries`, 0 s'il est connu et différent, 5 s'il est inconnu.
   - **Taille (5 pts)** : 5 si la `company_size` fait partie des `preferred_company_sizes`, 0 si elle est connue et différente, 2.5 si elle est inconnue.
   - Pas de points négatifs : le score reste dans [0, 100].

### 4.4. Conditions : Localisation & Contrat (plafonnement)

Une condition non remplie ne retire pas l'offre : elle **plafonne** son score à `CAP_SCORE` (départ : `MEDIUM_THRESHOLD - 1`), ce qui la range en niveau faible (§4.5) et la place sous toutes les offres compatibles dans le tri. Le score avant plafonnement reste visible dans `breakdown`, et la condition échouée est listée dans `failed_conditions`.

Une donnée absente ne fait jamais échouer une condition (localisation « Non spécifié », mode de travail ou contrat inconnu : condition considérée comme remplie).

1. **Localisation (`geo`)** — à partir de `locations` (liste de chaînes) et `remote_policy` (`full_remote` / `hybrid` / `on_site` / `flexible`). Sans `locations`, pas de condition géographique. Sinon, la condition est remplie si :
   - la ville de l'offre correspond à l'une des `locations`, ou l'offre est dans le même département que l'une d'elles ;
   - **ou** l'offre est en télétravail total et `remote_policy` ≠ `on_site`.
   
   Exception : un candidat `full_remote` ne remplit la condition qu'avec une offre en télétravail total, quel que soit le lieu.
   
   Prérequis : un référentiel ville → département (fichier statique, par exemple la table des communes INSEE). Il n'existe pas aujourd'hui dans le projet. Le rayon kilométrique et les départements limitrophes sont hors Lot 1.
2. **Contrat (`contract`)** — si les `contract_types` du candidat ne sont pas vides et que le contrat canonique de l'offre (`detect_contract_type`, comparé via `normalize_contract`) n'en fait pas partie. Le cas stage / alternance reste une exclusion de l'Étage 1 (§4.2).

### 4.5. Niveaux, Classification & Rattachement

Le score exact sert au tri. L'affichage, lui, ne montre qu'un niveau : un écart de quelques points entre deux offres n'est pas significatif, et un pourcentage laisserait croire le contraire.

* **`level: "strong"`** (« Pertinence forte ») : $\text{Score} \ge \text{STRONG\_THRESHOLD}$ (départ : 75).
* **`level: "medium"`** (« Pertinence moyenne ») : $\text{MEDIUM\_THRESHOLD} \le \text{Score} < \text{STRONG\_THRESHOLD}$ (départ : 60).
* **`level: "weak"`** (« Pertinence faible ») : $\text{FLOOR} \le \text{Score} < \text{MEDIUM\_THRESHOLD}$ (départ : 20), ou toute offre plafonnée par une condition (§4.4).
* **Rattachement** (`matched_user_ids`) : une offre est rattachée si elle passe l'Étage 1 et que son score est ≥ `FLOOR`. Ce critère remplace le rattachement par `source_query` d'`offer_matches_criteria`, et supprime le biais du §1.1. Une offre plafonnée par une condition reste rattachée (niveau faible) : elle n'est pas supprimée, seulement reléguée.
* **Garde d'interaction** : une offre avec laquelle l'utilisateur a une interaction (`saved`, `applied`, `hidden` ou tout statut de candidature) n'est **jamais** retirée de `matched_user_ids` par le rematch, quel que soit son score. Une offre postulée dont le score est sous `FLOOR` est un faux négatif : elle est journalisée et versée au benchmark.
* `rematch_user` et `tag_new_offers` (`offer_profile_matcher.py`) calculent le score et écrivent `offer_relevance` ; le `$pull` de `rematch_user` respecte la garde d'interaction.

### 4.6. Constantes calibrées

`COS_FLOOR`, `COS_CEIL`, `STRONG_THRESHOLD`, `MEDIUM_THRESHOLD`, `FLOOR`, `CAP_SCORE` et les poids vivent dans un seul module, avec une `SCORING_VERSION` recopiée dans chaque document `offer_relevance`. Les valeurs de départ ci-dessus sont des hypothèses : elles sont fixées par le benchmark (§6), pas par ce document.

### 4.7. Two-Pass : séparer le calcul de l'enregistrement (tranché le 2026-10-24)

**Constat.** `evaluate_offer_two_pass` (`backend/app/services/evaluation/evaluator.py`) calcule l'évaluation et produit en même temps quatre effets de bord :

| Ligne | Effet | Problème |
|---|---|---|
| 228 | `require_user_quota(EVALUATION)` | Le benchmark (200 appels) épuiserait le quota de l'utilisateur |
| 555 | upsert `offer_evaluations` | Le benchmark afficherait 100 badges « Analyse IA » chez l'utilisateur |
| 562 | `$set` de `evaluation_score` et `pipeline_stage: "evaluated"` dans le document **partagé** `job_offers` | `evaluation_score` ne sert à rien : le routeur le retire et réinjecte le score propre à l'utilisateur depuis `offer_evaluations` (`routers/job_offers.py`, `pop` puis `eval_score_map`). `pipeline_stage` fuit : un utilisateur B voit le badge « Évaluée » (`offers/page.tsx`) et voit compter l'offre dans `applications/page.tsx` (`pipeline_stage === "evaluated"`) pour une offre que seul A a évaluée |
| 574 | `record_api_usage` | La consommation du benchmark serait imputée à l'utilisateur |

**Découpage.**
- **Calcul pur** (nouvelle fonction, nom laissé au plan) : passes 1 et 2, score final, tokens, latence et modèles utilisés. Lectures en base permises (offre, profil, comptage de publications), **aucune écriture, aucun quota**.
- **`evaluate_offer_two_pass`** garde sa signature, et les boutons « évaluation avancée » (`POST /job-offers/{id}/evaluate`, `POST /applications/{id}/evaluate`) restent inchangés : quota, appel du calcul pur, upsert `offer_evaluations`, `record_api_usage`. Elle **n'écrit plus rien dans `job_offers`**.
- L'état « évaluée » est calculé **par le routeur** pour l'utilisateur courant, comme il le fait déjà pour `evaluation_score` : `pipeline_stage` vaut `"evaluated"` seulement si l'utilisateur a son propre document `offer_evaluations` (et que l'offre n'est pas `"expired"`, état partagé qui reste vrai pour tous) ; un `"evaluated"` stocké dans `job_offers` par un autre utilisateur est rendu comme `"discovered"`. Le frontend continue de lire `pipeline_stage` et n'a **rien à changer** (`offers/page.tsx`, `applications/page.tsx` hors périmètre). Le rattrapage de `clean_job_offers.py` qui déduit `pipeline_stage = "evaluated"` d'`evaluation_score` est retiré. Seul `routers/job_offers.py` relève de la précondition du §5.
- Le benchmark appelle seulement le calcul pur ; son coût figure dans le rapport du benchmark, pas dans `api_usage`.

---

## 5. Interface Utilisateur & Expérience (UI/UX)

> **Périmètre d'exécution** : l'API et l'UI font partie du Lot 1 et sont implémentées par la même session que le backend (§8, décision 3), après lui, sur le contrat d'API qu'il définit. `backend/app/routers/job_offers.py`, `TargetingPreferencesSection.tsx`, `offers/page.tsx` et `frontend/src/types/coverLetter.ts` portent aujourd'hui des modifications non commitées d'une autre session : avant d'y toucher, vérifier qu'elles sont commitées, pour ne pas écraser ce travail.

### 5.1. Écran Préférences Candidat (`TargetingPreferencesSection.tsx`)
* Nouvelle section accordéon dédiée : **« Secteurs d'activité & Taille d'entreprise »**.
* Sélection par badges/chips cliquables des 12 secteurs de la taxonomie (pas de tags libres : un tag hors taxonomie ne correspondrait jamais au `sector` d'une offre).
* Boutons de sélection multiple pour les 4 tailles d'entreprise.
* La sauvegarde déclenche le recalcul asynchrone du matching (`rematch_user`).

### 5.2. Écran Liste & Kanban des Offres (`offers/page.tsx`)
* **Barre d'outils / Contrôle de tri** :
  * Sélecteur de tri par défaut sur **« Pertinence »** (score exact `offer_relevance.score` de l'utilisateur courant, décroissant), avec possibilité de basculer sur « Plus récentes » (`created_at`). Le tri utilise le score exact, pas le niveau : deux offres « fortes » restent ordonnées entre elles.
  * Nouveaux filtres déroulants par Secteur et par Taille d'entreprise (champs partagés `job_offers.sector` / `company_size`).
* **Carte d'offre** :
  * Badge de niveau, sans pourcentage (§4.5) : « Pertinence forte » (vert), « Pertinence moyenne » (bleu), « Pertinence faible » (gris).
  * Tooltip au survol : score exact, décomposition par composante (`breakdown`), composantes inconnues signalées, et conditions non remplies (`failed_conditions`) formulées pour l'utilisateur (ex : « Hors de votre zone géographique », « Contrat différent de vos préférences »).
  * Coexistence avec le score IA Two-Pass (`evaluation_score`) déjà affiché : badge distinct « Analyse IA », réservé aux meilleures offres (§8, décision 2).
* **Section repliée « Moins pertinentes »** :
  * Les offres avec `level === "weak"` sont regroupées par défaut sous un bandeau replié : *« X offres moins pertinentes — Déplier »*.
  * L'utilisateur parcourt ses offres prioritaires sans être pollué, tout en conservant la visibilité complète en un clic.

---

## 6. Stratégie de Mesure & Validation

Le banc de mesure est livré **en premier** (§7, étape 1b) ; il fixe, une fois le score branché à l'étape 3, les constantes du §4.6 et décide quelle mesure alimente les niveaux affichés (§6.2).

1. **Jeu de test de référence (Benchmark)** :
   - Export en lecture seule des interactions de prod, lancé par l'utilisateur (aucun accès direct à la base de prod depuis l'outillage d'implémentation). Chiffres annoncés à confirmer par cet export : 41 interactions (30 positives `applied`, 11 négatives `hidden`), 2 profils actifs.
   - **Biais de sélection** : ces interactions portent sur des offres déjà rattachées par l'ancien matcher. Elles servent de contrôle de cohérence, pas de calibrage fin.
   - Annotations LLM (juge) sur un échantillon de 100 offres pour les 2 profils actifs, tiré **à la fois** parmi les offres rattachées et non rattachées, pour mesurer aussi ce que l'ancien matcher manquait.
   - Le juge est un modèle d'une **autre famille** que celui du Two-Pass (aujourd'hui gemini) : sinon le Two-Pass serait noté par un modèle qui pense comme lui, et la comparaison du §6.2 serait biaisée en sa faveur. Choix retenu le 2026-10-24 : un modèle OpenAI (clé déjà configurée pour les embeddings et `gpt-5-nano`), plus capable que `gpt-5-nano` ; le modèle exact est fixé par le plan du benchmark.
   - Validation manuelle d'un sous-ensemble de 20 offres pour mesurer l'accord du juge.
2. **Comparaison de trois classements et critère de livraison** — sur les mêmes 100 offres × 2 profils :
   - **Chronologique** : le tri actuel (`created_at` décroissant), référence à battre.
   - **Hybride** : le score des §4.3 à §4.5.
   - **Two-Pass** : le calcul pur du §4.7 sur chaque offre (jamais `evaluate_offer_two_pass`, qui écrit en base et consomme le quota). Coût estimé à environ 3,5 $ pour un passage unique (mesure locale : 0,0176 $ et 28 s par offre). Le coût et la latence réels sont relevés : ils servent à dimensionner le périmètre des meilleures offres analysées par le Two-Pass (§8, décision 2).
   - **Critère** (valeurs de départ, à confirmer à la lecture des premiers résultats) : le score hybride alimente seul les niveaux si, **sur chacun des 2 profils**, sa Precision@10 dépasse celle du chronologique d'au moins 0.2 (deux bonnes offres de plus dans le Top 10) **et** que la garde de rappel est respectée.
   - **Sinon**, l'identification rapide (§2) est livrée quand même, avec l'une de ces deux sources, choisie sur les mesures du benchmark :
     - (a) hybride corrigé (poids ou composantes), remesuré sur le même jeu ;
     - (b) hybride en présélection (rattachement, tri grossier), et calcul Two-Pass lancé automatiquement sur son Top N : quand la note Two-Pass existe, elle donne le niveau, avec les seuils déjà utilisés par `offers/page.tsx` (forte ≥ 4.0, moyenne ≥ 3.0). C'est le Lot 2 avancé dans le Lot 1. Garde-fous retenus le 2026-10-24 si cette option est choisie :
       - **Quota séparé** : nouvelle action `ApiUsageAction.AUTO_EVALUATION`, avec sa propre limite par palier dans `TIER_MONTHLY_LIMITS`. Jamais imputée à `EVALUATION` : ce quota mensuel (20 en palier gratuit, 100 en pro) serait vidé en quelques jours, et l'utilisateur perdrait ses boutons d'évaluation avancée sans comprendre pourquoi.
       - **Périmètre** : nouvelles offres de niveau fort ou moyen seulement, une fois par couple (offre, utilisateur), 5 par jour et par utilisateur au plus, soit environ 2,6 $ par utilisateur et par mois au maximum. Les limites par palier sont une décision commerciale de l'utilisateur.

   **Recommandation (2026-10-24)** : miser sur l'hybride seul. Le besoin est de séparer les offres adaptées des offres hors sujet, ce que l'hybride fait bien ; l'ordre fin entre offres d'un même domaine, où il est plus faible, compte peu pour ce besoin. L'option (b) n'est construite que si le benchmark l'impose.
3. **Métriques d'évaluation** :
   - **Precision@10 et Precision@20** par profil et par classement. Avec 2 profils, l'écart entre deux réglages n'est significatif que s'il est net.
   - **Taux de faux positifs dans le Top 20**, pour chaque classement.
   - **Garde de rappel** : aucune offre `applied` sous `FLOOR`.
4. **Tests automatisés (Pytest)**, tous exécutables sans réseau ni base externe :
   - `test_hybrid_scoring.py` : arithmétique du score avec des vecteurs fixes (normalisation par points applicables, règle de la moitié pour l'inconnu, bornes [0, 100]) ; correspondance score → niveau aux bornes des seuils (`FLOOR`, `MEDIUM_THRESHOLD`, `STRONG_THRESHOLD`).
   - Conditions (§4.4) : une offre hors zone ou au contrat non souhaité est plafonnée à `CAP_SCORE`, passe en niveau `weak`, reste rattachée, et `failed_conditions` le dit ; une localisation ou un contrat inconnu ne déclenche pas de plafond ; un candidat `full_remote` face à une offre sur site est plafonné.
   - Texte d'embedding de l'offre : il ne contient pas `competences_cles` (pas de double comptage avec la composante lexicale).
   - Two-Pass (§4.7), LLM simulé : le calcul pur n'écrit rien et ne touche pas au quota (base factice dont les méthodes d'écriture échouent) ; `evaluate_offer_two_pass` écrit `offer_evaluations` et `api_usage` mais plus `job_offers` ; un utilisateur B ne voit pas « évaluée » une offre que seul A a évaluée.
   - Cache `company_profiles` : pas de second appel API ou LLM pour une entreprise déjà connue ; une valeur connue n'est jamais écrasée par `None`.
   - Garde de correspondance de l'API Recherche d'entreprises (nom différent : rien n'est écrit).
   - Garde d'interaction : une offre `applied` sous `FLOOR` reste dans `matched_user_ids`.
   - Ségrégation multi-utilisateurs de `offer_relevance` (contrat d'API).

---

## 7. Roadmap d'Implémentation & Handoff

**Prérequis** : les conteneurs locaux (`jobtracker-backend`, `jobtracker-airflow`) doivent tourner avec la version de `python-jobspy` du lockfile (1.4.1). Avec 1.1.82, l'import Indeed de `jobboards.py` échoue.

**Lot 1, dans l'ordre** :
1. **Séparation du Two-Pass et banc de mesure** :
   - 1a. Séparation du Two-Pass (§4.7) : calcul pur sans effet de bord, `evaluate_offer_two_pass` qui n'écrit plus dans `job_offers`, `pipeline_stage` calculé par utilisateur dans le routeur. Livrable seul : corrige la fuite de l'état « Évaluée » entre utilisateurs. La partie routeur attend la précondition du §5.
   - 1b. Banc de mesure : export de prod lancé par l'utilisateur, échantillon de 100 offres, annotations du LLM-juge (§6.1) figées dans un fichier versionné, classements chronologique et Two-Pass (calcul pur) mesurés. Le classement hybride n'existe pas encore à ce stade : il est branché sur ce banc à l'étape 3.
2. **Taxonomie & `company_profiles`** : mapping natif depuis `raw_data`, API Recherche d'entreprises pour la taille, repli `gpt-5-nano`, écriture à l'ingestion, script de rattrapage du stock (`--apply` lancé par l'utilisateur), migration de `preferred_industries`, ajout de `preferred_company_sizes`.
3. **Score** : module de scoring réutilisant `domain_relevance` et `offer_fit`, collections `offer_embeddings` et `offer_relevance`. Les constantes (§4.6) sont calibrées sur le banc de l'étape 1b, puis le critère du §6.2 est appliqué : son issue décide de la source des niveaux affichés (hybride seul, hybride corrigé, ou hybride + Two-Pass sur le Top N) **avant** les étapes 4 et 5, qui sont livrées dans tous les cas.
4. **Rematch par score** : `offer_profile_matcher.py`, remplacement du rattachement par `source_query`, garde d'interaction.
5. **API & UI** (§5) : tri, filtres et badges, une fois les modifications en cours sur ces fichiers commitées.

* **Lot 2 (Prochain sprint)** : approfondissement LLM ciblé sur le Top N (périmètre exact selon §8, décision 2).
* **Lot 3 (Futur sprint)** : Boucle d'apprentissage continu par feedback utilisateur (méthode de Rocchio) et diversification MMR.

---

## 8. Décisions ouvertes

1. **Stockage du score par utilisateur — tranchée le 2026-10-24** : le score est stocké pour être affiché, dans la collection `offer_relevance`, sur le modèle de `offer_evaluations`. Alternative écartée : champ `relevance.<user_id>` dans `job_offers` (tri plus simple, mais index wildcard, document partagé qui grossit avec le nombre d'utilisateurs, et précédent de fuite avec `evaluation_score`).
2. **Relation avec le score IA Two-Pass — tranchée par l'utilisateur le 2026-10-24** : « limite-le aux meilleures offres car les deux n'ont pas le même purpose ». Le score de pertinence trie et rattache tout le stock à faible coût ; le Two-Pass reste l'analyse approfondie existante, **réservée aux meilleures offres** du score de pertinence. Sur la carte, deux badges distincts et nommés différemment (« Pertinence », « Analyse IA »), jamais fusionnés : ils ne répondent pas à la même question. Le Lot 2 n'est donc plus conditionné à un gain de précision du Two-Pass ; le benchmark (§6.2) ne sert plus qu'à en dimensionner le périmètre (N, à partir du coût et de la latence réels). Reste à préciser au moment du Lot 2 : déclenchement automatique sur le Top N (garde-fous de l'option (b) du §6.2) ou bouton d'évaluation proposé seulement sur ces offres.
3. **Partie API & UI — tranchée le 2026-10-24** : implémentée dans le Lot 1 par la même session que le backend (précondition au §5).

---

## 9. Journal des révisions

**2026-10-24 — révision après revue de cohérence avec le code :**
- §1 : affirmation sur les acronymes corrigée par la mesure du projet (0.28 → 0.43). Le seuil 0.85 cité auparavant est celui de la fusion d'alias de rôles (`ROLE_SIMILARITY_THRESHOLD`), pas un seuil de matching.
- §1.1 : ajout de l'existant à réutiliser (`domain_relevance`, `offer_fit`, `detect_contract_type`, `raw_data` par source, Two-Pass).
- §3.1 : ajout de `other` et de la frontière ESN.
- §3.2 : `relevance.<user_id>` déplacé vers la collection `offer_relevance`, `embedding` vers `offer_embeddings` ; sources distinctes pour secteur et taille ; migration de `preferred_industries`.
- §4.1 : écriture à l'ingestion à cause de la fusion de `raw_data` par clé ; tableau des champs natifs réellement disponibles (jobspy n'a pas de `company_size`) ; API Recherche d'entreprises pour la taille, sans le NAF pour le secteur.
- §4.2 : filtres appliqués avant l'embedding ; « score < 20 » déplacé vers le §4.4 (c'est une sortie de l'Étage 2).
- §4.3 : normalisation sémantique recalibrée (l'ancienne formule donnait 0 à un vrai match) ; score normalisé par points applicables (85 était le maximum sans préférences secteur/taille) ; règle unique de la moitié des points pour l'inconnu ; suppression du malus de -5, qui pouvait rendre le score négatif ; géographie ramenée aux données existantes.
- §4.4 : garde d'interaction ; §4.5 : constantes calibrées et versionnées.
- §5 : suppression des tags libres ; périmètre d'exécution signalé.
- §6 : benchmark en premier, biais de sélection, échantillon hors rattachement, garde de rappel, tests sans réseau.
- §7 : prérequis jobspy et ordre de livraison ; §8 : décisions ouvertes.

**2026-10-24 — décisions de l'utilisateur :** §8 décision 1 (score stocké dans `offer_relevance` et affiché) et décision 3 (API & UI dans le Lot 1, même session) tranchées ; §5 et §7 mis à jour en conséquence.

**2026-10-24 — quatre changements du score validés par l'utilisateur :**
- Géographie et contrat : conditions qui plafonnent le score en niveau faible (nouveau §4.4), au lieu de points additifs. La composante Localisation (15 pts) est retirée du §4.3 ; poids de départ redistribués : sémantique 45, lexical 30, séniorité 10, secteur 10, taille 5. Le §4.2 renvoie les écarts de contrat non rédhibitoires vers le §4.4.
- Double comptage supprimé : l'embedding de l'offre (§3.2) et le vecteur profil (§4.3.1) excluent les compétences, mesurées par la seule composante lexicale.
- Affichage en trois niveaux (forte, moyenne, faible) ; score exact et détail dans le tooltip, tri sur le score exact (§4.5, §5.2). `OfferRelevance.tier` devient `level`, avec `failed_conditions` ; `TIER_THRESHOLD` devient `MEDIUM_THRESHOLD`, et `STRONG_THRESHOLD` et `CAP_SCORE` s'ajoutent (§4.6).
- Benchmark : comparaison chronologique, hybride et Two-Pass sur les mêmes offres, juge d'une autre famille de modèle, critère de livraison (§6.2) ; la décision 2 du §8 sera tranchée par ces mesures.
- Renumérotation : l'ancien §4.4 (classification et rattachement) devient le §4.5, l'ancien §4.5 (constantes) devient le §4.6. Les entrées précédentes de ce journal gardent l'ancienne numérotation.

**2026-10-24 — séparation du Two-Pass et besoin utilisateur :**
- Nouveau §4.7, validé par l'utilisateur : `evaluate_offer_two_pass` est découpé en un calcul pur (utilisé par le benchmark) et un enregistrement (utilisé par les boutons). L'enregistrement n'écrit plus `evaluation_score` ni `pipeline_stage` dans `job_offers` : le premier était inutile, le second faisait voir à un utilisateur l'état « Évaluée » d'une offre évaluée par un autre.
- §2 : besoin de l'utilisateur inscrit comme objectif, « identifier d'un coup d'œil les offres adaptées à son profil ». Il est livré quelle que soit l'issue du benchmark ; §6.2 et §7 ne conditionnent plus la livraison, seulement la source des niveaux (options (a) et (b) du §6.2). §8 décision 2 mise à jour en conséquence.

**2026-10-24 — recommandation acceptée par l'utilisateur :**
- §4.7 : l'état « évaluée » est calculé par utilisateur dans le routeur ; le frontend ne change pas, `applications/page.tsx` sort de la précondition du §5.
- §6.1 : juge OpenAI, plus capable que `gpt-5-nano`.
- §6.2 : recommandation de miser sur l'hybride seul ; garde-fous de l'option (b) (action `AUTO_EVALUATION` à quota séparé, nouvelles offres fortes ou moyennes, 5 par jour et par utilisateur au plus).
- §7 : incohérence corrigée. Le benchmark ne pouvait pas comparer l'hybride à l'étape 1, puisque le score n'existe qu'à l'étape 3. L'étape 1 est scindée en 1a (séparation du Two-Pass) et 1b (banc de mesure figé) ; la calibration et la décision du §6.2 ont lieu à l'étape 3.

**2026-10-24 — décision 2 tranchée par l'utilisateur :**
- §8 décision 2 : le Two-Pass est réservé aux meilleures offres du score de pertinence, avec un badge distinct, parce que les deux scores n'ont pas le même objectif. Le benchmark ne décide plus de l'existence du Lot 2, il en dimensionne le périmètre. Reste ouvert pour le Lot 2 : déclenchement automatique ou bouton limité à ces offres.
- §5.2 (badge) et §6 point 2 (rôle du coût et de la latence mesurés) alignés sur cette décision.
