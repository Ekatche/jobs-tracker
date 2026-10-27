"""Garde SSRF au moment de la connexion.

Valider une URL puis laisser le client HTTP (ou le navigateur) résoudre le nom
une seconde fois laisse une fenêtre de DNS rebinding : le nom résout vers une
IP publique au contrôle, puis vers une IP interne à la connexion. Ces tests
simulent exactement cet écart — le contrôle préalable est déclaré public, la
résolution réelle renvoie 127.0.0.1 — et vérifient que le serveur local n'est
jamais contacté.
"""
import asyncio
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from app.services import pdf_job_offer
from app.services.egress_guard import public_only_proxy

PDF_BYTES = b"%PDF-1.4\n" + b"0" * 64


@pytest.fixture
def local_server():
    hits = []
    headers = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append((self.headers.get("Host"), self.path))
            headers.append(dict(self.headers))
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(PDF_BYTES)))
            self.end_headers()
            self.wfile.write(PDF_BYTES)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield SimpleNamespace(port=server.server_address[1], hits=hits, headers=headers)
    server.shutdown()
    server.server_close()


@pytest.fixture
def rebinding_dns(monkeypatch):
    """`rebind.test` a été validé public, mais résout vers 127.0.0.1 à la connexion."""
    real_getaddrinfo = socket.getaddrinfo

    def fake_getaddrinfo(host, *args, **kwargs):
        if host in ("rebind.test", b"rebind.test"):
            host = "127.0.0.1"
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr("app.services.profile.urls._resolves_to_public_ip", lambda host: True)


@pytest.mark.asyncio
async def test_pdf_download_never_connects_to_rebound_internal_ip(local_server, rebinding_dns):
    port, hits = local_server.port, local_server.hits

    assert await pdf_job_offer.download_pdf_bytes(f"http://rebind.test:{port}/offre.pdf") is None
    assert hits == []


@pytest.mark.asyncio
async def test_pdf_download_reaches_validated_ip_with_original_host(local_server, rebinding_dns, monkeypatch):
    # 127.0.0.1 classée publique pour ce test : la connexion passe, par l'IP
    # validée, et l'origine reçoit toujours le nom demandé dans `Host`
    monkeypatch.setattr("app.services.egress_guard._is_public_address", lambda address: True)
    port, hits = local_server.port, local_server.hits

    assert await pdf_job_offer.download_pdf_bytes(f"http://rebind.test:{port}/offre.pdf") == PDF_BYTES
    assert hits == [(f"rebind.test:{port}", "/offre.pdf")]


@pytest.mark.asyncio
async def test_ats_fetch_never_connects_to_rebound_internal_ip(local_server, rebinding_dns):
    from app.services.ats.router import extract_ats_or_jsonld_offer

    port, hits = local_server.port, local_server.hits

    assert await extract_ats_or_jsonld_offer(f"http://rebind.test:{port}/offre") is None
    assert hits == []


@pytest.mark.asyncio
async def test_website_fetch_never_connects_to_rebound_internal_ip(local_server, rebinding_dns):
    from app.services.profile.collectors.website import _default_fetch

    port, hits = local_server.port, local_server.hits

    assert await _default_fetch(f"http://rebind.test:{port}/sitemap.xml") is None
    assert hits == []


async def _proxy_exchange(proxy_url, payload, read_until_close=True):
    """Envoie `payload` brut au proxy et rend la réponse (jusqu'à fermeture)."""
    proxy = urlsplit(proxy_url)
    reader, writer = await asyncio.open_connection(proxy.hostname, proxy.port)
    writer.write(payload)
    await writer.drain()
    response = await asyncio.wait_for(reader.read() if read_until_close else reader.readuntil(b"\r\n\r\n"), 5)
    return response, reader, writer


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["rebind.test", "127.0.0.1"])
async def test_proxy_refuses_connect_to_internal_ip(local_server, rebinding_dns, target):
    port, hits = local_server.port, local_server.hits

    async with public_only_proxy() as proxy_url:
        response, _, writer = await _proxy_exchange(
            proxy_url, f"CONNECT {target}:{port} HTTP/1.1\r\nHost: {target}:{port}\r\n\r\n".encode()
        )
        writer.close()

    assert response.startswith(b"HTTP/1.1 403")
    assert hits == []


@pytest.mark.asyncio
async def test_proxy_refuses_plain_http_to_internal_ip(local_server, rebinding_dns):
    port, hits = local_server.port, local_server.hits

    async with public_only_proxy() as proxy_url:
        response, _, writer = await _proxy_exchange(
            proxy_url, f"GET http://rebind.test:{port}/secret HTTP/1.1\r\nHost: rebind.test:{port}\r\n\r\n".encode()
        )
        writer.close()

    assert response.startswith(b"HTTP/1.1 403")
    assert hits == []


@pytest.mark.asyncio
async def test_proxy_relays_plain_http_in_origin_form_and_closes(local_server, rebinding_dns, monkeypatch):
    monkeypatch.setattr("app.services.egress_guard._is_public_address", lambda address: True)
    port, hits = local_server.port, local_server.hits

    async with public_only_proxy() as proxy_url:
        response, _, writer = await _proxy_exchange(
            proxy_url,
            (
                f"GET http://rebind.test:{port}/offre.pdf?x=1 HTTP/1.1\r\nHost: rebind.test:{port}\r\n"
                "Proxy-Connection: keep-alive\r\nConnection: keep-alive\r\n\r\n"
            ).encode(),
        )
        writer.close()

    assert response.startswith(b"HTTP/1.0 200")
    assert response.endswith(PDF_BYTES)
    assert hits == [(f"rebind.test:{port}", "/offre.pdf?x=1")]
    [headers] = local_server.headers
    assert headers["Connection"] == "close"
    assert "Proxy-Connection" not in headers


@pytest.mark.asyncio
async def test_proxy_tunnels_connect_to_validated_ip(local_server, rebinding_dns, monkeypatch):
    monkeypatch.setattr("app.services.egress_guard._is_public_address", lambda address: True)
    port, hits = local_server.port, local_server.hits

    async with public_only_proxy() as proxy_url:
        established, reader, writer = await _proxy_exchange(
            proxy_url, f"CONNECT rebind.test:{port} HTTP/1.1\r\nHost: rebind.test:{port}\r\n\r\n".encode(),
            read_until_close=False,
        )
        writer.write(f"GET /offre.pdf HTTP/1.1\r\nHost: rebind.test:{port}\r\nConnection: close\r\n\r\n".encode())
        await writer.drain()
        response = await asyncio.wait_for(reader.read(), 5)
        writer.close()

    assert established.startswith(b"HTTP/1.1 200")
    assert response.endswith(PDF_BYTES)
    assert hits == [(f"rebind.test:{port}", "/offre.pdf")]


@pytest.mark.asyncio
async def test_proxy_shutdown_closes_open_tunnels(local_server, rebinding_dns, monkeypatch):
    monkeypatch.setattr("app.services.egress_guard._is_public_address", lambda address: True)
    port = local_server.port

    async def open_tunnel_then_exit():
        async with public_only_proxy() as proxy_url:
            _, reader, _ = await _proxy_exchange(
                proxy_url, f"CONNECT rebind.test:{port} HTTP/1.1\r\n\r\n".encode(), read_until_close=False
            )
        return reader

    reader = await asyncio.wait_for(open_tunnel_then_exit(), 5)
    assert await asyncio.wait_for(reader.read(), 5) == b""


@pytest.mark.asyncio
async def test_offer_verification_never_connects_to_rebound_internal_ip(local_server, rebinding_dns):
    from app.tasks.verify_job_offers import check_url_http_fast

    port, hits = local_server.port, local_server.hits

    assert (await check_url_http_fast(f"http://rebind.test:{port}/offre"))["status"] == "unknown"
    assert hits == []
