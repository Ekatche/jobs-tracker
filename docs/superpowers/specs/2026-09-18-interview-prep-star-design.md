# Design Spec: Phase 6 — Interview Prep ("STAR+R & Behavioral Intelligence")

## 1. Contexte & Objectif
La Phase 6 complète le cycle de candidature de **Career-Ops** dans `job-tracker`. Lorsqu'une offre a été évaluée (Score >= 1.0) ou qu'une candidature atteint l'étape `interview`, le candidat doit pouvoir préparer ses entretiens de manière personnalisée, percutante et déterministe.

Inspiré de l'intelligence éprouvée de `career-ops` (`interview-prep.md`, `interview-redflag.md`, `match-star.mjs`), ce module génère un **Kit de Préparation d'Entretien modulaire et isolé par offre**.

---

## 2. Piliers Fonctionnels & Principes d'Ingénierie

### 2.1 Approche Modulaire
Plutôt qu'un bloc monolithique coûteux et rigide, la génération est découpée en **4 modules indépendants**, déclenchables et régénérables unitairement :
1. **Module 1 : Banque d'Histoires STAR+R** (3 à 5 histoires percutantes extraites des expériences réelles du profil candidat et ciblées sur les exigences clés du Bloc B).
2. **Module 2 : Packs d'Audience Segmentés** (Recruteur / RH, Hiring Manager, Panel / Pairs Techniques).
3. **Module 3 : Questions Anticipées** (Questions comportementales mappées sur les histoires STAR+R, et questions techniques probables taguées `[inferred from JD]`).
4. **Module 4 : Questions Inversées & Détection Anti Red-Flags** (Questions tactiques à poser au recruteur pour auditer la santé du projet, la culture et l'autonomie).

### 2.2 Règles de Vérité et Anti-Hallucination
- **Aucune invention d'expérience** : Les histoires STAR+R doivent impérativement s'appuyer sur les faits déclarés dans le profil candidat (`candidate_profile`).
- **Transparence des sources** : Les questions techniques doivent être explicitement rattachées soit à une exigence du Bloc B, soit taguées `[inferred from JD]`.
- **Édition Libre** : L'utilisateur peut modifier manuellement chaque champ du kit (titre, situation, questions, etc.) sans risque d'écrasement intempestif.
- **Export Markdown** : Un bouton permet de copier ou exporter l'intégralité du kit au format Markdown propre, prêt à être emporté ou imprimé.

---

## 3. Architecture Technique & Modèles de Données

### 3.1 Schémas Backend (`app/models.py`)

```python
class StarRStory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    theme: str  # ex: Architecture, Leadership, Gestion de crise, Optimisation
    target_requirement: str  # Exigence ciblée du Bloc B
    situation: str
    task: str
    action: str
    result: str
    reflection: str  # Enseignement / ce qu'on ferait différemment
    key_tags: List[str] = Field(default_factory=list)

class AudiencePackRecruiter(BaseModel):
    pitch_30s: str
    comp_strategy: Dict[str, str] = Field(default_factory=dict)  # "volunteer", "avoid"
    red_flags_they_screen_for: List[str] = Field(default_factory=list)
    key_questions_to_ask_recruiter: List[str] = Field(default_factory=list)

class AudiencePackHiringManager(BaseModel):
    strategic_alignment: str
    internal_vocabulary: List[str] = Field(default_factory=list)
    sharp_questions: List[str] = Field(default_factory=list)

class AudiencePackTechPanel(BaseModel):
    architecture_points: List[str] = Field(default_factory=list)
    tradeoffs_and_risks: List[str] = Field(default_factory=list)
    reverse_questions: List[str] = Field(default_factory=list)

class AnticipatedQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str  # "behavioral" | "technical"
    question: str
    why_it_will_be_asked: str  # Source Bloc B ou "[inferred from JD]"
    mapped_story_id: Optional[str] = None
    key_points_to_cover: List[str] = Field(default_factory=list)

class ReverseQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str  # "Culture & Rythme", "Dette Technique", "Organisation & Autonomie"
    question: str
    probe_intent: str

class InterviewPrep(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    offer_id: PyObjectId
    user_id: PyObjectId
    stories: List[StarRStory] = Field(default_factory=list)
    recruiter_pack: Optional[AudiencePackRecruiter] = None
    hm_pack: Optional[AudiencePackHiringManager] = None
    tech_pack: Optional[AudiencePackTechPanel] = None
    anticipated_questions: List[AnticipatedQuestion] = Field(default_factory=list)
    reverse_questions: List[ReverseQuestion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
```

### 3.2 Endpoints REST (`app/routers/interview_prep.py`)
- `GET /api/offers/{offer_id}/interview-prep` : Récupération du kit d'entretien pour l'offre donnée.
- `POST /api/offers/{offer_id}/interview-prep/generate/stories` : Génération des histoires STAR+R via Gemini 3.7 Flash + `candidate_profile` + `offer_evaluation`.
- `POST /api/offers/{offer_id}/interview-prep/generate/audience-pack` : Génération des 3 packs d'audience.
- `POST /api/offers/{offer_id}/interview-prep/generate/questions` : Génération des questions comportementales et techniques anticipées (avec mapping d'histoires).
- `POST /api/offers/{offer_id}/interview-prep/generate/reverse-questions` : Génération des questions inversées / anti red-flags.
- `PUT /api/offers/{offer_id}/interview-prep` : Mise à jour manuelle des histoires ou contenus par l'utilisateur.
- `GET /api/offers/{offer_id}/interview-prep/export` : Export brut en format texte Markdown.

### 3.3 Quotas & Suivi Consommation
Chaque appel de génération modulaire décompte l'action `ApiUsageAction.INTERVIEW_PREP` avec le modèle standard `gemini/gemini-3.7-flash`, contrôlé par `require_user_quota(user_id, ApiUsageAction.INTERVIEW_PREP)`.

---

## 4. Expérience Utilisateur Frontend

### 4.1 Onglet dédié sur `/offers/[id]`
- Ajout d'un 4ème onglet : `activeTab === "interview"`.
- Header d'action :
  - Barre de progression ou état des modules (ex : *3/4 modules générés*).
  - Bouton *"Tout générer"* ou boutons de génération unitaire par module.
  - Bouton *"Exporter en Markdown"* (téléchargement `.md` et copie presse-papier).
- Sections interactives :
  1. **Banque STAR+R** : Accordéons fluides avec mise en exergue des sections S, T, A, R, +R et badge d'exigence Bloc B.
  2. **Packs d'Audience** : Sélecteur d'onglet à 3 facettes (*Recruteur*, *Manager*, *Pairs*) pour basculer facilement en direct.
  3. **Questions Anticipées** : Cartes catégorisées avec bouton de liaison vers l'histoire STAR+R correspondante.
  4. **Questions Inversées (Anti Red-Flags)** : Liste des questions à poser avec encart "Ce que révèle la réponse".

### 4.2 Passerelle depuis le Kanban (`/applications`)
- Dans `ApplicationDetails.tsx`, affichage d'une carte d'action dédiée dès que la candidature est en cours, avec un bouton direct *"🎯 Préparer mon entretien"* redirigeant vers `/offers/{offer_id}?tab=interview`.

---

## 5. Stratégie de Tests (TDD)
1. **Backend Unit Tests** :
   - `test_interview_prep_models.py` : Validation des schémas Pydantic et sérialisation.
   - `test_interview_prep_service.py` : Mocks LiteLLM pour valider le parsing et l'intégrité des 4 modules de prompts.
   - `test_interview_prep_api.py` : Test des endpoints REST avec authentification et gestion des quotas.
2. **Frontend Build & Integration** :
   - `npm run build` propre, sans erreur TypeScript.
   - Validation de la navigation et de l'interactivité des 4 modules.
