from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from people.identity_verification import IdentityVerifier
from people.sources.search_engine import SearchEngine


EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


class PublicEmailFinder:

    def __init__(
        self,
        search_url: str = "http://localhost:8080",
        search_engine: Optional[SearchEngine] = None,
    ):
        self.search_url = search_url.rstrip("/")
        self.search_engine = search_engine or SearchEngine(self.search_url)
        self._robots_cache: Dict[str, Any] = {}
        self._company_domain_cache: Dict[str, Optional[str]] = {}

    # =========================================================
    # SEARCH
    # =========================================================

    async def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, str]]:

        return await self.search_engine.search(query=query, limit=limit)

    async def resolve_company_domain(self, company: str) -> Optional[str]:
        known = IdentityVerifier.primary_domain(company)
        if known:
            return known

        cache_key = " ".join(company.casefold().split())
        if cache_key in self._company_domain_cache:
            return self._company_domain_cache[cache_key]

        results = await self.search(f'"{company}" official website', limit=10)
        company_terms = [
            token.lower()
            for token in re.findall(r"[A-Za-z0-9]+", company)
            if len(token) >= 3
        ]
        blocked = {
            "linkedin.com", "facebook.com", "instagram.com", "x.com",
            "twitter.com", "youtube.com", "wikipedia.org", "glassdoor.com",
            "indeed.com", "naukri.com", "crunchbase.com",
        }
        for result in results:
            url = result.get("url", "")
            parsed = urlparse(url)
            host = (parsed.hostname or "").lower().removeprefix("www.")
            if parsed.scheme != "https" or not host or host in blocked:
                continue
            host_labels = set(host.split("."))
            if any(
                term in host_labels
                or any(label.startswith(term + "-") for label in host_labels)
                for term in company_terms
            ):
                self._company_domain_cache[cache_key] = host
                return host
        self._company_domain_cache[cache_key] = None
        return None

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
        company_domain = person.get("company_domain")

        queries = [
            f'"{name}" "{company}" email',
        ]

        if company_domain:
            queries.append(f'"{name}" "@{company_domain}"')

        if title:
            queries.append(f'"{name}" "{title}" "{company}" email')

        # LinkedIn is a discovery signal only. GitHub account discovery is
        # handled by GitHubSource; we don't search or fetch private LinkedIn.

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

        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            return None
        host = parsed.hostname.lower().removeprefix("www.")
        if host in {
            "linkedin.com", "facebook.com", "instagram.com", "x.com",
            "twitter.com", "youtube.com",
        }:
            return None
        if not await self._robots_allow(url):
            return None

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
                timeout=httpx.Timeout(connect=5, read=12, write=5, pool=5),
                follow_redirects=True,
                headers=headers,
            ) as client:

                response = await client.get(url)

                if response.status_code != 200:
                    return None

                if len(response.content) > 2_000_000:
                    return response.content[:2_000_000].decode(
                        response.encoding or "utf-8", errors="replace"
                    )
                return response.text

        except Exception:

            return None

    async def _robots_allow(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots_cache:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=4, read=5, write=4, pool=4),
                    follow_redirects=True,
                    headers={"User-Agent": "JobReferralAgent/1.0"},
                ) as client:
                    response = await client.get(f"{origin}/robots.txt")
                if response.status_code == 404:
                    self._robots_cache[origin] = None
                elif response.status_code == 200:
                    parser = RobotFileParser()
                    parser.set_url(f"{origin}/robots.txt")
                    parser.parse(response.text.splitlines())
                    self._robots_cache[origin] = parser
                else:
                    # Fail closed for 403, 429, and server errors.
                    self._robots_cache[origin] = False  # type: ignore[assignment]
            except Exception:
                self._robots_cache[origin] = False  # type: ignore[assignment]
        policy = self._robots_cache[origin]
        if policy is False:
            return False
        if policy is None:
            return True
        return policy.can_fetch("JobReferralAgent/1.0", url)

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

            local, _, domain = email.partition("@")

            if (
                "noreply" in email
                or "example.com" in email
                or "example.org" in email
                or "example.net" in email
                or domain in {
                    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in",
                    "hotmail.com", "outlook.com", "live.com", "icloud.com",
                    "protonmail.com", "proton.me", "rediffmail.com",
                }
                or local in {
                    "info", "hello", "contact", "support", "sales", "admin",
                    "help", "hr", "jobs", "careers", "recruiting", "noreply",
                    "no-reply", "webmaster",
                }
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

        text_tokens = set(re.findall(r"[a-z0-9]+", text))
        matched_name_parts = sum(part in text_tokens for part in name_parts)

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

        company = person.get("company", "")
        if not company or not person.get("name"):
            return []

        company_domain = person.get("company_domain")
        if not company_domain:
            company_domain = await self.resolve_company_domain(company)
        if not company_domain:
            print("No company domain evidence; declining to associate a work email.")
            return []

        lookup_person = {**person, "company_domain": company_domain}
        queries = self.build_queries(lookup_person)

        candidates = []

        visited_urls = set()

        for query in queries:

            results = await self.search(
                query,
                limit=10,
            )

            for result in results:

                url = result.get("url", "")
                if not url:
                    continue

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
                        result["title"].encode("ascii", errors="replace").decode("ascii"),
                    )
                    continue

                # -----------------------------------------
                # Search snippet
                # -----------------------------------------

                snippet = result.get(
                    "snippet",
                    "",
                )

                snippet_emails = self.extract_emails(snippet)

                for email in snippet_emails:

                    candidates.append(
                        {
                            "email": email,
                            "source": "search_snippet",
                            "source_url": url,
                            "company_domain": company_domain,
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

                html = await self.fetch_page(url)

                if not html:
                    continue

                text = self.extract_page_content(
                    html
                )

                page_emails = self.extract_emails(text)
                page_emails.extend(self._extract_mailto_emails(html))

                for email in page_emails:

                    candidates.append(
                        {
                            "email": email,
                            "source": "public_webpage",
                            "source_url": url,
                            "company_domain": company_domain,
                            "evidence_text": text[
                                :5000
                            ],
                        }
                    )

        # Verify only against text and profile fields originating from the
        # source. Do not add the lookup target's name/company as evidence.

        verified = []

        for candidate in candidates:

            result = IdentityVerifier.verify(lookup_person, candidate)

            candidate[
                "verification"
            ] = result

            if result["verified"]:

                candidate["status"] = "PUBLIC_EVIDENCE"

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
        print("PUBLIC EMAIL EVIDENCE")
        print("=" * 60)

        if not final:

            print(
                "No person-linked public company email found."
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

    @staticmethod
    def _extract_mailto_emails(html: str) -> List[str]:
        soup = BeautifulSoup(html, "html.parser")
        found = []
        for link in soup.select('a[href^="mailto:"]'):
            value = link.get("href", "").split(":", 1)[-1].split("?", 1)[0]
            found.extend(PublicEmailFinder.extract_emails(value))
        return list(dict.fromkeys(found))
