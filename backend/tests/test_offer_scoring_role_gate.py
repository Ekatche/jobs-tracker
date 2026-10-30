import pytest

from app.services.offer_scoring.role_gate import role_terms, title_matches_roles

# Rôles du profil d'animatrice créé en prod le 26/10 : tout le stock (offres
# data surtout) lui était rattaché, une offre ALM de banque en pertinence forte.
ANIMATION_ROLES = [
    "Animateur socioculturel",
    "Responsable Animation Jeunesse et Accompagnement Social",
    "Responsable de l'animation socioculturelle",
    "Coordinateur de projets jeunesse",
    "Chargé de mission en insertion sociale",
]

DATA_ROLES = ["Data Scientist", "Ingénieur Data", "Data Engineer", "AI Engineer", "MLOPS Engineer"]


@pytest.mark.parametrize(
    "title",
    [
        "Gestionnaire actif passif - Responsable de projets ALM",
        "Data Engineer Confirmé",
        "Contrôleur de Gestion",
        "Chef de projet Data",
        "Tech Lead IA",
    ],
)
def test_animation_roles_reject_unrelated_titles(title):
    assert not title_matches_roles(title, role_terms(ANIMATION_ROLES))


@pytest.mark.parametrize(
    "title",
    [
        "Animateur périscolaire H/F",
        "Animatrice enfance jeunesse",
        "Coordinatrice jeunesse",
        "Conseiller en insertion professionnelle",
        "Responsable de l'animation - Centre social",
    ],
)
def test_animation_roles_keep_related_titles(title):
    assert title_matches_roles(title, role_terms(ANIMATION_ROLES))


@pytest.mark.parametrize(
    "title,expected",
    [
        ("Data Scientist", True),
        ("Ingénieur(e) Data Scientist confirmé(e)", True),
        ("Data Analyst", True),
        ("Data Engineer AWS Senior / Cloud", True),
        ("Contrôleur de gestion", False),
        ("Animateur périscolaire", False),
        ("Chef de projet", False),
    ],
)
def test_data_roles(title, expected):
    assert title_matches_roles(title, role_terms(DATA_ROLES)) is expected


def test_generic_words_do_not_count_as_role_terms():
    """« Chef de projet » ne dit rien du métier : aucun terme, donc pas de garde."""
    assert role_terms(["Chef de projet", "Consultant senior"]) == frozenset()


def test_empty_terms_let_every_title_pass():
    assert title_matches_roles("Contrôleur de gestion", frozenset())


def test_missing_title_passes():
    """Intitulé absent : rien pour trancher, l'offre n'est pas écartée."""
    assert title_matches_roles("", role_terms(DATA_ROLES))
    assert title_matches_roles(None, role_terms(DATA_ROLES))


def test_short_terms_need_exact_match():
    """Un terme court (« rh ») ne doit pas attraper tout mot qui commence pareil."""
    assert title_matches_roles("Chargée RH", role_terms(["Responsable RH"]))
    assert not title_matches_roles("Rhumatologue", role_terms(["Responsable RH"]))


@pytest.mark.parametrize(
    "roles,title,expected",
    [
        # data <-> données / donnée
        (["Data Scientist", "Ingénieur Data"], "Analyste données web", True),
        (["Data Scientist", "Ingénieur Data"], "Ingénieur Eau, Données et Outils Numériques", True),
        (["Ingénieur de données"], "Data Engineer Senior", True),
        # analyste / analyst <-> analytics / analytical / analyse
        (["Data analyste"], "Analytics Engineer - Power BI", True),
        (["Data analyste"], "Analytical Performance Lead (English, French)", True),
        (["Contrôle de gestion FP&A"], "Responsable Reporting et Analyse Financière Groupe", True),
        # FP&A <-> FPA / Financial Planning and Analysis
        (["Contrôle de gestion FP&A"], "FPA Manager", True),
        (["Contrôle de gestion FP&A"], "Financial Planning and Analysis Manager", True),
        # Generic English words (project, management) should NOT make "Finance project manager" match unrelated "Chef de Projet"
        (["Contrôle de gestion FP&A", "Data analyste", "Finance project manager"], "Chef de Projet Monétique", False),
        (["Contrôle de gestion FP&A", "Data analyste", "Finance project manager"], "Project Manager IT", False),
        (["Contrôle de gestion FP&A", "Data analyste", "Finance project manager"], "Finance Project Manager", True),
    ],
)
def test_bilingual_and_synonym_role_matching(roles, title, expected):
    assert title_matches_roles(title, role_terms(roles)) is expected
