import os
from typing import Optional
from crewai import LLM

# Modèles épinglés par défaut selon la spec
DEFAULT_MODELS = {
    "offer_analyst": "gemini/gemini-3.8-flash",
    "writer": "openai/gpt-5.6-sol",
    "critic": "gemini/gemini-3.8-flash",
    "reviser": "openai/gpt-5.6-sol",
}

ROLE_TEMPERATURES = {
    "offer_analyst": 0.1,
    "writer": 0.7,
    "critic": 0.2,
    "reviser": 0.5,
}

def get_model_provider(model_name: str) -> str:
    clean = model_name.lower()
    if clean.startswith("gemini/") or "gemini" in clean:
        return "google"
    if clean.startswith("openai/") or "gpt" in clean:
        return "openai"
    if clean.startswith("mistral/") or "mistral" in clean:
        return "mistral"
    raise ValueError(f"Unknown provider for model: {model_name}")

def validate_no_floating_alias(model_name: str) -> None:
    lower = model_name.lower()
    if "latest" in lower or "preview" in lower:
        raise ValueError(f"Model '{model_name}' contains floating alias ('latest' or 'preview'). Pinned versions are required.")

def validate_cross_provider(writer_model: str, critic_model: Optional[str] = None) -> str:
    writer_prov = get_model_provider(writer_model)
    if critic_model:
        critic_prov = get_model_provider(critic_model)
        if writer_prov == critic_prov:
            raise ValueError(f"Writer ({writer_model}) and Critic ({critic_model}) resolve to the same provider ('{writer_prov}'). Cross-provider critic is required.")
        return critic_model

    # Résolution automatique basée sur la spec
    if writer_prov == "openai":
        return "gemini/gemini-3.8-flash"
    else:
        return "openai/gpt-5.6-sol"

def get_letter_llm(role: str, model_override: Optional[str] = None) -> LLM:
    env_var_map = {
        "offer_analyst": "LETTER_MODEL_ANALYST",
        "writer": "LETTER_MODEL_WRITER",
        "critic": "LETTER_MODEL_CRITIC",
        "reviser": "LETTER_MODEL_REVISER",
    }
    model = model_override or os.getenv(env_var_map.get(role, ""), DEFAULT_MODELS.get(role, ""))
    validate_no_floating_alias(model)

    provider = get_model_provider(model)
    if provider == "google":
        api_key = os.getenv("GEMINI_API_KEY", "dummy_gemini_key_for_test")
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "dummy_openai_key_for_test")
    elif provider == "mistral":
        api_key = os.getenv("MISTRAL_API_KEY", "dummy_mistral_key_for_test")
    else:
        api_key = None

    if not api_key:
        raise ValueError(f"Missing API key for provider '{provider}' required by role '{role}'.")

    temp = ROLE_TEMPERATURES.get(role, 0.5)
    return LLM(model=model, api_key=api_key, temperature=temp)

def format_llm_error(error: Exception, provider: Optional[str] = None) -> str:
    """Format and diagnose raw LLM errors into helpful, actionable messages."""
    err_str = str(error).lower()
    prov_str = provider.upper() if provider else "DU FOURNISSEUR"

    if any(term in err_str for term in ["insufficient_quota", "quota", "credit", "exceeded your current quota", "billing", "402", "payment_required"]):
        return (
            f"Crédits épuisés ou quota dépassé sur votre compte API {prov_str}. "
            "Veuillez recharger votre solde ou vérifier votre compte sur la console du fournisseur."
        )
    if any(term in err_str for term in ["invalid_api_key", "incorrect api key", "unauthorized", "401", "authentication"]):
        return (
            f"Clé API {prov_str} invalide ou expirée. "
            "Veuillez vérifier vos clés API dans le fichier .env."
        )
    if any(term in err_str for term in ["rate_limit", "ratelimit", "429", "resource_exhausted"]):
        return (
            f"Limite de requêtes par minute (Rate Limit) atteinte pour {prov_str}. "
            "Veuillez patienter quelques instants avant de relancer la génération."
        )
    return f"Erreur lors de l'appel LLM ({prov_str}) : {str(error)}"

def get_api_status() -> dict:
    """
    Retourne le statut des clés API configurées et des liens d'administration.
    Note : OpenAI, Google AI Studio et Mistral ne fournissent pas d'endpoint public
    sécurisé permettant d'interroger le solde de crédit restant avec une clé d'API standard.
    """
    return {
        "google": {
            "configured": bool(os.getenv("GEMINI_API_KEY")),
            "note": "Palier gratuit standard disponible sur Gemini 3.8 Flash (limité en requêtes par minute).",
            "billing_url": "https://aistudio.google.com/",
        },
        "openai": {
            "configured": bool(os.getenv("OPENAI_API_KEY")),
            "note": "Facturation prépayée. Les crédits restants sont consultables sur platform.openai.com/billing.",
            "billing_url": "https://platform.openai.com/billing",
        },
        "mistral": {
            "configured": bool(os.getenv("MISTRAL_API_KEY")),
            "note": "Compte à crédits. Solde consultable sur console.mistral.ai/billing.",
            "billing_url": "https://console.mistral.ai/billing",
        },
    }

