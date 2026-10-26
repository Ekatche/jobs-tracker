"""Secteur d'activité et taille d'entreprise des offres (taxonomie du Lot 1 matching).

Le secteur et la taille sont déduits, du moins cher au plus cher, des données natives du job board
(`raw_data`), du cache `company_profiles`, de l'API publique Recherche d'entreprises pour la taille,
puis d'un repli LLM.

Collection `company_profiles`, un document par entreprise (index unique sur `company_name_normalized`) :
    company_name_normalized: str       # normalize_company(entreprise)
    company_name_raw: str
    sector: Optional[str]              # clé de SECTORS, dont "other"
    sector_source: Optional[str]       # "native_source" | "llm_inferred" | "manual"
    company_size: Optional[str]        # clé de COMPANY_SIZES
    size_source: Optional[str]         # "native_source" | "api_entreprises" | "llm_inferred" | "manual"
    siren: Optional[str]               # quand l'API Recherche d'entreprises a validé la correspondance
    updated_at: datetime
Une source posée avec une valeur nulle signifie « déjà tenté » : la valeur n'est pas redemandée.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from time import monotonic
from typing import Optional

import httpx
from litellm import acompletion

from app.services.normalization import _fold_ascii, company_match_strength, normalize_company

logger = logging.getLogger(__name__)

SECTORS: tuple[str, ...] = (
    "tech_it",
    "finance_insurance",
    "healthcare_pharma",
    "consulting_services",
    "retail_ecommerce",
    "industry_aerospace",
    "energy_environment",
    "media_communication",
    "public_education",
    "construction_realestate",
    "logistics_transport",
    "agri_food",
    "other",
)
# "other" sort de l'enrichissement mais n'est jamais proposé comme préférence
PREFERENCE_SECTORS: tuple[str, ...] = SECTORS[:-1]
COMPANY_SIZES: tuple[str, ...] = ("startup_tpe", "pme", "eti", "grand_groupe")

# Règles ordonnées : la première qui trouve un mot-clé (en début de mot) l'emporte.
# Santé et finance passent avant l'informatique (« Fintech », « Health tech ») ; l'informatique
# générique ne tranche pas entre éditeur (tech_it) et ESN (consulting_services) : le LLM décide.
_SECTOR_RULES: tuple[tuple[Optional[str], tuple[str, ...]], ...] = (
    ("healthcare_pharma", ("pharma", "biotech", "sante", "health", "hopital", "hospitalier", "medic")),
    ("finance_insurance", ("banque", "bank", "assurance", "insurance", "financ", "fintech")),
    (None, ("informatique", "information technology")),
    ("tech_it", ("telecom", "logiciel", "software", "internet", "tech", "saas")),
    ("consulting_services", ("conseil", "consulting", "audit", "services aux entreprises", "business services")),
    # Avant la distribution (« Production et distribution d'énergie ») et l'alimentaire (« Restaurants & Food Service »)
    ("energy_environment", ("energ", "environnement", "environment", "utilities", "cleantech")),
    ("retail_ecommerce", ("retail", "commerce", "ecommerce", "distribution", "luxe")),
    (
        "other",
        ("tourisme", "hotel", "hospitality", "restaura", "food service", "food and beverage service", "services aux personnes"),
    ),
    ("agri_food", ("agro", "agricult", "aliment", "food")),
    ("industry_aerospace", ("aero", "defense", "defence", "automobile", "automotive", "industri")),
    (
        "media_communication",
        (
            "media",
            "communication",
            "publicite",
            "advertising",
            "edition",
            "publishing",
            "divertissement",
            "entertainment",
            "jeux video",
            "video game",
        ),
    ),
    (
        "public_education",
        ("enseignement", "education", "formation", "recherche", "research", "public", "administration", "government"),
    ),
    ("construction_realestate", ("immobilier", "real estate", "construction", "btp", "batiment", "urbanisme")),
    ("logistics_transport", ("transport", "logisti", "supply chain")),
)

# Libellés Indeed (virgules retirées). Les tranches à cheval sur un seuil (11-50, 201-500) restent inconnues.
_INDEED_SIZES = {
    "1 to 10": "startup_tpe",
    "51 to 200": "pme",
    "501 to 1000": "eti",
    "1001 to 5000": "eti",
    "5001 to 10000": "grand_groupe",
    "10000+": "grand_groupe",
}


def map_sector_label(label: Optional[str]) -> Optional[str]:
    """Libellé de secteur d'un job board -> clé de la taxonomie, ou None si rien ne correspond."""
    if not label:
        return None
    folded = _fold_ascii(label)
    for sector, keywords in _SECTOR_RULES:
        if any(re.search(r"\b" + re.escape(kw), folded) for kw in keywords):
            return sector
    return None


def map_indeed_size(label: Optional[str]) -> Optional[str]:
    """Libellé d'effectif Indeed (« 1,001 to 5,000 ») -> taille de la taxonomie."""
    if not label:
        return None
    return _INDEED_SIZES.get(label.replace(",", "").strip())


def extract_native_attributes(raw_data: Optional[dict]) -> dict:
    """Secteur et taille lus dans les enregistrements natifs des job boards (jobspy HelloWork et Indeed).

    France Travail (`secteurActiviteLibelle`, `trancheEffectifEtab`) est absent : la source a été retirée
    le 2026-10-25 et son format réel n'a jamais été observé.
    `sector_label` garde le libellé brut, transmis au LLM quand il ne se mappe pas.
    """
    sector_label = None
    size_label = None
    for record in (raw_data or {}).values():
        if not isinstance(record, dict):
            continue
        if not sector_label and record.get("company_industry"):
            sector_label = str(record["company_industry"])
        if not size_label and record.get("company_num_employees"):
            size_label = str(record["company_num_employees"])
    return {
        "sector": map_sector_label(sector_label),
        "company_size": map_indeed_size(size_label),
        "sector_label": sector_label,
    }


RECHERCHE_ENTREPRISES_URL = "https://recherche-entreprises.api.gouv.fr/search"
API_USER_AGENT = "job-tracker/1.0 (enrichissement taille entreprise)"
API_TIMEOUT_SECONDS = 10
# Codes INSEE de tranche d'effectif sous 20 salariés ("NN" = non renseigné)
TPE_TRANCHES = {"00", "01", "02", "03", "11"}
_CATEGORY_SIZES = {"GE": "grand_groupe", "ETI": "eti"}


def _retry_delay(response: httpx.Response) -> float:
    """Attente avant la nouvelle tentative après un 429 : Retry-After plafonné à 5 s, 1 s s'il est illisible."""
    try:
        return min(float(response.headers.get("Retry-After", "")), 5.0)
    except ValueError:
        return 1.0


def _size_from_result(result: dict) -> Optional[str]:
    """La catégorie INSEE donne la taille du groupe ; la tranche du siège ne sert qu'à couper les PME en deux."""
    category = result.get("categorie_entreprise")
    if category in _CATEGORY_SIZES:
        return _CATEGORY_SIZES[category]
    if category == "PME":
        tranche = result.get("tranche_effectif_salarie")
        if tranche in TPE_TRANCHES:
            return "startup_tpe"
        if tranche and tranche.isdigit():
            return "pme"
    return None


async def _search_company(company: str, client: httpx.AsyncClient) -> dict:
    params = {"q": company, "per_page": 1, "minimal": "true"}
    headers = {"User-Agent": API_USER_AGENT}
    response = await client.get(RECHERCHE_ENTREPRISES_URL, params=params, headers=headers)
    if response.status_code == 429:
        # Limite documentée : 7 requêtes/s par IP
        await asyncio.sleep(_retry_delay(response))
        response = await client.get(RECHERCHE_ENTREPRISES_URL, params=params, headers=headers)
    response.raise_for_status()
    return response.json()


async def lookup_company_size(
    company: str, client: Optional[httpx.AsyncClient] = None
) -> tuple[Optional[str], Optional[str]]:
    """Taille de l'entreprise et SIREN via recherche-entreprises.api.gouv.fr, ou (None, None).

    Seul le premier résultat est lu, et il n'est retenu que si son nom (ou son sigle) correspond
    fortement à celui de l'offre : « Orange » ne doit pas hériter de la taille d'« Orange Bank ».
    Le code NAF n'est pas utilisé : il décrit l'unité légale (un siège social), pas le groupe.
    """
    try:
        if client is None:
            async with httpx.AsyncClient(timeout=API_TIMEOUT_SECONDS) as own_client:
                payload = await _search_company(company, own_client)
        else:
            payload = await _search_company(company, client)
        first = (payload.get("results") or [None])[0]
        if not first:
            return None, None
        name = re.sub(r"\s*\(.*\)\s*$", "", first.get("nom_complet") or "")
        if "strong" not in (company_match_strength(name, company), company_match_strength(first.get("sigle"), company)):
            return None, None
        size = _size_from_result(first)
        return (size, first.get("siren")) if size else (None, None)
    except Exception as e:
        logger.warning(f"⚠️ Recherche d'entreprises indisponible pour '{company}': {e}")
        return None, None


_SECTOR_LABELS = {
    "tech_it": "Éditeurs de logiciels, produits et plateformes numériques, Télécoms",
    "finance_insurance": "Banque, Finance, Assurance, Fintech",
    "healthcare_pharma": "Santé, Pharmacie, Biotech, Médical",
    "consulting_services": "Conseil, Audit, ESN, Services B2B",
    "retail_ecommerce": "E-commerce, Retail, Grande Distribution, Mode",
    "industry_aerospace": "Industrie, Aéronautique, Automobile, Défense",
    "energy_environment": "Énergie, Environnement, CleanTech, RSE",
    "media_communication": "Médias, Communication, Divertissement, Jeux vidéo",
    "public_education": "Secteur Public, Administration, Éducation, Recherche",
    "construction_realestate": "Immobilier, Construction, BTP, Urbanisme",
    "logistics_transport": "Transport, Logistique, Supply Chain",
    "agri_food": "Agroalimentaire, Agriculture",
    "other": "aucune des catégories ci-dessus",
}
_SIZE_LABELS = {
    "startup_tpe": "Startup / TPE (< 20 salariés)",
    "pme": "PME (20 - 249 salariés)",
    "eti": "ETI (250 - 4 999 salariés)",
    "grand_groupe": "Grand Groupe (5 000+ salariés)",
}
LLM_DESCRIPTION_CHARS = 1500
LLM_TIMEOUT_SECONDS = 30


# Noms génériques, comparés après normalize_company puis _fold_ascii
_PLACEHOLDER_COMPANIES = {
    "non specifie",
    "non communique",
    "non disponible",
    "non precise",
    "inconnu",
    "n/a",
    "none",
    "null",
    "undefined",
    "nan",
    "notre client",
    "client final",
}


def is_placeholder_company(company: Optional[str]) -> bool:
    """Nom d'entreprise générique (vide, « Non communiqué », confidentiel, anonyme) : rien à mettre en cache."""
    if not company:
        return True
    folded = _fold_ascii(normalize_company(company))
    return folded in _PLACEHOLDER_COMPANIES or any(word in folded for word in ("confidenti", "anonym", "stealth"))


def _build_inference_prompt(company: str, poste: str, description: str, sector_label: Optional[str]) -> str:
    sectors = "\n".join(f"- {key} : {label}" for key, label in _SECTOR_LABELS.items())
    sizes = "\n".join(f"- {key} : {label}" for key, label in _SIZE_LABELS.items())
    context = [f"Entreprise : {company}"]
    if poste:
        context.append(f"Poste : {poste}")
    if sector_label:
        context.append(f"Secteur indiqué par le job board : {sector_label}")
    if description:
        context.append(f"Description de l'offre :\n{description[:LLM_DESCRIPTION_CHARS]}")
    return f"""Tu classes l'entreprise qui publie une offre d'emploi selon son secteur d'activité et sa taille.

Secteurs possibles :
{sectors}

Frontière `tech_it` / `consulting_services` : une ESN ou un cabinet de conseil IT relève de `consulting_services`, même si son code NAF est en 62.0x ; `tech_it` est réservé aux entreprises qui vendent leur propre produit ou plateforme.

Tailles possibles (taille du groupe) :
{sizes}

Réponds `other` si aucun secteur ne convient, `null` si tu ne sais pas.
Réponds uniquement par un objet JSON de la forme {{"sector": "<clé ou null>", "company_size": "<clé ou null>"}}.

{chr(10).join(context)}
"""


async def infer_company_attributes(
    company: str, poste: str = "", description: str = "", sector_label: Optional[str] = None
) -> Optional[dict]:
    """Secteur et taille déduits par LLM (SUMMARY_MODEL) ; une valeur hors taxonomie devient None.

    Renvoie None si l'appel échoue ou si la réponse n'est pas un objet JSON.
    """
    model_name = os.getenv("SUMMARY_MODEL", "gpt-5-nano")
    extra_kwargs = {"drop_params": True}
    short = model_name.split("/")[-1].lower()
    if not any(short.startswith(p) for p in ("o1", "o3", "gpt-5", "gpt-o")):
        extra_kwargs["temperature"] = 0.2
    prompt = _build_inference_prompt(company, poste, description, sector_label)
    try:
        resp = await acompletion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=LLM_TIMEOUT_SECONDS,
            **extra_kwargs,
        )
        data = json.loads(resp.choices[0].message.content or "")
    except Exception as e:
        logger.warning(f"⚠️ Secteur/taille non déduits par LLM pour '{company}': {e}")
        return None
    if not isinstance(data, dict):
        return None
    sector = data.get("sector")
    size = data.get("company_size")
    return {
        "sector": sector if sector in SECTORS else None,
        "company_size": size if size in COMPANY_SIZES else None,
    }


DEFAULT_MAX_LLM_CALLS = 50
# La sauvegarde tourne dans les 420 s de COLLECT_QUERY_TIMEOUT, avant tag_new_offers : passé ce budget,
# seuls les valeurs natives et le cache servent ; le reste attend l'ingestion suivante ou le rattrapage.
DEFAULT_TIME_BUDGET_SECONDS = 60
# (champ de l'offre et du profil, champ de source du profil)
_ATTRIBUTES = (("sector", "sector_source"), ("company_size", "size_source"))


class CompanyResolver:
    """Complète `sector` et `company_size` d'une offre, du moins cher au plus cher, via le cache `company_profiles`.

    Un résolveur par lot : `llm_calls` compte les appels LLM du lot, plafonnés à `max_llm_calls`
    (None : pas de plafond). Les appels externes (API, LLM) s'arrêtent à l'échéance du lot,
    `time_budget_seconds` après la création (None : pas d'échéance), et ne sont tentés qu'une fois
    par entreprise et par lot, même en échec. Une valeur connue n'est jamais remplacée par None.
    """

    def __init__(
        self,
        db,
        http_client: Optional[httpx.AsyncClient] = None,
        max_llm_calls: Optional[int] = DEFAULT_MAX_LLM_CALLS,
        time_budget_seconds: Optional[float] = DEFAULT_TIME_BUDGET_SECONDS,
    ):
        self.db = db
        self.http_client = http_client
        self.max_llm_calls = max_llm_calls
        self.llm_calls = 0
        self.deadline = None if time_budget_seconds is None else monotonic() + time_budget_seconds
        self._remote_tried: set[str] = set()

    def _llm_budget_left(self) -> bool:
        return self.max_llm_calls is None or self.llm_calls < self.max_llm_calls

    def _out_of_time(self) -> bool:
        return self.deadline is not None and monotonic() >= self.deadline

    async def _within_budget(self, call, fallback):
        """Attend l'appel externe jusqu'à l'échéance du lot ; `fallback` s'il est coupé."""
        timeout = None if self.deadline is None else self.deadline - monotonic()
        try:
            return await asyncio.wait_for(call, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("⚠️ Budget temps de l'enrichissement secteur/taille épuisé : appels externes arrêtés")
            return fallback

    async def resolve(self, offer: dict) -> None:
        native = extract_native_attributes(offer.get("raw_data"))
        for field, _ in _ATTRIBUTES:
            if not offer.get(field) and native[field]:
                offer[field] = native[field]

        company = offer.get("entreprise")
        has_native = any(native[field] for field, _ in _ATTRIBUTES)
        if is_placeholder_company(company):
            return
        if all(offer.get(field) for field, _ in _ATTRIBUTES) and not has_native:
            return

        profiles = self.db["company_profiles"]
        name = normalize_company(company)
        profile = await profiles.find_one({"company_name_normalized": name}) or {}
        changes: dict = {}

        def record(field: str, value: Optional[str], source_field: str, source: str) -> None:
            changes[field] = profile[field] = value
            changes[source_field] = profile[source_field] = source

        for field, source_field in _ATTRIBUTES:
            if native[field] and profile.get(source_field) in (None, "llm_inferred"):
                record(field, native[field], source_field, "native_source")
            if not offer.get(field) and profile.get(field):
                offer[field] = profile[field]

        first_attempt = name not in self._remote_tried
        if first_attempt and not offer.get("company_size") and not profile.get("size_source") and not self._out_of_time():
            self._remote_tried.add(name)
            size, siren = await self._within_budget(lookup_company_size(company, client=self.http_client), (None, None))
            if size:
                record("company_size", size, "size_source", "api_entreprises")
                changes["siren"] = profile["siren"] = siren
                offer["company_size"] = size

        missing = [(f, s) for f, s in _ATTRIBUTES if not offer.get(f) and not profile.get(s)]
        if first_attempt and missing and self._llm_budget_left() and not self._out_of_time():
            self._remote_tried.add(name)
            self.llm_calls += 1
            inferred = await self._within_budget(
                infer_company_attributes(
                    company,
                    poste=offer.get("poste") or "",
                    description=offer.get("description") or "",
                    sector_label=native["sector_label"],
                ),
                None,
            )
            if inferred is not None:
                for field, source_field in missing:
                    record(field, inferred[field], source_field, "llm_inferred")
                    if inferred[field]:
                        offer[field] = inferred[field]

        if changes:
            changes["updated_at"] = datetime.now(timezone.utc)
            await profiles.update_one(
                {"company_name_normalized": name},
                {"$set": changes, "$setOnInsert": {"company_name_raw": company}},
                upsert=True,
            )
