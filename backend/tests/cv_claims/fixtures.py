"""Profil synthétique à deux postes et cas annotés du garde-fou par expérience (cv_guards.audit_cv_claims)."""
from app.models import TailoredCVSchema, TailoredExperienceItem, TailoredSkillGroup

CLAIMS_PROFILE = {
    "experiences": [
        {
            "company": "Acme", "title": "Data Scientist", "start": "2021-01", "end": "2024-01",
            "missions": ["Réduction de 30 % du temps de traitement de séries temporelles.", "Suivi d'un budget de 1,5 M€."],
            "stack": ["Python", "Airflow"],
        },
        {
            "company": "Beta", "title": "Ingénieur Données", "start": "2018-01", "end": "2021-01",
            "missions": ["Pipelines temps réel pour 200 clients.", "Baisse de 40 % des incidents."],
            "stack": ["Kafka", "Spark"],
        },
    ],
    "skills": ["Python", "Airflow", "Kafka", "Spark", "Rust"],
    "projects": [{"name": "Perso", "stack": ["Rust", "Julia"], "description": "Prototype de prévision en Julia."}],
    "certifications": [{"name": "AWS Solutions Architect"}],
    "contact": {"mobility": "Permis B"},
}


def build_cv(bullets=(), technologies=(), skills=(), certifications=()) -> TailoredCVSchema:
    """CV adapté dont l'unique expérience reprend le poste Acme du profil."""
    return TailoredCVSchema(
        target_role_title="Data Scientist",
        professional_summary="Data scientist séries temporelles.",
        prioritized_skills=[TailoredSkillGroup(category="Outils", skills=list(skills))] if skills else [],
        experiences=[
            TailoredExperienceItem(
                title="Data Scientist", company="Acme", start_date="2021-01", end_date="2024-01",
                bullet_points=list(bullets), relevant_technologies=list(technologies),
            )
        ],
        certifications=list(certifications),
    )


# id : (arguments de build_cv, fragments attendus dans les violations, fragments attendus dans les non vérifiables)
CLAIM_CASES = {
    "metric_from_other_post": ({"bullets": ["Déploiement pour 200 clients."]}, ["autre poste"], []),
    "metric_invented": ({"bullets": ["Réduction de 70 % des coûts."]}, ["inventée"], []),
    "technology_from_other_post": ({"technologies": ["Kafka"]}, ["issue d'un autre poste"], []),
    "technology_in_bullet_from_other_post": ({"bullets": ["Orchestration de flux avec Kafka."]}, ["Kafka"], []),
    "certification_invented": ({"certifications": ["Google Cloud Professional"]}, ["Certification"], []),
    "technology_unverifiable": ({"technologies": ["Rust"]}, [], ["Rust"]),
    "ok_bullet_reworded_without_figure": ({"bullets": ["Accélération mesurable du traitement des séries temporelles."]}, [], []),
    "ok_transferable_skill": ({"skills": ["Julia"]}, [], []),
    "ok_metric_written_differently": ({"bullets": ["Traitement 30% plus rapide.", "Budget de 1.5 M€ suivi."]}, [], []),
}
