import json
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
    "je serais": 1,
    "j'ai": 3,
}

# Source unique des seuils : consommée par les garde-fous ci-dessous ET
# injectée dans le prompt du rédacteur (cover_letter_crew.py), pour que les
# règles jugées par le code soient aussi les règles connues du rédacteur.
LETTER_RULES = {
    "min_words": 200,
    "max_words": 350,
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
    "Lors", "Cette", "Ce", "Cet", "Ces", "Sur", "Dans", "Pour", "Par", "Avec", "Sous",
    "Elle", "Elles", "Il", "Ils", "Nous", "Vous", "On",
    "Rejoindre", "Intégrer", "Depuis", "Durant", "Pendant", "Grâce",
    "Ainsi", "Aussi", "Enfin", "En", "De", "Du", "Des",
    "Tout", "Toute", "Tous", "Toutes", "Notre", "Nos",
}


def _check_entities(letter_text: str, offer_description: str, analyst_data: Dict[str, Any]) -> List[str]:
    """Toute entité nommée doit venir des faits fournis à l'analyste.

    Aucune exemption de position n'est accordée au premier mot d'une phrase :
    un LLM pourrait sinon placer une entité inventée en tête de n'importe
    laquelle des phrases du texte pour la faire passer. Le nettoyage des
    connecteurs capitalisés (`_SENTENCE_START_STOPWORDS`) suffit à traiter le
    cas légitime des connecteurs en tête de phrase.
    """
    allowed = {
        _normalize_entity(value)
        for value in (
            list(analyst_data.get("companies") or [])
            + list(analyst_data.get("stacks") or [])
            + list(analyst_data.get("projects") or [])
            + [analyst_data.get("company_name") or ""]
            + [analyst_data.get("candidate_name") or ""]
            + [analyst_data.get("candidate_headline") or ""]
        )
        if value
    }
    # Une entité citée dans l'offre brute (partenaire, client, concurrent du
    # recruteur) n'est PAS légitime pour autant dans la lettre : seuls les
    # faits fournis à l'analyste (companies/stacks/projects/company_name/
    # candidate_name ci-dessus) blanchissent une entité. Ne jamais construire
    # `allowed` à partir de `offer_description`.

    violations: List[str] = []
    seen: set = set()
    for paragraph in re.split(r"\n\s*\n", letter_text):
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip()):
            sentence = sentence.strip()
            if not sentence:
                continue
            for match in _ENTITY_PATTERN.finditer(sentence):
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
                    candidate_tokens <= set(entity.split())
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

    # 2b. Formule accordée au candidat : le prompt impose une conclusion neutre
    # en genre, le rédacteur écrit quand même « Je serais heureuse ».
    gendered = _GENDERED_CLOSING.search(lower_text)
    if gendered:
        violations.append(f"Formule accordée au candidat interdite : '{gendered.group(0)}'")

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
    # Seul le corps compte : salutation, formule de politesse et signature
    # imposées par le prompt ne sont pas des paragraphes d'argumentation.
    body_paragraphs = [
        p for p in paragraphs
        if not re.match(r"^(madame|monsieur)\b", p.lower())
        and not p.lower().replace("’", "'").startswith("je vous prie d'agréer")
    ]
    if body_paragraphs and len(body_paragraphs[-1].split()) <= 4 and not re.search(r"[.?]$", body_paragraphs[-1]):
        body_paragraphs = body_paragraphs[:-1]
    stats["paragraph_count"] = len(body_paragraphs)
    min_paragraphs, max_paragraphs = LETTER_RULES["min_paragraphs"], LETTER_RULES["max_paragraphs"]
    if not (min_paragraphs <= len(body_paragraphs) <= max_paragraphs):
        violations.append(
            f"Nombre de paragraphes hors bornes ({min_paragraphs}-{max_paragraphs} requis, {len(body_paragraphs)} trouvés)"
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

    # 8. Répétitions plafonnées (apostrophe typographique ramenée à ' : les LLM
    # écrivent « J’ai » aussi souvent que « J'ai »)
    straight_text = lower_text.replace("’", "'")
    for term, max_allowed in LETTER_RULES["capped_repetitions"].items():
        occurrences = len(re.findall(r"\b" + re.escape(term) + r"\b", straight_text))
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

    # 13. Chiffres non vérifiables : tout nombre cité dans la lettre doit
    # apparaître littéralement soit dans l'offre, soit dans le JSON des
    # expériences sélectionnées transmises à l'analyste — sinon rien ne prouve
    # que le LLM ne l'a pas inventé. Une année plausible (1900-2099) est
    # exemptée : elle n'a pas besoin d'être présente ailleurs pour être
    # légitime dans une lettre.
    experiences_json = json.dumps(
        analyst_data.get("selected_experiences", []), ensure_ascii=False
    )
    for number in re.findall(r"\b\d+(?:[.,]\d+)?\b", letter_text):
        if re.fullmatch(r"(?:19|20)\d{2}", number) and 1900 <= int(number) <= 2099:
            continue
        if number in (offer_description or "") or number in experiences_json:
            continue
        violations.append(f"Chiffre non vérifiable cité dans la lettre : '{number}'")

    # 14. Débuts de paragraphe centrés sur un employeur
    for p in paragraphs:
        # Ignore la salutation
        p_clean = p.strip()
        if p_clean.lower().startswith("madame") or p_clean.lower().startswith("monsieur"):
            continue
        if _FORBIDDEN_EMPLOYER_OPENING.match(p_clean):
            violations.append(
                f"Paragraphe débutant par une formule d'ouverture d'employeur/expérience interdite : '{p_clean[:45]}...'"
            )

    # 15. Nombre d'employeurs candidats cités (max 2 pour éviter l'effet catalogue de CV)
    target_company = (analyst_data.get("company_name") or "").strip().lower()
    candidate_companies = {
        c.strip()
        for c in (analyst_data.get("companies") or [])
        if c and c.strip().lower() != target_company
    }
    if candidate_companies:
        cited_companies = []
        for comp in candidate_companies:
            if re.search(r"\b" + re.escape(comp) + r"\b", letter_text, re.IGNORECASE):
                cited_companies.append(comp)
        if len(cited_companies) > 2:
            violations.append(
                f"Trop d'employeurs candidats cités ({len(cited_companies)} cités : {cited_companies}, maximum 2 autorisé pour éviter l'effet catalogue)"
            )


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
