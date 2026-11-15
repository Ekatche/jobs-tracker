import re
from typing import Any, Dict, List, Set

from .constants import _AMBIGUOUS_TERMS
from .metrics import _check_delegated_authorship_escalation, _ClaimContext, _extract_metrics
from .models import CVAudit, Finding
from .text_matching import (
    _clean_str,
    _collect_strings,
    _is_skill_supported,
    _post_label,
    _post_strings,
    _short_term_in,
    _stack_terms,
)


def _audit_experience(
    exp: Any,
    exp_idx: int,
    own_posts: List[Dict[str, Any]],
    other_posts: List[Dict[str, Any]],
    global_ctx: _ClaimContext,
    known_skills: Set[str],
    profile_corpus: str,
    profile_tokens: Set[str],
    audit: CVAudit,
) -> None:
    """Technologies, puces et métriques d'une expérience contre son poste du profil."""
    own_stack = tuple(
        s for p in own_posts for key in ("stack", "technologies") for s in _collect_strings(p.get(key))
    )
    own = _ClaimContext.from_strings(_post_strings(own_posts), own_stack)
    others = [
        (
            p,
            _ClaimContext.from_strings(
                _post_strings([p]),
                tuple(s for key in ("stack", "technologies") for s in _collect_strings(p.get(key))),
            ),
        )
        for p in other_posts
    ]
    where = f"'{exp.title}' chez '{exp.company}'"

    for tech_idx, tech in enumerate(exp.relevant_technologies):
        if own.supports(tech):
            continue
        source = next((_post_label(p) for p, ctx in others if ctx.supports(tech)), None)
        if source:
            audit.violations.append(
                Finding(
                    f"Technologie '{tech}' du poste {where} issue d'un autre poste du profil ({source}) : retire-la de ce poste.",
                    "relevant_technologies", exp_idx, item_index=tech_idx,
                )
            )
        elif _is_skill_supported(tech, known_skills, profile_corpus, profile_tokens):
            audit.unverifiable.append(
                Finding(
                    f"Technologie '{tech}' du poste {where} absente de ce poste, présente ailleurs dans le profil (compétences, projets, formation).",
                    "relevant_technologies", exp_idx, item_index=tech_idx,
                )
            )
        else:
            audit.violations.append(
                Finding(
                    f"Technologie '{tech}' du poste {where} absente du profil candidat vérifié.",
                    "relevant_technologies", exp_idx, item_index=tech_idx,
                )
            )

    other_terms = [(p, _stack_terms(p)) for p, _ in others]
    for bullet_idx, bullet in enumerate(exp.bullet_points):
        escalated = _check_delegated_authorship_escalation(bullet, own.raw)
        if escalated:
            audit.violations.append(
                Finding(
                    f"Puce {bullet_idx + 1} du poste {where} surévalue la responsabilité ('{escalated}') par rapport à une contribution ou prestation déléguée dans le profil.",
                    "bullet_points", exp_idx, item_index=bullet_idx,
                )
            )

        for metric in _extract_metrics(bullet):
            if metric.context and metric.context in global_ctx.corpus and not any(
                ctx.has_canon(metric) for _, ctx in others
            ):
                continue
            if own.has_metric(metric):
                continue
            source = next((_post_label(p) for p, ctx in others if ctx.has_canon(metric)), None)
            if source:
                audit.violations.append(
                    Finding(
                        f"Métrique '{metric.raw}' de la puce {bullet_idx + 1} du poste {where} d'un autre poste du profil ({source}) : ne transfère aucune métrique d'un poste à l'autre.",
                        "bullet_points", exp_idx, item_index=bullet_idx,
                    )
                )
            elif global_ctx.has_metric(metric):
                audit.unverifiable.append(
                    Finding(
                        f"Métrique '{metric.raw}' de la puce {bullet_idx + 1} du poste {where} absente de ce poste, présente ailleurs dans le profil.",
                        "bullet_points", exp_idx, item_index=bullet_idx,
                    )
                )
            else:
                audit.violations.append(
                    Finding(
                        f"Métrique '{metric.raw}' de la puce {bullet_idx + 1} du poste {where} inventée : absente du profil.",
                        "bullet_points", exp_idx, item_index=bullet_idx,
                    )
                )

        clean_bullet = _clean_str(bullet)
        for post, terms in other_terms:
            leaked: List[str] = []
            ambiguous: List[str] = []
            for t, raw in terms.items():
                if own.supports(raw):
                    continue
                hit = (
                    _short_term_in(raw, bullet)
                    if len(t) <= 3
                    else re.search(rf"(?<!\w){re.escape(t)}(?!\w)", clean_bullet)
                )
                if hit:
                    (ambiguous if t in _AMBIGUOUS_TERMS else leaked).append(raw)
            if leaked:
                audit.violations.append(
                    Finding(
                        f"Puce {bullet_idx + 1} du poste {where} cite {', '.join(sorted(leaked))}, technologie(s) d'un autre poste du profil ({_post_label(post)}) : ne transfère aucune technologie d'un poste à l'autre.",
                        "bullet_points", exp_idx, item_index=bullet_idx,
                    )
                )
            if ambiguous:
                audit.unverifiable.append(
                    Finding(
                        f"Puce {bullet_idx + 1} du poste {where} mentionne {', '.join(sorted(ambiguous))}, terme courant déclaré dans un autre poste.",
                        "bullet_points", exp_idx, item_index=bullet_idx,
                    )
                )
