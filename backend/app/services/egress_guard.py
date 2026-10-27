"""Garde SSRF au moment de la connexion.

`validate_public_url_async` résout le nom, puis le client HTTP (ou Chromium)
le résout une seconde fois pour se connecter. Entre les deux, un DNS contrôlé
par un attaquant peut changer de réponse (DNS rebinding) : public au contrôle,
interne à la connexion. Ce module ferme cette fenêtre en ne résolvant qu'une
fois et en se connectant à l'adresse validée elle-même.

- `public_only_transport()` : transport httpx dont chaque connexion TCP, sauts
  de redirection compris, vise une IP publique validée.
- `public_only_proxy()` : proxy HTTP local, à donner à Chromium, qui applique
  la même règle à tout ce que le navigateur ouvre (page, ressources,
  redirections, WebSocket, popups, service workers).

SNI et vérification du certificat restent faits sur le nom d'hôte : httpcore
passe `server_hostname` depuis l'URL, et Chromium chiffre de bout en bout dans
le tunnel CONNECT.
"""

import asyncio
import ipaddress
import logging
import socket
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional
from urllib.parse import urlsplit

import httpcore
import httpx

from app.services.profile.urls import _is_public_address

logger = logging.getLogger(__name__)

DNS_TIMEOUT = 5.0
UPSTREAM_CONNECT_TIMEOUT = 10.0
PROXY_HEADER_TIMEOUT = 30.0
PROXY_HEADER_LIMIT = 64 * 1024
# En-têtes propres au saut client -> proxy, jamais relayés à l'origine
_HOP_BY_HOP = {"connection", "proxy-connection", "keep-alive", "proxy-authorization"}


async def resolve_public_ips(host: str, port: int, timeout: float = DNS_TIMEOUT) -> List[str]:
    """Résout `host` une seule fois et renvoie ses adresses, dans l'ordre du DNS.

    Lève `ValueError` si le nom ne résout pas, ou si une seule des adresses
    n'est pas publique : l'attaquant ne choisit pas l'adresse retenue.
    """
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(host, port, type=socket.SOCK_STREAM), timeout=timeout
        )
    except (socket.gaierror, UnicodeError, asyncio.TimeoutError) as exc:
        raise ValueError(f"Hôte introuvable : {host}") from exc

    addresses: List[str] = []
    for info in infos:
        address = info[4][0]
        if not _is_public_address(ipaddress.ip_address(address)):
            raise ValueError(f"L'hôte {host} résout vers une adresse non publique")
        if address not in addresses:
            addresses.append(address)
    if not addresses:
        raise ValueError(f"Hôte introuvable : {host}")
    return addresses


class PublicOnlyNetworkBackend(httpcore.AsyncNetworkBackend):
    """Backend réseau httpcore : se connecte à l'IP publique validée, jamais au nom."""

    def __init__(self) -> None:
        self._backend = httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options=None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            addresses = await resolve_public_ips(host, port)
        except ValueError as exc:
            raise httpcore.ConnectError(str(exc)) from exc

        # Plusieurs adresses (IPv6 puis IPv4, typiquement) : on les essaie dans
        # l'ordre, comme le ferait le client sur le nom
        last_error: Optional[Exception] = None
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last_error = exc
        raise last_error

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):
        raise httpcore.ConnectError("Socket Unix refusé")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


def public_only_transport() -> httpx.AsyncHTTPTransport:
    """Transport httpx dont chaque connexion vise une IP publique validée.

    httpx n'expose pas `network_backend` : on le remplace sur le pool httpcore
    (attribut privé, couvert par `tests/test_egress_guard.py`).
    """
    transport = httpx.AsyncHTTPTransport()
    transport._pool._network_backend = PublicOnlyNetworkBackend()
    return transport


def browser_config_behind_proxy(browser_config, proxy_url: str):
    """Copie d'un `BrowserConfig` crawl4ai dont tout le trafic passe par `proxy_url`.

    `clone()` (crawl4ai 0.6.3) repasse par `from_kwargs`, qui ignore `verbose` :
    on le recopie.
    """
    config = browser_config.clone(proxy=proxy_url)
    config.verbose = browser_config.verbose
    return config


async def _open_upstream(host: str, port: int):
    """Connexion TCP vers l'IP validée. `ValueError` : refusé ; `OSError` : injoignable."""
    addresses = await resolve_public_ips(host, port)
    last_error: Optional[BaseException] = None
    for address in addresses:
        try:
            return await asyncio.wait_for(asyncio.open_connection(address, port), UPSTREAM_CONNECT_TIMEOUT)
        except (OSError, asyncio.TimeoutError) as exc:
            last_error = exc
    raise OSError(f"{host}:{port} injoignable") from last_error


async def _reply(writer: asyncio.StreamWriter, status: int, reason: str) -> None:
    writer.write(f"HTTP/1.1 {status} {reason}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".encode())
    try:
        await writer.drain()
    except ConnectionError:
        pass


async def _copy(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass


async def _splice(client_reader, client_writer, upstream_reader, upstream_writer) -> None:
    """Copie dans les deux sens ; le premier sens qui se termine ferme l'échange."""
    tasks = [
        asyncio.create_task(_copy(client_reader, upstream_writer)),
        asyncio.create_task(_copy(upstream_reader, client_writer)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def _handle_proxy_client(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    """Une connexion du navigateur = une seule origine, à une IP publique validée.

    CONNECT (https, ws, wss) : tunnel vers l'IP validée. Requête http en forme
    absolue : réécrite en forme origine avec `Connection: close`, pour que le
    navigateur ne réutilise jamais cette connexion vers un autre hôte.
    """
    upstream_writer = None
    try:
        try:
            head = await asyncio.wait_for(client_reader.readuntil(b"\r\n\r\n"), PROXY_HEADER_TIMEOUT)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError, ConnectionError):
            return
        request_line, *header_lines = head[:-4].decode("latin-1").split("\r\n")
        try:
            method, target, version = request_line.split(" ")
            if method == "CONNECT":
                authority = urlsplit(f"//{target}")
                host, port, path = authority.hostname, authority.port or 443, None
            else:
                url = urlsplit(target)
                if url.scheme != "http":
                    raise ValueError(f"schéma refusé : {url.scheme}")
                host, port = url.hostname, url.port or 80
                path = (url.path or "/") + (f"?{url.query}" if url.query else "")
            if not host:
                raise ValueError("hôte absent")
        except ValueError:
            await _reply(client_writer, 400, "Bad Request")
            return

        try:
            upstream_reader, upstream_writer = await _open_upstream(host, port)
        except ValueError as exc:
            logger.info("proxy navigateur : %s:%s refusé (%s)", host, port, exc)
            await _reply(client_writer, 403, "Forbidden")
            return
        except OSError:
            await _reply(client_writer, 502, "Bad Gateway")
            return

        if path is None:
            client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        else:
            kept = [line for line in header_lines if line.split(":", 1)[0].strip().lower() not in _HOP_BY_HOP]
            request = "\r\n".join([f"{method} {path} {version}", *kept, "Connection: close"]) + "\r\n\r\n"
            upstream_writer.write(request.encode("latin-1"))
        await _splice(client_reader, client_writer, upstream_reader, upstream_writer)
    finally:
        client_writer.close()
        if upstream_writer is not None:
            upstream_writer.close()


@asynccontextmanager
async def public_only_proxy() -> AsyncIterator[str]:
    """Proxy HTTP local (`http://127.0.0.1:<port>`) à donner à Chromium.

    Toute connexion du navigateur passe par lui : Chromium ne résout aucun nom
    lui-même, et Playwright fait passer le loopback par le proxy
    (`--proxy-bypass-list=<-loopback>`). Les connexions ouvertes sont fermées
    à la sortie du contexte.
    """
    handlers: set = set()

    async def handle(reader, writer):
        task = asyncio.current_task()
        handlers.add(task)
        try:
            await _handle_proxy_client(reader, writer)
        finally:
            handlers.discard(task)

    server = await asyncio.start_server(handle, "127.0.0.1", 0, limit=PROXY_HEADER_LIMIT)
    port = server.sockets[0].getsockname()[1]
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.close()
        pending = list(handlers)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        try:
            await asyncio.wait_for(server.wait_closed(), 5)
        except asyncio.TimeoutError:
            logger.warning("proxy navigateur : fermeture incomplète après 5 s")
