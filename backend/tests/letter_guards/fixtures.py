ATTRIBUTION_ANALYST = {
    "company_name": "Acme",
    "selected_experiences": [
        {"company": "Initech", "title": "Data engineer", "missions": ["Pipelines d'ingestion, équipe de 12 personnes"],
         "stack": ["Kafka", "Docker"]},
        {"company": "DataCorp", "title": "ML engineer", "missions": ["Modèles de scoring, 40% de gain"],
         "stack": ["PyTorch", "Airflow"]},
    ],
    "selected_projects": [],
}

# (phrase, élément attendu dans la violation ou None)
ATTRIBUTION_CASES = [
    ("Chez Initech, j'ai obtenu 40% de gain sur les pipelines.", "« 40% » rattaché à Initech mais issu de DataCorp"),
    ("Chez Initech, j'ai déployé des modèles avec PyTorch.", "« PyTorch » rattaché à Initech mais issu de DataCorp"),
    ("Chez Initech, j'ai monté des pipelines Kafka pour une équipe de 12 personnes.", None),
    ("Entre Initech et DataCorp, j'ai utilisé PyTorch et Kafka, avec 40% de gain.", None),
    ("Depuis 2021, je travaille chez Initech sur des pipelines.", None),
]
