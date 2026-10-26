"""Garde métier : l'intitulé de l'offre doit partager un terme métier avec les
rôles visés par le candidat.

Le cosinus mistral-embed absolu ne se transpose pas d'un profil à l'autre :
une offre data atteint 0.75 face à un profil d'animation, assez pour passer
FLOOR avec la base fixe des composantes hors métier. Cette garde lexicale,
sans appel réseau, écarte l'offre avant tout score (`hard_filter_reason`).
"""

from typing import Iterable, Optional

import snowballstemmer

from app.services.evaluation.domain_relevance import expand_title_acronyms
from app.services.relevance import normalize_text

_STEMMER = snowballstemmer.stemmer("french")

# Mots qui ne disent rien du métier : niveau, contrat, fonction générique,
# mots vides (déjà normalisés : minuscules, sans accents). Un rôle fait
# uniquement de ces mots (« Chef de projet ») ne donne aucun terme, donc
# aucune garde.
GENERIC_TITLE_WORDS = frozenset(
    """
    h f hf x e de du des d l la le les un une et ou en a au aux pour par sur avec dans chez
    the of and for in at to
    responsable chef cheffe charge chargee mission missions projet projets
    coordinateur coordinatrice coordination directeur directrice direction manager management
    assistant assistante adjoint adjointe senior junior confirme confirmee experimente experimentee
    debutant stagiaire stage alternance alternant alternante apprenti apprentie
    cdi cdd interim freelance poste offre emploi
    specialiste specialise specialisee expert experte consultant consultante ingenieur ingenieure
    engineer lead head officer associate principal staff
    professionnel professionnelle professionnels service services general generale
    agent technicien technicienne conseiller conseillere gestionnaire employe employee
    developpement
    """.split()
)

# Sous cette longueur, un terme ne vaut que s'il est égal ou de même racine :
# « rh » ne doit pas attraper « rhumatologue ».
_MIN_PREFIX_LENGTH = 4


def _title_tokens(text: Optional[str]) -> list[str]:
    normalized = normalize_text(expand_title_acronyms(text or ""))
    return [token for token in normalized.split() if token not in GENERIC_TITLE_WORDS]


def role_terms(roles: Iterable[str]) -> frozenset[str]:
    """Termes métier des rôles visés, mots génériques retirés."""
    return frozenset(token for role in roles if role for token in _title_tokens(role))


def _related(a: str, b: str) -> bool:
    if a == b or _STEMMER.stemWord(a) == _STEMMER.stemWord(b):
        return True
    short, long_ = sorted((a, b), key=len)
    return len(short) >= _MIN_PREFIX_LENGTH and long_.startswith(short)


def title_matches_roles(title: Optional[str], terms: frozenset[str]) -> bool:
    """Vrai si l'intitulé partage un terme métier avec les rôles visés.

    Pas de terme côté candidat ou pas d'intitulé : rien pour trancher, l'offre
    passe. Un intitulé fait seulement de mots génériques n'apporte aucun signal
    métier : il ne passe pas.
    """
    if not terms or not (title or "").strip():
        return True
    return any(_related(token, term) for token in _title_tokens(title) for term in terms)
