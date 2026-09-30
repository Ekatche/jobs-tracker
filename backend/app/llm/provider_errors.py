"""Traduit les erreurs des fournisseurs LLM (quota, crédits, clé, surcharge) en
messages affichables dans l'application, fournisseur et modèle nommés."""
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException

PROVIDERS = {
    "openai": ("OpenAI", "https://platform.openai.com/settings/organization/billing"),
    "google": ("Google Gemini", "https://aistudio.google.com/"),
    "mistral": ("Mistral", "https://console.mistral.ai/billing"),
    "anthropic": ("Anthropic", "https://console.anthropic.com/settings/billing"),
}
# `llm_provider` de LiteLLM -> clé de PROVIDERS
_PROVIDER_ALIASES = {"gemini": "google", "vertex_ai": "google", "vertex_ai_beta": "google"}

# Épuisement du solde ou de la facturation. Le 429 « per minute » de Gemini parle
# lui aussi de « billing details » : ces marqueurs doivent rester spécifiques.
_CREDIT_MARKERS = (
    "insufficient_quota", "credit balance", "credits are depleted", "prepayment",
    "payment required", "payment_required",
)
_RATE_LIMIT_MARKERS = ("rate limit", "rate_limit", "resource_exhausted", "exceeded your current quota", "quota exceeded")
_OVERLOAD_MARKERS = ("overloaded", "high demand", "unavailable")

STATUS_BY_KIND = {"credits": 402, "rate_limit": 429, "auth": 502, "overloaded": 503}


@dataclass
class ProviderErrorInfo:
    kind: str
    provider: str
    model: str
    message: str

    @property
    def status_code(self) -> int:
        return STATUS_BY_KIND[self.kind]


def _find_llm_error(err: BaseException) -> Optional[BaseException]:
    """Remonte la chaîne des causes : les services enveloppent parfois l'erreur LiteLLM."""
    seen = set()
    while err is not None and id(err) not in seen:
        seen.add(id(err))
        if getattr(err, "llm_provider", None) is not None:
            return err
        err = err.__cause__ or err.__context__
    return None


def _provider_key(err: BaseException) -> Optional[str]:
    raw = (getattr(err, "llm_provider", "") or "").lower()
    raw = _PROVIDER_ALIASES.get(raw, raw)
    if raw in PROVIDERS:
        return raw
    model = (getattr(err, "model", "") or "").lower()
    for key, needle in (("google", "gemini"), ("openai", "gpt"), ("mistral", "mistral"), ("anthropic", "claude")):
        if model.startswith(f"{key}/") or needle in model:
            return key
    return None


def _kind(err: BaseException) -> Optional[str]:
    text = str(err).lower()
    status = getattr(err, "status_code", None)
    if status == 402 or any(m in text for m in _CREDIT_MARKERS):
        return "credits"
    if status in (401, 403) or "authentication" in type(err).__name__.lower():
        return "auth"
    if status == 429 or any(m in text for m in _RATE_LIMIT_MARKERS):
        return "rate_limit"
    if status in (500, 503, 529) or any(m in text for m in _OVERLOAD_MARKERS):
        return "overloaded"
    return None


def classify_llm_error(err: BaseException) -> Optional[ProviderErrorInfo]:
    """Décrit l'erreur fournisseur contenue dans `err`, ou None si ce n'en est pas une."""
    llm_err = _find_llm_error(err)
    if llm_err is None:
        return None
    kind = _kind(llm_err)
    if kind is None:
        return None
    key = _provider_key(llm_err)
    name, billing_url = PROVIDERS.get(key, ("du fournisseur", ""))
    model = (getattr(llm_err, "model", "") or "").split("/")[-1]
    where = f"{name} (modèle {model})" if model else name
    messages = {
        "credits": f"Crédits épuisés sur votre compte {where}. Rechargez votre solde : {billing_url}",
        "rate_limit": (
            f"Quota de requêtes atteint sur {where}. Patientez quelques minutes avant de relancer ; "
            f"si l'erreur persiste, le quota journalier est atteint ({billing_url})."
        ),
        "auth": f"Clé API refusée par {where} : vérifiez-la dans le fichier .env.",
        "overloaded": f"{where} est momentanément surchargé. Relancez dans quelques minutes.",
    }
    return ProviderErrorInfo(kind=kind, provider=name, model=model, message=messages[kind])


def llm_http_exception(err: BaseException) -> Optional[HTTPException]:
    """HTTPException à lever pour une erreur fournisseur, ou None pour toute autre erreur."""
    info = classify_llm_error(err)
    if info is None:
        return None
    return HTTPException(status_code=info.status_code, detail=info.message)
