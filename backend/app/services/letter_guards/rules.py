import re
from typing import Any, Dict, List

from pydantic import BaseModel, Field

BANNED_LEXICON = [
    "forte appétence", "solide expertise", "je suis convaincu que mon profil",
    "force de proposition", "dynamique", "rigoureux", "passionné par",
    "vivement intéressé", "à la pointe de", "parfaitement adapté",
    "dans l'attente de votre retour", "restant à votre entière disposition",
    "permettez-moi de vous présenter", "polyvalent",
    "synergie", "actionable insights", "valeur ajoutée", "alignement stratégique",
    "opportunité unique", "profil idéal", "mettre à profit",
    "plus tôt chez", "plus tôt, chez", "auparavant chez", "précédemment chez",
]

_FORBIDDEN_EMPLOYER_OPENING = re.compile(
    r"^(?:À\s+(?:l[’']\s*)?|Au\s+(?:sein\s+de\s+)?|Chez\s+|Mon\s+expérience\s+(?:à|chez|au)\s+|Lors\s+de\s+mon\s+passage\s+(?:chez|à|au)\s+)[A-ZÀ-Ý]",
    re.IGNORECASE,
)

_GENDERED_CLOSING = re.compile(
    r"\bje (?:serais|serai|suis) (?:très |vraiment )?(?:heureu(?:x|se)|ravie?|convaincue?|enthousiaste)\b"
)

BANNED_OPENINGS = [
    "je vous adresse ma candidature",
    "actuellement à la recherche",
    "titulaire de",
    "fort de",
    "c'est avec grand intérêt",
]

SENTENCE_CONNECTORS = [
    "de plus", "par ailleurs", "en outre", "enfin", "de même",
    "en effet", "ainsi", "dans ce contexte", "à ce titre", "fort de cette expérience",
]

GENERIC_COMPLIMENTS = [
    "entreprise leader", "entreprise innovante", "acteur majeur",
    "entreprise reconnue", "culture d'innovation", "excellence", "forte croissance",
]

CAPPED_REPETITIONS = {
    "mon parcours": 1,
    "mon expérience": 1,
    "mes compétences": 1,
    "je souhaite": 1,
    "je suis": 1,
    "je serais": 1,
    # Conditionnel réservé à la demande d'entretien : répété, il fait hésitant.
    "je voudrais": 1,
    "j'aimerais": 1,
    "je souhaiterais": 1,
    "j'ai": 3,
}

# Source unique des seuils : consommée par les garde-fous ET
# injectée dans le prompt du rédacteur (cover_letter_crew.py).
LETTER_RULES = {
    "min_words": 200,
    "max_words": 350,
    "min_paragraphs": 3,
    "max_paragraphs": 5,
    "max_head_connectors": 1,
    "max_semicolons": 1,
    "max_verbatim_title_words": 6,
    "max_lesson_formulas": 1,
    "capped_repetitions": CAPPED_REPETITIONS,
    "banned_lexicon": BANNED_LEXICON,
    "banned_openings": BANNED_OPENINGS,
    "generic_compliments": GENERIC_COMPLIMENTS,
}

_ENTITY_PATTERN = re.compile(
    r"\b[A-ZÀ-Ý][A-Za-zÀ-ÿ0-9&.\-]{2,}(?: [A-ZÀ-Ý][A-Za-zÀ-ÿ0-9&.\-]{2,})?"
)
_SENTENCE_START_STOPWORDS = {
    "Madame", "Monsieur", "Cordialement", "Je", "Mon", "Ma", "Mes",
    "Votre", "Vos", "Chez", "Au", "Le", "La", "Les",
    "Lors", "Cette", "Ce", "Cet", "Ces", "Sur", "Dans", "Pour", "Par", "Avec", "Sous",
    "Elle", "Elles", "Il", "Ils", "Nous", "Vous", "On",
    "Rejoindre", "Intégrer", "Depuis", "Durant", "Pendant", "Grâce",
    "Ainsi", "Aussi", "Enfin", "En", "De", "Du", "Des",
    "Tout", "Toute", "Tous", "Toutes", "Notre", "Nos",
}


class GuardReport(BaseModel):
    is_blocking: bool = False
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)
