# Ingestion, Normalisation & Déduplication des Offres d'Emploi

Ce document définit l'architecture de collecte, de normalisation et de déduplication des offres d'emploi pour la plateforme SaaS `job-tracker`. Il formalise la stratégie multi-tenant, la couverture des ATS (tech et non-tech) et le pipeline de matching.

---

## 1. Modèle de Données & Isolation Multi-Tenant

### A. Le Problème du Pool Global
Dans un modèle SaaS, le scraping ne doit **jamais** être exécuté individuellement par utilisateur (inondation de requêtes, explosion des coûts d'API Firecrawl/Tavily, blocages Cloudflare). La base d'offres est donc un **catalogue partagé (Pool Global)**.

Cependant, les statuts d'une offre pour un utilisateur (*Sauvegardée*, *Masquée*, *Refusée*, *Postulée*) ne doivent jamais impacter les autres utilisateurs.

### B. Architecture Découplée (Lecture Seule vs Interaction Utilisateur)

```
[ Pool Global: job_offers ] (Lecture seule pour les utilisateurs)
  ├── _id: ObjectId
  ├── company, position, clean_title, canonical_title
  ├── location, contract_type, remote_status
  ├── url, source_domain, ats_platform
  ├── description, raw_text, embedding_vector
  └── pipeline_stage: discovered | evaluated | expired
         │
         │  1:N
         ▼
[ Interactions: user_offer_interactions ] (Isolé par user_id)
  ├── user_id: ObjectId (Indexé)
  ├── offer_id: ObjectId (Indexé)
  ├── status: SAVED | HIDDEN | DISMISSED | APPLIED
  ├── match_score: float (Score de pertinence calculé pour ce candidat)
  └── updated_at: datetime
```

Dès qu'un utilisateur postule, la passerelle crée un `JobApplication` avec `offer_id` rattaché à son `user_id`.

### C. Protection contre les Purges (Rétention & Soft-Delete)
* **Durée de rétention standard** : Les offres actives sont conservées **30 jours** (la durée de vie moyenne d'une annonce).
* **Interdiction de Hard Delete sur les offres référencées** :
  * Le cron de nettoyage ne supprime jamais physiquement (`delete_many`) une offre si son `_id` est présent dans `JobApplication.offer_id` ou référencé dans `user_offer_interactions`.
  * Si une offre expire ou est close par le recruteur, elle passe à `pipeline_stage: "expired"` (soft-delete), permettant au candidat de conserver l'historique complet de sa candidature.

---

## 2. Stratégie de Collecte : "Demand-Driven Scraping"

Pour ne pas scraper dans le vide des métiers inutiles, Airflow n'utilise plus de requêtes codées en dur, mais orchestre une collecte guidée par les besoins réels des utilisateurs.

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Profils & Alertes Candidats (Demande active)              │
│    - Rôles cibles (ex: "Contrôleur de gestion", "AI Eng")   │
│    - Villes cibles (ex: "Lyon", "Nantes", "Remote")         │
│    ──► Enregistrés dans SearchSubscriptions                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Déduplication des Requêtes (Airflow)                     │
│    Agrégation distincte : 100 utilisateurs sur "Data Lyon"   │
│    = 1 seule requête exécutée sur le réseau                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. On-Demand Scrape (Extension Chrome / Coller URL)         │
│    Extraction instantanée d'une URL soumise par un user     │
│    ──► Enrichit immédiatement le pool global                │
└─────────────────────────────────────────────────────────────┘
```

### Fréquences Recommandées des Crons Airflow

| DAG / Tâche | Fréquence | Expression Cron | Objectif |
|---|---|---|---|
| `collect_job_offers` | 2x / jour en semaine | `0 6,13 * * 1-5` | Capte les parutions de nuit (06h UTC) et le pic de fin de matinée (13h UTC). |
| `verify_job_offers` | 1x / jour la nuit | `0 2 * * *` | Vérifie la validité des liens (détection 404/expirées). |
| `clean_job_offers` | 1x / jour la nuit | `0 4 * * *` | Déduplication et archivage des offres > 30 jours sans candidature liée. |
| `archive_applications` | 1x / jour la nuit | `0 3 * * *` | Archivage des candidatures inactives > 90 jours. |

---

## 3. Matrice de Couverture des Sources & ATS (Tech et Hors-Tech)

Pour permettre aux candidats de **tous les secteurs** (industrie, santé, finance, juridique, commerce, tech) de trouver des opportunités, le collecteur intègre 4 catégories de sources :

| Catégorie | Domaines & Plateformes | Profils & Métiers Ciblés |
|---|---|---|
| **Grands Groupes & Multinationales** | `myworkdayjobs.com` (Workday)<br>`smartrecruiters.com`<br>`jobs2web.com` (SAP SuccessFactors)<br>`taleo.net` (Oracle Taleo)<br>`icims.com` | **Tous métiers** (Ouvriers, logisticiens, juristes, acheteurs, pharmaciens, comptables, ingénieurs, managers). |
| **Job Boards Nationaux Généralistes** | `francetravail.fr` (France Travail)<br>`hellowork.com`<br>`apec.fr`<br>`indeed.fr`<br>`cadremploi.fr` | **Tous métiers** (PME régionales, secteur public, artisanat, commerce, cadres non-tech). |
| **PME & Scale-ups Européennes** | `personio.de` / `personio.com`<br>`workable.com` / `apply.workable.com`<br>`teamtailor.com`<br>`recruitee.com`<br>`breezy.hr` / `flatchr.io` | **Multi-secteurs** (Agences, retail, hôtellerie, conseil, services, PME). |
| **Tech, Startups & IA Mondiales** | `greenhouse.io`<br>`lever.co`<br>`ashbyhq.com` / `jobs.ashbyhq.com`<br>`bamboohr.com`<br>`welcometothejungle.com` | **Tech & Digital** (Développeurs, Data/AI, Product, Growth, Design). |

---

## 4. Pipeline de Normalisation en 4 Couches

Face à la multiplicité des formulations recruteurs (`"Data Scientist (H/F) - CDI"`, `"[LYON] Lead Data Scientist F/H 🚀"`, `"Senior Data Scientist | Python"`), le traitement s'opère en 4 passes successives :

### Couche 1 : Nettoyage Syntaxique Déterministe
* Suppression des mentions légales : `(H/F)`, `(F/H)`, `HF`, `Homme/Femme`.
* Suppression des types de contrat : `CDI`, `CDD`, `Stage`, `Alternance`, `Freelance`, `Interim`.
* Suppression des balises et localisations polluantes : `[Lyon]`, `- Paris`, `| Remote`, `Télétravail`.
* Suppression des éléments marketing : emojis (`🚀`, `🔥`), mentions `[URGENT]`, `Top Mission`.
* Normalisation des espaces, passage en majuscules, suppression de la ponctuation, tri alphabétique des tokens significatifs.

### Couche 2 : Extraction de la Séniorité & Titre Canonique
* **Séniorité** isolée dans `seniority_level` : `intern` | `junior` | `mid` | `senior` | `lead` | `principal` | `director`.
* **Titre Canonique (`canonical_title`)** : Mappé via un dictionnaire de synonymes ou classification (ROME / O*NET) :
  * *"Ingénieur Données"*, *"Data Engineer"*, *"Consultant ETL"* ➔ **`Data Engineer`**
  * *"Ingénieur IA"*, *"AI Engineer"*, *"Machine Learning Engineer"* ➔ **`ML Engineer`**
  * *"Contrôleur de gestion"*, *"Financial Controller"* ➔ **`Contrôleur de gestion`**

### Couche 3 : Déduplication Multi-Critères (Fuzzy & Jaccard)
1. **Passe stricte** : Clé composite `hash(Entreprise_normalisée + Ville_normalisée + Titre_canonique)` avec fenêtre glissante de 15 jours.
2. **Passe floue (Levenshtein / Jaro-Winkler)** : Similarité > 85% sur le titre pour la même entreprise et même ville.
3. **Passe de contenu (Distance de Jaccard)** : Comparaison des n-grammes de la description (> 80% de similitude textuelle = détection de multidiffusion Indeed/LinkedIn).

### Couche 4 : Déduplication Sémantique par Embeddings
* Vecteur dense généré sur la signature normalisée de l'offre : `"{company} | {canonical_title} | {location} | {first_300_chars}"`.
* Si `cosine_similarity > 0.94` à moins de 20 jours d'intervalle chez le même employeur : fusion dans une offre unique avec multi-liens sources (`sources: [linkedin_url, direct_ats_url]`).
