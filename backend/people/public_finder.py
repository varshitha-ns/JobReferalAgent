from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

from people.identity_verification import IdentityVerifier


EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


class PublicEmailFinder:

    def __init__(
        self,
        search_url: str = "http://localhost:8080",
    ):
        self.search_url = search_url.rstrip("/")

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:

        print(
            f'\nSearXNG search: "{query}"'
        )

        try:

            timeout = httpx.Timeout(
                connect=15,
                read=30,
                write=15,
                pool=15,
            )

            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
            ) as client:

                response = await client.get(
                    f"{self.search_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                    },
                )

                response.raise_for_status()

                data = response.json()

        except Exception as error:

            print(
                "SearXNG search failed:",
                type(error).__name__,
                str(error),
            )

            return []

        results = []

        for item in data.get(
            "results",
            [],
        )[:limit]:

            url = item.get("url")

            if not url:
                continue

            results.append(
                {
                    "title": item.get(
                        "title",
                        "",
                    ),
                    "url": url,
                    "snippet": item.get(
                        "content",
                        "",
                    ),
                }
            )

        print(
            f"SearXNG returned {len(results)} results."
        )

        return results

    # =========================================================
    # QUERY GENERATION
    # =========================================================

    def build_queries(
        self,
        person: Dict[str, Any],
    ) -> List[str]:

        name = person.get("name", "")
        company = person.get("company", "")
        title = person.get("title", "")
        linkedin_url = person.get(
            "linkedin_url",
            "",
        )

        queries = [
            f'"{name}" "{company}"',
            f'"{name}" "{company}" email',
            f'"{name}" "{company}" contact',
            f'"{name}" "{company}" developer',
            f'"{name}" "{company}" engineer',
            f'"{name}" "{company}" GitHub',
            f'site:github.com "{name}"',
            f'site:github.com "{name}" "{company}"',
        ]

        if title:
            queries.extend(
                [
                    f'"{name}" "{title}" "{company}"',
                    f'"{name}" "{title}" email',
                ]
            )

        # Extract LinkedIn slug.
        if "/in/" in linkedin_url:

            slug = (
                linkedin_url
                .split("/in/", 1)[1]
                .strip("/")
                .split("?", 1)[0]
            )

            if slug:
                queries.extend(
                    [
                        f'"{slug}" github',
                        f'"{slug}" email',
                        f'site:github.com "{slug}"',
                    ]
                )

        # Deduplicate.
        unique = []

        for query in queries:

            if query not in unique:
                unique.append(query)

        return unique

    # =========================================================
    # FETCH PAGE
    # =========================================================

    async def fetch_page(
        self,
        url: str,
    ) -> Optional[str]:

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "Chrome/154.0 Safari/537.36"
            )
        }

        try:

            async with httpx.AsyncClient(
                timeout=20,
                follow_redirects=True,
                headers=headers,
            ) as client:

                response = await client.get(url)

                if response.status_code != 200:
                    return None

                return response.text

        except Exception:

            return None

    # =========================================================
    # EMAIL EXTRACTION
    # =========================================================

    @staticmethod
    def extract_emails(
        text: str,
    ) -> List[str]:

        if not text:
            return []

        found = EMAIL_REGEX.findall(
            text
        )

        results = []

        for email in found:

            email = email.lower().strip()

            if (
                "noreply" in email
                or "example.com" in email
                or "example.org" in email
                or "example.net" in email
            ):
                continue

            if email not in results:
                results.append(email)

        return results

    def extract_page_content(
        self,
        html: str,
    ) -> str:

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        # Remove scripts/styles.
        for tag in soup(
            [
                "script",
                "style",
                "noscript",
            ]
        ):
            tag.decompose()

        return soup.get_text(
            " ",
            strip=True,
        )

    # =========================================================
    # RESULT RELEVANCE
    # =========================================================

    @staticmethod
    def is_probably_relevant(
        person: Dict[str, Any],
        result: Dict[str, Any],
    ) -> bool:

        name = (
            person.get("name")
            or ""
        ).lower()

        company = (
            person.get("company")
            or ""
        ).lower()

        title = (
            person.get("title")
            or ""
        ).lower()

        text = " ".join(
            [
                result.get(
                    "title",
                    "",
                ),
                result.get(
                    "snippet",
                    "",
                ),
                result.get(
                    "url",
                    "",
                ),
            ]
        ).lower()

        # Exact full name is strongest signal.
        name_parts = [
            part
            for part in re.findall(
                r"[a-z0-9]+",
                name,
            )
            if len(part) > 1
        ]

        if not name_parts:
            return False

        matched_name_parts = sum(
            1
            for part in name_parts
            if part in text
        )

        name_ratio = (
            matched_name_parts
            / len(name_parts)
        )

        company_match = (
            company
            and company in text
        )

        title_match = (
            title
            and any(
                token in text
                for token in title.split()
                if len(token) > 3
            )
        )

        # Require the person identity to be
        # reasonably represented.
        if name_ratio >= 0.75:
            return True

        if name_ratio >= 0.50 and (
            company_match
            or title_match
        ):
            return True

        return False

    # =========================================================
    # DISCOVERY
    # =========================================================

    async def find_public_emails(
        self,
        person: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        print()
        print("=" * 60)
        print("PUBLIC EMAIL DISCOVERY")
        print("=" * 60)

        queries = self.build_queries(
            person
        )

        candidates = []

        visited_urls = set()

        for query in queries:

            results = await self.search(
                query,
                limit=10,
            )

            for result in results:

                url = result["url"]

                if url in visited_urls:
                    continue

                visited_urls.add(url)

                # -----------------------------------------
                # Check relevance before trusting page.
                # -----------------------------------------

                if not self.is_probably_relevant(
                    person,
                    result,
                ):
                    print(
                        "Rejected unrelated result:",
                        result["title"],
                    )
                    continue

                # -----------------------------------------
                # Search snippet
                # -----------------------------------------

                snippet = result.get(
                    "snippet",
                    "",
                )

                snippet_emails = (
                    self.extract_emails(
                        snippet
                    )
                )

                for email in snippet_emails:

                    candidates.append(
                        {
                            "email": email,
                            "source": "search_snippet",
                            "source_url": url,
                            "person_name": person.get(
                                "name"
                            ),
                            "company": person.get(
                                "company"
                            ),
                            "evidence_text": (
                                result.get(
                                    "title",
                                    "",
                                )
                                + " "
                                + snippet
                            ),
                        }
                    )

                # -----------------------------------------
                # Fetch public page
                # -----------------------------------------

                html = await self.fetch_page(
                    url
                )

                if not html:
                    continue

                text = self.extract_page_content(
                    html
                )

                page_emails = (
                    self.extract_emails(
                        text
                    )
                )

                for email in page_emails:

                    candidates.append(
                        {
                            "email": email,
                            "source": "public_webpage",
                            "source_url": url,
                            "person_name": person.get(
                                "name"
                            ),
                            "company": person.get(
                                "company"
                            ),
                            "evidence_text": text[
                                :5000
                            ],
                        }
                    )

        # =====================================================
        # VERIFY IDENTITY
        # =====================================================

        verified = []

        for candidate in candidates:

            result = IdentityVerifier.verify(
                person,
                candidate,
            )

            candidate[
                "verification"
            ] = result

            if result["verified"]:

                candidate[
                    "status"
                ] = "verified_public"

                verified.append(
                    candidate
                )

            else:

                candidate[
                    "status"
                ] = "rejected"

        # =====================================================
        # DEDUPLICATE
        # =====================================================

        unique = {}

        for candidate in verified:

            email = candidate[
                "email"
            ]

            if email not in unique:
                unique[email] = candidate

        final = list(
            unique.values()
        )

        print()
        print("=" * 60)
        print("VERIFIED PUBLIC EMAILS")
        print("=" * 60)

        if not final:

            print(
                "No verified public email found."
            )

        for candidate in final:

            verification = candidate[
                "verification"
            ]

            print(
                f"Email: {candidate['email']}"
            )

            print(
                f"Source: {candidate['source']}"
            )

            print(
                f"URL: {candidate['source_url']}"
            )

            print(
                "Identity score:",
                verification[
                    "identity_score"
                ],
            )

            print(
                "Reasons:",
                verification[
                    "reasons"
                ],
            )

            print("-" * 60)

        return final