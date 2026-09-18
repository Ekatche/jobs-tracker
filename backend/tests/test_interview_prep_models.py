import pytest
from bson import ObjectId
from app.models import (
    StarRStory,
    AudiencePackRecruiter,
    AudiencePackHiringManager,
    AudiencePackTechPanel,
    AnticipatedQuestion,
    ReverseQuestion,
    InterviewPrep,
)

def test_interview_prep_model_instantiation():
    story = StarRStory(
        title="[Scalabilité] Pipeline Kafka",
        theme="Architecture",
        target_requirement="Expérience Kafka",
        situation="Charge de 50k req/s",
        task="Concevoir l'ingestion",
        action="Mise en place de partitions et consumer groups",
        result="Latence réduite de 40%",
        reflection="Mieux anticiper les rebalances",
        key_tags=["kafka", "python"]
    )
    assert story.id is not None
    assert story.title.startswith("[Scalabilité]")

    prep = InterviewPrep(
        offer_id=ObjectId(),
        user_id=ObjectId(),
        stories=[story],
        recruiter_pack=AudiencePackRecruiter(
            pitch_30s="Ingénieur backend senior...",
            comp_strategy={"volunteer": "fourchette marché", "avoid": "chiffre ferme prématuré"},
            red_flags_they_screen_for=["instabilité"],
            key_questions_to_ask_recruiter=["Quel est le calendrier ?"]
        ),
        anticipated_questions=[
            AnticipatedQuestion(
                category="behavioral",
                question="Parlez-moi d'une panne complexe.",
                why_it_will_be_asked="Bloc B: Fiabilité système",
                mapped_story_id=story.id,
                key_points_to_cover=["Isolation", "Communication"]
            )
        ],
        reverse_questions=[
            ReverseQuestion(
                category="Dette Technique",
                question="Comment gérez-vous la dette technique ?",
                probe_intent="Vérifier si les refactors sont autorisés"
            )
        ]
    )
    assert len(prep.stories) == 1
    assert prep.recruiter_pack.pitch_30s.startswith("Ingénieur")
    assert prep.anticipated_questions[0].mapped_story_id == story.id
    assert len(prep.reverse_questions) == 1
