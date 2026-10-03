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

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
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
            logger.warning("SearXNG returned HTTP %s for query %r", error.response.status_code, query)
            return []
        except httpx.HTTPError as error:
            logger.warning("SearXNG request failed for query %r: %s", query, error)
            return []

        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type or response.text.lstrip().startswith("{"):
            try:
                payload = response.json()
            except ValueError:
                logger.warning("SearXNG returned invalid JSON for query %r", query)
                return []
            return self._parse_json(payload, limit)

        return self._parse_html(response.text, limit)

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
