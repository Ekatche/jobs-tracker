"""Tests pour la validation anti-SSRF des URLs de profil.

Aucun test ici ne doit résoudre un nom d'hôte réel ni émettre de requête
réseau : `socket.getaddrinfo` est remplacé par un faux résolveur déterministe
(fixture `fake_resolver`, autouse) qui connaît une poignée d'hôtes publics de
test et échoue explicitement (`socket.gaierror`) sur tout le reste, y compris
les hôtes réels utilisés dans les cas d'attaque. Les adresses IP littérales
(ex. 127.0.0.1, ::1) ne dépendent pas du DNS : elles sont acceptées telles
quelles par le faux résolveur, comme le ferait `getaddrinfo` réel.
"""

import ipaddress
import socket

import pytest

from app.services.profile.urls import validate_public_url

# Table de résolution en mémoire : hôtes publics (acceptés) et hôtes qui
# résolvent vers de l'interne ou du loopback (doivent être rejetés au même
# titre qu'une IP littérale privée). Tout hôte absent de cette table lève
# gaierror, comme un vrai DNS pour un nom inconnu.
# Une valeur peut être une IP unique ou une liste (hôte multi-adresses).
_FAKE_DNS = {
    "github.com": "140.82.121.3",  # public
    "www.elielkatche.me": "76.76.21.21",  # public
    "example.com": "93.184.216.34",  # public
    "localhost": "127.0.0.1",
    "localhost.": "127.0.0.1",  # nom pleinement qualifié (point final)
    "mongodb": "172.18.0.5",  # nom de service Docker -> IP privée
    "0x7f.0.0.1": "127.0.0.1",  # loopback en notation hexadécimale
    "2130706433": "127.0.0.1",  # loopback en notation décimale
    "multihomed.example": ["93.184.216.34", "10.0.0.9"],  # publique + privée
}


@pytest.fixture(autouse=True)
def fake_resolver(monkeypatch):
    """Remplace socket.getaddrinfo par un résolveur en mémoire, sans réseau."""

    def fake_getaddrinfo(host, *args, **kwargs):
        bare_host = host.strip("[]") if host else host
        try:
            ip = ipaddress.ip_address(bare_host)
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (str(ip), 0))]
        except ValueError:
            pass

        if host in _FAKE_DNS:
            ips = _FAKE_DNS[host]
            if isinstance(ips, str):
                ips = [ips]
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in ips]

        raise socket.gaierror(f"faux DNS : hôte inconnu {host}")

    monkeypatch.setattr("app.services.profile.urls.socket.getaddrinfo", fake_getaddrinfo)


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/Ekatche",
        "https://www.elielkatche.me/experience",
    ],
)
def test_public_https_urls_are_accepted(url):
    assert validate_public_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # métadonnées cloud
        "http://localhost:8000/admin",
        "http://127.0.0.1/",
        "http://[::1]/",
        "http://10.0.0.5/internal",
        "http://192.168.1.10/",
        "http://mongodb:27017/",  # service interne Docker
        "file:///etc/passwd",
        "gopher://evil/",
        "https://user:pass@github.com/",  # credentials dans l'URL
        "not-a-url",
        "",
        "HTTP://169.254.169.254/",  # schéma en majuscules
        "http://0x7f.0.0.1/",  # loopback en notation hexadécimale
        "http://2130706433/",  # loopback en notation décimale (127.0.0.1)
        "http://169.254.169.254.evil.example/",  # nom, pas une IP littérale
        "http://localhost./admin",  # point final (FQDN) pour contourner un filtre par nom
        "http://multihomed.example/",  # résout vers une IP publique ET une IP privée
    ],
)
def test_dangerous_urls_are_rejected(url):
    with pytest.raises(ValueError):
        validate_public_url(url)


def test_allowed_hosts_restricts_further():
    validate_public_url("https://github.com/Ekatche", allowed_hosts={"github.com"})
    with pytest.raises(ValueError):
        validate_public_url("https://example.com/x", allowed_hosts={"github.com"})


def test_subdomain_of_allowed_host_is_accepted():
    assert validate_public_url(
        "https://www.elielkatche.me/experience", allowed_hosts={"elielkatche.me"}
    )


def test_allowed_hosts_accepts_any_iterable_not_just_a_set():
    # allowed_hosts est documenté comme un Iterable[str] : une liste doit marcher.
    assert validate_public_url(
        "https://github.com/Ekatche", allowed_hosts=["github.com"]
    )
