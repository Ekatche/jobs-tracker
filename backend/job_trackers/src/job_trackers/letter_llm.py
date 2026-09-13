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
