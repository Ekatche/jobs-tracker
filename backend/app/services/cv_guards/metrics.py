import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Sequence, Set, Tuple

from .constants import (
    _ATTRIBUTION_STOPWORDS,
    _COUNT_RE,
    _DELEGATED_PARTY_RE,
    _DIRECT_LEADERSHIP_RE,
    _DIRECT_OWNERSHIP_CLAIM_RE,
    _ENGLISH_THOUSANDS_RE,
    _METRIC_NOUN_SYNONYMS,
    _MONEY_RE,
    _MULT_POST_RE,
    _MULT_PRE_RE,
    _NAME_QUALIFIERS,
    _NEAREST_METRIC_RE,
    _NON_CLAIM_NOUNS,
    _NUMBER_RE,
    _NUMBER_WORDS,
    _NUMBER_WORDS_RE,
    _PARTICIPATION_RE,
    _PCT_RE,
    _PLAN_HORIZON_LEAD_RE,
    _PLAN_HORIZON_TRAIL_RE,
    _PROSPECTIVE_CLAUSE_RE,
    _SCALED_RE,
    _SCALES,
    _THIRD_PARTY_EXECUTION_RE,
    _TIME_UNIT_NOUNS,
    STOPWORDS,
)
from .models import _Metric
from .text_matching import _clean_str, _short_term_in


def _normalize_digits(text: str) -> str:
    """Espaces insécables, nombres écrits en lettres (FR/EN), milliers « 1,500 » et « 1 500 »."""
    text = re.sub("[\u00a0\u202f\u2009]", " ", text)
    text = _NUMBER_WORDS_RE.sub(lambda m: str(_NUMBER_WORDS[m.group(1).lower()]), text)
    text = _ENGLISH_THOUSANDS_RE.sub(lambda m: m.group(0).replace(",", ""), text)
    while True:
        joined = re.sub(r"(?<=\d) (?=\d{3}(?!\d))", "", text)
        if joined == text:
            return text
        text = joined


def _to_float(raw: str) -> float:
    return round(float(raw.replace(",", ".")), 6)


def _canonical_metric_noun(raw_noun: str) -> str:
    cleaned = _clean_str(raw_noun).split(" ")[0]
    return _METRIC_NOUN_SYNONYMS.get(cleaned, cleaned)


def _is_plan_horizon(text: str, match_start: int, match_end: int, noun: str) -> bool:
    """Detect prospective 30/60/90-day plan horizons so they are not flagged as fabricated metrics."""
    if noun not in _TIME_UNIT_NOUNS:
        return False
    lead_window = text[max(0, match_start - 30) : match_start]
    between = text[match_start:match_end]
    if not (_PLAN_HORIZON_LEAD_RE.search(lead_window) or _PLAN_HORIZON_TRAIL_RE.search(between)):
        return False
    clause_start = (
        max((text.rfind(sep, 0, match_start) for sep in (".", "!", "?", "\n")), default=-1) + 1
    )
    end_candidates = [
        text.find(sep, match_end) for sep in (".", "!", "?", "\n") if text.find(sep, match_end) != -1
    ]
    clause_end = min(end_candidates) if end_candidates else len(text)
    return bool(_PROSPECTIVE_CLAUSE_RE.search(text[clause_start:clause_end]))


def _extract_metrics(text: str) -> List[_Metric]:
    """Valeurs chiffrées porteuses d'une affirmation : %, montants, multiplicateurs, volumes."""
    text = _normalize_digits(text)
    consumed: List[Tuple[int, int]] = []
    found: List[_Metric] = []

    def free(span: Tuple[int, int]) -> bool:
        return not any(span[0] < end and start < span[1] for start, end in consumed)

    def add(match: "re.Match[str]", canon: Tuple[str, float], context: str = "", noun: str = "") -> None:
        consumed.append(match.span(1))
        found.append(_Metric(match.group(0).strip(), canon, _to_float(match.group(1)), context, noun))

    for rx, kind in (
        (_PCT_RE, "pct"),
        (_MONEY_RE, "money"),
        (_SCALED_RE, "scaled"),
        (_MULT_PRE_RE, "mult"),
        (_MULT_POST_RE, "mult"),
    ):
        for m in rx.finditer(text):
            if not free(m.span(1)):
                continue
            value = _to_float(m.group(1))
            if kind in ("money", "scaled"):
                scale_key = (m.group(2) or "").lower()
                add(m, ("n", value * _SCALES[scale_key]))
            else:
                add(m, (kind, value))

    for m in _NEAREST_METRIC_RE.finditer(text):
        raw_number = m.group(1)
        noun = _canonical_metric_noun(m.group(2))
        if not free(m.span(1)) or not noun or re.fullmatch(r"(?:19|20)\d\d", raw_number):
            continue
        if _is_plan_horizon(text, m.start(1), m.end(2), noun) or noun in _NON_CLAIM_NOUNS:
            consumed.append(m.span(1))
            continue
        words = re.findall(r"[\w.+#'’-]+", text[max(0, m.start(1) - 40) : m.start(1)])
        context = _clean_str(f"{words[-1]} {raw_number}") if words and words[-1][:1].isupper() else ""
        add(m, ("n", _to_float(raw_number)), context, noun)

    for m in _COUNT_RE.finditer(text):
        raw_number = m.group(1)
        noun = _canonical_metric_noun(m.group(2))
        if not free(m.span(1)) or noun in _NON_CLAIM_NOUNS or not noun:
            continue
        if re.fullmatch(r"(?:19|20)\d\d", raw_number):
            continue
        words = re.findall(r"[\w.+#'’-]+", text[max(0, m.start(1) - 40) : m.start(1)])
        context = _clean_str(f"{words[-1]} {raw_number}") if words and words[-1][:1].isupper() else ""
        add(m, ("n", _to_float(raw_number)), context, noun)

    return found


@dataclass
class _ClaimContext:
    """Ce que le texte d'un poste (ou du profil) permet d'étayer."""

    known: Set[str]
    corpus: str
    tokens: Set[str]
    numbers: Set[float]
    metrics: List[_Metric]
    raw: Tuple[str, ...] = ()
    stack: Tuple[str, ...] = ()

    @classmethod
    def from_strings(cls, strings: List[str], stack: Tuple[str, ...] = ()) -> "_ClaimContext":
        known: Set[str] = set()
        for text in strings:
            known.add(text.strip())
            known.update(
                tok
                for tok in re.findall(r"[\w\.\+#\-]+", text)
                if len(tok) >= 3 and tok.lower() not in STOPWORDS
            )
        joined = " ".join(strings)
        corpus = _clean_str(joined)
        return cls(
            known=known,
            corpus=corpus,
            tokens=set(re.findall(r"[\w\.\+#\-]+", corpus)),
            numbers={_to_float(n) for n in _NUMBER_RE.findall(_normalize_digits(joined))},
            metrics=_extract_metrics(joined),
            raw=tuple(strings),
            stack=tuple(stack),
        )

    def has_metric(self, metric: _Metric) -> bool:
        return any(m.canon == metric.canon for m in self.metrics) or metric.mantissa in self.numbers

    def has_canon(self, metric: _Metric) -> bool:
        return any(m.canon == metric.canon and m.noun == metric.noun for m in self.metrics)

    def supports(self, skill: str) -> bool:
        clean = _clean_str(skill)
        if not clean:
            return True
        if len(clean) <= 3:
            raw_skill = skill.strip()
            parts = {p for s in self.stack for p in re.split(r"[-./\s]+", s.lower()) if p}
            return (
                raw_skill.lower() in {k.lower() for k in self.known}
                or raw_skill.lower().lstrip(".") in parts
                or any(_short_term_in(raw_skill, t) for t in self.raw)
            )
        if re.search(rf"(?<!\w){re.escape(clean)}(?!\w)", self.corpus):
            return True
        if any(
            SequenceMatcher(None, clean, c).ratio() >= 0.85 for c in map(_clean_str, self.known) if c
        ):
            return True
        words = clean.split()
        for c in map(_clean_str, self.stack):
            if len(c) < 3 or not set(c.split()) <= set(words):
                continue
            extras = [w for w in words if w not in c.split()]
            if set(extras) <= _NAME_QUALIFIERS or "".join(w[0] for w in extras) == c.replace(" ", ""):
                return True
        return False


def _attribution_tokens(text: str) -> Set[str]:
    return {
        tok
        for tok in _clean_str(text).split()
        if len(tok) >= 3 and tok not in _ATTRIBUTION_STOPWORDS and not tok.isdigit()
    }


def _check_delegated_authorship_escalation(
    bullet: str, own_strings: Sequence[str]
) -> Optional[str]:
    """Detect upgrading delegated or subordinate participation into direct authorship."""
    if _DELEGATED_PARTY_RE.search(bullet) or _PARTICIPATION_RE.search(bullet):
        return None
    claims = list(_DIRECT_OWNERSHIP_CLAIM_RE.finditer(bullet))
    if not claims:
        return None

    source_statements = [
        stmt.strip()
        for raw in own_strings
        for stmt in re.split(r"[.!?;]+|\n+", raw)
        if stmt.strip()
    ]
    direct_sets: List[Set[str]] = []
    delegated_sets: List[Set[str]] = []
    for stmt in source_statements:
        has_delegated = bool(_DELEGATED_PARTY_RE.search(stmt) or _PARTICIPATION_RE.search(stmt))
        has_direct = bool(_DIRECT_LEADERSHIP_RE.search(stmt)) and not bool(
            _THIRD_PARTY_EXECUTION_RE.search(stmt)
        )
        if has_direct and not has_delegated:
            direct_sets.append(_attribution_tokens(stmt))
        elif has_delegated and (not has_direct or _THIRD_PARTY_EXECUTION_RE.search(stmt)):
            delegated_sets.append(_attribution_tokens(stmt))

    if not delegated_sets:
        return None

    for claim in claims:
        obj_tokens = _attribution_tokens(claim.group(2))
        if len(obj_tokens) < 2:
            continue
        if any(len(obj_tokens & direct) >= 2 for direct in direct_sets):
            continue
        if any(len(obj_tokens & delegated) >= 2 for delegated in delegated_sets):
            return claim.group(0).strip()
    return None
