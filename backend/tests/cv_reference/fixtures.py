"""Faux fournisseurs et profils de vérité réduits pour les tests du banc."""
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scripts.cv_reference_bench import make_oracle

INVENTED_EXPERIENCE = {"company": "Entreprise Inventée SA", "role": "Directeur général", "start": "2010", "end": "2012"}
INVENTED_ROLE_EXPERIENCE = {"role": "Directeur général"}


def llm_response(payload: dict, prompt_tokens=100, completion_tokens=50):
    message = SimpleNamespace(content=json.dumps(payload))
    return SimpleNamespace(choices=[SimpleNamespace(message=message)],
                           usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens))


def inventing_oracle(extra_experience: dict, replace_role: bool = False):
    """Fabrique d'oracle : l'oracle parfait, plus une expérience inventée (ou un intitulé inventé)."""

    def factory(truth, calls=None):
        base = make_oracle(truth, calls)

        async def fake(**kwargs):
            response = await base(**kwargs)
            payload = json.loads(response.choices[0].message.content)
            if replace_role and payload.get("experiences"):
                payload["experiences"][0]["role"] = extra_experience["role"]
            else:
                payload.setdefault("experiences", []).append(dict(extra_experience))
            response.choices[0].message.content = json.dumps(payload)
            return response

        return fake

    return factory


def refusing_acompletion():
    return AsyncMock(side_effect=AssertionError("aucun appel fournisseur attendu"))
