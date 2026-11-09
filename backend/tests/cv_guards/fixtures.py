"""Profil synthétique à deux postes et cas annotés du garde-fou par expérience (cv_guards.audit_cv_claims)."""
from app.models import TailoredCVSchema, TailoredExperienceItem, TailoredSkillGroup

CLAIMS_PROFILE = {
    "experiences": [
        {
            "company": "Acme", "title": "Data Scientist", "start": "2021-01", "end": "2024-01",
            "missions": ["Réduction de 30 % du temps de traitement de séries temporelles.", "Suivi d'un budget de 1,5 M€.",
                         "Développement et maintenance de pipelines de données.", "Amélioration de la scalabilité du service.",
                         "Encadrement d'une équipe de cinq personnes."],
            "stack": ["Python", "Airflow", "Spring", "AWS", "T-SQL"],
        },
        {
            "company": "Beta", "title": "Ingénieur Données", "start": "2018-01", "end": "2021-01",
            "missions": ["Pipelines temps réel pour 200 clients.", "Baisse de 40 % des incidents."],
            "stack": ["Kafka", "Spark", "Kubernetes", "Go", "Scala", "AWS Glue", "SQL"],
        },
    ],
    "summary": "Migration de 500 Go de données pour un client.",
    "skills": ["Python", "Airflow", "Kafka", "Spark", "Rust", "Google Cloud"],
    "projects": [{"name": "Perso", "stack": ["Rust", "Julia"], "description": "Prototype de prévision en Julia."}],
    "certifications": [{"name": "AWS Certified Solutions Architect – Associate"}, {"name": "ITIL 4 Foundation"}],
    "education": [{"degree": "CACES R489 cat. 3", "school": "Centre de formation"}],
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
    "technology_from_other_post_despite_common_words": ({"technologies": ["Kubernetes", "Scala"]}, ["Kubernetes", "Scala"], []),
    "ok_short_stack_term_as_unit_or_compound": ({"bullets": ["Migration de 500 Go de données.", "Préparation du Go-live."]}, [], ["500 Go"]),
    "ok_number_written_in_letters": ({"bullets": ["Encadrement de 5 personnes."]}, [], []),
    "ok_certification_reworded": ({"certifications": ["AWS Solutions Architect Associate (2023)"]}, [], []),
    "certification_only_in_education": ({"certifications": ["CACES R489 cat. 3"]}, [], ["CACES"]),
    "ok_metric_written_differently": ({"bullets": ["Traitement 30% plus rapide.", "Budget de 1.5 M€ suivi."]}, [], []),
    # Spring chez Acme : « Spring Security » n'est pas Spring, mais reste une trace de journal (jamais acceptée en silence)
    "qualified_technology_invented": ({"technologies": ["Spring Security"]}, [], ["Spring Security"]),
    # AWS chez Acme, AWS Glue chez Beta : AWS Glue est un autre produit, transféré d'un poste à l'autre
    "qualified_technology_from_other_post": ({"technologies": ["AWS Glue"]}, ["'AWS Glue' du poste 'Data Scientist' chez 'Acme' issue"], []),
    # T-SQL chez Acme, SQL chez Beta : SQL est un composant de la pile d'Acme
    "ok_short_term_component_of_own_stack": ({"technologies": ["SQL"], "bullets": ["Requêtes SQL d'analyse."]}, [], []),
    # Profil « ITIL 4 Foundation » : le CV qui omet la version n'ajoute aucun niveau
    "ok_certification_shorter_than_profile": ({"certifications": ["ITIL Foundation"]}, [], []),
}
