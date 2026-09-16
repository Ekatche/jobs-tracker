#!/usr/bin/env python3
"""
CRAWL_LLM_MODEL bake-off script.

Usage:
    cd backend
    .venv/bin/python scripts/crawl_bakeoff.py \
        --url "https://exemple.fr/offre-1" \
        --url "https://exemple.fr/offre-2" \
        --out ../docs/micro/20260916-crawl-llm-bakeoff/

Contexte : `get_shared_crawl_config()` (job_crawler/crawler1.py) fixe
CRAWL_LLM_MODEL sur openai/gpt-4o-mini par défaut, avec ce commentaire :

    "gpt-4o-mini reste le défaut ici : gpt-5-nano renvoie des champs nuls
    sur l'extraction structurée (offres rejetées par le contrôle d'ancrage)."

Ce script vérifie empiriquement cette affirmation (et teste des alternatives
modernes) au lieu de la prendre pour acquise indéfiniment, et sert de
protocole répétable la prochaine fois que CRAWL_LLM_MODEL doit être reconsidéré.

Contrairement à letter_bakeoff.py (rédaction, jugement subjectif → blind
ranking humain), l'extraction d'offre est une tâche factuelle : le
contrôle d'ancrage `_offer_grounded_in_page` donne un verdict pass/fail
objectif. Pas besoin d'anonymisation ni de classement à l'aveugle ici.

Ce script ne modifie JAMAIS crawler1.py, docker-compose.yml ni aucune
config source — le choix final de CRAWL_LLM_MODEL reste manuel, après
lecture du rapport.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap — allow running from backend/ without installing the package.
# ---------------------------------------------------------------------------
_BACKEND = Path(__file__).parent.parent.resolve()
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

try:
    from dotenv import load_dotenv  # type: ignore

    _ENV_FILE = _BACKEND.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE, override=False)
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Internal imports (after path bootstrap)
# ---------------------------------------------------------------------------
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, LLMConfig  # type: ignore
from crawl4ai.async_configs import CacheMode  # type: ignore
from crawl4ai.extraction_strategy import (  # type: ignore
    LLMExtractionStrategy,
    perform_completion_with_backoff,
)
from crawl4ai.content_filter_strategy import PruningContentFilter  # type: ignore
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator  # type: ignore
from crawl4ai.utils import extract_xml_data  # type: ignore
import re


class RobustLLMExtractionStrategy(LLMExtractionStrategy):
    """Contourne un bug de crawl4ai (vérifié 2026-09-16) : les modèles Gemini ne
    respectent pas la balise <blocks> attendue par PROMPT_EXTRACT_SCHEMA_WITH_INSTRUCTION
    (ils répondent en ```json``` nu). extract_xml_data renvoie alors une chaîne vide,
    json.loads('') lève une exception, et le bloc `except` de crawl4ai retente
    `response.choices[0].message.content` alors que `response` a déjà été réécrasé
    par une string plus haut dans le même bloc `try` -> crash silencieux
    ('str' object has no attribute 'choices'), avalé par extract() et transformé
    en bloc d'erreur (poste/entreprise null côté appelant). Cette sous-classe
    ajoute un repli : extraire le JSON d'un fence ```json``` ou du texte brut
    si <blocks> est absent, sans jamais réutiliser `response` après réassignation."""

    def extract(self, url: str, ix: int, html: str):
        if self.verbose:
            print(f"[LOG] Call LLM for {url} - block index: {ix}")

        variable_values = {"URL": url, "HTML": html}
        prompt_with_variables = None
        from crawl4ai.prompts import (
            PROMPT_EXTRACT_BLOCKS,
            PROMPT_EXTRACT_BLOCKS_WITH_INSTRUCTION,
            PROMPT_EXTRACT_SCHEMA_WITH_INSTRUCTION,
            PROMPT_EXTRACT_INFERRED_SCHEMA,
        )
        from crawl4ai.utils import escape_json_string, sanitize_html

        variable_values = {"URL": url, "HTML": escape_json_string(sanitize_html(html))}
        prompt_with_variables = PROMPT_EXTRACT_BLOCKS
        if self.instruction:
            variable_values["REQUEST"] = self.instruction
            prompt_with_variables = PROMPT_EXTRACT_BLOCKS_WITH_INSTRUCTION
        if self.extract_type == "schema" and self.schema:
            variable_values["SCHEMA"] = json.dumps(self.schema, indent=2)
            prompt_with_variables = PROMPT_EXTRACT_SCHEMA_WITH_INSTRUCTION
        if self.extract_type == "schema" and not self.schema:
            prompt_with_variables = PROMPT_EXTRACT_INFERRED_SCHEMA
        for variable in variable_values:
            prompt_with_variables = prompt_with_variables.replace(
                "{" + variable + "}", variable_values[variable]
            )

        try:
            response = perform_completion_with_backoff(
                self.llm_config.provider,
                prompt_with_variables,
                self.llm_config.api_token,
                base_url=self.llm_config.base_url,
                json_response=self.force_json_response,
                extra_args=self.extra_args,
            )
            usage = response.usage
            self.total_usage.completion_tokens += usage.completion_tokens
            self.total_usage.prompt_tokens += usage.prompt_tokens
            self.total_usage.total_tokens += usage.total_tokens

            raw_content = response.choices[0].message.content

            blocks_str = extract_xml_data(["blocks"], raw_content)["blocks"]
            if not blocks_str:
                fence_match = re.search(r"```(?:json)?\s*(.*?)```", raw_content, re.DOTALL)
                blocks_str = fence_match.group(1).strip() if fence_match else raw_content.strip()

            blocks = json.loads(blocks_str)
            if isinstance(blocks, dict):
                blocks = [blocks]
            for block in blocks:
                block["error"] = False
            if self.verbose:
                print("[LOG] Extracted", len(blocks), "blocks from URL:", url, "block index:", ix)
            return blocks
        except Exception as e:
            if self.verbose:
                print(f"[LOG] Error in LLM extraction: {e}")
            return [{"index": ix, "error": True, "tags": ["error"], "content": str(e)}]

from job_crawler.crawler1 import (  # type: ignore
    JobOffer,
    get_shared_browser_config,
    _get_page_text,
    _is_dead_or_expired,
    _is_empty_crawl,
    _offer_grounded_in_page,
)
from app.services.normalization import (  # type: ignore
    extract_company_from_url,
    optimize_crawl_url,
    restore_canonical_job_url,
)

# ---------------------------------------------------------------------------
# Candidats — incumbent + régression documentée (à re-vérifier plutôt qu'à
# croire sur parole) + alternatives modernes déjà utilisées ailleurs dans l'app.
# ---------------------------------------------------------------------------
CANDIDATE_MODELS = [
    "openai/gpt-4o-mini",              # incumbent actuel de CRAWL_LLM_MODEL
    "openai/gpt-5-nano",                # régression documentée dans crawler1.py — infirmée (bug extra_args, cf. run 2026-09-16)
    "openai/gpt-5.6-luna",               # modèle OpenAI moderne (déjà DEFAULT_MODELS["offer_analyst"])
    "gemini/gemini-3.8-flash",          # meilleur flash Gemini actif — à égalité de qualité avec gpt-5.6-luna une fois le bug <blocks> corrigé (run 2026-09-16)
    "gemini/gemini-3.1-pro-preview",    # tier "Pro" raisonnement, successeur actif de gemini-3-pro-preview (shutdown 9/3/2026)
    "gemini/gemini-3.7-flash",           # génération flash précédente, demandé pour comparaison
    "gemini/gemini-3.6-flash",           # génération flash encore antérieure, demandé pour comparaison
    "gemini/gemini-3.5-flash-lite",      # tier flash-lite (moins cher), demandé pour comparaison
]

# $ / 1M tokens (input, output) — recopié de app/services/usage_tracker.py au
# 2026-09-16 ; à resynchroniser manuellement si la table de pricing bouge.
COST_PER_MILLION: dict[str, tuple[float, float]] = {
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-5-nano": (0.50, 1.50),
    "openai/gpt-5.6-luna": (2.00, 6.00),
    "gemini/gemini-3.8-flash": (0.75, 3.75),
    # tarif Standard <=200k tokens, vérifié sur ai.google.dev/gemini-api/docs/pricing
    # le 2026-09-16 ; output inclut les tokens de raisonnement ("thinking").
    "gemini/gemini-3.1-pro-preview": (2.00, 12.00),
    # pricing des 3 lignes suivantes lu depuis litellm.model_cost le 2026-09-16
    # (pas revérifié sur ai.google.dev/gemini-api/docs/pricing)
    "gemini/gemini-3.7-flash": (0.75, 3.75),
    "gemini/gemini-3.6-flash": (0.75, 3.75),
    "gemini/gemini-3.5-flash-lite": (0.30, 2.50),
}


def _api_key_for(model: str) -> str | None:
    provider = model.split("/", 1)[0]
    return {
        "openai": os.getenv("OPENAI_API_KEY"),
        "gemini": os.getenv("GEMINI_API_KEY"),
        "mistral": os.getenv("MISTRAL_API_KEY"),
    }.get(provider)


def _extraction_instruction() -> str:
    """Copie verbatim de l'instruction de get_shared_crawl_config, pour comparer
    les modèles sur EXACTEMENT le même prompt que la production."""
    return f"""
    Extrait toutes les offres d'emploi RÉELLES et ACTIVES de cette page web.

    RÈGLE CRITIQUE D'EXPIRATION :
    - Si la page indique que l'offre n'est plus disponible (ex: "L'offre que vous souhaitez afficher n'est plus disponible", "Offre expirée", "Offre introuvable", page d'erreur 404, page de connexion), NE RETOURNE AUCUNE OFFRE (tableau vide []).

    Pour chaque offre active, identifie et extrait précisément :
    - poste : le titre exact du poste/métier (ne jamais mettre "Non spécifié" si une offre est présente)
    - entreprise : le nom réel de l'entreprise ou du cabinet employeur (cherche attentivement dans l'en-tête, le titre, le texte d'introduction ou la signature)
    - description : une synthèse structurée, riche et directement exploitable rédigée en français avec des puces Markdown, organisée en sections claires :
      • Contexte & Enjeux : 1 à 2 phrases sur l'entreprise, l'équipe et la mission générale.
      • Missions principales : 3 à 5 puces concrètes décrivant les responsabilités quotidiennes et les livrables attendus.
      • Profil recherché : niveau d'expérience requis, formation et critères indispensables.
      • Stack & Outils : technologies, frameworks, cloud et méthodologies utilisés.
      • Avantages & Modalités : politique de télétravail, salaire ou package si mentionnés (sinon omettre ce point).
      Ne reste jamais vague ou générique : extrais les détails techniques et fonctionnels réels présents dans le texte.
    - localisation : ville, département ou région du poste
    - date : date de publication au format ISO (YYYY-MM-DD), basée sur la date d'aujourd'hui {datetime.now().strftime('%Y-%m-%d')}
    - type_contrat : type de contrat (CDI, CDD, Alternance, Stage, Freelance, ou "Non spécifié")
    - salaire : rémunération ou fourchette salariale indiquée (ou "Non spécifié")
    - mode_travail : Télétravail total, Hybride, Présentiel (ou "Non spécifié")
    - competences_cles : liste des technologies, outils, langages ou compétences clés exigées
    - url : lien direct vers l'offre (si disponible)

    Ignore les menus, bannières, pied de page et publicités.
    Retourne une liste d'offres au format JSON.
    """


def _build_crawl_config(model: str, api_key: str) -> CrawlerRunConfig:
    """Reconstruit une CrawlerRunConfig pour UN modèle donné.

    Mirroir volontaire de get_shared_crawl_config() plutôt qu'un appel direct :
    cette dernière est un singleton mis en cache par api_key (pas par modèle),
    et son routage Gemini est câblé en dur sur "gemini/gemini-flash-latest"
    (alias flottant, indépendant de CRAWL_LLM_MODEL) — inadapté à un bake-off
    qui doit pouvoir tester n'importe quel candidat, y compris Gemini, à l'identique.
    """
    job_content_filter = PruningContentFilter(threshold=0.45, threshold_type="fixed", min_word_threshold=5)
    md_generator = DefaultMarkdownGenerator(
        content_filter=job_content_filter,
        options={"ignore_links": False, "strip_whitespace": True},
    )

    if "gpt-5" in model:
        # `reasoning_effort` et `max_tokens` sont listés comme "supportés" par le
        # mapping openai de cette version de litellm, mais l'API OpenAI les rejette
        # tous les deux pour gpt-5-nano/gpt-5.6-luna en pratique (vérifié 2026-09-16,
        # litellm.UnsupportedParamsError puis BadRequestError). drop_params=True fait
        # tomber silencieusement reasoning_effort (donc raisonnement par défaut, pas
        # "minimal" comme espéré) ; max_completion_tokens remplace max_tokens. Budget
        # relevé à 6000 pour laisser de la marge après les tokens de raisonnement
        # (vérifié : ~130 tokens de raisonnement rien que pour "dis OK").
        extra_args = {"temperature": 1, "max_completion_tokens": 6000, "drop_params": True}
    else:
        extra_args = {"temperature": 0.1, "max_tokens": 4000}

    extraction_strategy = RobustLLMExtractionStrategy(
        llm_config=LLMConfig(provider=model, api_token=api_key),
        schema=json.dumps(JobOffer.model_json_schema()),
        extraction_type="schema",
        instruction=_extraction_instruction(),
        extra_args=extra_args,
        apply_chunking=True,
        input_format="fit_markdown",
        verbose=False,
    )

    scroll_js = """
    const cookieSelectors = [
        '#tarteaucitronPersonalize2', '#axeptio_btn_acceptAll',
        '#onetrust-accept-btn-handler', 'button[id*="accept"]',
        'button[class*="cookie-accept"]', 'button[class*="consent-accept"]'
    ];
    for (const sel of cookieSelectors) {
        const btn = document.querySelector(sel);
        if (btn) { try { btn.click(); } catch(e){} break; }
    }
    window.scrollTo(0, document.body.scrollHeight / 2);
    await new Promise(r => setTimeout(r, 600));
    window.scrollTo(0, document.body.scrollHeight);
    await new Promise(r => setTimeout(r, 600));
    """

    return CrawlerRunConfig(
        word_count_threshold=30,
        cache_mode=CacheMode.BYPASS,
        screenshot=False,
        verbose=False,
        ignore_body_visibility=True,
        extraction_strategy=extraction_strategy,
        markdown_generator=md_generator,
        js_code=scroll_js,
        wait_until="networkidle",
        page_timeout=45000,
        delay_before_return_html=2.5,
        magic=True,
        simulate_user=False,
        override_navigator=True,
        remove_overlay_elements=True,
    )


async def run_candidate(model: str, urls: list[str]) -> dict[str, Any]:
    """Crawl chaque URL une seule fois avec `model` (pas de retry : on isole la
    variable testée — qualité d'extraction du LLM — de la flakiness réseau,
    qui affecte tous les candidats de façon comparable dans la même run)."""
    api_key = _api_key_for(model)
    if not api_key:
        return {"model": model, "skipped": True, "reason": f"clé API manquante pour {model.split('/')[0]}"}

    browser_config = get_shared_browser_config()
    crawl_config = _build_crawl_config(model, api_key)

    url_mapping: dict[str, str] = {}
    crawl_urls: list[str] = []
    for u in urls:
        opt = optimize_crawl_url(u)
        crawl_urls.append(opt)
        url_mapping[opt] = u
        url_mapping[u] = u

    def _resolve(u: str) -> str:
        if u in url_mapping:
            return url_mapping[u]
        stripped = u.rstrip("/")
        return url_mapping.get(stripped, restore_canonical_job_url(u))

    per_url: list[dict[str, Any]] = []
    t0 = time.monotonic()

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(urls=crawl_urls, config=crawl_config)

        for result in results:
            orig_url = _resolve(result.url)
            page_text = _get_page_text(result)

            if _is_dead_or_expired(result, page_text):
                per_url.append({"url": orig_url, "status": "dead_or_expired"})
                continue

            if _is_empty_crawl(result, page_text):
                per_url.append({
                    "url": orig_url,
                    "status": "empty_crawl",
                    "detail": result.error_message or f"{len(page_text.strip())} chars",
                })
                continue

            if not result.extracted_content:
                per_url.append({"url": orig_url, "status": "no_extraction"})
                continue

            try:
                offers = json.loads(result.extracted_content)
                offers = [offers] if isinstance(offers, dict) else (offers if isinstance(offers, list) else [])
            except json.JSONDecodeError as e:
                per_url.append({"url": orig_url, "status": "json_error", "detail": str(e)})
                continue

            for offer in offers:
                ent = (offer.get("entreprise") or "").strip().lower()
                if ent in ("", "non spécifié", "non disponible", "inconnu", "none", "null", "undefined"):
                    fallback = extract_company_from_url(orig_url)
                    if fallback:
                        offer["entreprise"] = fallback

            grounded = [o for o in offers if _offer_grounded_in_page(o, page_text, orig_url)]

            if offers and not grounded:
                # Signature exacte de la régression documentée : extraction "réussie"
                # mais champs non retrouvables dans la page réellement crawlée.
                per_url.append({
                    "url": orig_url,
                    "status": "grounding_rejected",
                    "rejected_offer": {"poste": offers[0].get("poste"), "entreprise": offers[0].get("entreprise")},
                })
            elif not offers:
                per_url.append({"url": orig_url, "status": "empty_extraction"})
            else:
                per_url.append({"url": orig_url, "status": "success", "offers_count": len(grounded)})

    elapsed = round(time.monotonic() - t0, 2)
    usage = crawl_config.extraction_strategy.total_usage
    in_price, out_price = COST_PER_MILLION.get(model, (0.0, 0.0))
    cost = (usage.prompt_tokens / 1_000_000) * in_price + (usage.completion_tokens / 1_000_000) * out_price

    status_counts: dict[str, int] = {}
    for r in per_url:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    return {
        "model": model,
        "skipped": False,
        "duration_s": elapsed,
        "status_counts": status_counts,
        "success_rate": round(status_counts.get("success", 0) / len(urls), 2) if urls else 0.0,
        "grounding_rejected_rate": round(status_counts.get("grounding_rejected", 0) / len(urls), 2) if urls else 0.0,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
        },
        "estimated_cost_usd": round(cost, 6),
        "per_url": per_url,
    }


async def run_bakeoff(urls: list[str]) -> list[dict[str, Any]]:
    results = []
    for model in CANDIDATE_MODELS:
        print(f"\n=== {model} ===")
        r = await run_candidate(model, urls)
        if r.get("skipped"):
            print(f"  SKIP — {r['reason']}")
        else:
            print(
                f"  succès {r['success_rate']*100:.0f}% | rejets ancrage {r['grounding_rejected_rate']*100:.0f}%"
                f" | {r['usage']['total_tokens']} tokens | ~${r['estimated_cost_usd']:.4f} | {r['duration_s']}s"
            )
        results.append(r)
        # Reset entre candidats : chaque LLMExtractionStrategy est locale à sa
        # propre CrawlerRunConfig ici, donc pas de cache partagé à invalider —
        # contrairement à get_shared_crawl_config() en production.
    return results


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Bake-off CRAWL_LLM_MODEL")
    p.add_argument("--url", required=True, action="append", dest="urls",
                    metavar="URL", help="URL d'offre réelle et actuellement en ligne (répétable, ≥3 recommandé)")
    p.add_argument("--out", required=True, help="Répertoire de sortie")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if len(args.urls) < 3:
        print(
            "ATTENTION : moins de 3 URLs — le taux de succès par candidat sera peu significatif.",
            file=sys.stderr,
        )

    results = asyncio.run(run_bakeoff(args.urls))

    report_path = out_dir / "crawl-bakeoff-report.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓ Rapport détaillé  → {report_path}")

    summary_lines = [
        "# Bake-off CRAWL_LLM_MODEL — résumé",
        "",
        f"URLs testées : {len(args.urls)}",
        "",
        "| Modèle | Succès | Rejets ancrage | Autres échecs | Tokens | Coût USD | Durée (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        if r.get("skipped"):
            summary_lines.append(f"| {r['model']} | SKIP: {r['reason']} | | | | | |")
            continue
        sc = r["status_counts"]
        other_fails = sum(v for k, v in sc.items() if k not in ("success", "grounding_rejected"))
        summary_lines.append(
            f"| {r['model']} | {sc.get('success', 0)}/{len(args.urls)}"
            f" | {sc.get('grounding_rejected', 0)}"
            f" | {other_fails}"
            f" | {r['usage']['total_tokens']}"
            f" | {r['estimated_cost_usd']:.4f}"
            f" | {r['duration_s']} |"
        )

    summary_lines += [
        "",
        "## Comment lire ce tableau",
        "",
        "- **Rejets ancrage** = extraction \"réussie\" côté LLM mais champs non retrouvés dans la page réelle "
        "(`_offer_grounded_in_page`) — c'est la signature exacte de la régression documentée sur gpt-5-nano.",
        "- **Autres échecs** = dead_link / empty_crawl / no_extraction / json_error — généralement des soucis "
        "réseau ou de rendu de page, pas de qualité LLM (comparer avec les autres candidats sur les mêmes URLs).",
        "",
        "## Prochaines étapes",
        "",
        "1. Vérifier `crawl-bakeoff-report.json` → `per_url` pour chaque rejet d'ancrage : le champ "
        "`rejected_offer` doit montrer un poste/entreprise plausible mais absent de la page réelle.",
        "2. Choisir le candidat avec le meilleur ratio succès/coût qui n'a AUCUN rejet d'ancrage sur ce jeu d'URLs.",
        "3. Mettre à jour manuellement `CRAWL_LLM_MODEL` dans `docker-compose.yml` (2 occurrences) — "
        "ce script ne le fait jamais automatiquement.",
        "4. Mettre à jour le commentaire au-dessus de la ligne `openai_model = os.getenv(\"CRAWL_LLM_MODEL\", ...)` "
        "dans `crawler1.py` pour refléter le nouveau choix et sa justification mesurée.",
        "5. Si Gemini est retenu, corriger aussi l'alias flottant `gemini/gemini-flash-latest` "
        "(branche PREFER_GEMINI de `get_shared_crawl_config`) vers un modèle Gemini pinné.",
        "",
        f"> Candidats évalués : {', '.join(CANDIDATE_MODELS)}",
    ]

    summary_path = out_dir / "crawl-bakeoff-summary.md"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    print(f"✓ Résumé lisible    → {summary_path}")


if __name__ == "__main__":
    main()
