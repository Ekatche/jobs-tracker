import re
from typing import Dict, List, Set

ATOMIC_FIELDS = frozenset({
    "prioritized_skills", "relevant_technologies", "bullet_points", "certifications",
})

SENIORITY_CLAIM_RE = re.compile(
    r"\b(\d+)\s*\+?\s*(?:ans?\s+d['’]\s?exp[eé]rience|years?\s+of\s+experience)\b",
    re.IGNORECASE,
)

STOPWORDS: Set[str] = {
    "de", "d", "des", "du", "le", "la", "les", "un", "une", "et", "en", "pour", "par",
    "sur", "a", "au", "aux", "dans", "avec", "sous", "and", "of", "the", "in", "for",
    "with", "on", "to", "at",
}

ACTION_PREFIXES: Set[str] = {
    "conception", "developpement", "gestion", "mise en place", "creation", "architecture",
    "administration", "optimisation", "implementation", "pilotage", "design", "engineering",
    "analyse", "deploiement", "integration", "maintenance", "redaction", "structuration",
    "elaboration", "definition", "suivi",
}

TECHNICAL_SYNONYMS: Dict[str, List[str]] = {
    "modelisation de donnees": ["data modeling", "data model", "modelisation", "data models"],
    "modeles semantiques": ["semantic models", "semantic model", "modele semantique"],
    "dashboards decisionnels": [
        "dashboards", "dashboard", "power bi", "tableaux de bord", "tableau de bord",
    ],
    "reporting analytique": ["reporting", "power bi", "analyses avancees", "analytics"],
    "pipelines multi sources": ["etl elt", "pipelines", "multi sources", "etl multi sources", "etl"],
    "apis rest": ["api rest", "fastapi", "rest api", "apis", "restful", "rest"],
    "api rest": ["apis rest", "fastapi", "rest api", "apis", "restful", "rest"],
    "rag": ["retrieval augmented generation", "systemes rag", "agents ia"],
    "apprentissage automatique": ["machine learning", "ml"],
    "apprentissage profond": ["deep learning", "dl"],
}

_NUM = r"\d+(?:[.,]\d+)?"
_PCT_RE = re.compile(rf"(?<![\w.,])({_NUM})\s?%")
_MONEY_RE = re.compile(
    rf"(?<![\w.,])({_NUM})\s?(k|md|m|b)?\s?(?:€|\$|£|\b(?:eur|euros?|usd)\b)", re.IGNORECASE
)
_SCALED_RE = re.compile(rf"(?<![\w.,])({_NUM})([kK]|M)(?![A-Za-z€$£])")
_MULT_PRE_RE = re.compile(rf"(?<![\w.,])[x×]\s?({_NUM})(?![\w%])", re.IGNORECASE)
_MULT_POST_RE = re.compile(rf"(?<![\w.,])({_NUM})[x×](?!\w)", re.IGNORECASE)
_COUNT_RE = re.compile(rf"(?<![\w.,/-])({_NUM})\s+([^\W\d_][\w'’-]*)")
_NUMBER_RE = re.compile(_NUM)
_SCALES = {"": 1.0, "k": 1e3, "m": 1e6, "md": 1e9, "b": 1e9}

_NON_CLAIM_NOUNS: Set[str] = STOPWORDS | {
    "an", "ans", "annee", "annees", "mois", "semaine", "semaines", "jour", "jours",
    "heure", "heures", "h", "minute", "minutes", "min", "seconde", "secondes", "sec",
    "ms", "s", "year", "years", "month", "months", "week", "weeks", "day", "days",
    "hour", "hours", "second", "seconds", "ou", "or", "mais", "but", "que", "qui",
    "janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout",
    "septembre", "octobre", "novembre", "decembre", "new",
}

_METRIC_NOUNS_RAW = (
    "an", "ans", "année", "années", "annee", "annees", "mois", "semaine", "semaines",
    "jour", "jours", "heure", "heures", "year", "years", "month", "months", "week",
    "weeks", "day", "days", "hour", "hours", "utilisateurs", "utilisateur", "users", "user",
    "clients", "client", "customers", "customer", "employés", "employes", "employees",
    "collaborateurs", "staff", "personnel", "personnes", "people", "ingénieurs", "ingenieurs",
    "engineers", "équipes", "equipes", "teams", "entreprises", "companies", "partenaires",
    "partners", "organisations", "organizations", "pays", "countries", "candidats", "candidat",
    "candidates", "candidate", "stagiaires", "trainees", "apprenants", "learners",
    "participants", "étudiants", "etudiants", "students", "élèves", "eleves", "diplômés",
    "graduates", "formateurs", "instructors", "enseignants", "teachers", "écoles", "ecoles",
    "schools", "classes", "classrooms", "formations", "courses", "workshops", "ateliers",
    "certifications", "certificats", "techniciens", "technicians", "opérateurs", "operators",
    "chercheurs", "researchers", "bénévoles", "volunteers", "patients", "projets", "projects",
    "workflows", "pipelines", "agents", "documents", "rapports", "reports", "déploiements",
    "deploiements", "deployments", "serveurs", "servers", "services", "modules", "outils",
    "tools", "modèles", "modeles", "models", "intégrations", "integrations", "tests", "sites",
    "magasins", "bâtiments",
)
_NEAREST_METRIC_RE = re.compile(
    rf"(?<![\w.,/-])({_NUM})\s*\+?\s*(?:[^\W\d_][\w'’-]*\s+){{0,4}}?"
    rf"({'|'.join(sorted(set(_METRIC_NOUNS_RAW), key=len, reverse=True))})\b",
    re.IGNORECASE,
)

_TIME_UNIT_NOUNS = {
    "jour", "jours", "day", "days", "semaine", "semaines", "week", "weeks",
    "mois", "month", "months", "heure", "heures", "hour", "hours",
}
_PLAN_HORIZON_LEAD_RE = re.compile(
    r"\b(?:les?\s+(?:premiers?|prochains?)?|the\s+(?:first|next)|my\s+(?:first|next)|first|next)\s*$",
    re.IGNORECASE,
)
_PLAN_HORIZON_TRAIL_RE = re.compile(r"^\s*(?:premiers?|prochains?|first|next)\b", re.IGNORECASE)
_PROSPECTIVE_CLAUSE_RE = re.compile(
    r"\b(?:plan|plans|planifi[ée]r?|feuille\s+de\s+route|roadmap|approche|approach|objectif|objectives?|"
    r"would|will|shall|should|d['’]ici|pour\s+les)\b|['’](?:ll|d)\b|\b30\s*/\s*60\s*/\s*90\b",
    re.IGNORECASE,
)

_DELEGATED_PARTY_RE = re.compile(
    r"\b(?:prestataires?|agences?|cabinets?|sous-traitants?|fournisseurs?|"
    r"vendors?|agenc(?:y|ies)|contractors?|consultanc(?:y|ies)|consultants?|external\s+teams?|outsourc(?:ed|ing))\b",
    re.IGNORECASE,
)
_PARTICIPATION_RE = re.compile(
    r"\b(?:particip[ée]s?|contribu[ée]s?|assist[ée]s?|aid[ée]s?|en\s+appui|second[ée]s?|"
    r"collaborat(?:ed|ing)|assisted|contributed|participated|supported|helped)\b",
    re.IGNORECASE,
)
_THIRD_PARTY_EXECUTION_RE = re.compile(
    r"\b(?:prestataires?|agences?|cabinets?|vendors?|agenc(?:y|ies)|contractors?|consultants?)\b"
    r"[^.;!?]{0,120}\b(?:qui|ont|which|who|that)\b[^.;!?]{0,120}"
    r"\b(?:d[ée]velopp[ée]|cod[ée]|con[çc]u|construit|authored|built|coded|developed|engineered|implemented|wrote)\b",
    re.IGNORECASE,
)
_DIRECT_LEADERSHIP_RE = re.compile(
    r"\b(?:dirig[ée]|pilot[ée]|architectur[ée]|con[çc]u|fond[ée]|cr[ée]{2}|d[ée]velopp[ée]|impl[ée]ment[ée]|"
    r"led|architected|owned|spearheaded|directed|authored|built|coded|developed|engineered|implemented|wrote)\b",
    re.IGNORECASE,
)
_DIRECT_OWNERSHIP_CLAIM_RE = re.compile(
    r"\b(dirig[ée]|pilot[ée]|architectur[ée]|con[çc]u\s+de\s+bout\s+en\s+bout|fond[ée]|cr[ée]{2}\s+de\s+z[ée]ro|"
    r"led|architected|owned|spearheaded|directed|built\s+from\s+scratch|built\s+end[\s-]+to[\s-]+end)\b\s+([^.;!?]{1,160})",
    re.IGNORECASE,
)
_ATTRIBUTION_STOPWORDS: Set[str] = STOPWORDS | {
    "a", "an", "the", "my", "our", "by", "from", "with", "through", "sur", "du", "des",
    "une", "mon", "ma", "mes", "dirige", "pilote", "architecture", "concu", "fonde", "cree",
    "participe", "contribue", "assiste", "aide", "led", "architected", "owned", "spearheaded",
    "directed", "built", "authored", "developed", "engineered", "prestataire", "prestataires",
    "agence", "agences", "vendor", "vendors", "agency", "contractor", "consultant",
}

_METRIC_NOUN_SYNONYMS: Dict[str, str] = {
    "candidates": "candidats", "candidat": "candidats", "trainees": "stagiaires",
    "learners": "apprenants", "students": "etudiants", "schools": "ecoles",
    "ecole": "ecoles", "classrooms": "classes", "workshops": "ateliers",
    "teams": "equipes", "equipe": "equipes", "users": "utilisateurs",
    "utilisateur": "utilisateurs", "deployments": "deploiements",
    "projects": "projets", "projet": "projets", "personnel": "staff",
    "employees": "collaborateurs",
}

_SKIPPED_KEYS = {
    "start", "end", "start_date", "end_date", "year", "date", "dates",
    "phone", "email", "url", "id", "_id", "user_id", "sources", "conflicts", "writing_samples",
}
_AMBIGUOUS_TERMS = {"agile", "scrum", "kanban", "lean", "teams", "notion", "excel", "word", "office"}
_NAME_QUALIFIERS = {"apache", "microsoft", "google", "amazon", "js", "platform"}

_NUMBER_WORDS = {
    **{w: i for i, w in enumerate(
        "deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize dix-sept dix-huit dix-neuf vingt".split(), 2)},
    **{w: i for i, w in enumerate(
        "two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split(), 2)},
}
_NUMBER_WORDS_RE = re.compile(
    r"(?<![\w-])(" + "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True)) + r")(?![\w-])"
    r"(?!\s+(?:mille|cents?|millions?|milliards?|hundred|thousand|million|billion)(?![\w-]))",
    re.IGNORECASE,
)
_ENGLISH_THOUSANDS_RE = re.compile(r"(?<![\w.,])(?!0,)[1-9]\d{0,2}(?:,\d{3})+(?!\d)(?!,\d)(?!\s*%)")
_POST_TEXT_KEYS = (
    "description", "missions", "missions_alt", "achievements", "stack", "technologies", "role", "title",
)
_LEVEL_WORDS = {
    "associate", "professional", "expert", "foundation", "foundational",
    "practitioner", "advanced", "specialty", "master", "senior", "junior",
}
_ROMAN_NUMERALS = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
