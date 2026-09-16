"""Collecte GitHub par l'API REST.

L'API distingue les forks des dépôts propres, ce qu'un scrape de la page de
profil ne fait pas. GitHub documente des projets, jamais des emplois : ce
collecteur ne produit donc aucune expérience.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

API_ROOT = "https://api.github.com"
MAX_REPOS = 12
README_CHARS = 1200


def parse_github_username(url_or_handle: str) -> str:
    """Extrait le pseudo depuis une URL GitHub ou un pseudo nu."""
    value = (url_or_handle or "").strip().rstrip("/")
    if not value:
        raise ValueError("Identifiant GitHub vide")

    if "/" in value or "." in value:
        match = re.search(r"github\.com/([A-Za-z0-9-]+)", value)
        if not match:
            raise ValueError(f"URL GitHub non reconnue : {url_or_handle}")
        return match.group(1)

    if not re.fullmatch(r"[A-Za-z0-9-]+", value):
        raise ValueError(f"Pseudo GitHub invalide : {url_or_handle}")
    return value


class GitHubClient:
    """Accès minimal à l'API REST. Le token est optionnel mais relève le quota."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def get_repos(self, username: str) -> List[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{API_ROOT}/users/{username}/repos",
                params={"per_page": 100, "sort": "pushed"},
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def get_readme(self, username: str, repo: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{API_ROOT}/repos/{username}/{repo}/readme",
                headers={**self._headers(), "Accept": "application/vnd.github.raw"},
            )
            if response.status_code == 200:
                return response.text
        return None


async def collect_github(url_or_handle: str, client=None) -> Dict[str, Any]:
    """Rend un payload de source prêt à être rangé dans `sources.github`."""
    username = parse_github_username(url_or_handle)
    client = client or GitHubClient()

    repos = await client.get_repos(username)
    own = [
        repo
        for repo in repos
        if not repo.get("fork") and not repo.get("archived")
    ]
    own.sort(
        key=lambda r: (r.get("stargazers_count", 0), r.get("pushed_at", "")),
        reverse=True,
    )

    projects: List[Dict[str, Any]] = []
    languages: List[str] = []
    for repo in own[:MAX_REPOS]:
        description = repo.get("description") or ""
        if len(description) < 40:
            readme = await client.get_readme(username, repo["name"])
            if readme:
                body = re.sub(r"^#.*$", "", readme, flags=re.MULTILINE).strip()
                description = (description + " " + body[:README_CHARS]).strip()

        stack = list(repo.get("topics") or [])
        if repo.get("language"):
            stack.insert(0, repo["language"])
            languages.append(repo["language"])

        projects.append(
            {
                "name": repo["name"],
                "description": description,
                "stack": stack,
                "url": repo.get("html_url"),
                "repo": repo.get("html_url"),
                "context": "perso",
            }
        )

    payload: Dict[str, Any] = {
        "projects": projects,
        "experiences": [],  # GitHub ne documente pas d'emploi
        "contact": {"github": f"https://github.com/{username}"},
    }
    if languages:
        payload["skills"] = {"langages": list(dict.fromkeys(languages))}
    return payload
