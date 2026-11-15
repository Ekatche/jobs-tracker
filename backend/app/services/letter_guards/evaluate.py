import json
import math
import re
from typing import Any, Dict, List

from .attribution import _check_attribution, _check_entities
from .rules import (
    _FORBIDDEN_EMPLOYER_OPENING,
    _GENDERED_CLOSING,
    BANNED_LEXICON,
    BANNED_OPENINGS,
    GENERIC_COMPLIMENTS,
    GuardReport,
    LETTER_RULES,
    SENTENCE_CONNECTORS,
)


def _check_punctuation_and_lexicon(letter_text: str, lower_text: str) -> List[str]:
    violations: List[str] = []
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
        violations.append(
            f"Point-virgule en excès ({letter_text.count(';')} trouvés, maximum {max_semicolons} autorisé)"
        )

    for phrase in BANNED_LEXICON:
        if phrase in lower_text:
            violations.append(f"Lexique banni détecté : '{phrase}'")
    gendered = _GENDERED_CLOSING.search(lower_text)
    if gendered:
        violations.append(f"Formule accordée au candidat interdite : '{gendered.group(0)}'")
    trimmed = lower_text.strip()
    for opening in BANNED_OPENINGS:
        if trimmed.startswith(opening):
            violations.append(f"Ouverture interdite détectée : '{opening}'")
    for comp in GENERIC_COMPLIMENTS:
        if comp in lower_text:
            violations.append(f"Compliment générique interdit : '{comp}'")
    return violations


def _check_structure_and_repetitions(
    letter_text: str,
    lower_text: str,
    paragraphs: List[str],
    sentences: List[str],
    words: List[str],
    analyst_data: Dict[str, Any],
    stats: Dict[str, Any],
) -> List[str]:
    violations: List[str] = []
    body_paragraphs = [
        p
        for p in paragraphs
        if not re.match(r"^(madame|monsieur)\b", p.lower())
        and not p.lower().replace("’", "'").startswith("je vous prie d'agréer")
    ]
    if (
        body_paragraphs
        and len(body_paragraphs[-1].split()) <= 4
        and not re.search(r"[.?]$", body_paragraphs[-1])
    ):
        body_paragraphs = body_paragraphs[:-1]
    stats["paragraph_count"] = len(body_paragraphs)
    min_p, max_p = LETTER_RULES["min_paragraphs"], LETTER_RULES["max_paragraphs"]
    if not (min_p <= len(body_paragraphs) <= max_p):
        violations.append(
            f"Nombre de paragraphes hors bornes ({min_p}-{max_p} requis, {len(body_paragraphs)} trouvés)"
        )

    stats["word_count"] = len(words)
    min_w, max_w = LETTER_RULES["min_words"], LETTER_RULES["max_words"]
    if not (min_w <= len(words) <= max_w):
        violations.append(f"Longueur hors bornes ({min_w}-{max_w} mots requis, {len(words)} trouvés)")

    connector_count = sum(
        1 for s in sentences if any(s.lower().startswith(c) for c in SENTENCE_CONNECTORS)
    )
    stats["head_connector_count"] = connector_count
    max_conn = LETTER_RULES["max_head_connectors"]
    if connector_count > max_conn:
        violations.append(
            f"Connecteurs en tête de phrase en excès ({connector_count} trouvés, maximum {max_conn} autorisé)"
        )

    straight = lower_text.replace("’", "'")
    for term, max_allowed in LETTER_RULES["capped_repetitions"].items():
        occurrences = len(re.findall(r"\b" + re.escape(term) + r"\b", straight))
        if occurrences > max_allowed:
            violations.append(f"Répétition excessive de '{term}' ({occurrences} trouvés, max {max_allowed})")

    lesson_count = len(re.findall(r"\bm'(?:a|ont) (?:appris|montré|enseigné)\b", straight))
    max_lessons = LETTER_RULES["max_lesson_formulas"]
    if lesson_count > max_lessons:
        violations.append(
            f"Leçons tirées en excès ({lesson_count} formules « m'a appris / m'a montré », maximum {max_lessons} autorisé)"
        )

    if len(paragraphs) > 1 and all(re.match(r"^(je|j')", p.lower().strip()) for p in paragraphs):
        violations.append("Tous les paragraphes débutent par 'Je' ou 'J''")

    known_stacks = [s.lower() for s in analyst_data.get("stacks", [])]
    for s in sentences:
        found_in_s = [t for t in known_stacks if re.search(r"\b" + re.escape(t) + r"\b", s.lower())]
        if len(found_in_s) > 3:
            violations.append(f"Plus de 3 technologies énumérées dans la même phrase : {found_in_s}")
            break
    return violations


def _check_grounding_and_openings(
    letter_text: str,
    offer_description: str,
    analyst_data: Dict[str, Any],
    paragraphs: List[str],
    words: List[str],
) -> List[str]:
    violations: List[str] = []
    letter_words = [w.lower() for w in words]

    if offer_description:
        offer_words = [w.lower() for w in re.findall(r"\b\w+\b", offer_description)]
        if len(offer_words) >= 8 and len(letter_words) >= 8:
            offer_8grams = {tuple(offer_words[i : i + 8]) for i in range(len(offer_words) - 7)}
            for i in range(len(letter_words) - 7):
                ngram = tuple(letter_words[i : i + 8])
                if ngram in offer_8grams:
                    violations.append(
                        f"Recouvrement textuel de 8 mots avec l'offre détecté : '{' '.join(ngram)}'"
                    )
                    break

    title_words = [w.lower() for w in re.findall(r"\b\w+\b", analyst_data.get("job_title") or "")]
    span = LETTER_RULES["max_verbatim_title_words"] + 1
    if len(title_words) >= span:
        title_grams = {tuple(title_words[i : i + span]) for i in range(len(title_words) - span + 1)}
        if any(
            tuple(letter_words[i : i + span]) in title_grams
            for i in range(len(letter_words) - span + 1)
        ):
            violations.append(
                "Intitulé du poste recopié mot pour mot : désigne le poste par son métier, "
                "« ce poste d'ingénieur de recherche »"
            )

    violations.extend(_check_entities(letter_text, offer_description, analyst_data))

    experiences_json = json.dumps(
        list(analyst_data.get("selected_experiences", []))
        + list(analyst_data.get("selected_projects", [])),
        ensure_ascii=False,
    )
    for number in re.findall(r"\b\d+(?:[.,]\d+)?\b", letter_text):
        if re.fullmatch(r"(?:19|20)\d{2}", number) and 1900 <= int(number) <= 2099:
            continue
        if number not in (offer_description or "") and number not in experiences_json:
            violations.append(f"Chiffre non vérifiable cité dans la lettre : '{number}'")

    violations.extend(_check_attribution(letter_text, analyst_data, offer_description))

    for p in paragraphs:
        p_clean = p.strip()
        if p_clean.lower().startswith("madame") or p_clean.lower().startswith("monsieur"):
            continue
        if _FORBIDDEN_EMPLOYER_OPENING.match(p_clean):
            violations.append(
                f"Paragraphe débutant par une formule d'ouverture d'employeur/expérience interdite : '{p_clean[:45]}...'"
            )

    target_company = (analyst_data.get("company_name") or "").strip().lower()
    candidate_companies = {
        c.strip()
        for c in (analyst_data.get("companies") or [])
        if c and c.strip().lower() != target_company
    }
    if candidate_companies:
        cited = [
            comp
            for comp in candidate_companies
            if re.search(r"\b" + re.escape(comp) + r"\b", letter_text, re.IGNORECASE)
        ]
        if len(cited) > 2:
            violations.append(
                f"Trop d'employeurs candidats cités ({len(cited)} cités : {cited}, maximum 2 autorisé pour éviter l'effet catalogue)"
            )
    return violations


def evaluate_letter_guards(
    letter_text: str,
    offer_description: str,
    analyst_data: Dict[str, Any],
) -> GuardReport:
    lower_text = letter_text.lower()
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", letter_text.strip()) if p.strip()]
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", letter_text) if s.strip()]
    words = re.findall(r"\b\w+\b", letter_text)

    stats: Dict[str, Any] = {}
    violations = _check_punctuation_and_lexicon(letter_text, lower_text)
    violations.extend(
        _check_structure_and_repetitions(
            letter_text, lower_text, paragraphs, sentences, words, analyst_data, stats
        )
    )
    violations.extend(
        _check_grounding_and_openings(
            letter_text, offer_description, analyst_data, paragraphs, words
        )
    )

    warnings: List[str] = []
    sentence_lengths = [len(re.findall(r"\b\w+\b", s)) for s in sentences if s]
    if sentence_lengths:
        mean_len = sum(sentence_lengths) / len(sentence_lengths)
        variance = sum((length - mean_len) ** 2 for length in sentence_lengths) / len(sentence_lengths)
        stdev = math.sqrt(variance)
        stats["sentence_length_stdev"] = round(stdev, 2)
        if stdev < 4.0 and len(sentences) >= 3:
            warnings.append(f"Faible variance de longueur de phrase (écart-type {stdev:.2f} < 4 mots)")
        extreme_sentences = [length for length in sentence_lengths if length > 40]
        if extreme_sentences:
            warnings.append(f"Phrase extrême détectée (> 40 mots : {extreme_sentences[0]} mots)")

    return GuardReport(
        is_blocking=len(violations) > 0,
        violations=violations,
        warnings=warnings,
        stats=stats,
    )
