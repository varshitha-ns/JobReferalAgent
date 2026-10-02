
from typing import List, Dict

import httpx
from bs4 import BeautifulSoup


class SearchEngine:
    """
    Public web search adapter.

    This talks to a SearXNG instance and returns public search results.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
    ):
        self.base_url = base_url.rstrip("/")

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:

        params = {
            "q": query,
            "format": "html",
        }

        timeout = httpx.Timeout(
            connect=15.0,
            read=30.0,
            write=15.0,
            pool=15.0,
        )

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
        ) as client:

            response = await client.get(
                f"{self.base_url}/search",
                params=params,
            )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        results = []

        for result in soup.select(".result")[:limit]:

            link = result.select_one("a.url")

            if not link:
                link = result.select_one("h3 a")

            if not link:
                continue

            title_element = result.select_one("h3")
            content_element = result.select_one(".content")

            url = link.get("href")

            if not url:
                continue

            results.append(
                {
                    "title": (
                        title_element.get_text(
                            " ",
                            strip=True,
                        )
                        if title_element
                        else ""
                    ),
                    "url": url,
                    "snippet": (
                        content_element.get_text(
                            " ",
                            strip=True,
                        )
                        if content_element
                        else ""
                    ),
                }
            )

        return results