from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
import uuid
from bson import ObjectId
from pydantic import BaseModel, Field, GetCoreSchemaHandler, HttpUrl, ConfigDict, model_validator
from pydantic_core import core_schema


# Fonction utilitaire pour créer des dates UTC avec timezone
def utcnow_with_timezone():
    return datetime.now(timezone.utc)


# Classe personnalisée pour gérer les ObjectId de MongoDB
class PyObjectId(str):
    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        def validate(value: Any) -> str:
            if isinstance(value, ObjectId):
                return str(value)
            if isinstance(value, str) and ObjectId.is_valid(value):
                return value
            raise ValueError(f"Invalid ObjectId: {value}")

        return core_schema.no_info_plain_validator_function(
            validate,
            metadata={"title": "ObjectId", "description": "MongoDB ObjectId"},
        )

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


class UserTier(str, Enum):
    FREE = "free"
    ADVANCED = "advanced"
    PRO = "pro"


# Modèle utilisateur
class UserModel(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str = Field(...)
    email: str = Field(...)
    hashed_password: str = Field(...)
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    tier: UserTier = UserTier.FREE
    onboarding_completed: Optional[bool] = False
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: Optional[datetime] = None
    cv_url: Optional[HttpUrl] = None  # <--- Ajouté ici

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john.doe@example.com",
                "full_name": "John Doe",
                "disabled": False,
                "tier": "free",
                "onboarding_completed": False,
                "cv_url": "https://monapp.com/uploads/cv_johndoe.pdf",
            }
        },
    }


# Modèle pour la création d'utilisateur (sans les champs générés automatiquement)
class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    full_name: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "username": "johndoe",
                "email": "john.doe@example.com",
                "password": "strongpassword",
                "full_name": "John Doe",
            }
        }
    }


# Modèle pour les réponses (sans le mot de passe)
class UserResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    username: str
    email: str
    full_name: Optional[str] = None
    disabled: Optional[bool] = False
    tier: UserTier = UserTier.FREE
    onboarding_completed: Optional[bool] = False
    created_at: datetime

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# Énumération pour le statut de candidature
class ApplicationStatus(str, Enum):
    ETUDE = "En étude"
    APPLIED = "Candidature envoyée"
    SCREENING = "Première sélection"
    INTERVIEW = "Entretien"
    TECHNICAL_TEST = "Test technique"
    NEGOTIATION = "Négociation"
    OFFER = "Offre reçue"
    OFFER_RECEIVED = "Offre reçue"
    ACCEPTED = "Offre acceptée"
    REJECTED = "Refusée"
    WITHDRAWN = "Retirée"


# Modèle pour les candidatures
class JobApplication(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId = Field(...)
    offer_id: Optional[str] = None
    company: str = Field(...)
    position: str = Field(...)
    location: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: datetime = Field(default_factory=utcnow_with_timezone)
    status: ApplicationStatus = Field(default=ApplicationStatus.APPLIED)
    description: Optional[str] = None
    notes: Optional[List[str]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: Optional[datetime] = None
    archived: Optional[bool] = False

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "company": "Entreprise XYZ",
                "position": "Développeur Full Stack",
                "url": "https://www.entreprisexyz.com/jobs/123",
                "application_date": "2025-04-08T10:00:00Z",
                "status": "Candidature envoyée",
                "description": "Poste de développeur full stack avec React et Python",
                "notes": ["Entretien téléphonique prévu le 15 avril"],
            }
        },
    }


# Modèle pour la création d'une candidature
class JobApplicationCreate(BaseModel):
    company: str
    position: str
    offer_id: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: Optional[datetime] = None
    location: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.APPLIED
    description: Optional[str] = None
    archived: Optional[bool] = False

    model_config = {
        "json_schema_extra": {
            "example": {
                "company": "Entreprise XYZ",
                "position": "Développeur Full Stack",
                "location": "Paris, France",
                "url": "https://www.entreprisexyz.com/jobs/123",
                "application_date": "2025-04-08T10:00:00Z",
                "status": "Candidature envoyée",
                "description": "Poste de développeur full stack avec React et Python",
                "offer_id": "673f1c9d8e5f2a1b3c4d5e6f",
            }
        }
    }


# Modèle pour la mise à jour d'une candidature
class JobApplicationUpdate(BaseModel):
    company: Optional[str] = None
    position: Optional[str] = None
    offer_id: Optional[str] = None
    location: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: Optional[datetime] = None
    status: Optional[ApplicationStatus] = None
    description: Optional[str] = None
    notes: Optional[List[str]] = None
    archived: Optional[bool] = None  # Changé de str à bool

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "Entretien",
                "notes": [
                    "Entretien téléphonique prévu le 15 avril",
                    "Prévoir de poser des questions sur l'équipe",
                ],
            }
        }
    }


# Modèle pour les réponses de candidature
class JobApplicationResponse(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    company: str
    position: str
    offer_id: Optional[str] = None
    url: Optional[HttpUrl] = None
    application_date: datetime
    status: ApplicationStatus
    location: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[List[str]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    archived: Optional[bool] = False  # Ajout du champ archived
    days_since_application: Optional[int] = None
    follow_up_alert: Optional[str] = None  # None, "relance_due" (J+7), "remerciement_due" (J+1)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class PipelineSummaryResponse(BaseModel):
    total_active: int
    total_archived: int
    status_counts: Dict[str, int]
    interview_conversion_rate: float
    offer_conversion_rate: float
    follow_ups_due_count: int
    thank_yous_due_count: int
    evaluated_offers_ready_count: int = 0


class TaskStatus(str, Enum):
    TODO = "À faire"
    IN_PROGRESS = "En cours"
    DONE = "Terminée"


class Task(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId = Field(...)
    title: str = Field(...)
    description: Optional[str] = None
    status: TaskStatus = Field(default=TaskStatus.TODO)
    archived: Optional[bool] = False
    due_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: Optional[datetime] = None

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
        "json_schema_extra": {
            "example": {
                "title": "Préparer le CV",
                "description": "Mettre à jour le CV avec les dernières expériences.",
                "status": "À faire",
                "due_date": "2025-04-10T10:00:00Z",
            }
        },
    }


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    # Ajoute d'autres champs si besoin (ex: attached_files, etc.)

    model_config = ConfigDict(extra="forbid")


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[datetime] = None
    model_config = ConfigDict(extra="forbid")


class JobOfferCreate(BaseModel):
    poste: str
    entreprise: str
    description: Optional[str] = None
    localisation: Optional[str] = None
    date: Optional[str] = None
    type_contrat: Optional[str] = None  # Ex: CDI, CDD, Freelance, Stage, Alternance
    salaire: Optional[str] = None       # Ex: 45k€ - 55k€
    mode_travail: Optional[str] = None  # Ex: Télétravail, Hybride, Présentiel
    competences_cles: Optional[List[str]] = None
    is_deleted: Optional[bool] = False  # Indique si l'offre a été supprimée
    deleted_date: Optional[datetime] = None  # Date de suppression
    deletion_reason: Optional[str] = None  # Raison de suppression / expiration
    url: Optional[str] = None
    source_url: Optional[str] = None  # URL de la page où l'offre a été trouvée
    pipeline_stage: Optional[str] = "discovered"
    evaluation_score: Optional[float] = None
    canonical_title: Optional[str] = None
    seniority_level: Optional[str] = None
    alternative_urls: Optional[List[str]] = None


class JobOfferResponse(BaseModel):
    id: str
    poste: str
    entreprise: str
    description: Optional[str] = None
    localisation: Optional[str] = None
    date: Optional[str] = None
    type_contrat: Optional[str] = None
    salaire: Optional[str] = None
    mode_travail: Optional[str] = None
    competences_cles: Optional[List[str]] = None
    url: Optional[str] = None
    is_deleted: Optional[bool] = False  # Indique si l'offre a été supprimée
    deleted_date: Optional[datetime] = None  # Date de suppression
    deletion_reason: Optional[str] = None  # Raison de suppression / expiration
    source_url: Optional[str] = None
    pipeline_stage: Optional[str] = "discovered"
    evaluation_score: Optional[float] = None
    canonical_title: Optional[str] = None
    seniority_level: Optional[str] = None
    alternative_urls: Optional[List[str]] = None
    user_interaction: Optional[str] = None  # Interaction: "saved", "hidden", "applied", "dismissed"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserOfferInteractionRequest(BaseModel):
    status: Literal["saved", "hidden", "applied", "dismissed", "none"]
    notes: Optional[str] = None


class UserOfferInteractionResponse(BaseModel):
    id: Optional[str] = None
    user_id: str
    offer_id: str
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class JobOfferFilter(BaseModel):
    keywords: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    companies: Optional[List[str]] = None
    min_score: Optional[float] = None
    pipeline_stage: Optional[str] = None
    limit: int = 50
    skip: int = 0


# --- Modèles d'Évaluation d'Offre (Two-Pass Career-Ops) ---
class RequirementMatch(BaseModel):
    requirement: str
    weight: Literal["critical", "high", "meaningful"] = "high"
    candidate_evidence: str
    verbatim_quote: str  # Citation exacte de l'offre
    status: Literal["full_match", "partial_match"] = "full_match"
    # "stated" : preuve explicite dans le profil (poste, stack, mission listée).
    # "inferred" : déduction du modèle sans mention explicite. Ne peut jamais à
    # elle seule justifier un full_match sur une exigence critical/high — voir
    # le gate déterministe dans evaluator.py::evaluate_offer_two_pass.
    evidence_tier: Literal["stated", "inferred"] = "stated"


class MissingRequirement(BaseModel):
    requirement: str
    weight: Literal["critical", "high", "meaningful"] = "high"
    reason: str
    impact_on_role: Optional[str] = None


class BlocA(BaseModel):
    summary: str = ""
    archetype: str = ""
    red_flags: List[str] = Field(default_factory=list)
    geo_mismatch: bool = False
    visa_sponsoring_refused: bool = False
    notes: Optional[str] = None


class BlocB(BaseModel):
    matched_requirements: List[RequirementMatch] = Field(default_factory=list)
    missing_requirements: List[MissingRequirement] = Field(default_factory=list)
    score_justification: str = ""


class BlocG(BaseModel):
    is_ghost_job: bool = False
    is_scam_risk: bool = False
    reposted_frequency: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class OfferEvaluation(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    offer_id: PyObjectId
    score: float = 1.0  # 1.0 to 5.0
    headline: str = ""
    pipeline_stage: Literal["discovered", "evaluated", "expired"] = "evaluated"
    bloc_a: BlocA = Field(default_factory=BlocA)
    bloc_b: BlocB = Field(default_factory=BlocB)
    bloc_g: BlocG = Field(default_factory=BlocG)
    models_used: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class OfferEvaluationResponse(BaseModel):
    id: Optional[str] = None
    user_id: str
    offer_id: str
    score: float
    headline: str
    pipeline_stage: str
    bloc_a: BlocA
    bloc_b: BlocB
    bloc_g: BlocG
    created_at: datetime
    updated_at: datetime


# Modèles pour le profil candidat et la génération de lettres de motivation
CandidateSource = Literal["cv", "github", "website", "manual", "saisie"]
# For CandidateProvenance.source: includes "site" for backwards compatibility with existing data
CandidateProvenanceSource = Union[CandidateSource, Literal["site"]]


class CandidateAchievement(BaseModel):
    text: str
    metric: Optional[str] = None


class CandidateExperience(BaseModel):
    company: str
    role: Optional[str] = None
    location: Optional[str] = None
    contract: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
    sector: Optional[str] = None
    missions: List[str] = Field(default_factory=list)
    missions_alt: List[str] = Field(default_factory=list)
    missions_source: Optional[str] = None
    achievements: List[CandidateAchievement] = Field(default_factory=list)
    stack: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


class CandidateProject(BaseModel):
    name: str
    description: str = ""
    stack: List[str] = Field(default_factory=list)
    url: Optional[str] = None
    repo: Optional[str] = None
    year: Optional[str] = None
    context: Literal["perso", "client", "recherche", "consortium"] = "perso"
    highlights: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)


class CandidateEducation(BaseModel):
    school: str = ""
    degree: str = ""
    years: Optional[str] = None
    topics: List[str] = Field(default_factory=list)


class CandidateCertification(BaseModel):
    name: str = ""
    issuer: str = ""
    year: Optional[str] = None
    topics: List[str] = Field(default_factory=list)


class CandidateConflict(BaseModel):
    company: str = ""
    field: str
    kept: Any = None
    kept_source: str = ""
    discarded: Any = None
    discarded_source: str = ""


class CandidateProvenance(BaseModel):
    field_path: str
    source: CandidateProvenanceSource


class RemotePolicy(str, Enum):
    FULL_REMOTE = "full_remote"
    HYBRID = "hybrid"
    ON_SITE = "on_site"
    FLEXIBLE = "flexible"


class CandidatePreferences(BaseModel):
    target_roles: List[str] = Field(default_factory=list)
    seniority_level: Optional[str] = None
    seniority_levels: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    remote_policy: RemotePolicy = RemotePolicy.FLEXIBLE
    min_salary: Optional[int] = None
    target_salary: Optional[int] = None
    currency: str = "EUR"
    contract_types: List[str] = Field(default_factory=list)
    notice_period: Optional[str] = None
    work_authorization: Optional[str] = None
    excluded_keywords: List[str] = Field(default_factory=list)
    preferred_industries: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sync_seniority(self) -> "CandidatePreferences":
        if self.seniority_levels and not self.seniority_level:
            self.seniority_level = self.seniority_levels[0]
        elif self.seniority_level and not self.seniority_levels:
            self.seniority_levels = [self.seniority_level]
        return self


class CandidateProfile(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    headline: str = ""
    summary: str = ""
    contact: Dict[str, Optional[str]] = Field(default_factory=dict)
    preferences: CandidatePreferences = Field(default_factory=CandidatePreferences)
    experiences: List[CandidateExperience] = Field(default_factory=list)
    projects: List[CandidateProject] = Field(default_factory=list)
    education: List[CandidateEducation] = Field(default_factory=list)
    certifications: List[CandidateCertification] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    skills: Dict[str, List[str]] = Field(default_factory=dict)
    provenance: List[CandidateProvenance] = Field(default_factory=list)
    sources: Dict[str, dict] = Field(default_factory=dict)
    conflicts: List[CandidateConflict] = Field(default_factory=list)
    excluded_projects: List[str] = Field(default_factory=list)
    writing_style: Optional[str] = None
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


class CoverLetterVersion(BaseModel):
    n: int
    body: str
    origin: Literal["generated", "edited"]
    models: Dict[str, str] = Field(default_factory=dict)
    prompt_version: str = "1.0"
    guard_report: Dict[str, Any] = Field(default_factory=dict)
    critic_verdict: Optional[Dict[str, Any]] = None
    revised: bool = False
    created_at: datetime = Field(default_factory=utcnow_with_timezone)


class CoverLetter(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    application_id: PyObjectId
    status: Literal["pending", "ready", "failed"] = "pending"
    versions: List[CoverLetterVersion] = Field(default_factory=list)
    current_version: int = 1
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = {"populate_by_name": True, "arbitrary_types_allowed": True}


# --- API Usage & Quota Models ---
class ApiUsageAction(str, Enum):
    COVER_LETTER = "cover_letter"
    EVALUATION = "evaluation"
    CV_TAILORING = "cv_tailoring"
    CV_PARSING = "cv_parsing"
    INTERVIEW_PREP = "interview_prep"
    OFFER_SUMMARY = "offer_summary"


class ApiUsageRecord(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    action: ApiUsageAction
    models_used: List[str] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: Optional[int] = None
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class TierQuota(BaseModel):
    action: ApiUsageAction
    monthly_limit: Optional[int] = None  # None = unlimited


class ActionQuotaUsage(BaseModel):
    action: ApiUsageAction
    used: int = 0
    monthly_limit: Optional[int] = None  # None = unlimited
    remaining: Optional[int] = None  # None = unlimited


class UserQuotaSummary(BaseModel):
    user_id: PyObjectId
    tier: UserTier
    year: int
    month: int
    usage: Dict[str, ActionQuotaUsage]
    total_cost_usd: float = 0.0
    total_tokens: int = 0


# --- Tailored CV Models ---

class TailoredExperienceItem(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    start_date: str
    end_date: Optional[str] = "Présent"
    bullet_points: List[str] = Field(default_factory=list, description="Puces d'impact réordonnées et alignées sur l'offre")
    relevant_technologies: List[str] = Field(default_factory=list)


class TailoredProjectItem(BaseModel):
    name: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    url: Optional[str] = None


class TailoredSkillGroup(BaseModel):
    category: str
    skills: List[str] = Field(default_factory=list)


class TailoredLanguage(BaseModel):
    language: str
    level: str  # ex: "Natif", "C1 - Professionnel courant"


class TailoredEducationItem(BaseModel):
    degree: str
    institution: str
    year: str
    details: Optional[str] = None


class TailoredCVSchema(BaseModel):
    target_role_title: str
    professional_summary: str = Field(..., description="Accroche ciblée 3-4 lignes")
    prioritized_skills: List[TailoredSkillGroup] = Field(default_factory=list)
    experiences: List[TailoredExperienceItem] = Field(default_factory=list)
    featured_projects: List[TailoredProjectItem] = Field(default_factory=list)
    education: List[TailoredEducationItem] = Field(default_factory=list)
    languages: List[TailoredLanguage] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)


class TailoredResumeInDB(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    offer_id: PyObjectId
    application_id: Optional[PyObjectId] = None
    target_role: str
    target_company: str
    template: str = "sidebar_elegance"  # "sidebar_elegance" or "executive_minimalist"
    with_photo: bool = False
    content: TailoredCVSchema
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


# --- Phase 6: Interview Prep Models ---
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

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class AudiencePackRecruiter(BaseModel):
    pitch_30s: str
    comp_strategy: Dict[str, str] = Field(default_factory=dict)  # "volunteer", "avoid"
    red_flags_they_screen_for: List[str] = Field(default_factory=list)
    key_questions_to_ask_recruiter: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class AudiencePackHiringManager(BaseModel):
    strategic_alignment: str
    internal_vocabulary: List[str] = Field(default_factory=list)
    sharp_questions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class AudiencePackTechPanel(BaseModel):
    architecture_points: List[str] = Field(default_factory=list)
    tradeoffs_and_risks: List[str] = Field(default_factory=list)
    reverse_questions: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class AnticipatedQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str  # "behavioral" | "technical"
    question: str
    why_it_will_be_asked: str  # Source Bloc B ou "[inferred from JD]"
    mapped_story_id: Optional[str] = None
    key_points_to_cover: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class ReverseQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str  # "Culture & Rythme", "Dette Technique", "Organisation & Autonomie"
    question: str
    probe_intent: str

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


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


