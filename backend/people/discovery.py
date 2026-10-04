from typing import List
import logging
from urllib.parse import urlparse

from people.schemas import (
    PersonProfile,
    ContactEvidence,
)
from people.sources.search_engine import SearchEngine


logger = logging.getLogger(__name__)


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

            try:
                results = await self.search_engine.search(query=query, limit=10)
            except Exception as error:
                # A failed query/source must not stop discovery from trying
                # the remaining role queries.
                logger.warning("People search failed for %r: %s", query, error)
                continue

            for result in results:

                linkedin_url = self._get_linkedin_profile(result.get("url", ""))

                if not linkedin_url:
                    continue

                if linkedin_url in seen_linkedin:
                    continue

                person = self._create_person(
                    result=result,
                    linkedin_url=linkedin_url,
                    company=company,
                )

                if person:
                    seen_linkedin.add(linkedin_url)
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

        # Use the plain query form validated against this instance. Prefer the
        # job location, then broaden once if fewer than the requested number of
        # profiles are found. The previous seven-query fan-out exhausted free
        # providers before email discovery could run.
        queries = []
        if location:
            queries.append(f"site:linkedin.com/in {company} {job_title} {location}")
        broad_query = f"site:linkedin.com/in {company} {job_title}"
        if broad_query not in queries:
            queries.append(broad_query)
        return queries

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

        title = (result.get("title", "") or "").strip()
        snippet = (result.get("snippet", "") or "").strip()
        evidence_text = f"{title} {snippet}"

        # Search terms are discovery signals only. The returned LinkedIn
        # result itself must mention the company and an in-scope role.
        company_terms = [
            token.lower()
            for token in company.replace("&", "and").split()
            if len(token) >= 3
        ]
        evidence_lower = evidence_text.lower()
        if not company_terms or not any(term in evidence_lower for term in company_terms):
            return None

        name = self._extract_name(title)

        if not name:
            return None

        role = self._extract_role(evidence_text)
        if not role:
            return None

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
            "Associate Software Engineer",
            "Associate AI Engineer",
            "Machine Learning Engineer",
            "AI Engineer",
            "ML Engineer",
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
