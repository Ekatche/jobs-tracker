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

### Normalisation Sémantique des Rôles (Registre d'Alias Auto-Alimenté)

Problème : Deux utilisateurs ayant `"Ingénieur IA"` et `"AI Engineer"` dans leurs préférences lancent deux requêtes distinctes, fragmentant la couverture. Solution : registre MongoDB `role_aliases` avec embeddings sémantiques.

**Architecture** :
```
role_aliases : {
  canonical: "AI Engineer",
  embedding: [0.12, -0.45, 0.78, ...],  // text-embedding-3-small (1536 dims)
  variants: ["ai engineer", "ingénieur ia", "ingenieur ia", "artificial intelligence engineer", ...]
}
```

**Logique** :
1. **Fast Path** (0 coût token) : Recherche exacte insensible à la casse dans `variants`. Hit → retourne `canonical`.
2. **Slow Path** (1 appel OpenAI Embedding/run) : Calcul embedding du rôle brut. Similarité cosinus ≥ 0.85 avec les canoniques existants → rattachement et ajout de la variante. Sinon, création d'un nouveau canonical.
3. **Fallback** : En cas d'erreur (Mongo, OpenAI), retourne le rôle brut nettoyé.

**Implémentation** : `app/services/role_normalizer.py` (126 lignes). Seed initial dans `scripts/seed_role_aliases.py` (24 rôles tech : Data Engineer, AI Engineer, Backend Developer, etc. avec variantes FR/EN). Appels depuis `build_search_queries()` en `app/tasks/job_offers_collectors.py` avec mémoïsation par run pour éviter les refactorisations inutiles.

**Bénéfice** : Mutualisation multi-utilisateurs. 100 profils ayant `target_roles = ["AI Engineer", "Ingénieur IA"]` convertis à `["AI Engineer", "AI Engineer"]` → dédup intra-profil + round-robin produit une seule requête au lieu de deux.

### Fréquences Recommandées des Crons Airflow

| DAG / Tâche | Fréquence | Expression Cron | Objectif |
|---|---|---|---|
| `collect_job_offers` | 2x / jour en semaine | `0 7,16 * * 1-5` | Capte les parutions nuit (07h UTC) et fin matinée (16h UTC). |
| `verify_job_offers` | 1x / jour la nuit | `0 2 * * *` | Vérifie la validité des liens (détection 404/expirées). |
| `clean_job_offers` | 1x / jour la nuit | `0 4 * * *` | Déduplication et archivage des offres > 30 jours sans candidature liée. |
| `archive_applications` | 1x / jour la nuit | `0 3 * * *` | Archivage des candidatures inactives > 90 jours. |

---

## 3. Matrice de Couverture des Sources & ATS (Tech et Hors-Tech)

Pour permettre aux candidats de **tous les secteurs** (industrie, santé, finance, juridique, commerce, tech) de trouver des opportunités, le collecteur intègre 4 catégories de sources :

| Catégorie | Domaines & Plateformes | Méthode d'Extraction | Statut |
|---|---|---|---|
| **Tech & Startups Mondiales** | `greenhouse.io`, `lever.co`, `workable.com` | **Zero-Token ATS API** direct HTTP (0 token LLM) | ✅ Implémenté (`app/services/ats/router.py`) |
| **PME & Scale-ups Européennes** | `ashbyhq.com`, `teamtailor.com`, `recruitee.com`, `personio.de`, `breezy.hr` | **Schema.org JSON-LD Parser** direct HTTP (0 token LLM) | ✅ Implémenté (`app/services/ats/router.py`) |
| **Grands Groupes & Multinationales** | `myworkdayjobs.com`, `smartrecruiters.com`, `jobs2web.com`, `taleo.net`, `icims.com` | Extraction hybride JSON-LD + Crawl4AI avec LLM | ✅ Implémenté |
| **Job Boards Nationaux Généralistes** | `welcometothejungle.com`, `apec.fr`, `francetravail.fr`, `hellowork.com`, `cadremploi.fr`, `linkedin.com` | Funnel CrewAI 3 passes + Crawl4AI optimisé | ✅ Implémenté |

### Zero-Token ATS & JSON-LD Router (`app/services/ats/router.py`)
Avant tout appel lourd et coûteux à Crawl4AI (Chromium headless + extraction LLM) :
1. Le routeur intercepte l'URL de l'offre.
2. Si l'URL correspond à **Greenhouse**, **Lever** ou **Workable**, il interroge directement leurs API REST publiques pour obtenir les champs structurés (`title`, `company`, `location`, `description`, `salary`) en quelques millisecondes à coût token nul.
3. Pour tous les autres domaines (Ashby, Teamtailor, Personio, etc.), il effectue une requête HTTP légère (GET) et parse les balises `<script type="application/ld+json">` avec type `@type: "JobPosting"`.
4. En cas d'échec ou de page dynamique protégée, le système bascule gracieusement sur le crawling standard Crawl4AI.

### Funnel de Recherche Équilibré CrewAI (`job_trackers/tools/custom_tool.py`)
Pour éviter que les agrégateurs à fort trafic (HelloWork, Indeed) ne monopolisent les résultats au détriment des ATS directs d'entreprises :
- **Passe 1 - Job boards nationaux (max 12)** : Welcome to the Jungle, Apec, France Travail, HelloWork, Cadremploi.
- **Passe 2 - ATS direct entreprises & portails (max 10)** : Greenhouse, Lever, Workable, Ashby, Teamtailor, Recruitee, Personio, Workday.
- **Passe 3 - LinkedIn Jobs (max 8)** : Ciblage spécifique des offres LinkedIn directes.
- Chaque passe dispose d'une tolérance aux pannes isolée (`try/except`) et les URLs sont dédupliquées à l'insertion.

---

## 4. Pipeline de Normalisation en 4 Couches (Implémenté)

Face à la multiplicité des formulations recruteurs (`"Data Scientist (H/F) - CDI"`, `"[LYON] Lead Data Scientist F/H 🚀"`, `"Senior Data Scientist | Python"`), le traitement s'opère en 4 passes successives dans `app/services/normalization.py` :

### Couche 1 : Nettoyage Syntaxique Déterministe (`clean_job_title_syntax`)
* **Mentions légales éliminées** : `(H/F)`, `(F/H)`, `HF`, `Homme/Femme`, `M/F/D`, `(h/f/x)`.
* **Types de contrat retirés de l'intitulé** : `CDI`, `CDD`, `Stage`, `Alternance`, `Freelance`, `Interim`, `Apprentissage`, `Contrat Pro`.
* **Balises et localisations polluantes supprimées** : `[Lyon]`, `[CDI]`, `- Paris`, `| Remote`, `Télétravail`, `Full Remote`.
* **Éléments marketing et emojis éliminés** : `🚀`, `🔥`, `⭐`, `[URGENT]`, `Top Mission`, `Super opportunité`.
* **Garde-fou Profil Candidat** : Appliqué également aux préférences saisies par les candidats dans `build_search_queries` pour garantir qu'aucune scorie utilisateur ne contamine les requêtes web.

### Couche 2 : Extraction de la Séniorité & Titre Canonique (`extract_seniority`, `role_normalizer.py`)
* **Séniorité standardisée** dans `seniority_level` :
  - `intern` : Stage, Alternance, Apprentissage, Intern
  - `junior` : Junior, Jr, Débutant, Graduate, 0-2 ans
  - `mid` : Confirmé, Intermédiaire, 2-5 ans
  - `senior` : Senior, Sr, Confirmé+, 5+ ans
  - `lead` : Lead, Principal, Staff, Tech Lead, Architecte
  - `director` : Director, Directeur, VP, Head of, Chief, CTO
* **Titre Canonique (`canonical_title`)** : Mappé via le registre MongoDB `role_aliases` (24 rôles tech canoniques avec résolution sémantique cosinus ≥ 0.85).

### Couche 3 : Déduplication Multi-Critères (`are_offers_duplicates`, `jaccard_description_similarity`)
1. **Passe exacte** : URLs identiques = doublon immédiat.
2. **Passe entreprise + ville** : Entreprise normalisée (`normalize_company`) + compatibilité géographique (`normalize_city`).
3. **Passe floue sur l'intitulé (Levenshtein / SequenceMatcher)** : Similarité ≥ 82% sur l'intitulé nettoyé par la Couche 1.
4. **Passe de contenu (Distance de Jaccard)** : Tokenisation de la description (hors stopwords français/anglais). Si Jaccard ≥ 65% pour la même entreprise : détection formelle de multidiffusion (ex: Indeed / LinkedIn / ATS avec des intitulés légèrement différents).

### Couche 4 : Fusion & Consolidation Multi-Sources (`merge_multidiffusion_offers`, `deduplicate_and_merge_offers`)
* **Hiérarchie de priorité des sources** :
  - **Priorité 100** : ATS direct entreprise (`greenhouse.io`, `lever.co`, `workable.com`, `ashbyhq.com`, etc.)
  - **Priorité 80** : Job boards qualifiés (`welcometothejungle.com`, `apec.fr`, `francetravail.fr`)
  - **Priorité 50** : Agrégateurs généralistes (`linkedin.com`, `hellowork.com`, `indeed.com`, `cadremploi.fr`)
* **Consolidation intelligente** :
  - L'URL la plus noble (ATS direct) devient l'URL principale (`url`).
  - Les URLs des autres parutions sont rattachées dans `alternative_urls`.
  - **Préservation des métadonnées les plus riches** : Si le salaire est présent sur une source mais absent sur l'autre, le salaire réel est conservé. Idem pour le type de contrat et la description la plus détaillée.
  - **Sauvegarde MongoDB** : Les documents survivants sont mis à jour dans `remove_similarity_duplicates` (`clean_job_offers.py`) avant l'archivage sécurisé des doublons.
