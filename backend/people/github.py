from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx


GITHUB_API = "https://api.github.com"

EMAIL_REGEX = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


class GitHubSource:
    """
    Finds public GitHub evidence associated with a person.

    Important:
    - Does NOT invent email addresses.
    - Does NOT treat GitHub noreply addresses as contact emails.
    - Uses LinkedIn slug as a discovery signal.
    - Uses GitHub API for direct profile lookup.
    - Searches public commits for additional evidence.
    """

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    async def _get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:

        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "JobReferralAgent/1.0",
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            ) as client:

                response = await client.get(
                    url,
                    params=params,
                    headers=headers,
                )

                if response.status_code == 404:
                    return None

                response.raise_for_status()

                return response.json()

        except Exception as error:
            print(
                f"GitHub request failed: "
                f"{type(error).__name__}: {error}"
            )
            return None

    # ---------------------------------------------------------
    # LinkedIn slug
    # ---------------------------------------------------------

    def extract_linkedin_slug(
        self,
        linkedin_url: Optional[str],
    ) -> Optional[str]:

        if not linkedin_url:
            return None

        try:
            parsed = urlparse(linkedin_url)

            path = parsed.path.strip("/")

            parts = path.split("/")

            if len(parts) >= 2 and parts[0].lower() == "in":
                slug = parts[1].strip()

                if slug:
                    return slug

        except Exception:
            pass

        return None

    # ---------------------------------------------------------
    # Direct GitHub profile lookup
    # ---------------------------------------------------------

    async def find_username_from_linkedin_slug(
        self,
        linkedin_url: Optional[str],
    ) -> Optional[str]:

        slug = self.extract_linkedin_slug(linkedin_url)

        if not slug:
            return None

        print(
            f'GitHub direct lookup using LinkedIn slug: "{slug}"'
        )

        profile = await self._get(
            f"{GITHUB_API}/users/{slug}"
        )

        if profile:
            login = profile.get("login")

            if login:
                print(
                    f"GitHub profile found directly: {login}"
                )

                return login

        print(
            "LinkedIn slug is not a GitHub username."
        )

        return None

    # ---------------------------------------------------------
    # GitHub user search
    # ---------------------------------------------------------

    async def search_users(
        self,
        name: str,
        company: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        query_parts = []

        if name:
            query_parts.append(f'"{name}"')

        if company:
            query_parts.append(f'company:"{company}"')

        query = " ".join(query_parts)

        print(f'GitHub user search: "{query}"')

        data = await self._get(
            f"{GITHUB_API}/search/users",
            params={
                "q": query,
                "per_page": 10,
            },
        )

        if not data:
            return []

        return data.get("items", [])

    # ---------------------------------------------------------
    # Get profile
    # ---------------------------------------------------------

    async def get_profile(
        self,
        username: str,
    ) -> Optional[Dict[str, Any]]:

        return await self._get(
            f"{GITHUB_API}/users/{username}"
        )

    # ---------------------------------------------------------
    # Public commits
    # ---------------------------------------------------------

    async def search_public_commits(
        self,
        name: str,
        company: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        query_parts = [f'"{name}"']

        if company:
            query_parts.append(f'"{company}"')

        query = " ".join(query_parts)

        print(
            f'GitHub commit search: "{query}"'
        )

        data = await self._get(
            f"{GITHUB_API}/search/commits",
            params={
                "q": query,
                "per_page": 10,
            },
        )

        if not data:
            return []

        return data.get("items", [])

    # ---------------------------------------------------------
    # Email validation
    # ---------------------------------------------------------

    @staticmethod
    def is_valid_email(email: Optional[str]) -> bool:

        if not email:
            return False

        email = email.strip().lower()

        if not EMAIL_REGEX.fullmatch(email):
            return False

        # GitHub-generated noreply addresses are not useful
        # as professional contact addresses.
        if "noreply" in email:
            return False

        if email.endswith("@users.noreply.github.com"):
            return False

        return True

    # ---------------------------------------------------------
    # Name similarity
    # ---------------------------------------------------------

    @staticmethod
    def normalize_name(value: Optional[str]) -> str:

        if not value:
            return ""

        value = value.lower()

        value = re.sub(
            r"[^a-z0-9\s]",
            " ",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    @classmethod
    def name_similarity(
        cls,
        expected_name: Optional[str],
        actual_name: Optional[str],
    ) -> float:

        expected = cls.normalize_name(expected_name)
        actual = cls.normalize_name(actual_name)

        if not expected or not actual:
            return 0.0

        expected_tokens = set(expected.split())
        actual_tokens = set(actual.split())

        if not expected_tokens:
            return 0.0

        intersection = expected_tokens & actual_tokens

        return len(intersection) / len(expected_tokens)

    # ---------------------------------------------------------
    # Collect profile email
    # ---------------------------------------------------------

    def profile_email_candidate(
        self,
        person: Dict[str, Any],
        profile: Dict[str, Any],
        username: str,
    ) -> Optional[Dict[str, Any]]:

        email = profile.get("email")

        if not self.is_valid_email(email):
            return None

        person_name = person.get("name")

        github_name = profile.get("name")

        similarity = self.name_similarity(
            person_name,
            github_name,
        )

        if similarity < 0.5:
            print(
                "GitHub profile email rejected because "
                "identity similarity is too low."
            )
            return None

        return {
            "email": email.strip().lower(),
            "source": "github_profile",
            "source_url": profile.get("html_url")
            or f"https://github.com/{username}",
            "github_username": username,
            "github_name": github_name,
            "identity_score": similarity,
            "evidence": {
                "github_profile": True,
                "name_match": similarity >= 0.5,
            },
        }

    # ---------------------------------------------------------
    # Collect commit email candidates
    # ---------------------------------------------------------

    def commit_email_candidates(
        self,
        person: Dict[str, Any],
        commits: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        results = []

        person_name = person.get("name")

        for commit in commits:

            commit_data = commit.get("commit") or {}

            author = commit_data.get("author") or {}

            email = author.get("email")
            commit_name = author.get("name")

            if not self.is_valid_email(email):
                continue

            similarity = self.name_similarity(
                person_name,
                commit_name,
            )

            if similarity < 0.5:
                print(
                    f"Rejected commit email {email}: "
                    f"name mismatch ({commit_name})"
                )
                continue

            html_url = commit.get("html_url")

            results.append(
                {
                    "email": email.strip().lower(),
                    "source": "github_public_commit",
                    "source_url": html_url,
                    "github_commit_author": commit_name,
                    "identity_score": similarity,
                    "evidence": {
                        "github_public_commit": True,
                        "name_match": similarity >= 0.5,
                    },
                }
            )

        return results

    # ---------------------------------------------------------
    # Main discovery function
    # ---------------------------------------------------------

    async def find_public_emails(
        self,
        person: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        name = person.get("name")
        company = person.get("company")
        linkedin_url = person.get("linkedin_url")

        if not name:
            return []

        print("\n========================================")
        print("GITHUB EMAIL DISCOVERY")
        print("========================================")
        print("Person:", name)
        print("Company:", company)
        print("LinkedIn:", linkedin_url)
        print("========================================")

        candidates: List[Dict[str, Any]] = []

        # -----------------------------------------------------
        # 1. Direct LinkedIn-slug → GitHub lookup
        # -----------------------------------------------------

        username = await self.find_username_from_linkedin_slug(
            linkedin_url
        )

        # -----------------------------------------------------
        # 2. GitHub search fallback
        # -----------------------------------------------------

        if not username:

            users = await self.search_users(
                name=name,
                company=company,
            )

            for user in users:

                login = user.get("login")

                if not login:
                    continue

                profile = await self.get_profile(login)

                if not profile:
                    continue

                similarity = self.name_similarity(
                    name,
                    profile.get("name"),
                )

                if similarity >= 0.5:

                    username = login

                    print(
                        f"GitHub candidate accepted: "
                        f"{login}"
                    )

                    break

        # -----------------------------------------------------
        # 3. Profile email
        # -----------------------------------------------------

        if username:

            profile = await self.get_profile(username)

            if profile:

                candidate = self.profile_email_candidate(
                    person,
                    profile,
                    username,
                )

                if candidate:
                    candidates.append(candidate)

        # -----------------------------------------------------
        # 4. Public commit emails
        # -----------------------------------------------------

        commits = await self.search_public_commits(
            name=name,
            company=company,
        )

        candidates.extend(
            self.commit_email_candidates(
                person,
                commits,
            )
        )

        # -----------------------------------------------------
        # 5. Deduplicate
        # -----------------------------------------------------

        unique = {}

        for candidate in candidates:

            email = candidate["email"]

            if email not in unique:
                unique[email] = candidate

        results = list(unique.values())

        print("\nGitHub email candidates:")

        for result in results:
            print(
                f"  {result['email']} "
                f"| {result['source']} "
                f"| score={result['identity_score']:.2f}"
            )

        print(
            f"Total GitHub email candidates: {len(results)}"
        )

        return results