"""Contrôle des URLs fournies par l'utilisateur avant toute requête sortante.

Deux sources du profil (site personnel, GitHub) obligent le serveur à
récupérer une URL choisie par l'utilisateur. Sans ce filtre, un compte
authentifié peut faire émettre au serveur des requêtes vers le réseau interne
(un service Docker, `localhost`) ou vers l'endpoint de métadonnées cloud
(`169.254.169.254`), et récupérer la réponse dans son propre profil.

Le filtre refuse par défaut : seul un schéma http(s), sans identifiants, avec
un hôte qui résout vers au moins une adresse IP publique, est accepté. Le
rejet se fait sur la classe de l'adresse IP réellement résolue — pas sur une
liste de noms interdits — car un nom de service interne (`mongodb`) ou une
IP écrite en notation hexadécimale/décimale contournerait une liste de noms.
"""

import ipaddress
import socket
from typing import Iterable
from urllib.parse import urlparse

_ALLOWED_SCHEMES = ("http", "https")


def _is_public_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    # `is_global` remplace l'énumération manuelle (`is_private`, `is_loopback`,
    # `is_link_local`, `is_reserved`, `is_unspecified`) : il couvre le RFC 1918,
    # le loopback, le link-local, le non spécifié, le réservé, *et* le RFC 6598
    # « shared address space » 100.64.0.0/10 (NAT opérateur / réseau interne de
    # nombreux fournisseurs cloud) qu'une énumération de drapeaux manuelle avait
    # oublié — `is_private` seul est `False` pour 100.64.0.0/10.
    #
    # Vérifié empiriquement (cpython 3.12) : `is_global` ne couvre PAS le
    # multicast (`ipaddress.ip_address("224.0.0.1").is_global` vaut `True`),
    # parce que la plage multicast (224.0.0.0/4, ff00::/8) n'appartient pas à
    # la liste `_private_networks` que `is_global`/`is_private` consultent.
    # `is_multicast` reste donc une vérification indépendante à conserver.
    return address.is_global and not address.is_multicast


def _resolves_to_public_ip(hostname: str) -> bool:
    """Résout `hostname` et vérifie que toutes les adresses obtenues sont publiques.

    Une seule adresse non publique parmi plusieurs suffit à rejeter l'hôte :
    un attaquant ne contrôle pas quelle adresse le client HTTP choisira.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except (socket.gaierror, UnicodeError) as exc:
        raise ValueError(f"Hôte introuvable : {hostname}") from exc

    if not infos:
        raise ValueError(f"Hôte introuvable : {hostname}")

    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if not _is_public_address(address):
            return False
    return True


def validate_public_url(raw: str, allowed_hosts: Iterable[str] | None = None) -> str:
    """Retourne `raw` si c'est une URL publique admissible, lève `ValueError` sinon.

    `allowed_hosts`, s'il est fourni, restreint en plus aux hôtes listés (ou à
    leurs sous-domaines) ; il ne dispense jamais des contrôles d'IP publique.
    """
    if not raw or not raw.strip():
        raise ValueError("URL vide")

    candidate = raw.strip()
    parsed = urlparse(candidate)

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"Schéma non autorisé : {parsed.scheme or 'absent'}")
    if parsed.username or parsed.password:
        raise ValueError("Les identifiants dans l'URL ne sont pas acceptés")
    if not parsed.hostname:
        raise ValueError("Hôte absent de l'URL")

    host = parsed.hostname.lower()

    if allowed_hosts is not None:
        if not any(
            host == allowed.lower() or host.endswith(f".{allowed.lower()}")
            for allowed in allowed_hosts
        ):
            raise ValueError(f"Hôte non autorisé : {host}")

    if not _resolves_to_public_ip(host):
        raise ValueError(f"L'hôte {host} résout vers une adresse non publique")

    return candidate
