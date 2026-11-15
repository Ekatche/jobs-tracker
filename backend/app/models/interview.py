from datetime import datetime
from typing import Dict, List, Literal, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from .common import PyObjectId, utcnow_with_timezone


class StarRStory(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    theme: str
    target_requirement: str
    situation: str
    task: str
    action: str
    result: str
    reflection: str
    key_tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


StoryFit = Literal["strong", "partial", "transferable", "gap", "no_experience", "manual"]


class StoryExperience(BaseModel):
    company: str
    role: Optional[str] = None
    start: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class StoryFacts(BaseModel):
    title: str
    theme: str = "Général"
    situation: str
    task: str
    action: str
    result: str
    reflection: str = ""
    key_tags: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class StoryOrigin(BaseModel):
    kind: Literal["migrated", "generated", "manual"]
    offer_id: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class DiscardedStoryVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    facts: StoryFacts
    source_story_id: str
    discarded_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class BankStory(StoryFacts):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    experience: Optional[StoryExperience] = None
    origin: StoryOrigin
    discarded_versions: List[DiscardedStoryVersion] = Field(default_factory=list)
    not_duplicate_of: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class StorySlot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    requirement: str
    story_id: Optional[str] = None
    fit: StoryFit = "gap"
    angle: str = ""
    angle_edited: bool = False

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class AudiencePackRecruiter(BaseModel):
    pitch_30s: str
    comp_strategy: Dict[str, str] = Field(default_factory=dict)
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
    category: str
    question: str
    why_it_will_be_asked: str
    mapped_story_id: Optional[str] = None
    key_points_to_cover: List[str] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class ReverseQuestion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str
    question: str
    probe_intent: str

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)


class PracticeCriterion(BaseModel):
    key: str
    score: int = Field(ge=1, le=5)
    comment: str


class PracticeAttempt(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question_id: str
    question: str
    answer: str
    criteria: List[PracticeCriterion] = Field(default_factory=list)
    overall_score: float
    missing: List[str] = Field(default_factory=list)
    improved_answer: str
    created_at: datetime = Field(default_factory=utcnow_with_timezone)

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
    practice_attempts: List[PracticeAttempt] = Field(default_factory=list)
    story_slots: Optional[List[StorySlot]] = None
    created_at: datetime = Field(default_factory=utcnow_with_timezone)
    updated_at: datetime = Field(default_factory=utcnow_with_timezone)

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
