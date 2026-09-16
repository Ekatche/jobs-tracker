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
        "candidate_headline": "Lead Data Engineer",
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


def test_invented_entity_sharing_a_prefix_with_known_stack_is_still_flagged():
    # "Go" est une stack connue : une comparaison par sous-chaîne de caractères
    # laisserait passer "Google" car "go" in "google" est vrai. La comparaison
    # doit se faire par ensemble de tokens (mots entiers).
    letter = (
        "Madame, Monsieur,\n\nJ'ai travaillé chez Google avec Kafka.\n\n"
        "Ma méthode est rigoureuse.\n\nCordialement"
    )
    analyst_data = {"stacks": ["Go", "Kafka"], "companies": []}
    report = evaluate_letter_guards(letter, "offre", analyst_data)
    assert any("Google" in v for v in report.violations)


def test_accented_entity_is_flagged_in_full_not_truncated():
    # La classe de caractères de _ENTITY_PATTERN doit couvrir les lettres
    # accentuées françaises : sinon "Biomédica" est tronqué à "Biom" avant
    # comparaison, ce qui masque le nom réel dans le message de violation.
    letter = (
        "Madame, Monsieur,\n\nJ'ai eu un entretien chez Biomédica avant de rejoindre "
        "Agence Nile.\n\nMa méthode repose sur Python.\n\nCordialement"
    )
    report = evaluate_letter_guards(letter, "offre", ANALYST)
    assert any("Biomédica" in v for v in report.violations)


def test_invented_entity_at_sentence_start_is_now_flagged():
    # C3-1 : l'ancienne exemption "match.start() == 0" laissait passer toute
    # entité inventée placée en tête de n'importe quelle phrase du texte.
    # Supprimée : une entité en tête de phrase doit être contrôlée comme
    # n'importe quelle autre.
    letter = (
        "Innotech m'a inspiré durant mes études.\n\n"
        "Ma méthode repose sur Python.\n\nCordialement"
    )
    analyst_data = {"stacks": ["Python"], "companies": []}
    report = evaluate_letter_guards(letter, "offre", analyst_data)
    assert any("Innotech" in v for v in report.violations)


def test_entity_present_only_in_offer_description_is_now_rejected():
    # C3-2 : whitelister depuis l'offre brute est contraire à la spec —
    # l'offre peut citer un partenaire, un client ou un concurrent du
    # recruteur que le candidat n'a aucune légitimité à reprendre.
    letter = (
        "Madame, Monsieur,\n\nJ'ai suivi votre partenariat avec PartnerCorp "
        "avec beaucoup d'intérêt.\n\nMa méthode repose sur Python.\n\nCordialement"
    )
    offer_desc = "Cette offre est proposée en collaboration avec PartnerCorp."
    analyst_data = {"stacks": ["Python"], "companies": []}
    report = evaluate_letter_guards(letter, offer_desc, analyst_data)
    assert any("PartnerCorp" in v for v in report.violations)


def test_longer_invented_entity_containing_a_known_short_token_is_rejected():
    # I5 : la comparaison à double sens ("entity <= candidate" en plus de
    # "candidate <= entity") laissait blanchir une entité inventée plus
    # longue qui contient un token autorisé court (ex. "Python" dans la
    # stack blanchissant à tort "Python Institute"). Seule la direction
    # "candidate est un sous-ensemble d'une entité autorisée" doit rester.
    letter = (
        "Madame, Monsieur,\n\nJ'ai suivi une formation chez Python Institute "
        "avant de rejoindre Agence Nile.\n\nMa méthode repose sur Python.\n\nCordialement"
    )
    report = evaluate_letter_guards(letter, "offre", ANALYST)
    assert any("Python Institute" in v for v in report.violations)


def test_unverifiable_number_is_flagged():
    # C3-3 : tout chiffre cité dans la lettre doit apparaître littéralement
    # dans l'offre ou dans les expériences sélectionnées transmises à
    # l'analyste, sinon rien ne prouve qu'il n'a pas été inventé.
    letter = (
        "Madame, Monsieur,\n\nJ'ai réduit les coûts de 47 pourcent.\n\n"
        "Ma méthode est rigoureuse.\n\nCordialement"
    )
    analyst_data = {"stacks": [], "companies": [], "selected_experiences": []}
    report = evaluate_letter_guards(letter, "offre sans chiffres", analyst_data)
    assert any("Chiffre non vérifiable" in v and "47" in v for v in report.violations)


def test_number_present_in_offer_description_is_accepted():
    letter = (
        "Madame, Monsieur,\n\nJ'ai géré une équipe de 12 personnes.\n\n"
        "Ma méthode est rigoureuse.\n\nCordialement"
    )
    offer_desc = "Nous recherchons quelqu'un pour encadrer une équipe de 12 personnes."
    analyst_data = {"stacks": [], "companies": [], "selected_experiences": []}
    report = evaluate_letter_guards(letter, offer_desc, analyst_data)
    assert not any("Chiffre non vérifiable" in v for v in report.violations)


def test_number_present_in_selected_experiences_is_accepted():
    letter = (
        "Madame, Monsieur,\n\nJ'ai traité 500 dossiers.\n\n"
        "Ma méthode est rigoureuse.\n\nCordialement"
    )
    analyst_data = {
        "stacks": [],
        "companies": [],
        "selected_experiences": [{"company": "Sanofi", "metric": "500 dossiers traités"}],
    }
    report = evaluate_letter_guards(letter, "offre sans chiffres", analyst_data)
    assert not any("Chiffre non vérifiable" in v for v in report.violations)


def test_plausible_year_is_accepted_without_being_present_elsewhere():
    letter = (
        "Madame, Monsieur,\n\nDepuis 2023, je me spécialise en data engineering.\n\n"
        "Ma méthode est rigoureuse.\n\nCordialement"
    )
    analyst_data = {"stacks": [], "companies": [], "selected_experiences": []}
    report = evaluate_letter_guards(letter, "offre sans chiffres", analyst_data)
    assert not any("Chiffre non vérifiable" in v and "2023" in v for v in report.violations)


def test_guards_new_career_ops_banned_lexicon_fails():
    newly_banned = [
        "synergie", "actionable insights", "valeur ajoutée",
        "alignement stratégique", "opportunité unique", "profil idéal", "mettre à profit"
    ]
    for term in newly_banned:
        letter = f"Madame, Monsieur,\n\nNotre collaboration créera une {term} remarquable.\n\nCordialement"
        report = evaluate_letter_guards(letter, "offre", {})
        assert report.is_blocking is True
        assert any(term in v for v in report.violations), f"Le terme banni '{term}' n'a pas été détecté"

