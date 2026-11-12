"""Security regressions for the public-only page fetcher, without network access."""
import io
import socket
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests
import urllib3

from core.tools import call_tool
from core.tools import web_search as web


PUBLIC_IP = "8.8.8.8"


def _addrinfo(address, port):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    sockaddr = (address, port, 0, 0) if family == socket.AF_INET6 else (address, port)
    return (family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr)


@pytest.fixture
def public_dns(monkeypatch):
    resolver = Mock(side_effect=lambda host, port, *a, **kw: [_addrinfo(PUBLIC_IP, port)])
    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    return resolver


@pytest.fixture
def transport(monkeypatch):
    """Use real urllib3 pools/responses, intercepting only the HTTP exchange."""
    calls = []
    responses = []

    def exchange(pool, method, url, **kwargs):
        calls.append((pool, method, url, kwargs))
        assert responses, "unexpected HTTP request"
        return responses.pop(0)

    monkeypatch.setattr(urllib3.HTTPConnectionPool, "urlopen", exchange)
    return calls, responses


def _response(body=b"<p>Public page</p>", status=200, headers=None):
    return urllib3.HTTPResponse(
        body=io.BytesIO(body), status=status, headers=headers or {}, preload_content=False,
    )


@pytest.mark.parametrize("url", [
    "http://127.0.0.1\\@8.8.8.8/",
    "http://8.8.8.8\\@127.0.0.1/",
    "http://user:password@8.8.8.8/",
    "http://user@8.8.8.8/",
    "http://%31%32%37.0.0.1/",
    "http://[fe80::1%25eth0]/",
    "http://8.8.8.8\t/",
    "http://8.8.8.8\n/",
    "http://8.8.8.8\x00/",
])
def test_ambiguous_urls_are_blocked_before_dns(url, public_dns, transport):
    calls, _ = transport
    assert web.fetch_page(url).startswith("Blocked URL:")
    public_dns.assert_not_called()
    assert not calls


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.1", "169.254.169.254", "192.168.1.1", "0.0.0.0",
    "::1", "fd00::1", "fe80::1", "::ffff:127.0.0.1", "::ffff:10.0.0.1",
])
def test_private_dns_answers_are_blocked(address, monkeypatch, transport):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [_addrinfo(address, port)])
    calls, _ = transport
    assert web.fetch_page("https://example.com/").startswith("Blocked URL:")
    assert not calls


def test_mixed_public_and_private_dns_answers_are_blocked(monkeypatch, transport):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [
        _addrinfo(PUBLIC_IP, port), _addrinfo("::1", port),
    ])
    calls, _ = transport
    assert web.fetch_page("http://example.com/").startswith("Blocked URL:")
    assert not calls


@pytest.mark.parametrize("answers", [[], socket.gaierror("not found")])
def test_unresolvable_host_is_blocked(answers, monkeypatch, transport):
    monkeypatch.setattr(socket, "getaddrinfo", Mock(
        side_effect=answers if isinstance(answers, Exception) else None,
        return_value=answers,
    ))
    calls, _ = transport
    assert web.fetch_page("http://example.com/").startswith("Blocked URL:")
    assert not calls


def test_prepared_url_is_the_one_validated(monkeypatch, transport):
    # Exercise the post-preparation guard even if a client changes its parsing.
    prepare = requests.Request.prepare

    def changed_prepare(request):
        prepared = prepare(request)
        prepared.url = "http://127.0.0.1/"
        return prepared

    monkeypatch.setattr(requests.Request, "prepare", changed_prepare)
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [_addrinfo(host, port)])
    calls, _ = transport
    assert web.fetch_page("http://example.com/").startswith("Blocked URL:")
    assert not calls


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_rebinding_cannot_change_socket_destination(scheme, monkeypatch):
    """Drive the actual pool/connection code through the socket boundary."""
    resolutions = []
    connections = []
    original_resolve = socket.getaddrinfo

    def resolve(host, port, *args, **kwargs):
        resolutions.append(host)
        if host == "rebind.example":
            address = PUBLIC_IP if resolutions.count(host) == 1 else "127.0.0.1"
            return [_addrinfo(address, port)]
        # Numeric addresses use the OS resolver (no DNS lookup).
        return original_resolve(host, port, *args, **kwargs)

    def connect(sock, address):
        connections.append(address)
        raise OSError("intercepted before network access")

    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9999")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:9999")
    assert web.fetch_page(f"{scheme}://rebind.example:8443/").startswith("Failed to fetch page:")
    assert resolutions.count("rebind.example") == 1
    assert connections == [(PUBLIC_IP, 8443)]


def test_https_preserves_host_sni_and_certificate_verification(public_dns, transport):
    calls, responses = transport
    responses.append(_response())
    assert call_tool("fetch_page", {"url": "https://Example.COM:8443/a b?q=c d"}) == "Public page"
    pool, method, path, kwargs = calls[0]
    assert isinstance(pool, urllib3.HTTPSConnectionPool)
    assert (pool.host, pool.port) == (PUBLIC_IP, 8443)
    assert (method, path) == ("GET", "/a%20b?q=c%20d")
    assert kwargs["headers"]["Host"] == "example.com:8443"
    connection = pool._new_conn()
    assert connection.host == PUBLIC_IP
    assert connection.server_hostname == "example.com"
    assert connection.assert_hostname == "example.com"
    assert connection.cert_reqs == "CERT_REQUIRED"
    assert connection.ca_certs == requests.certs.where()
    assert kwargs["redirect"] is False and kwargs["retries"] is False
    assert kwargs["preload_content"] is False
    assert kwargs["timeout"] == 12
    public_dns.assert_called_once_with("example.com", 8443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)


@pytest.mark.parametrize("url, hostname, address, host_header", [
    ("https://bücher.de/article", "xn--bcher-kva.de", PUBLIC_IP, "xn--bcher-kva.de"),
    ("http://[2606:4700:4700::1111]:8080/", "2606:4700:4700::1111", "2606:4700:4700::1111", "[2606:4700:4700::1111]:8080"),
])
def test_idna_and_public_ipv6(url, hostname, address, host_header, monkeypatch, transport):
    resolver = Mock(side_effect=lambda host, port, **kw: [_addrinfo(address, port)])
    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    calls, responses = transport
    responses.append(_response())
    assert web.fetch_page(url) == "Public page"
    assert resolver.call_args.args[0] == hostname
    assert calls[0][0].host == address
    assert calls[0][3]["headers"]["Host"] == host_header


@pytest.mark.parametrize("location", [
    "http://127.0.0.1/", "http://internal.example/", "http://127.0.0.1\\@8.8.8.8/", "file:///etc/passwd",
])
def test_redirect_cannot_reach_private_or_ambiguous_destination(location, monkeypatch, transport):
    monkeypatch.setattr(socket, "getaddrinfo", lambda host, port, **kw: [
        _addrinfo(PUBLIC_IP if host == "example.com" else "127.0.0.1", port),
    ])
    calls, responses = transport
    first = _response(status=302, headers={"Location": location})
    responses.append(first)
    assert web.fetch_page("http://example.com/").startswith("Blocked URL:")
    assert len(calls) == 1
    assert first.closed


def test_relative_redirect_revalidates_and_closes_each_response(public_dns, transport):
    calls, responses = transport
    first = _response(status=302, headers={"Location": "/next"})
    last = _response()
    responses.extend([first, last])
    assert web.fetch_page("http://example.com/start") == "Public page"
    assert [call[2] for call in calls] == ["/start", "/next"]
    assert public_dns.call_count == 2
    assert first.closed and last.closed


def test_redirect_to_rebound_hostname_is_blocked(public_dns, transport):
    public_dns.side_effect = [
        [_addrinfo(PUBLIC_IP, 80)], [_addrinfo("127.0.0.1", 80)],
    ]
    calls, responses = transport
    responses.append(_response(status=302, headers={"Location": "/next"}))
    assert web.fetch_page("http://example.com/start").startswith("Blocked URL:")
    assert public_dns.call_count == 2
    assert len(calls) == 1


def test_redirect_limit(public_dns, transport):
    calls, responses = transport
    redirects = [_response(status=302, headers={"Location": "/again"}) for _ in range(web._MAX_REDIRECTS + 1)]
    responses.extend(redirects)
    assert web.fetch_page("http://example.com/") == "Failed to fetch page: too many redirects."
    assert len(calls) == web._MAX_REDIRECTS + 1
    assert all(response.closed for response in redirects)


def test_bounded_read_encoding_and_text_limit(public_dns, transport, monkeypatch):
    monkeypatch.setattr(web, "_MAX_FETCH_BYTES", 100)
    calls, responses = transport
    response = _response(b"<p>caf\xe9 " + b"x" * 200, headers={"Content-Type": "text/html; charset=iso-8859-1"})
    read = Mock(wraps=response.read)
    response.read = read
    responses.append(response)
    text = web.fetch_page("http://example.com/", max_chars=20)
    assert text.startswith("café " + "x" * 15)
    assert "Content truncated at 20 chars" in text
    read.assert_called_once_with(101, decode_content=True)
    assert response.closed


def test_http_errors_close_response(public_dns, transport):
    _, responses = transport
    response = _response(status=404)
    responses.append(response)
    assert web.fetch_page("http://example.com/") == "Failed to fetch page: HTTP 404"
    assert response.closed


@pytest.mark.parametrize("tag", [
    "script", "style", "nav", "header", "footer", "noscript", "aside", "iframe", "svg",
])
def test_extract_text_omits_unreadable_elements(tag):
    assert web._extract_text(f"<p>Before</p><{tag}>Hidden</{tag}><p>After</p>") == "Before After"


@pytest.mark.parametrize("markup, expected", [
    ("<p>A &amp; B &#60;tag&#62; &amp;lt;</p>\n\n\n<p>C\t  D</p>", "A & B <tag> &lt; \n\n C D"),
    ("<NAV><aside>Hidden</aside><nav>Nested</nav>Hidden</NAV>Visible", "Visible"),
    ("Before<script><script><nav>Hidden</script>After", "Before After"),
    ("Before<style><style><aside>Hidden</style>After", "Before After"),
    ("Before<script>Hidden</style>Still hidden</script>After", "Before After"),
    ("<header>Hidden</header><headerish>Visible</headerish>", "Visible"),
    ("<svg/>Visible<br/>text", "Visible text"),
    ("Visible<script>Hidden", "Visible"),
    ("Visible<nav>Hidden", "Visible"),
    ("", ""),
])
def test_extract_text_handles_entities_nesting_and_malformed_html(markup, expected):
    assert web._extract_text(markup) == expected


def test_fetch_page_drops_unclosed_script_content(public_dns, transport):
    _, responses = transport
    responses.append(_response(b"<p>Visible &amp; readable</p><script>" * 2 + b"Hidden"))
    assert call_tool("fetch_page", {"url": "https://example.com/"}) == "Visible & readable"


@pytest.mark.parametrize("fragment", ["<script>", "<nav>", "<", "<a "])
def test_malformed_html_at_download_limit_finishes_promptly(fragment):
    # Isolate extraction so restoring a quadratic regex fails within a bounded
    # time instead of hanging the test runner on attacker-controlled HTML.
    source = textwrap.dedent("""\
        import sys
        from core.tools.web_search import _extract_text, _MAX_FETCH_BYTES

        fragment = sys.argv[1]
        payload = fragment * (_MAX_FETCH_BYTES // len(fragment))
        text = _extract_text('Visible' + payload)
        if fragment in ('<script>', '<nav>'):
            assert text == 'Visible'
        else:
            assert text == ('Visible' + payload).rstrip()
    """)
    subprocess.run(
        [sys.executable, "-c", source, fragment],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True, text=True, check=True, timeout=10,
    )
