"""Règles pures de la banque d'histoires STAR+R : aucun accès base de données ici.

Le rattachement d'une histoire à une expérience du profil se fait par
instantané (`StoryExperience`), car `CandidateExperience` n'a pas d'identifiant
stable (voir docs/superpowers/specs/2026-10-24-banque-histoires-star-design.md,
section Données).
"""

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from app.models import BankStory, StoryExperience
from app.services.normalization import normalize_company, normalize_position


def guess_experience(situation: str, experiences: List[Dict[str, Any]]) -> Optional[StoryExperience]:
    """Devine l'expérience du profil racontée dans `situation`.

    Une entreprise du profil est "trouvée" si son nom apparaît comme mot entier
    dans la situation (comparaison insensible à la casse). On ne retient le
    rattachement que si une seule entreprise distincte (par `normalize_company`)
    est trouvée ; sinon le rattachement est ambigu ou absent.
    """
    situation_cf = situation.casefold()
    matched_normalized: set[str] = set()
    for exp in experiences:
        company = exp.get("company")
        if not company:
            continue
        pattern = r"\b" + re.escape(company.casefold()) + r"\b"
        if re.search(pattern, situation_cf):
            matched_normalized.add(normalize_company(company))

    if len(matched_normalized) != 1:
        return None

    target = next(iter(matched_normalized))
    first_exp = next(exp for exp in experiences if normalize_company(exp.get("company")) == target)
    return StoryExperience(
        company=first_exp.get("company"),
        role=first_exp.get("role"),
        start=first_exp.get("start"),
    )


def match_profile_experience(
    experience: Optional[StoryExperience], experiences: List[Dict[str, Any]]
) -> Optional[int]:
    """Retrouve l'index, dans `experiences`, de l'expérience du profil correspondant à `experience`.

    Égalité sur l'entreprise normalisée ; si un rôle est renseigné sur
    `experience`, il doit aussi correspondre (normalisé). Sans rôle,
    l'entreprise doit désigner une unique expérience du profil pour lever
    l'ambiguïté.
    """
    if experience is None:
        return None

    target_company = normalize_company(experience.company)

    if experience.role:
        target_role = normalize_position(experience.role)
        for idx, exp in enumerate(experiences):
            if (
                normalize_company(exp.get("company")) == target_company
                and normalize_position(exp.get("role")) == target_role
            ):
                return idx
        return None

    matches = [idx for idx, exp in enumerate(experiences) if normalize_company(exp.get("company")) == target_company]
    if len(matches) == 1:
        return matches[0]
    return None


def experience_label(experience: StoryExperience) -> str:
    """Libellé d'affichage d'une expérience : "{role} · {company}", ou `company` seul sans rôle."""
    if experience.role:
        return f"{experience.role} · {experience.company}"
    return experience.company


_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def _mask_invented_numbers(text: str, sources: str) -> str:
    """Remplace par `[à chiffrer]` tout nombre absent des sources (réponse du candidat, histoire liée)."""
    known = {n.replace(",", ".") for n in _NUMBER_RE.findall(sources)}
    return _NUMBER_RE.sub(
        lambda m: m.group(0) if m.group(0).replace(",", ".") in known else "[à chiffrer]",
        text,
    )


def _story_facts_sources(story: BankStory) -> str:
    return "\n".join([story.situation, story.task, story.action, story.result, story.reflection, story.title])


_THEME_PREFIX_RE = re.compile(r"^\[[^\]]*\]\s*")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_RESULT_NUMBER_RE = re.compile(r"\d{2,}")


def _title_words(title: str) -> set:
    """Mots de 3 caractères ou plus du titre, préfixe "[Thème] " retiré, casefold, accents retirés."""
    stripped = _THEME_PREFIX_RE.sub("", title)
    folded = unicodedata.normalize("NFKD", stripped).encode("ascii", "ignore").decode().casefold()
    words = _NON_ALNUM_RE.split(folded)
    return {w for w in words if len(w) >= 3}


def _title_jaccard(a_title: str, b_title: str) -> float:
    words_a, words_b = _title_words(a_title), _title_words(b_title)
    union = words_a | words_b
    if not union:
        return 0.0
    return len(words_a & words_b) / len(union)


def _shares_result_number(a_result: str, b_result: str) -> bool:
    numbers_a = set(_RESULT_NUMBER_RE.findall(a_result))
    numbers_b = set(_RESULT_NUMBER_RE.findall(b_result))
    return bool(numbers_a & numbers_b)


def _same_company_group(a: BankStory, b: BankStory) -> bool:
    """Même groupe : les deux sans expérience, ou `normalize_company` égal."""
    if a.experience is None and b.experience is None:
        return True
    company_a = a.experience.company if a.experience else None
    company_b = b.experience.company if b.experience else None
    return normalize_company(company_a) == normalize_company(company_b)


def _excluded_as_not_duplicate(a: BankStory, b: BankStory) -> bool:
    return b.id in a.not_duplicate_of or a.id in b.not_duplicate_of


def find_duplicate_pairs(stories: List[BankStory]) -> List[Tuple[str, str]]:
    """Paires d'histoires probablement doublons, dans l'ordre d'entrée (`a` avant `b`).

    Même groupe (les deux sans expérience, ou entreprises normalisées égales) et
    au moins un signal de ressemblance (titres proches ou un nombre de résultat
    partagé). Exclut les paires explicitement marquées « histoires différentes »
    via `not_duplicate_of`.
    """
    pairs: List[Tuple[str, str]] = []
    for i, a in enumerate(stories):
        for b in stories[i + 1 :]:
            if _excluded_as_not_duplicate(a, b):
                continue
            if not _same_company_group(a, b):
                continue
            if _title_jaccard(a.title, b.title) >= 0.5 or _shares_result_number(a.result, b.result):
                pairs.append((a.id, b.id))
    return pairs
