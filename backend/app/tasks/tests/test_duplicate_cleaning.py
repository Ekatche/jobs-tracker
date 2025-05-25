import sys
from pathlib import Path

# Add backend root to path before importing app modules
script_dir = Path(__file__).parent.absolute()
backend_root = script_dir.parent.parent.parent
sys.path.insert(0, str(backend_root))
from app.services.job_offers import clean_job_offer_duplicates  # noqa: E402


def test_duplicate_cleaning():
    """Test de la fonction de nettoyage"""

    test_offers = [
        {
            "entreprise": "Google",
            "poste": "Développeur Python",
            "url": "https://site1.com/job1",
        },
        {
            "entreprise": "ACTIVUS GROUP",
            "poste": "Chef de Projet IT / Data Scientist - Maintenance Prédictive F/H - Informatique de gestion (H/F)",
            "url": "https://candidat.francetravail.fr/offres/recherche/detail/6721251",
        },
        {
            "entreprise": "ACTIVUS GROUP",
            "poste": "Chef de Projet IT / Data Scientist - Maintenance Prédictive F/H - Informatique de gestion (H/F)",
            "url": "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/176452017W?motsCles=DATA%20Scientist%20-%20LYON&typesConvention=143684&typesConvention=143685&typesConvention=143686&typesConvention=143687&typesConvention=143706&selectedIndex=4&page=0",
        },
        {
            "entreprise": "AMILTONE",
            "poste": "Data Scientist/IA F/H",
            "url": "https://www.apec.fr/candidat/recherche-emploi.html/emploi/detail-offre/176528999W?motsCles=DATA%20Scientist%20-%20LYON&typesConvention=143684&typesConvention=143685&typesConvention=143686&typesConvention=143687&typesConvention=143706&selectedIndex=3&page=0",
        },
        {
            "entreprise": "AMILTONE",
            "poste": "Data Scientist/IA F/H - Système, réseaux, données (H/F)",
            "url": "https://candidat.francetravail.fr/offres/recherche/detail/6723587",
        },
        {
            "entreprise": "Google Inc",
            "poste": "Développeur Python Senior",
            "url": "https://site2.com/job2",
        },  # Doublon
        {
            "entreprise": "Microsoft",
            "poste": "Data Scientist",
            "url": "https://site3.com/job3",
        },
        {
            "entreprise": "Apple",
            "poste": "iOS Developer",
            "url": "https://site4.com/job4",
        },
        {
            "entreprise": "Google",
            "poste": "Python Developer",
            "url": "https://site5.com/job5",
        },  # Doublon
    ]

    cleaned = clean_job_offer_duplicates(
        test_offers,
        company_similarity_threshold=0.75,
        position_similarity_threshold=0.8,
    )

    print(f"Original: {len(test_offers)} offres")
    print(f"Nettoyé: {len(cleaned)} offres")
    for offer in cleaned:
        print(f"  - {offer['entreprise']} - {offer['poste']}")


if __name__ == "__main__":
    test_duplicate_cleaning()
