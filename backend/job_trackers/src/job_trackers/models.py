from typing import List, Optional
from pydantic import BaseModel, Field


class OptimizedQueries(BaseModel):
    """Modèle structuré pour la conversion de la demande utilisateur en requêtes de recherche."""

    primary_query: str = Field(
        description="Requête principale de recherche optimisée pour les job boards (ex: 'offres emploi Data Scientist Lyon CDI')"
    )
    alternative_queries: List[str] = Field(
        default_factory=list,
        description="2 à 3 requêtes alternatives ciblées avec mots-clés ou opérateurs booléens",
    )
    extracted_job_title: str = Field(
        description="Intitulé du poste ciblé (ex: 'Data Scientist', 'Lead Developer')"
    )
    extracted_location: str = Field(
        description="Localisation géographique ciblée (ex: 'Lyon', 'Île-de-France', 'Remote')"
    )
    contract_type: Optional[str] = Field(
        default=None,
        description="Type de contrat si détecté (ex: 'CDI', 'CDD', 'Freelance', 'Stage', 'Alternance')",
    )


class JobUrlItem(BaseModel):
    """Détail structuré pour une URL d'offre d'emploi trouvée."""

    url: str = Field(description="URL directe vers l'offre d'emploi")
    source_platform: str = Field(
        description="Plateforme source identifiée (ex: 'Welcome to the Jungle', 'APEC', 'France Travail', 'HelloWork', 'LinkedIn', 'Indeed')"
    )
    is_direct_job_offer: bool = Field(
        default=True,
        description="True si l'URL est une offre directe individuelle, False si page de listing",
    )
    relevance_score: int = Field(
        default=8,
        description="Score de pertinence de 1 à 10 par rapport au poste et à la ville demandés",
    )
    notes: Optional[str] = Field(
        default=None,
        description="Brève note sur la pertinence ou la source de l'offre",
    )


class FilteredJobOffersResult(BaseModel):
    """Résultat final structuré après filtrage des URLs d'offres d'emploi."""

    urls: List[str] = Field(
        default_factory=list,
        description="Liste ordonnée des URLs d'offres d'emploi sélectionnées pour le crawling",
    )
    items: List[JobUrlItem] = Field(
        default_factory=list,
        description="Liste détaillée des métadonnées pour chaque URL retenue",
    )
