import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

try:
    import dns.resolver
except ImportError:  # DNS enrichment is optional in minimal installations.
    dns = None

from people.sources.search_engine import SearchEngine
from people.github import GitHubPublicSource


EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\b"
)


GENERIC_LOCAL_PARTS = {
    "info",
    "hello",
    "contact",
    "support",
    "sales",
    "admin",
    "administrator",
    "help",
    "hr",
    "jobs",
    "careers",
    "recruiting",
    "recruitment",
    "marketing",
    "billing",
    "finance",
    "accounts",
    "legal",
    "privacy",
    "security",
    "webmaster",
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
}


BLOCKED_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.in",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "icloud.com",
    "protonmail.com",
    "proton.me",
    "rediffmail.com",
}


BLOCKED_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "twitter.com",
    "x.com",
}


class PublicEmailFinder:
    """
    Finds professional email addresses using public sources.

    This class deliberately does NOT guess an email and call it verified.

    Directly published email:
        public evidence; mailbox ownership remains unverified

    Pattern-generated email:
        verified = False
    """

    def __init__(
        self,
        search_engine: Optional[SearchEngine] = None,
        github_source=None,
    ):
        self.search_engine = search_engine or SearchEngine()
        self.github_source = github_source or GitHubPublicSource()

    async def find(
        self,
        person_name: str,
        company: str,
        linkedin_url: Optional[str] = None,
        company_domain: Optional[str] = None,
        max_results: int = 10,
    ) -> List[Dict]:

        print("\n========================================")
        print("PUBLIC EMAIL FINDER")
        print("Person:", person_name)
        print("Company:", company)
        print("LinkedIn:", linkedin_url)
        print("========================================")

        domain = company_domain

        if not domain:
            domain = await self._discover_company_domain(company)

        if domain:
            domain = self._normalize_domain(domain)

        print("Company domain:", domain)

        discovered = []

        # GitHub discovery uses the LinkedIn slug as a search signal only;
        # GitHubPublicSource verifies the candidate profile independently.
        try:
            github_result = await self.github_source.find_public_email(
                person_name=person_name,
                company=company,
                linkedin_url=linkedin_url,
            )
        except Exception as error:
            print("GitHub public source failed:", repr(error))
            github_result = None

        if github_result:
            candidate = dict(github_result)
            candidate.update({
                "person_name": person_name,
                "company": company,
                "company_domain": domain,
                "source": candidate.get("source", "github_public"),
                "verification_type": "PUBLIC_EVIDENCE",
                "verified": False,
                "evidence": "Email is publicly exposed on GitHub; this does not prove current mailbox control.",
            })
            # A known company domain is mandatory before associating any address.
            if self._is_valid_email(candidate.get("email", "")) and domain and self._same_domain(
                candidate["email"].split("@", 1)[1], domain
            ):
                discovered.append(candidate)

        # ---------------------------------------------------------
        # 1. Search public sources for the exact person.
        # ---------------------------------------------------------

        search_results = await self._search_person(
            person_name=person_name,
            company=company,
            domain=domain,
        )

        print(
            f"Public search returned {len(search_results)} results."
        )

        # ---------------------------------------------------------
        # 2. Inspect search results.
        # ---------------------------------------------------------

        for result in search_results:

            url = result.get("url", "")

            if not url:
                continue

            if self._is_blocked_host(url):
                continue

            # First inspect title/snippet because search engines
            # sometimes expose the email directly there.
            snippet_text = " ".join(
                [
                    result.get("title", ""),
                    result.get("snippet", ""),
                ]
            )

            snippet_emails = self._extract_emails(snippet_text)

            for email in snippet_emails:

                candidate = self._evaluate_email(
                    email=email,
                    person_name=person_name,
                    company=company,
                    domain=domain,
                    source_url=url,
                    source_text=snippet_text,
                )

                if candidate:
                    discovered.append(candidate)

            # -----------------------------------------------------
            # 3. Fetch public page and inspect it.
            # -----------------------------------------------------

            page_data = await self._fetch_page(url)

            if not page_data:
                continue

            page_text, page_html = page_data

            emails = set()

            for email in self._extract_emails(page_text):
                emails.add(email)

            # Also inspect mailto links.
            for email in self._extract_mailto_emails(
                page_html
            ):
                emails.add(email)

            for email in emails:

                candidate = self._evaluate_email(
                    email=email,
                    person_name=person_name,
                    company=company,
                    domain=domain,
                    source_url=url,
                    source_text=page_text,
                )

                if candidate:
                    discovered.append(candidate)

        # ---------------------------------------------------------
        # 4. Remove duplicates.
        # ---------------------------------------------------------

        discovered = self._deduplicate(discovered)

        # ---------------------------------------------------------
        # 5. Sort direct evidence first.
        # ---------------------------------------------------------

        discovered.sort(
            key=lambda item: (
                item["verified"],
                item["identity_score"],
                item["domain_verified"],
            ),
            reverse=True,
        )

        # ---------------------------------------------------------
        # 6. If no direct email was found, attempt pattern
        #    detection using other public company emails.
        # ---------------------------------------------------------

        if not discovered and domain:

            pattern_result = await self._find_company_pattern(
                company=company,
                domain=domain,
                target_name=person_name,
            )

            if pattern_result:
                discovered.append(pattern_result)

        return discovered[:max_results]

    # =============================================================
    # SEARCH
    # =============================================================

    async def _search_person(
        self,
        person_name: str,
        company: str,
        domain: Optional[str],
    ) -> List[Dict]:

        queries = [
            f'"{person_name}" "{company}" email',
            f'"{person_name}" "{company}" "@',
            f'"{person_name}" "{company}" contact',
            f'site:github.com "{person_name}" "{company}" email',
        ]

        if domain:
            queries.extend(
                [
                    f'site:{domain} "{person_name}"',
                    f'site:{domain} "{person_name}" "@{domain}"',
                    f'"{person_name}" "@{domain}"',
                ]
            )

        results = []

        seen_urls = set()

        for query in queries:

            print("Email search:", query)

            try:
                found = await self.search_engine.search(
                    query=query,
                    limit=10,
                )
            except Exception as error:
                print(
                    "Search failed:",
                    query,
                    repr(error),
                )
                continue

            for result in found:

                url = result.get("url")

                if not url:
                    continue

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                results.append(result)

        return results

    # =============================================================
    # COMPANY DOMAIN
    # =============================================================

    async def _discover_company_domain(
        self,
        company: str,
    ) -> Optional[str]:

        query = f'"{company}" official website'

        print("Domain discovery:", query)

        try:
            results = await self.search_engine.search(
                query=query,
                limit=10,
            )
        except Exception as error:
            print(
                "Domain discovery failed:",
                repr(error),
            )
            return None

        candidates = []

        for result in results:

            url = result.get("url")

            if not url:
                continue

            parsed = urlparse(url)

            host = parsed.netloc.lower()

            if not host:
                continue

            if host.startswith("www."):
                host = host[4:]

            if host in BLOCKED_HOSTS:
                continue

            if any(
                blocked in host
                for blocked in [
                    "linkedin.",
                    "facebook.",
                    "instagram.",
                    "twitter.",
                    "x.com",
                    "youtube.",
                    "wikipedia.",
                    "indeed.",
                    "glassdoor.",
                    "naukri.",
                ]
            ):
                continue

            company_terms = [
                token.lower()
                for token in re.findall(r"[a-zA-Z0-9]+", company)
                if len(token) >= 3
            ]
            evidence_text = " ".join(
                [host, result.get("title", ""), result.get("snippet", "")]
            ).lower()
            if not company_terms or not any(term in evidence_text for term in company_terms):
                continue

            candidates.append(host)

        if not candidates:
            return None

        # Prefer the first search-engine result.
        return candidates[0]

    # =============================================================
    # PAGE FETCHING
    # =============================================================

    async def _fetch_page(
        self,
        url: str,
    ) -> Optional[Tuple[str, str]]:

        try:

            timeout = httpx.Timeout(
                connect=10.0,
                read=20.0,
                write=10.0,
                pool=10.0,
            )

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 "
                    "(Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/154.0 Safari/537.36"
                )
            }

            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers=headers,
            ) as client:

                response = await client.get(url)

            if response.status_code >= 400:
                return None

            content_type = response.headers.get(
                "content-type",
                "",
            ).lower()

            if "text/html" not in content_type:
                return None

            html = response.text

            if len(html) > 2_000_000:
                html = html[:2_000_000]

            soup = BeautifulSoup(
                html,
                "html.parser",
            )

            for element in soup(
                [
                    "script",
                    "style",
                    "noscript",
                    "svg",
                ]
            ):
                element.decompose()

            text = soup.get_text(
                " ",
                strip=True,
            )

            return text, html

        except (
            httpx.HTTPError,
            UnicodeError,
        ) as error:

            print(
                "Page fetch failed:",
                url,
                repr(error),
            )

            return None

    # =============================================================
    # EMAIL EXTRACTION
    # =============================================================

    @staticmethod
    def _extract_emails(
        text: str,
    ) -> List[str]:

        if not text:
            return []

        emails = EMAIL_REGEX.findall(text)

        normalized = []

        for email in emails:

            email = email.strip(
                ".,;:!?()[]{}<>\"'"
            ).lower()

            if email not in normalized:
                normalized.append(email)

        return normalized

    @staticmethod
    def _extract_mailto_emails(
        html: str,
    ) -> List[str]:

        if not html:
            return []

        matches = re.findall(
            r'href=["\']mailto:([^"\'>?]+)',
            html,
            flags=re.IGNORECASE,
        )

        results = []

        for value in matches:

            value = value.strip().lower()

            if "@" not in value:
                continue

            if value not in results:
                results.append(value)

        return results

    # =============================================================
    # EMAIL EVALUATION
    # =============================================================

    def _evaluate_email(
        self,
        email: str,
        person_name: str,
        company: str,
        domain: Optional[str],
        source_url: str,
        source_text: str,
    ) -> Optional[Dict]:

        email = email.lower().strip()

        if not self._is_valid_email(email):
            return None

        # Without an independently supplied or discovered company domain,
        # we cannot connect this address to the employer.
        if not domain:
            return None

        email_domain = email.split("@", 1)[1]

        # If we know the company domain, require the email
        # to belong to that domain.
        if domain and not self._same_domain(
            email_domain,
            domain,
        ):
            return None

        identity_score = self._identity_score(
            person_name,
            source_text,
        )

        # Require a full exact name (all name tokens) in the same source as
        # the address. A company name plus one common first/last token is weak.
        if identity_score < len([p for p in re.findall(r"[a-zA-Z]+", person_name) if len(p) >= 2]):
            return None

        # The email itself must also identify the person, or be directly
        # described alongside the full name. Avoid attaching arbitrary
        # addresses just because a page mentions both the person and company.
        if not self._email_name_matches(email, person_name):
            return None

        domain_verified = self._has_mx_record(
            email_domain
        )

        return {
            "email": email,
            "source": "public_source",
            "source_url": source_url,
            "verified": False,
            "verification_type": "PUBLIC_EVIDENCE",
            "identity_score": identity_score,
            "domain_verified": domain_verified,
            "company": company,
            "company_domain": email_domain,
            "person_name": person_name,
            "evidence": "Email and full person name co-occur in this public source; mailbox ownership is not independently verified.",
        }

    # =============================================================
    # IDENTITY
    # =============================================================

    @staticmethod
    def _identity_score(
        person_name: str,
        text: str,
    ) -> int:

        name_parts = [
            part.lower()
            for part in re.findall(
                r"[a-zA-Z]+",
                person_name,
            )
            if len(part) >= 2
        ]

        normalized_text = re.sub(
            r"[^a-z0-9]+",
            " ",
            text.lower(),
        )

        score = 0

        for part in name_parts:
            if re.search(
                rf"\b{re.escape(part)}\b",
                normalized_text,
            ):
                score += 1

        return score

    @staticmethod
    def _email_name_matches(email: str, person_name: str) -> bool:
        local = email.split("@", 1)[0].lower()
        parts = [p.lower() for p in re.findall(r"[a-zA-Z]+", person_name)]
        if len(parts) < 2:
            return False
        first, last = parts[0], parts[-1]
        compact = re.sub(r"[^a-z0-9]", "", local)
        return compact in {first + last, last + first} or local in {
            f"{first}.{last}", f"{first}_{last}", f"{first}-{last}",
            f"{first[0]}{last}", f"{first[0]}.{last}",
        }

    # =============================================================
    # COMPANY EMAIL PATTERN
    # =============================================================

    async def _find_company_pattern(
        self,
        company: str,
        domain: str,
        target_name: str,
    ) -> Optional[Dict]:

        query = (
            f'site:{domain} '
            f'"@{domain}" '
            f'email'
        )

        print(
            "Searching company email pattern:",
            query,
        )

        try:
            results = await self.search_engine.search(
                query=query,
                limit=20,
            )
        except Exception as error:
            print(
                "Pattern search failed:",
                repr(error),
            )
            return None

        public_pairs = []

        for result in results:

            text = " ".join(
                [
                    result.get("title", ""),
                    result.get("snippet", ""),
                ]
            )

            for email in self._extract_emails(text):

                if not self._is_valid_email(email):
                    continue

                if not self._same_domain(
                    email.split("@")[1],
                    domain,
                ):
                    continue

                matched_name = self._find_name_for_email(text, email)
                if matched_name:
                    public_pairs.append((matched_name, email))

        pattern = self._detect_pattern(
            public_pairs,
            domain,
        )

        if not pattern:
            return None

        generated = self._generate_email(
            target_name,
            domain,
            pattern["pattern"],
        )

        if not generated:
            return None

        return {
            "email": generated,
            "source": "public_pattern",
            "source_url": None,
            "verified": False,
            "identity_score": 0,
            "domain_verified": self._has_mx_record(
                domain
            ),
            "company": company,
            "company_domain": domain,
            "person_name": target_name,
            "pattern": pattern["pattern"],
            "pattern_confidence": pattern[
                "confidence"
            ],
            "evidence_emails": [email for _, email in public_pairs],
            "verification_type": "PATTERN_INFERRED",
            "notes": [
                "Email was generated from a "
                "public company email pattern.",
                "This address is NOT directly "
                "verified for the target person.",
            ],
        }

    @staticmethod
    def _detect_pattern(
        name_email_pairs: List[Tuple[str, str]],
        domain: str,
    ) -> Optional[Dict]:

        patterns = {
            "first.last": [],
            "firstlast": [],
            "flast": [],
            "f.last": [],
            "first_last": [],
        }

        for name, email in name_email_pairs:
            parts = re.findall(r"[a-zA-Z]+", name.lower())
            if len(parts) < 2 or not email.lower().endswith("@" + domain.lower()):
                continue
            first, last = parts[0], parts[-1]
            local = email.split("@", 1)[0].lower()
            forms = {
                "first.last": f"{first}.{last}",
                "firstlast": f"{first}{last}",
                "flast": f"{first[0]}{last}",
                "f.last": f"{first[0]}.{last}",
                "first_last": f"{first}_{last}",
            }
            for key, expected in forms.items():
                if local == expected:
                    patterns[key].append((name.lower(), email.lower()))
        viable = [(key, pairs) for key, pairs in patterns.items() if len({n for n, _ in pairs}) >= 2]
        if not viable:
            return None
        key, pairs = max(viable, key=lambda item: len(item[1]))
        return {"pattern": key, "confidence": min(0.95, 0.7 + 0.1 * (len(pairs) - 2)), "pairs": pairs}

    @staticmethod
    def _find_name_for_email(text: str, email: str) -> Optional[str]:
        # Accept a name/email pair only when the email's local part maps
        # unambiguously to a full name printed in that same result.
        local = email.split("@", 1)[0].lower()
        candidates = re.findall(r"\b([A-Z][a-z]+(?:[ '-][A-Z][a-z]+){1,3})\b", text)
        for name in candidates:
            if PublicEmailFinder._email_name_matches(email, name):
                return name
        return None

    @staticmethod
    def _generate_email(
        full_name: str,
        domain: str,
        pattern: str,
    ) -> Optional[str]:

        parts = re.findall(
            r"[a-zA-Z]+",
            full_name.lower(),
        )

        if len(parts) < 2:
            return None

        first = parts[0]
        last = parts[-1]

        if pattern == "first.last":
            local = f"{first}.{last}"

        elif pattern == "firstlast":
            local = f"{first}{last}"

        elif pattern == "flast":
            local = f"{first[0]}{last}"

        elif pattern == "f.last":
            local = f"{first[0]}.{last}"

        elif pattern == "first_last":
            local = f"{first}_{last}"

        else:
            return None

        return f"{local}@{domain}"

    # =============================================================
    # VALIDATION
    # =============================================================

    @staticmethod
    def _is_valid_email(
        email: str,
    ) -> bool:

        if not EMAIL_REGEX.fullmatch(email):
            return False

        local, domain = email.split("@", 1)

        if local.lower() in GENERIC_LOCAL_PARTS:
            return False

        if domain.lower() in BLOCKED_EMAIL_DOMAINS:
            return False

        return True

    @staticmethod
    def _same_domain(
        email_domain: str,
        company_domain: str,
    ) -> bool:

        email_domain = email_domain.lower().removeprefix("www.")

        company_domain = company_domain.lower().removeprefix("www.")

        return (
            email_domain == company_domain
            or email_domain.endswith(
                "." + company_domain
            )
        )

    @staticmethod
    def _normalize_domain(
        domain: str,
    ) -> str:

        domain = domain.strip().lower()

        if "://" in domain:
            domain = urlparse(domain).netloc

        domain = domain.split("/")[0]
        domain = domain.split(":")[0]

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    @staticmethod
    def _is_blocked_host(
        url: str,
    ) -> bool:

        try:
            host = urlparse(url).netloc.lower()
        except Exception:
            return True

        if host.startswith("www."):
            host = host[4:]

        return host in BLOCKED_HOSTS

    # =============================================================
    # DNS / MX
    # =============================================================

    @staticmethod
    def _has_mx_record(
        domain: str,
    ) -> bool:

        if dns is None:
            return False

        try:
            dns.resolver.resolve(
                domain,
                "MX",
                lifetime=5,
            )
            return True

        except Exception:
            return False

    # =============================================================
    # DEDUPLICATION
    # =============================================================

    @staticmethod
    def _deduplicate(
        results: List[Dict],
    ) -> List[Dict]:

        seen = set()
        output = []

        for result in results:

            email = result.get("email")

            if not email:
                continue

            if email in seen:
                continue

            seen.add(email)
            output.append(result)

        return output
