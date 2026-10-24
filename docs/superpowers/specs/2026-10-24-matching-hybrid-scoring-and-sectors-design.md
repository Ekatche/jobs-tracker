# Design Doc: Matching Hybride, Secteurs & Tailles d'Entreprise (Lot 1)

**Date** : 2026-10-24  
**Statut** : Validé  
**Périmètre** : Lot 1 — Mesure & Benchmark + Étage 1 (Filtres durs) + Étage 2 (Scoring Hybride Embeddings & Bonus Secteur/Taille) + UI Préférences & Tri Pertinence  

---

## 1. Contexte & Problématique

En production, un profil candidat accumule rapidement plus de 200 offres collectées sans hiérarchisation efficace. Trois limitations majeures ont été identifiées :
1. **Rattachement aveugle par `source_query`** : Toute offre issue d'une requête de recherche (ex: « Data Scientist ») est automatiquement rattachée au profil dans `offer_matches_criteria`, même si le contenu réel de l'offre est un faux positif (ex: stage RH, commercial).
2. **Échec des acronymes avec les embeddings bruts** : Des acronymes courants (*PM, PO, ML, QA, SRE, BI, DA, DE, DS*) présentent une similarité cosinus faible (< 0.85) avec leurs formes développées dans l'espace d'embedding, créant des ruptures de matching.
3. **Tri chronologique strict (`created_at: -1`)** : Les offres pertinentes sont noyées au milieu d'un flux non trié par adéquation.
4. **Absence de filtrage par secteur d'activité et taille d'entreprise** : Le champ `preferred_industries` existait dans le modèle Pydantic `CandidatePreferences` mais n'était ni exposé dans l'interface, ni enrichi sur les offres, ni pris en compte dans le scoring.

---

## 2. Objectifs & Non-Objectifs (Lot 1)

### Objectifs
* **Mesure & Vérité terrain** : Disposer d'un jeu de test de référence combinant les interactions de prod existantes (`applied`, `hidden`) et un échantillon évalué par LLM-juge (avec validation croisée manuelle) pour mesurer la précision (Precision@20).
* **Taxonomie & Profils Entreprise** : Structurer une taxonomie fermée de ~12 secteurs et 4 tailles d'entreprise, stockée dans une collection dédiée `company_profiles` avec cache pour éviter les requêtes redondantes.
* **Scoring Hybride Déterministe & Sémantique** : Remplacer le matching binaire par un score continu de 0 à 100 combinant similarité sémantique (embeddings), compétences clés, géographie, séniorité et bonus secteur/taille.
* **Seuil souple & Tri par Pertinence dans l'UI** : Afficher les offres triées par pertinence par défaut avec un badge de score explicatif, et reléguer les offres sous le seuil (< 60) dans une section repliée « Moins pertinentes » sans les supprimer.
* **Préférences utilisateur complètes** : Permettre la sélection intuitive de secteurs et tailles d'entreprise dans `TargetingPreferencesSection`.

### Non-Objectifs (Réservés aux Lots 2 et 3)
* Rerank LLM complet à chaque affichage (Lot 2 : limité au Top N).
* Ré-apprentissage dynamique des poids par utilisateur via Rocchio / feedback loop (Lot 3).
* Algorithme de diversification MMR (Lot 3).

---

## 3. Architecture & Modèle de Données

### 3.1. Taxonomie Standardisée

#### Secteurs d'activité (12 catégories normalisées) :
1. `tech_it` : Tech, Informatique, Édition logicielle & Télécoms
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

#### Tailles d'entreprise (4 segments normalisés) :
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
    sector: Optional[str] = None  # Valeur parmi la taxonomie normalisée
    company_size: Optional[str] = None  # Valeur parmi les 4 tailles
    source: str  # "native_source" (FT/Jobspy) | "llm_inferred" | "manual"
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```
*Index :* `{ "company_name_normalized": 1 }` (unique).

#### Collection `job_offers` (Enrichissement)
* `sector`: `Optional[str]` (hérité du profil entreprise ou de l'offre)
* `company_size`: `Optional[str]`
* `embedding`: `Optional[List[float]]` (calculé une seule fois sur `poste` + `competences_cles` + début de description synthétisée)
* `relevance`: `Dict[str, UserRelevance]` indexé par `user_id` :
  ```python
  class UserRelevance(BaseModel):
      score: float  # Entre 0 et 100
      tier: Literal["relevant", "low_relevance"]  # Seuil calibré (ex: 60)
      breakdown: Dict[str, float]  # Détail des points attribués
      updated_at: datetime
  ```
*Index :* `{ "matched_user_ids": 1, "created_at": -1 }`, `{ "relevance.<user_id>.score": -1 }`.

#### Modèle `CandidatePreferences` (`backend/app/models.py` & `frontend/src/types/coverLetter.ts`)
* `preferred_industries: List[str] = Field(default_factory=list)` (existant, désormais branché)
* `preferred_company_sizes: List[str] = Field(default_factory=list)` (nouveau)

---

## 4. Pipeline d'Enrichissement & Scoring

### 4.1. Enrichissement des Entreprises
1. **Extraction native** :
   - France Travail : mapping direct de `secteurActiviteLibelle` vers la taxonomie + `trancheEffectifEtab` vers `company_size`.
   - JobSpy / ATS : extraction des métadonnées `company_industry` / `company_size` quand disponibles.
2. **Fallback LLM avec cache** :
   - Si l'entreprise n'est pas encore dans `company_profiles` et sans métadonnées natives, un appel structuré léger (`gpt-5-nano` avec JSON schema contraint sur la taxonomie) déduit le secteur et la taille à partir du nom d'entreprise et du contexte de l'offre.
   - Le résultat est stocké en base dans `company_profiles`. Coût marginal quasi-nul (~300 entreprises uniques en base).

### 4.2. Étage 1 : Filtrage Éliminatoire (Hard Filter)
Une offre est exclue du matching pour un utilisateur si :
- Elle contient un mot-clé de `excluded_keywords`.
- Le contrat est incompatible de manière rédhibitoire (ex: offre de stage/alternance alors que le candidat cherche un CDI/CDD/Freelance).
- Le score brut calculé à l'Étage 2 est inférieur au plancher de viabilité (score < 20/100). Ceci supprime le biais du `source_query`.

### 4.3. Étage 2 : Score Hybride (0 - 100 points)

$$\text{Score} = \text{Score}_{\text{semantique}} + \text{Score}_{\text{lexical}} + \text{Score}_{\text{geo}} + \text{Score}_{\text{seniorite}} + \text{Bonus}_{\text{secteur/taille}}$$

1. **Proximité Sémantique (Poids : 40 pts)** :
   - Similarité cosinus entre le vecteur profil ($V_{\text{profil}}$ construit depuis les rôles cibles, headline et compétences) et le vecteur offre ($V_{\text{offre}}$).
   - Normalisation : $\max(0, (\text{cosine} - 0.5) / 0.5) \times 40$. Résout nativement les acronymes sans table statique fragile.
2. **Recouvrement Lexical & Compétences Clés (Poids : 25 pts)** :
   - Présence des compétences clés et mots-clés distinctifs de l'offre dans les compétences déclarées du profil candidat, pondérée par l'IDF.
3. **Localisation & Télétravail (Poids : 15 pts)** :
   - 15 pts si pleine adéquation géographique (même ville / rayon accepté) ou télétravail total conforme.
   - 7 pts si département limitrophe ou télétravail partiel compatible.
   - 0 pt si discordance géographique nette.
4. **Adéquation Séniorité (Poids : 5 pts)** :
   - 5 pts si niveau identique ou non spécifié.
   - 3 pts si 1 niveau d'écart dans `SENIORITY_ORDER`.
   - 0 pt au-delà.
5. **Bonus / Ajustement Secteur & Taille (Poids : 15 pts)** :
   - **Secteur** : +10 pts si le secteur de l'entreprise correspond aux `preferred_industries` du candidat.
   - **Taille** : +5 pts si la taille correspond aux `preferred_company_sizes`.
   - **Non renseigné / neutre** : 0 pt (aucune pénalité afin de ne jamais punir une offre pour manque de métadonnées).
   - **Secteur explicitement différent** : -5 pts d'ajustement doux.

### 4.4. Classification par Seuils
* **`tier: "relevant"`** : $\text{Score} \ge 60$
* **`tier: "low_relevance"`** : $20 \le \text{Score} < 60$
* Les offres avec $\text{Score} < 20$ sont retirées de `matched_user_ids`.

---

## 5. Interface Utilisateur & Expérience (UI/UX)

### 5.1. Écran Préférences Candidat (`TargetingPreferencesSection.tsx`)
* Nouvelle section accordéon dédiée : **« Secteurs d'activité & Taille d'entreprise »**.
* Sélection visuelle par badges/chips cliquables des 12 secteurs standards + champ pour ajouter des tags personnalisés.
* Boutons de sélection multiple pour les 4 tailles d'entreprise.
* Sauvegarde réactive déclenchant le recalcul asynchrone du matching (`rematch_user`).

### 5.2. Écran Liste & Kanban des Offres (`offers/page.tsx`)
* **Barre d'outils / Contrôle de tri** :
  * Sélecteur de tri par défaut sur **« Pertinence »** (tri sur `relevance.<user_id>.score` décroissant), avec possibilité de basculer sur « Plus récentes » (`created_at`).
  * Nouveaux filtres déroulants pour filtrer par Secteur et par Taille d'entreprise.
* **Carte d'offre** :
  * Affichage d'un badge de score coloré (ex: `92% Pertinence` en vert émeraude, `74%` en bleu ciel).
  * Tooltip détaillant la décomposition du score au survol.
* **Section repliée « Moins pertinentes »** :
  * Les offres avec `tier === "low_relevance"` sont regroupées par défaut sous un bandeau replié : *« X offres moins pertinentes (< 60%) — Déplier »*.
  * L'utilisateur peut ainsi parcourir ses offres prioritaires sans être pollué, tout en conservant la visibilité complète en un clic.

---

## 6. Stratégie de Mesure & Validation

1. **Jeu de test de référence (Benchmark)** :
   - Extraction des 41 interactions existantes en prod (30 positives `applied`, 11 négatives `hidden`).
   - Génération d'annotations LLM (juge) sur un échantillon représentatif de 100 offres pour les 2 profils actifs en prod.
   - Validation manuelle d'un sous-ensemble de 20 offres pour calibrer l'accord du juge.
2. **Métriques d'évaluation** :
   - **Precision@10 et Precision@20** : Proportion d'offres réellement pertinentes dans le top 10 et top 20 affiché.
   - **Taux de faux positifs dans le Top 20** : Doit chuter drastiquement par rapport au tri chronologique brut actuel.
3. **Tests automatisés (Pytest)** :
   - Tests unitaires sur le calcul du score hybride (`test_hybrid_scoring.py`).
   - Tests de non-régression sur le cache `company_profiles`.
   - Tests du contrat d'API et de la ségrégation multi-utilisateurs du score `relevance.<user_id>`.

---

## 7. Roadmap d'Implémentation & Handoff

* **Lot 1 (Présent document)** : Mesure + `company_profiles` + Pipeline de scoring hybride + Tri UI & Section repliée.
* **Lot 2 (Prochain sprint)** : Rerank LLM ciblé sur le Top 20 des offres candidates.
* **Lot 3 (Futur sprint)** : Boucle d'apprentissage continu par feedback utilisateur (méthode de Rocchio) et diversification MMR.
