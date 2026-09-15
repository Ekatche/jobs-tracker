import pytest
from app.services.letter_guards import LETTER_RULES, evaluate_letter_guards

def test_guards_clean_letter_passes():
    letter = """Madame, Monsieur, votre offre de Lead Data Engineer chez Biomérieux a retenu toute mon attention. Lors de mes trois années chez Sanofi, j'ai conçu et déployé des architectures de données distribuées sous Nextflow et Kafka avec un temps global de traitement divisé par deux pour l'ensemble des équipes d'analyse biologique et génomique. Cette expérience m'a permis d'acquérir une compréhension fine des contraintes opérationnelles liées aux volumes massifs et à la gouvernance rigoureuse des données dans un écosystème réglementé de santé.

Sur mon projet personnel Sentinel, j'ai développé un moteur de streaming temps réel sous Rust et DuckDB capable de traiter dix millions d'événements par jour avec une latence maîtrisée. Cette initiative m'a amené à optimiser l'utilisation des ressources mémoire, à fiabiliser les protocoles de reprise sur incident et à documenter précisément chaque module pour en assurer l'évolution pérenne. Elle témoigne de ma capacité à prendre en main des problématiques techniques complexes et à concevoir des solutions performantes de manière autonome.

Rejoindre votre équipe représente l'opportunité de mettre cette double compétence au service de vos projets analytiques majeurs. Je pourrai ainsi contribuer directement à la structuration de vos pipelines et à l'accélération de vos traitements de données cliniques. Mon expertise technique et mon autonomie me permettront d'être opérationnel rapidement au sein de votre collectif de travail.

Je serais ravi d'échanger prochainement avec vous pour évoquer plus en détail les enjeux techniques de ce poste et la manière dont mes réalisations passées peuvent répondre à vos besoins immédiats. Je vous remercie pour l'attention portée à ma candidature. Cordialement, Eliel Katche."""
    analyst_data = {
        "companies": ["Biomérieux", "Sanofi"],
        "stacks": ["Nextflow", "Kafka", "Rust", "DuckDB"],
        "metrics": ["trois années", "dix millions"],
        "projects": ["Sentinel"],
        "candidate_name": "Eliel Katche",
    }
    offer_desc = "Biomérieux recrute un Lead Data Engineer pour transformer ses pipelines analytiques de données de santé."

    report = evaluate_letter_guards(letter, offer_desc, analyst_data)
    assert report.is_blocking is False
    assert len(report.violations) == 0

def test_guards_forbidden_punctuation_fails():
    letter = "Bonjour! Nous devons avancer... Voici mon profil—parfait pour vous (vraiment); merci; encore."
    report = evaluate_letter_guards(letter, "offre", {})
    assert report.is_blocking is True
    assert any("Point d'exclamation" in v for v in report.violations)
    assert any("Points de suspension" in v for v in report.violations)
    assert any("Tiret cadratin" in v for v in report.violations)
    assert any("Parenthèses" in v for v in report.violations)
    assert any("Point-virgule" in v for v in report.violations)

def test_guards_banned_lexicon_and_openings_fail():
    letter = "Je vous adresse ma candidature. J'ai une solide expertise et une forte appétence pour votre projet."
    report = evaluate_letter_guards(letter, "offre", {})
    assert report.is_blocking is True
    assert any("Ouverture interdite" in v for v in report.violations)
    assert any("solide expertise" in v for v in report.violations)
    assert any("forte appétence" in v for v in report.violations)

def test_guards_word_count_and_paragraphs_fail():
    short_letter = "Trop court.\n\nDeuxième paragraphe."
    report = evaluate_letter_guards(short_letter, "offre", {})
    assert report.is_blocking is True
    assert any("Longueur hors bornes" in v for v in report.violations)
    assert any("Nombre de paragraphes" in v for v in report.violations)

def test_guards_sentence_connectors_fail():
    letter = "De plus, nous commençons.\n\nEn outre, nous poursuivons.\n\nEnfin, nous terminons."
    report = evaluate_letter_guards(letter, "offre", {})
    assert report.is_blocking is True
    assert any("Connecteurs en tête de phrase" in v for v in report.violations)

def test_guards_unauthorized_entities_fail():
    letter = "J'ai travaillé cinq ans chez Google avec Kubernetes.\n\nDeuxième paragraphe.\n\nTroisième paragraphe."
    analyst_data = {"companies": ["Biomérieux"], "stacks": ["Kafka"], "metrics": [], "projects": []}
    report = evaluate_letter_guards(letter, "offre", analyst_data)
    assert report.is_blocking is True
    assert any("Entité non autorisée" in v for v in report.violations)

def test_guards_warnings_flagged_without_blocking():
    # Sentences with identical construction and no variance
    uniform_letter = "Je code du python chaque jour. Je lis des livres chaque soir. Je fais du sport chaque matin. Je dors huit heures chaque nuit."
    report = evaluate_letter_guards(uniform_letter, "offre", {})
    assert report.is_blocking is False or len(report.warnings) > 0


ANALYST = {
    "stacks": ["Python", "Azure"],
    "companies": ["Agence Nile", "Bimedoc"],
}


def test_invented_company_is_flagged():
    letter = (
        "Madame, Monsieur,\n\nJ'ai conduit des projets chez Initech avant de rejoindre "
        "Agence Nile.\n\nMa méthode repose sur Python.\n\nCordialement"
    )
    report = evaluate_letter_guards(letter, "offre", ANALYST)
    assert any("Initech" in v for v in report.violations)


def test_known_company_is_not_flagged():
    letter = (
        "Madame, Monsieur,\n\nChez Agence Nile, j'ai industrialisé des flux.\n\n"
        "Ma méthode repose sur Python.\n\nCordialement"
    )
    report = evaluate_letter_guards(letter, "offre", ANALYST)
    assert not any("Entité non autorisée" in v for v in report.violations)


def test_word_bounds_come_from_a_single_source():
    assert LETTER_RULES["min_words"] == 250
    assert LETTER_RULES["max_words"] == 400
    assert "je suis" in LETTER_RULES["capped_repetitions"]
