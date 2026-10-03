import re
from typing import Optional
from urllib.parse import urlparse

import httpx

from people.sources.search_engine import SearchEngine


EMAIL_REGEX = re.compile(
    r"\b[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+\b"
)


GENERIC_EMAIL_DOMAINS = {
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
}


class GitHubPublicSource:

    BASE_URL = "https://api.github.com"

    def __init__(self):

        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "JobReferralAgent/1.0",
        }

        # Reuse our existing SearXNG search engine.
        self.search_engine = SearchEngine()

    # ============================================================
    # MAIN ENTRY POINT
    # ============================================================

    async def find_public_email(
        self,
        person_name: str,
        company: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        github_username: Optional[str] = None,
    ) -> Optional[dict]:

        print("\n========================================")
        print("GITHUB PUBLIC SOURCE")
        print("Person:", person_name)
        print("Company:", company)
        print("LinkedIn:", linkedin_url)
        print("========================================")

        # --------------------------------------------------------
        # 1. If we already know the GitHub username, use it.
        # --------------------------------------------------------

        if not github_username:

            github_username = await self.find_username(
                person_name=person_name,
                company=company,
                linkedin_url=linkedin_url,
            )

        if not github_username:

            print("GitHub username not found.")

            return None

        print(
            "GitHub username found:",
            github_username,
        )

        # --------------------------------------------------------
        # 2. Get the public GitHub profile.
        # --------------------------------------------------------

        profile = await self.get_profile(
            github_username
        )

        if not profile:

            print(
                "Could not retrieve GitHub profile."
            )

            return None

        profile_score = self._identity_score(
            person_name=person_name,
            company=company,
            profile=profile,
        )

        print(
            "GitHub profile identity score:",
            profile_score,
        )

        # We require strong identity evidence.
        if profile_score < 2:

            print(
                "GitHub profile identity is not strong enough."
            )

            return None

        # --------------------------------------------------------
        # 3. Check public profile email.
        # --------------------------------------------------------

        email = profile.get("email")

        if email and self._is_real_email(email):

            if self._matches_company_domain(
                email=email,
                company=company,
            ):

                return {
                    "email": email.lower(),
                    "source": "github_public_profile",
                    "source_url": (
                        f"https://github.com/"
                        f"{github_username}"
                    ),
                    "verified": False,
                    "verification_type": (
                        "PUBLIC_EVIDENCE"
                    ),
                    "evidence": "Address is publicly listed on the GitHub profile; this does not establish current mailbox ownership.",
                    "github_username": github_username,
                    "github_name": profile.get("name"),
                    "github_company": profile.get(
                        "company"
                    ),
                    "identity_score": profile_score,
                }

        # --------------------------------------------------------
        # 4. Check public commits.
        # --------------------------------------------------------

        result = await self.search_public_commits(
            github_username=github_username,
            person_name=person_name,
            company=company,
        )

        if result:

            result["github_name"] = profile.get(
                "name"
            )

            result["github_company"] = profile.get(
                "company"
            )

            result["identity_score"] = profile_score

            return result

        print(
            "No usable public GitHub email found."
        )

        return None

    # ============================================================
    # FIND GITHUB USERNAME THROUGH SEARXNG
    # ============================================================

    async def find_username(
        self,
        person_name: str,
        company: Optional[str] = None,
        linkedin_url: Optional[str] = None,
    ) -> Optional[str]:

        linkedin_handle = self._extract_linkedin_handle(
            linkedin_url
        )

        queries = []

        # Strongest query when LinkedIn slug is available.
        if linkedin_handle:

            queries.append(
                f'"{linkedin_handle}" github'
            )

            queries.append(
                f'"{linkedin_handle}" '
                f'"{person_name}" github'
            )

        queries.append(
            f'"{person_name}" github'
        )

        if company:

            queries.append(
                f'"{person_name}" '
                f'"{company}" github'
            )

            queries.append(
                f'site:github.com '
                f'"{person_name}" '
                f'"{company}"'
            )

        seen_urls = set()

        for query in queries:

            print(
                "\nGitHub discovery search:",
                query,
            )

            try:

                results = await self.search_engine.search(
                    query=query,
                    limit=10,
                )

            except Exception as error:

                print(
                    "SearXNG GitHub search failed:",
                    repr(error),
                )

                continue

            for result in results:

                url = result.get("url", "")

                github_username = (
                    self._extract_github_username(url)
                )

                if not github_username:
                    continue

                if github_username in seen_urls:
                    continue

                seen_urls.add(github_username)

                print(
                    "GitHub candidate:",
                    github_username,
                )

                profile = await self.get_profile(
                    github_username
                )

                if not profile:
                    continue

                score = self._identity_score(
                    person_name=person_name,
                    company=company,
                    profile=profile,
                    linkedin_handle=linkedin_handle,
                    search_result=result,
                )

                print(
                    "Candidate:",
                    github_username,
                    "identity score:",
                    score,
                )

                if score >= 2:

                    print(
                        "Accepted GitHub profile:",
                        github_username,
                    )

                    return github_username

        return None

    # ============================================================
    # GITHUB PROFILE
    # ============================================================

    async def get_profile(
        self,
        username: str,
    ) -> Optional[dict]:

        try:

            async with httpx.AsyncClient(
                timeout=15,
                headers=self.headers,
            ) as client:

                response = await client.get(
                    f"{self.BASE_URL}/users/{username}"
                )

            if response.status_code != 200:

                print(
                    "GitHub profile HTTP status:",
                    response.status_code,
                )

                return None

            return response.json()

        except httpx.HTTPError as error:

            print(
                "GitHub profile request failed:",
                repr(error),
            )

            return None

    # ============================================================
    # PUBLIC COMMITS
    # ============================================================

    async def search_public_commits(
        self,
        github_username: str,
        person_name: str,
        company: Optional[str] = None,
    ) -> Optional[dict]:

        params = {
            "q": f"author:{github_username}",
            "per_page": 30,
        }

        try:

            async with httpx.AsyncClient(
                timeout=20,
                headers=self.headers,
            ) as client:

                response = await client.get(
                    f"{self.BASE_URL}/search/commits",
                    params=params,
                )

            if response.status_code != 200:

                print(
                    "GitHub commit search failed:",
                    response.status_code,
                )

                return None

            data = response.json()

        except httpx.HTTPError as error:

            print(
                "GitHub commit search failed:",
                repr(error),
            )

            return None

        for item in data.get("items", []):

            commit = item.get("commit", {})

            author = commit.get("author") or {}

            name = author.get("name")
            email = author.get("email")

            if not email:
                continue

            if not self._is_real_email(email):
                continue

            # We don't want GitHub's anonymous noreply
            # addresses.
            if self._is_github_noreply(email):
                continue

            # A commit email is only useful for us if it
            # matches the company domain when we know it.
            if company and not self._matches_company_domain(
                email=email,
                company=company,
            ):
                continue

            identity_score = self._name_similarity(
                person_name,
                name or "",
            )

            if identity_score < 0.8:
                continue

            print(
                "Public GitHub commit email found:",
                email,
            )

            return {
                "email": email.lower(),
                "source": "github_public_commit",
                "source_url": item.get(
                    "html_url"
                ),
                # This is public evidence, but we
                # should not claim that a historical
                # commit proves the address is current.
                "verified": False,
                "verification_type": "PUBLIC_EVIDENCE",
                "evidence": "Address appeared in a public commit authored under this GitHub account; this does not establish current mailbox ownership.",
                "github_username": github_username,
                "commit_author": name,
                "identity_similarity": identity_score,
                "notes": [
                    "Email was exposed in a "
                    "public GitHub commit.",
                    "Historical commit evidence does "
                    "not guarantee the address is "
                    "currently active.",
                ],
            }

        return None

    # ============================================================
    # IDENTITY SCORING
    # ============================================================

    @staticmethod
    def _identity_score(
        person_name: str,
        company: Optional[str],
        profile: dict,
        linkedin_handle: Optional[str] = None,
        search_result: Optional[dict] = None,
    ) -> int:

        score = 0

        # --------------------------------------------------------
        # Name match
        # --------------------------------------------------------

        target_parts = {
            x.lower()
            for x in re.findall(
                r"[a-zA-Z]+",
                person_name,
            )
            if len(x) >= 2
        }

        github_name = profile.get("name") or ""

        github_parts = {
            x.lower()
            for x in re.findall(
                r"[a-zA-Z]+",
                github_name,
            )
            if len(x) >= 2
        }

        overlap = target_parts & github_parts

        if len(overlap) >= 2:
            score += 2

        elif len(overlap) == 1:
            score += 1

        # --------------------------------------------------------
        # Company match
        # --------------------------------------------------------

        github_company = (
            profile.get("company") or ""
        ).lower()

        if company:

            company_lower = company.lower()

            if (
                company_lower in github_company
                or github_company in company_lower
            ):
                score += 1

        # --------------------------------------------------------
        # LinkedIn handle / search-result evidence
        # --------------------------------------------------------

        if linkedin_handle and search_result:

            search_text = " ".join(
                [
                    search_result.get(
                        "title",
                        "",
                    ),
                    search_result.get(
                        "snippet",
                        "",
                    ),
                    search_result.get(
                        "content",
                        "",
                    ),
                ]
            ).lower()

            if linkedin_handle.lower() in search_text:
                score += 1

        return score

    # ============================================================
    # URL HELPERS
    # ============================================================

    @staticmethod
    def _extract_github_username(
        url: str,
    ) -> Optional[str]:

        try:

            parsed = urlparse(url)

            hostname = parsed.netloc.lower()

            if hostname != "github.com":
                return None

            path_parts = [
                part
                for part in parsed.path.split("/")
                if part
            ]

            if len(path_parts) != 1:
                return None

            username = path_parts[0]

            blocked = {
                "features",
                "topics",
                "trending",
                "collections",
                "marketplace",
                "explore",
                "login",
                "signup",
                "settings",
                "orgs",
                "organizations",
                "about",
                "pricing",
                "security",
            }

            if username.lower() in blocked:
                return None

            return username

        except Exception:
            return None

    @staticmethod
    def _extract_linkedin_handle(
        linkedin_url: Optional[str],
    ) -> Optional[str]:

        if not linkedin_url:
            return None

        value = linkedin_url.strip().rstrip("/")

        if "/in/" not in value:
            return None

        return value.split(
            "/in/",
            1,
        )[1].split(
            "/",
            1,
        )[0]

    # ============================================================
    # EMAIL VALIDATION
    # ============================================================

    @staticmethod
    def _is_real_email(
        email: str,
    ) -> bool:

        email = email.strip().lower()

        if not EMAIL_REGEX.fullmatch(email):
            return False

        if email.endswith(
            "@users.noreply.github.com"
        ):
            return False

        return True

    @staticmethod
    def _is_github_noreply(
        email: str,
    ) -> bool:

        email = email.lower()

        return (
            "noreply" in email
            or "users.noreply.github.com" in email
        )

    @staticmethod
    def _matches_company_domain(
        email: str,
        company: Optional[str],
    ) -> bool:

        if not company:
            return True

        email_domain = email.lower().split(
            "@",
            1,
        )[-1]

        company_lower = company.lower()

        # Microsoft-specific mapping for this test.
        # We'll replace this with our company-domain
        # resolver in the next stage.
        known_domains = {
            "microsoft": {
                "microsoft.com",
                "microsoftonline.com",
            },
        }

        if company_lower in known_domains:
            return (
                email_domain
                in known_domains[company_lower]
            )

        # For unknown companies, don't reject merely
        # because we don't yet know their domain.
        return True

    # ============================================================
    # NAME SIMILARITY
    # ============================================================

    @staticmethod
    def _name_similarity(
        first: str,
        second: str,
    ) -> float:

        a = {
            x.lower()
            for x in re.findall(
                r"[a-zA-Z]+",
                first,
            )
            if len(x) >= 2
        }

        b = {
            x.lower()
            for x in re.findall(
                r"[a-zA-Z]+",
                second,
            )
            if len(x) >= 2
        }

        if not a or not b:
            return 0.0

        return len(a & b) / max(
            len(a),
            len(b),
        )
