import logging
import os
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


class SearchEngine:
    """Small adapter for the user's local SearXNG instance."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or os.getenv(
            "SEARXNG_BASE_URL", "http://localhost:8080"
        )).rstrip("/")
        self.last_error: Optional[str] = None
        self.any_results = False

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        self.last_error = None
        params = {"q": query, "format": "json"}
        timeout = httpx.Timeout(connect=8.0, read=20.0, write=8.0, pool=8.0)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(f"{self.base_url}/search", params=params)

                # JSON is enabled in this project's SearXNG settings. Some
                # installations disable it, so retain the existing HTML mode.
                if response.status_code in {400, 406, 415}:
                    response = await client.get(
                        f"{self.base_url}/search",
                        params={"q": query, "format": "html"},
                    )
            response.raise_for_status()
        except httpx.HTTPStatusError as error:
            self.last_error = f"HTTP {error.response.status_code}"
            logger.warning("SearXNG returned HTTP %s for query %r", error.response.status_code, query)
            return []
        except httpx.HTTPError as error:
            self.last_error = str(error)
            logger.warning("SearXNG request failed for query %r: %s", query, error)
            return []

        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or response.text.lstrip().startswith("{"):
            try:
                payload = response.json()
            except ValueError:
                self.last_error = "Invalid JSON response"
                logger.warning("SearXNG returned invalid JSON for query %r", query)
                return []
            results = self._parse_json(payload, limit)
            if results:
                self.any_results = True
            if not results:
                # SearXNG's default engine bundle can return an empty result
                # set when individual providers are throttled. Try Bing as a
                # free fallback through the same local SearXNG instance.
                # Bing's fallback did not honor LinkedIn-focused queries in
                # this setup, so keep it for general web/email lookups only.
                if "linkedin.com/in" not in query.lower():
                    try:
                        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                            fallback = await client.get(
                                f"{self.base_url}/search",
                                params={"q": query, "format": "json", "engines": "bing"},
                            )
                        fallback.raise_for_status()
                        fallback_payload = fallback.json()
                        fallback_results = self._parse_json(fallback_payload, limit)
                        if fallback_results:
                            self.any_results = True
                            self.last_error = None
                            return fallback_results
                        payload = fallback_payload
                    except (httpx.HTTPError, ValueError) as error:
                        logger.warning("SearXNG Bing fallback failed for query %r: %s", query, error)
                unresponsive = payload.get("unresponsive_engines", [])
                failed_engines = [
                    str(item[0])
                    for item in unresponsive
                    if isinstance(item, (list, tuple)) and item
                ]
                if failed_engines:
                    self.last_error = (
                        "No results; search engines unavailable: "
                        + ", ".join(dict.fromkeys(failed_engines))
                    )
                    logger.warning("SearXNG had no results; unavailable engines: %s", self.last_error)
            return results

        results = self._parse_html(response.text, limit)
        if results:
            self.any_results = True
        return results

    @staticmethod
    def _parse_html(document: str, limit: int) -> List[Dict[str, str]]:
        soup = BeautifulSoup(document, "html.parser")
        results = []
        for result in soup.select(".result"):
            link = result.select_one("a.url") or result.select_one("h3 a")
            if not link or not link.get("href"):
                continue
            title = result.select_one("h3")
            content = result.select_one(".content")
            results.append({
                "title": title.get_text(" ", strip=True) if title else "",
                "url": link["href"],
                "snippet": content.get_text(" ", strip=True) if content else "",
            })
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _parse_json(payload: dict, limit: int) -> List[Dict[str, str]]:
        results = []
        for item in payload.get("results", []):
            if not isinstance(item, dict) or not item.get("url"):
                continue
            results.append({
                "title": item.get("title", "") or "",
                "url": item["url"],
                "snippet": item.get("content", "") or item.get("snippet", "") or "",
            })
            if len(results) >= limit:
                break
        return results
