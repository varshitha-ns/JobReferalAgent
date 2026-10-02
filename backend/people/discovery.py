from typing import List
from urllib.parse import urlparse

from people.schemas import (
    PersonProfile,
    ContactEvidence,
)
from people.sources.search_engine import SearchEngine


class PeopleDiscoveryAgent:

    def __init__(self):
        self.search_engine = SearchEngine()

    async def discover(
        self,
        company: str,
        job_title: str,
        location: str | None = None,
        limit: int = 10,
    ) -> List[PersonProfile]:

        queries = self._build_queries(
            company,
            job_title,
            location,
        )

        people = []
        seen_linkedin = set()

        for query in queries:

            print(f"\nSearching: {query}")

            results = await self.search_engine.search(
                query=query,
                limit=10,
            )

            for result in results:

                linkedin_url = self._get_linkedin_profile(
                    result["url"]
                )

                if not linkedin_url:
                    continue

                if linkedin_url in seen_linkedin:
                    continue

                seen_linkedin.add(linkedin_url)

                person = self._create_person(
                    result=result,
                    linkedin_url=linkedin_url,
                    company=company,
                )

                if person:
                    people.append(person)

                if len(people) >= limit:
                    return people

        return people

    def _build_queries(
        self,
        company: str,
        job_title: str,
        location: str | None,
    ) -> List[str]:

        location_part = (
            f' "{location}"'
            if location
            else ""
        )

        return [
            f'site:linkedin.com/in/ "{company}" "{job_title}"{location_part}',

            f'site:linkedin.com/in/ "{company}" "Software Engineer"{location_part}',

            f'site:linkedin.com/in/ "{company}" "Senior Software Engineer"{location_part}',

            f'site:linkedin.com/in/ "{company}" "Engineering Manager"{location_part}',

            f'site:linkedin.com/in/ "{company}" "Technical Recruiter"{location_part}',

            f'site:linkedin.com/in/ "{company}" "Talent Acquisition"{location_part}',
        ]

    @staticmethod
    def _get_linkedin_profile(
        url: str,
    ) -> str | None:

        try:
            parsed = urlparse(url)

            hostname = parsed.netloc.lower()

            if not (
                hostname == "linkedin.com"
                or hostname.endswith(".linkedin.com")
            ):
                return None

            path = parsed.path.rstrip("/")

            # We only accept actual person profiles.
            if not path.startswith("/in/"):
                return None

            parts = path.split("/")

            if len(parts) < 3:
                return None

            profile_slug = parts[2].strip()

            if not profile_slug:
                return None

            return (
                f"https://www.linkedin.com/in/"
                f"{profile_slug}/"
            )

        except Exception:
            return None

    def _create_person(
        self,
        result: dict,
        linkedin_url: str,
        company: str,
    ) -> PersonProfile | None:

        title = result.get("title", "").strip()
        snippet = result.get("snippet", "").strip()

        name = self._extract_name(title)

        if not name:
            return None

        role = self._extract_role(
            f"{title} {snippet}"
        )

        evidence = ContactEvidence(
            source_url=result["url"],
            source_type="public_search_result",
            evidence=(
                f"Title: {title}. "
                f"Snippet: {snippet}"
            ),
        )

        reasons = [
            f"Public LinkedIn profile associated with {company}"
        ]

        if role:
            reasons.append(
                f"Search result indicates role: {role}"
            )

        return PersonProfile(
            name=name,
            current_company=company,
            current_role=role,
            linkedin_url=linkedin_url,
            relevance_reasons=reasons,
            contact_evidence=[evidence],
        )

    @staticmethod
    def _extract_name(
        title: str,
    ) -> str | None:

        if not title:
            return None

        # Typical search result:
        # "John Doe - Software Engineer - Microsoft | LinkedIn"

        cleaned = title.replace(
            " | LinkedIn",
            "",
        ).strip()

        parts = cleaned.split(" - ")

        if not parts:
            return None

        name = parts[0].strip()

        if not name:
            return None

        # Reject obvious non-person results.
        blocked = {
            "linkedin",
            "microsoft",
            "software engineer",
            "jobs",
            "people",
        }

        if name.lower() in blocked:
            return None

        return name

    @staticmethod
    def _extract_role(
        text: str,
    ) -> str | None:

        roles = [
            "Principal Software Engineer",
            "Staff Software Engineer",
            "Senior Software Engineer",
            "Software Engineer",
            "Engineering Manager",
            "Engineering Lead",
            "Technical Lead",
            "Tech Lead",
            "Technical Recruiter",
            "Recruiter",
            "Talent Acquisition",
        ]

        text_lower = text.lower()

        for role in roles:

            if role.lower() in text_lower:
                return role

        return None