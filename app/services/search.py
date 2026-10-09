"""Search backends used by the fact-checking agent, behind one interface."""

import html
import re
from abc import ABC, abstractmethod
from urllib.parse import quote

import httpx

from app.schemas.fact_check import Source
from app.services.logger import get_logger

log = get_logger("search")
_TAG_RE = re.compile(r"<[^>]+>")


class SearchService(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, limit: int = 2) -> list[Source]:
        ...

    async def aclose(self) -> None:
        return None


class NullSearchService(SearchService):
    """Default: no search backend. Every claim is reported as unverified."""

    name = "none"

    async def search(self, query: str, limit: int = 2) -> list[Source]:
        return []


class WikipediaSearchService(SearchService):
    """Keyless full-text search over English Wikipedia (MediaWiki search API).

    Finding a related article does not verify a claim; results are labelled accordingly.
    """

    name = "wikipedia"
    API_URL = "https://en.wikipedia.org/w/api.php"

    def __init__(self, user_agent: str, timeout_seconds: float = 8.0,
                 transport: httpx.AsyncBaseTransport | None = None):
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds, headers={"User-Agent": user_agent}, transport=transport,
        )

    async def search(self, query: str, limit: int = 2) -> list[Source]:
        params = {"action": "query", "list": "search", "srsearch": query[:300],
                  "srlimit": limit, "format": "json", "utf8": 1}
        try:
            response = await self._client.get(self.API_URL, params=params)
            response.raise_for_status()
            results = response.json().get("query", {}).get("search", [])
        except (httpx.HTTPError, ValueError) as exc:
            # Search failure degrades to "unverified" rather than failing the request.
            log.warning("search failed", extra={"event": "search_error", "error_type": type(exc).__name__})
            return []
        sources = []
        for item in results[:limit]:
            title = item.get("title", "")
            snippet = html.unescape(_TAG_RE.sub("", item.get("snippet", "")))
            sources.append(Source(
                title=title,
                url=f"https://en.wikipedia.org/wiki/{quote(title.replace(' ', '_'))}",
                snippet=snippet,
            ))
        return sources

    async def aclose(self) -> None:
        await self._client.aclose()


def get_search_service(provider: str, user_agent: str, timeout_seconds: float = 8.0) -> SearchService:
    if provider == "wikipedia":
        return WikipediaSearchService(user_agent=user_agent, timeout_seconds=timeout_seconds)
    return NullSearchService()
