import re
import math
from typing import Dict, Any, List
from pydantic import BaseModel, Field

from app.services.profile.periods import company_slug as _normalize_entity

BANNED_LEXICON = [
    "forte appétence", "solide expertise", "je suis convaincu que mon profil",
    "force de proposition", "dynamique", "rigoureux", "passionné par",
    "vivement intéressé", "à la pointe de", "parfaitement adapté",
    "dans l'attente de votre retour", "restant à votre entière disposition",
    "permettez-moi de vous présenter", "polyvalent"
]

BANNED_OPENINGS = [
    "je vous adresse ma candidature", "actuellement à la recherche",
    "titulaire de", "fort de", "c'est avec grand intérêt"
]

SENTENCE_CONNECTORS = [
    "de plus", "par ailleurs", "en outre", "enfin", "de même",
    "en effet", "ainsi", "dans ce contexte", "à ce titre", "fort de cette expérience"
]

GENERIC_COMPLIMENTS = [
    "entreprise leader", "entreprise innovante", "acteur majeur",
    "entreprise reconnue", "culture d'innovation", "excellence", "forte croissance"
]

CAPPED_REPETITIONS = {
    "mon parcours": 1,
    "mon expérience": 1,
    "mes compétences": 1,
    "je souhaite": 1,
    "je suis": 1,
    "je serais": 1
}

# Source unique des seuils : consommée par les garde-fous ci-dessous ET
# injectée dans le prompt du rédacteur (cover_letter_crew.py), pour que les
# règles jugées par le code soient aussi les règles connues du rédacteur.
LETTER_RULES = {
    "min_words": 250,
    "max_words": 400,
    "min_paragraphs": 3,
    "max_paragraphs": 5,
    "max_head_connectors": 1,
    "max_semicolons": 1,
    "capped_repetitions": CAPPED_REPETITIONS,
    "banned_lexicon": BANNED_LEXICON,
    "banned_openings": BANNED_OPENINGS,
    "generic_compliments": GENERIC_COMPLIMENTS,
}

_ENTITY_PATTERN = re.compile(r"\b[A-ZÀ-Ý][A-Za-zÀ-ÿ0-9&.\-]{2,}(?: [A-ZÀ-Ý][A-Za-zÀ-ÿ0-9&.\-]{2,})?")
_SENTENCE_START_STOPWORDS = {
    "Madame", "Monsieur", "Cordialement", "Je", "Mon", "Ma", "Mes",
    "Votre", "Vos", "Chez", "Au", "Le", "La", "Les",
}


def _check_entities(letter_text: str, offer_description: str, analyst_data: Dict[str, Any]) -> List[str]:
    """Toute entité nommée doit venir des faits fournis à l'analyste.

    Seule une majuscule "interne" (qui n'a rien à voir avec la majuscule
    conventionnelle de début de phrase en français) est un indice fiable
    d'entité nommée : le premier mot de chaque phrase est donc exempté,
    plutôt que de maintenir une liste sans fin de mots de liaison.
    """
    allowed = {
        _normalize_entity(value)
        for value in (
            list(analyst_data.get("companies") or [])
            + list(analyst_data.get("stacks") or [])
            + list(analyst_data.get("projects") or [])
            + [analyst_data.get("company_name") or ""]
            + [analyst_data.get("candidate_name") or ""]
        )
        if value
    }
    # Toute entité déjà nommée dans l'offre elle-même est légitime à
    # reprendre (ex. l'intitulé du poste) : ce n'est pas une invention du
    # candidat.
    allowed |= {
        _normalize_entity(m.group(0))
        for m in _ENTITY_PATTERN.finditer(offer_description or "")
    }

    violations: List[str] = []
    seen: set = set()
    for paragraph in re.split(r"\n\s*\n", letter_text):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            sentence = sentence.strip()
            if not sentence:
                continue
            for match in _ENTITY_PATTERN.finditer(sentence):
                if match.start() == 0:
                    continue  # majuscule de début de phrase, pas un indice fiable
                raw_candidate = match.group(0)
                # Un connecteur capitalisé peut se retrouver accolé à
                # l'entité qui le suit (« Chez Agence Nile ») : on l'ignore
                # avant de comparer, plutôt que de rejeter le candidat entier.
                words = raw_candidate.split()
                while words and words[0] in _SENTENCE_START_STOPWORDS:
                    words.pop(0)
                if not words:
                    continue
                candidate = " ".join(words)
                normalized = _normalize_entity(candidate)
                if not normalized:
                    continue
                # Comparaison par ensemble de tokens (mots entiers), jamais par
                # sous-chaîne de caractères : sinon "Go" (stack connue) autorise
                # "Google" (entreprise inventée) puisque "go" in "google" est vrai.
                candidate_tokens = set(normalized.split())
                if candidate_tokens and any(
                    candidate_tokens <= set(entity.split()) or set(entity.split()) <= candidate_tokens
                    for entity in allowed
                    if entity
                ):
                    continue
                if candidate in seen:
                    continue
                seen.add(candidate)
                violations.append(f"Entité non autorisée citée dans la lettre : '{candidate}'")
    return violations


class GuardReport(BaseModel):
    is_blocking: bool = False
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=dict)

def evaluate_letter_guards(
    letter_text: str,
    offer_description: str,
    analyst_data: Dict[str, Any],
) -> GuardReport:
    violations: List[str] = []
    warnings: List[str] = []
    stats: Dict[str, Any] = {}

    lower_text = letter_text.lower()

    # 1. Ponctuation interdite
    if "!" in letter_text:
        violations.append("Point d'exclamation (!) interdit")
    if "..." in letter_text or "…" in letter_text:
        violations.append("Points de suspension (...) interdits")
    if "—" in letter_text:
        violations.append("Tiret cadratin (—) interdit")
    if "(" in letter_text or ")" in letter_text:
        violations.append("Parenthèses interdites")
    max_semicolons = LETTER_RULES["max_semicolons"]
    if letter_text.count(";") > max_semicolons:
        violations.append(f"Point-virgule en excès ({letter_text.count(';')} trouvés, maximum {max_semicolons} autorisé)")

    # 2. Lexique banni
    for phrase in BANNED_LEXICON:
        if phrase in lower_text:
            violations.append(f"Lexique banni détecté : '{phrase}'")

    # 3. Ouvertures interdites
    trimmed = lower_text.strip()
    for opening in BANNED_OPENINGS:
        if trimmed.startswith(opening):
            violations.append(f"Ouverture interdite détectée : '{opening}'")

    # 4. Compliments génériques
    for comp in GENERIC_COMPLIMENTS:
        if comp in lower_text:
            violations.append(f"Compliment générique interdit : '{comp}'")

    # 5. Paragraphes
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", letter_text.strip()) if p.strip()]
    stats["paragraph_count"] = len(paragraphs)
    min_paragraphs, max_paragraphs = LETTER_RULES["min_paragraphs"], LETTER_RULES["max_paragraphs"]
    if not (min_paragraphs <= len(paragraphs) <= max_paragraphs):
        violations.append(
            f"Nombre de paragraphes hors bornes ({min_paragraphs}-{max_paragraphs} requis, {len(paragraphs)} trouvés)"
        )

    # 6. Longueur en mots
    words = re.findall(r"\b\w+\b", letter_text)
    word_count = len(words)
    stats["word_count"] = word_count
    min_words, max_words = LETTER_RULES["min_words"], LETTER_RULES["max_words"]
    if not (min_words <= word_count <= max_words):
        violations.append(f"Longueur hors bornes ({min_words}-{max_words} mots requis, {word_count} trouvés)")

    # 7. Connecteurs en tête de phrase
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", letter_text) if s.strip()]
    connector_count = 0
    for s in sentences:
        s_lower = s.lower()
        for conn in SENTENCE_CONNECTORS:
            if s_lower.startswith(conn):
                connector_count += 1
                break
    stats["head_connector_count"] = connector_count
    max_head_connectors = LETTER_RULES["max_head_connectors"]
    if connector_count > max_head_connectors:
        violations.append(
            f"Connecteurs en tête de phrase en excès ({connector_count} trouvés, maximum {max_head_connectors} autorisé)"
        )

    # 8. Répétitions plafonnées
    for term, max_allowed in LETTER_RULES["capped_repetitions"].items():
        occurrences = len(re.findall(r"\b" + re.escape(term) + r"\b", lower_text))
        if occurrences > max_allowed:
            violations.append(f"Répétition excessive de '{term}' ({occurrences} trouvés, max {max_allowed})")

    # 9. Ouverture de paragraphe : pas tous commençant par "Je" ou "J'"
    if len(paragraphs) > 1 and all(re.match(r"^(je|j')", p.lower().strip()) for p in paragraphs):
        violations.append("Tous les paragraphes débutent par 'Je' ou 'J''")

    # 10. Énumérations technologiques (max 3 par phrase)
    known_stacks = [s.lower() for s in analyst_data.get("stacks", [])]
    for s in sentences:
        s_lower = s.lower()
        found_in_sentence = [t for t in known_stacks if re.search(r"\b" + re.escape(t) + r"\b", s_lower)]
        if len(found_in_sentence) > 3:
            violations.append(f"Plus de 3 technologies énumérées dans la même phrase : {found_in_sentence}")
            break

    # 11. Recouvrement de 8 mots consécutifs avec l'offre
    if offer_description:
        offer_words = [w.lower() for w in re.findall(r"\b\w+\b", offer_description)]
        letter_words = [w.lower() for w in words]
        if len(offer_words) >= 8 and len(letter_words) >= 8:
            offer_8grams = {tuple(offer_words[i:i+8]) for i in range(len(offer_words) - 7)}
            for i in range(len(letter_words) - 7):
                ngram = tuple(letter_words[i:i+8])
                if ngram in offer_8grams:
                    violations.append(f"Recouvrement textuel de 8 mots avec l'offre détecté : '{' '.join(ngram)}'")
                    break

    # 12. Entités : toute entité nommée (majuscule interne) doit venir des faits
    # fournis à l'analyste (entreprises, stacks, projets, entreprise destinataire).
    violations.extend(_check_entities(letter_text, offer_description, analyst_data))

    # --- Contrôles d'avertissement (non bloquants) ---
    sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences if s]
    if sentence_lengths:
        mean_len = sum(sentence_lengths) / len(sentence_lengths)
        variance = sum((l - mean_len) ** 2 for l in sentence_lengths) / len(sentence_lengths)
        stdev = math.sqrt(variance)
        stats["sentence_length_stdev"] = round(stdev, 2)
        if stdev < 4.0 and len(sentences) >= 3:
            warnings.append(f"Faible variance de longueur de phrase (écart-type {stdev:.2f} < 4 mots)")

        extreme_sentences = [l for l in sentence_lengths if l > 40]
        if extreme_sentences:
            warnings.append(f"Phrase extrême détectée (> 40 mots : {extreme_sentences[0]} mots)")

    return GuardReport(
        is_blocking=len(violations) > 0,
        violations=violations,
        warnings=warnings,
        stats=stats
    )
