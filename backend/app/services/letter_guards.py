import re
import math
from typing import Dict, Any, List
from pydantic import BaseModel, Field

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
    if letter_text.count(";") > 1:
        violations.append(f"Point-virgule en excès ({letter_text.count(';')} trouvés, maximum 1 autorisé)")

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
    if not (3 <= len(paragraphs) <= 5):
        violations.append(f"Nombre de paragraphes hors bornes (3-5 requis, {len(paragraphs)} trouvés)")

    # 6. Longueur en mots
    words = re.findall(r"\b\w+\b", letter_text)
    word_count = len(words)
    stats["word_count"] = word_count
    if not (250 <= word_count <= 400):
        violations.append(f"Longueur hors bornes (250-400 mots requis, {word_count} trouvés)")

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
    if connector_count > 1:
        violations.append(f"Connecteurs en tête de phrase en excès ({connector_count} trouvés, maximum 1 autorisé)")

    # 8. Répétitions plafonnées
    for term, max_allowed in CAPPED_REPETITIONS.items():
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

    # 12. Entités : toute entreprise/techno citée doit être dans analyst_data
    known_companies = {c.lower() for c in analyst_data.get("companies", [])}
    common_companies = ["google", "meta", "amazon", "apple", "microsoft", "netflix"]
    for comp in common_companies:
        if comp in lower_text and comp not in known_companies:
            violations.append(f"Entité non autorisée citée dans la lettre : '{comp}'")

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
