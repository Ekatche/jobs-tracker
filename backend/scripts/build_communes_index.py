"""Génère le référentiel géographique du score hybride (Task 3).

Interroge geo.api.gouv.fr (public, gratuit, sans clé, données sous Licence
Ouverte) pour construire un index unique `{clé normalize_text(nom) ->
[codes département triés]}` couvrant communes, départements et régions.
Les communes homonymes entre elles sont fusionnées (ex: « saint denis » ->
Seine-Saint-Denis + La Réunion + les communes métropolitaines homonymes) :
sens permissif, un faux « dans la zone » coûte moins cher qu'une offre
perdue. En revanche un nom de département ou de région REMPLACE l'entrée
d'éventuelles communes homonymes plutôt que de fusionner avec elles (ex:
une commune nommée comme une région ne doit pas élargir la région à ses
propres départements) ; les régions pointent vers la liste de leurs
départements.

Écrit `backend/app/services/offer_scoring/communes_departements.json`, PAS
`backend/app/data/` : `.gitignore:88` ignore tout dossier `data/`
(garde-fou vie privée), un fichier là-dessous ne serait jamais committé ni
déployé (ruling du contrôleur, 2026-10-25).

Usage: cd backend && uv run python scripts/build_communes_index.py
"""

import json
from datetime import date
from pathlib import Path

import httpx

from app.services.relevance import normalize_text

GEO_API_BASE = "https://geo.api.gouv.fr"
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "app" / "services" / "offer_scoring" / "communes_departements.json"


def _get(path: str, params: dict) -> list[dict]:
    resp = httpx.get(f"{GEO_API_BASE}{path}", params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _merge(index: dict[str, set[str]], name: str, code: str) -> None:
    key = normalize_text(name)
    if not key:
        return
    index.setdefault(key, set()).add(code)


def build_index() -> dict[str, list[str]]:
    communes = _get("/communes", {"fields": "nom,codeDepartement", "format": "json"})
    departements = _get("/departements", {"fields": "nom,code,codeRegion"})
    regions = _get("/regions", {})

    index: dict[str, set[str]] = {}

    for commune in communes:
        code_dept = commune.get("codeDepartement")
        if code_dept:
            _merge(index, commune["nom"], code_dept)

    departements_by_region: dict[str, set[str]] = {}
    for dept in departements:
        key = normalize_text(dept["nom"])
        if key:
            # Remplace (pas de fusion) : un nom de département prime sur une
            # commune homonyme, qui pointerait vers un autre département.
            index[key] = {dept["code"]}
        code_region = dept.get("codeRegion")
        if code_region:
            departements_by_region.setdefault(code_region, set()).add(dept["code"])

    for region in regions:
        code_region = region.get("code")
        depts = departements_by_region.get(code_region, set())
        if depts:
            key = normalize_text(region["nom"])
            if key:
                # Idem : un nom de région remplace une commune homonyme.
                index[key] = set(depts)

    return {key: sorted(codes) for key, codes in sorted(index.items())}


def main() -> None:
    index = build_index()
    index["_source"] = f"geo.api.gouv.fr (API Découpage administratif), généré le {date.today().isoformat()}"
    OUTPUT_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"Écrit {OUTPUT_PATH} ({len(index) - 1} clés + _source)")


if __name__ == "__main__":
    main()
