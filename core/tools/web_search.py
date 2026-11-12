"""Web search and intelligence tools for ClaudeOS agents.

Zero-config backends (no API key needed):
  - DuckDuckGo text + news search  (ddgs package)
  - Wikipedia REST API             (always free)
  - Web page fetch + text extract  (requests)

Enhanced backends (set keys in .env for better quality):
  - Brave Search API  BRAVE_SEARCH_KEY  — 2000 free/month, Google-quality results
  - Tavily API        TAVILY_API_KEY    — 1000 free/month, built for AI agents
  - NewsAPI           NEWSAPI_KEY       — 100 free/day, structured news with full dates

Tool names exposed to Claude via tool_use:
  web_search       — general web search (best available backend)
  get_news         — recent news on a topic
  search_wikipedia — instant factual lookup from Wikipedia
  multi_search     — run 2-5 queries in parallel (deep research mode)
  fetch_page       — read full text content of a URL
"""
from __future__ import annotations

import html
import ipaddress
import logging
import re
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

logger = logging.getLogger("claudeos.tools.web_search")

# ── Claude API tool definitions ───────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for current, real-time information. Use for: trending news, "
            "recent events, current prices, regulations, company info, market data, "
            "technical docs, product specs — anything that changes over time or that "
            "requires live verification. Always search before making claims about current state."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Specific search query. Include key terms and context.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Results to return (1–10). Default 3.",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_news",
        "description": (
            "Get recent news articles on a topic. Use for: breaking news, industry updates, "
            "market movements, policy changes, company announcements, current events. "
            "Returns articles with date, source, and URL."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "News topic or keyword. Be specific.",
                },
                "max_articles": {
                    "type": "integer",
                    "description": "Max articles to return (1–10). Default 3.",
                    "default": 3,
                },
            },
            "required": ["topic"],
        },
    },
    {
        "name": "search_wikipedia",
        "description": (
            "Look up factual information on Wikipedia. Use for: definitions, historical facts, "
            "company backgrounds, biographies, technical concepts, geography, science, "
            "established knowledge that needs a reliable overview."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look up. Can be a concept, name, place, or topic.",
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of Wikipedia articles to return (1–5). Default 2.",
                    "default": 2,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "multi_search",
        "description": (
            "Run 2–5 web searches simultaneously and get all results at once. "
            "Use for deep research: decompose a complex question into sub-questions, "
            "search all angles in parallel, get a comprehensive picture in one shot. "
            "More efficient than calling web_search multiple times."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "queries": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of 2–5 distinct search queries covering different angles.",
                    "minItems": 2,
                    "maxItems": 5,
                },
                "num_results_each": {
                    "type": "integer",
                    "description": "Results per query (1–5). Default 4.",
                    "default": 4,
                },
            },
            "required": ["queries"],
        },
    },
    {
        "name": "fetch_page",
        "description": (
            "Fetch and read the full text content of a specific web page or article URL. "
            "Use when you have a URL from search results and need the complete details, "
            "not just the snippet. Good for reading full articles, reports, or documentation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "Full URL to fetch (must start with http:// or https://).",
                },
            },
            "required": ["url"],
        },
    },
]

_TOOL_MAP = {t["name"]: t for t in TOOL_DEFINITIONS}


def get_definitions(tool_names: list[str]) -> list[dict]:
    """Return Claude tool definitions for the given tool name list."""
    return [_TOOL_MAP[n] for n in tool_names if n in _TOOL_MAP]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def call_tool(name: str, tool_input: dict) -> str:
    """Execute a tool by name. Returns string result for Claude tool_result."""
    try:
        if name == "web_search":
            results = web_search(
                query=tool_input.get("query", ""),
                num_results=min(int(tool_input.get("num_results", 6)), 10),
            )
            return _format_search_results(results) if results else "No results found. Try a different query."

        elif name == "get_news":
            articles = get_news(
                topic=tool_input.get("topic", ""),
                max_articles=min(int(tool_input.get("max_articles", 6)), 10),
            )
            return _format_news_results(articles) if articles else "No recent news found for this topic."

        elif name == "search_wikipedia":
            results = search_wikipedia(
                query=tool_input.get("query", ""),
                num_results=min(int(tool_input.get("num_results", 2)), 5),
            )
            return _format_search_results(results) if results else "No Wikipedia articles found."

        elif name == "multi_search":
            queries = tool_input.get("queries", [])[:5]
            n = min(int(tool_input.get("num_results_each", 4)), 5)
            return _run_multi_search(queries, n)

        elif name == "fetch_page":
            return fetch_page(tool_input.get("url", ""))

        else:
            return f"Unknown tool: {name}"

    except Exception as e:
        logger.warning("Tool %s failed: %s", name, e)
        return f"Tool error ({name}): {e}"


# ── Public search functions ───────────────────────────────────────────────────

def web_search(query: str, num_results: int = 6) -> list[dict]:
    """Search the web. Priority: Brave → Tavily → DuckDuckGo."""
    key = _get_key("BRAVE_SEARCH_KEY")
    if key:
        r = _brave_search(query, num_results, key)
        if r:
            return r

    key = _get_key("TAVILY_API_KEY")
    if key:
        r = _tavily_search(query, num_results, key)
        if r:
            return r

    return _ddg_search(query, num_results)


def get_news(topic: str, max_articles: int = 6) -> list[dict]:
    """Get news. Priority: NewsAPI → DuckDuckGo news."""
    key = _get_key("NEWSAPI_KEY")
    if key:
        r = _newsapi_search(topic, max_articles, key)
        if r:
            return r
    return _ddg_news(topic, max_articles)


def search_wikipedia(query: str, num_results: int = 2) -> list[dict]:
    """Wikipedia article search."""
    return _wikipedia_search(query, num_results)


def fetch_page(url: str, max_chars: int = 5000) -> str:
    """Fetch a web page and return readable text content."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return "Invalid URL: must start with http:// or https://"
    except Exception:
        return "Invalid URL format."

    try:
        import requests
        import urllib3
        from urllib.parse import urljoin
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        # Each hop gets its own pool, pinned to a validated numeric address.
        # Direct pools do not use environment proxies or resolve the hostname again.
        current = url
        for _ in range(_MAX_REDIRECTS + 1):
            try:
                prepared, address = _prepare_public_request(current, headers)
            except ValueError as e:
                return f"Blocked URL: {e}"
            target = urlparse(prepared.url)
            pool_type = urllib3.HTTPConnectionPool
            tls = {}
            if target.scheme == "https":
                pool_type = urllib3.HTTPSConnectionPool
                tls = {
                    "cert_reqs": "CERT_REQUIRED",
                    "ca_certs": requests.certs.where(),
                    "server_hostname": target.hostname,
                    "assert_hostname": target.hostname,
                }
            port = target.port or (443 if target.scheme == "https" else 80)
            with pool_type(address, port=port, **tls) as pool:
                with pool.urlopen(
                    "GET", prepared.path_url,
                    headers={**prepared.headers, "Host": target.netloc},
                    timeout=12, redirect=False, retries=False, preload_content=False,
                ) as resp:
                    location = resp.get_redirect_location()
                    if location:
                        current = urljoin(prepared.url, location)
                        continue
                    if resp.status >= 400:
                        return f"Failed to fetch page: HTTP {resp.status}"
                    raw = resp.read(_MAX_FETCH_BYTES + 1, decode_content=True)
                    encoding = requests.utils.get_encoding_from_headers(resp.headers) or "utf-8"
            break
        else:
            return "Failed to fetch page: too many redirects."
        text = _extract_text(raw[:_MAX_FETCH_BYTES].decode(encoding, errors="replace"))
        if not text:
            return "Page loaded but no readable text content found."
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n[Content truncated at {max_chars} chars — use a more specific URL for the full article]"
        return text
    except Exception as e:
        return f"Failed to fetch page: {e}"


_MAX_REDIRECTS = 4
_MAX_FETCH_BYTES = 2_000_000


def _prepare_public_request(url: str, headers: dict):
    """Prepare the actual URL and return it with a validated numeric destination."""
    import requests

    # Reject authority syntax that URL parsers can interpret differently, including
    # backslashes, userinfo, encoded hosts and scoped IPv6 addresses.
    if re.search(r"[\x00-\x1f\x7f]", url):
        raise ValueError("ambiguous URL syntax is not allowed")
    original = urlparse(url)
    if original.scheme not in ("http", "https") or not original.hostname:
        raise ValueError("only http(s) URLs are allowed")
    if re.search(r"[\\\s]", original.netloc):
        raise ValueError("ambiguous URL authority is not allowed")
    if original.username is not None or "%" in original.netloc:
        raise ValueError("userinfo and encoded hosts are not allowed")

    prepared = requests.Request("GET", url, headers=headers).prepare()
    parsed = urlparse(prepared.url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("only http(s) URLs are allowed")
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    try:
        infos = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM,
                                   proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError("host could not be resolved") from e
    if not infos:
        raise ValueError("host could not be resolved")
    addresses = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        checked_ip = ip.ipv4_mapped if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped else ip
        if not checked_ip.is_global:
            raise ValueError("private, loopback or link-local addresses are not allowed")
        addresses.append(str(ip))
    return prepared, addresses[0]


# ── Private: multi-search ─────────────────────────────────────────────────────

def _run_multi_search(queries: list[str], n: int) -> str:
    """Run all queries in parallel, return combined results."""
    if not queries:
        return "No queries provided."

    results_by_query: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        futures = {pool.submit(web_search, q, n): q for q in queries}
        for fut in as_completed(futures):
            q = futures[fut]
            try:
                results_by_query[q] = fut.result()
            except Exception as e:
                results_by_query[q] = []
                logger.warning("multi_search query failed (%s): %s", q, e)

    sections = []
    for q in queries:
        results = results_by_query.get(q, [])
        sections.append(f"### Query: \"{q}\"")
        if results:
            sections.append(_format_search_results(results))
        else:
            sections.append("No results found for this query.\n")

    return "\n".join(sections)


# ── Private: search backends ──────────────────────────────────────────────────

def _brave_search(query: str, num_results: int, api_key: str) -> list[dict]:
    try:
        import requests
        resp = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
            params={"q": query, "count": num_results, "search_lang": "en"},
            timeout=10,
        )
        resp.raise_for_status()
        results = []
        for r in resp.json().get("web", {}).get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            })
        return results
    except Exception as e:
        logger.warning("Brave search failed, trying next backend: %s", e)
        return []


def _tavily_search(query: str, num_results: int, api_key: str) -> list[dict]:
    try:
        import requests
        resp = requests.post(
            "https://api.tavily.com/search",
            json={"query": query, "max_results": num_results, "api_key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
        results = []
        for r in resp.json().get("results", []):
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            })
        return results
    except Exception as e:
        logger.warning("Tavily search failed, trying next backend: %s", e)
        return []


def _ddg_search(query: str, num_results: int = 6) -> list[dict]:
    try:
        from ddgs import DDGS
        results = []
        with DDGS(timeout=5) as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except ImportError:
        logger.error("ddgs not installed. Run: pip install ddgs")
        return []
    except Exception as e:
        logger.warning("DuckDuckGo search error: %s", e)
        return []


def _ddg_news(topic: str, max_articles: int = 6) -> list[dict]:
    try:
        from ddgs import DDGS
        results = []
        with DDGS(timeout=5) as ddgs:
            for r in ddgs.news(topic, max_results=max_articles):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "published": r.get("date", ""),
                    "source": r.get("source", ""),
                    "snippet": r.get("body", ""),
                })
        return results
    except ImportError:
        logger.error("ddgs not installed. Run: pip install ddgs")
        return []
    except Exception as e:
        logger.warning("DuckDuckGo news error: %s", e)
        return []


def _newsapi_search(topic: str, max_articles: int, api_key: str) -> list[dict]:
    try:
        import requests
        resp = requests.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": topic,
                "pageSize": max_articles,
                "sortBy": "publishedAt",
                "language": "en",
                "apiKey": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = []
        for a in resp.json().get("articles", []):
            results.append({
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "published": (a.get("publishedAt", "") or "")[:10],
                "source": a.get("source", {}).get("name", ""),
                "snippet": a.get("description", "") or a.get("content", "")[:200],
            })
        return results
    except Exception as e:
        logger.warning("NewsAPI search failed, falling back to DDG news: %s", e)
        return []


def _wikipedia_search(query: str, num_results: int = 2) -> list[dict]:
    try:
        import requests
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            headers={"User-Agent": "ClaudeOS/1.0 (internal research tool; contact@faiyke.ai)"},
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": num_results,
                "srprop": "snippet|titlesnippet",
                "format": "json",
                "utf8": 1,
            },
            timeout=8,
        )
        resp.raise_for_status()
        results = []
        for r in resp.json().get("query", {}).get("search", []):
            title = r.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", r.get("snippet", ""))
            results.append({
                "title": f"Wikipedia: {title}",
                "url": f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}",
                "snippet": snippet,
            })
        return results
    except Exception as e:
        logger.warning("Wikipedia search error: %s", e)
        return []


# ── Private: formatters ───────────────────────────────────────────────────────

def _format_search_results(results: list[dict]) -> str:
    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r['title']}")
        lines.append(f"    URL: {r['url']}")
        if r.get("snippet"):
            lines.append(f"    {r['snippet'][:350]}")
        lines.append("")
    return "\n".join(lines)


def _format_news_results(articles: list[dict]) -> str:
    lines = []
    for i, a in enumerate(articles, 1):
        meta = " | ".join(p for p in [a.get("published", ""), a.get("source", "")] if p)
        title_line = f"[{i}] {a['title']}"
        if meta:
            title_line += f"  ({meta})"
        lines.append(title_line)
        lines.append(f"    URL: {a['url']}")
        if a.get("snippet"):
            lines.append(f"    {a['snippet'][:300]}")
        lines.append("")
    return "\n".join(lines)


def _extract_text(html_content: str) -> str:
    """Strip HTML and return clean readable text."""
    ignored_tags = {"script", "style", "nav", "header", "footer", "noscript", "aside", "iframe", "svg"}
    hidden = []
    parts = []
    position = 0
    # Stop each token at another '<' as well as '>'. Failed matches cannot
    # rescan the same suffix, even for repeated unclosed or incomplete tags.
    for token in re.finditer(r"<[^<>]*>", html_content):
        if not hidden:
            parts.extend((html_content[position:token.start()], " "))
        tag = re.match(r"<(/?)([^\s/>]+)", token.group())
        if tag:
            closing, name = tag.groups()
            name = name.lower()
            if closing:
                if hidden and hidden[-1] == name:
                    hidden.pop()
            elif hidden and hidden[-1] in {"script", "style"}:
                # Script/style bodies are raw text, including apparent tags.
                pass
            elif name in ignored_tags and not token.group().endswith("/>"):
                hidden.append(name)
        position = token.end()
    if not hidden:
        parts.append(html_content[position:])
    text = "".join(parts)
    # Decode HTML entities
    text = html.unescape(text)
    # Normalize whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Private: config helper ────────────────────────────────────────────────────

def _get_key(key_name: str) -> str:
    """Safely read an API key from settings."""
    try:
        from core.config import get_settings
        return getattr(get_settings(), key_name, "") or ""
    except Exception:
        return ""
