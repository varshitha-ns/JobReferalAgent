from typing import List
import asyncio
import logging
import re
from urllib.parse import urlparse

from people.schemas import (
    PersonProfile,
    ContactEvidence,
)
from people.sources.search_engine import SearchEngine


logger = logging.getLogger(__name__)


class PeopleDiscoveryAgent:

    COUNTRY_MARKERS = {
        "India": (
            "india", "bengaluru", "bangalore", "mumbai", "hyderabad", "chennai",
            "pune", "gurugram", "gurgaon", "noida", "new delhi", "kolkata",
            "ahmedabad", "kochi", "coimbatore",
        ),
        "United States": (
            "united states", "u.s.a.", "usa", "u.s.", "us-based", "united states of america",
        ),
        "Canada": ("canada",),
        "United Kingdom": ("united kingdom", "u.k.", "uk-based", "england", "scotland", "wales"),
        "Germany": ("germany",),
        "France": ("france",),
        "Australia": ("australia",),
        "Singapore": ("singapore",),
        "Ireland": ("ireland",),
        "Netherlands": ("netherlands",),
        "Spain": ("spain",),
        "Brazil": ("brazil",),
        "Japan": ("japan",),
    }

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

        # Run a small, focused batch concurrently. Serial searches made the
        # popup appear stuck when one free search provider was slow.
        search_results = await asyncio.gather(
            *(
                asyncio.wait_for(
                    self.search_engine.search(query=query, limit=10),
                    timeout=14.0,
                )
                for query in queries
            ),
            return_exceptions=True,
        )

        people = []
        seen_linkedin = set()

        for query, results in zip(queries, search_results):
            print(f"\nSearching: {query}")
            if isinstance(results, Exception):
                logger.warning("People search failed for %r: %s", query, results)
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
                    target_location=location,
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

        # Discover peers and the people most likely to route a referral.
        # Search exact role first, then broaden to engineering leaders and a
        # recruiting route. Avoid punctuation in locations because free search
        # providers can treat commas as query operators.
        clean_location = " ".join((location or "").replace(",", " ").split())
        role = " ".join(job_title.replace(",", " ").split())
        queries = []

        def add_query(*terms: str) -> None:
            parts = ["site:linkedin.com/in", company, *terms]
            if clean_location:
                parts.append(clean_location)
            query = " ".join(" ".join(parts).split())
            if query not in queries:
                queries.append(query)

        add_query(role)
        normalized_role = role.lower()
        if "software" in normalized_role or "engineer" in normalized_role:
            add_query("Software Engineer")
        if any(term in normalized_role for term in ("data engineer", "data engineering", "adf")):
            add_query("Data Engineer")
            add_query("Data Engineering Manager")
        if any(term in normalized_role for term in ("ai", "machine learning", "ml")):
            add_query("AI Engineer")
        if any(term in normalized_role for term in ("machine learning", "ml", "ai")):
            add_query("Machine Learning Engineer")
            add_query("AI Engineer")
        elif "data" in normalized_role:
            add_query("Data Engineer")
        elif "engineer" in normalized_role or "software" in normalized_role:
            add_query("Software Engineer")
        add_query("Engineering Manager")
        add_query("Technical Recruiter")
        add_query("Talent Acquisition")
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
        target_location: str | None = None,
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

        person_location = self._extract_location(evidence_text)
        location_verified = self._verify_location(
            person_location,
            evidence_text,
            target_location,
        )
        if location_verified is False:
            # Don't present an explicitly different city as a local contact.
            return None
        if not person_location and location_verified is True and target_location:
            person_location = target_location.split(",", 1)[0].strip()

        if self._is_former_employee(title, snippet, company):
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
            location=person_location,
            location_verified=location_verified,
            linkedin_url=linkedin_url,
            relevance_reasons=reasons,
            contact_evidence=[evidence],
        )

    @staticmethod
    def _extract_location(text: str) -> str | None:
        import re

        match = re.search(r"\bLocation:\s*([^·|\n]+)", text, re.IGNORECASE)
        return match.group(1).strip(" .,") if match else None

    @classmethod
    def _verify_location(
        cls,
        profile_location: str | None,
        evidence: str,
        target_location: str | None,
    ) -> bool | None:
        if not target_location:
            return None
        target_city = target_location.split(",", 1)[0].strip().casefold()
        if target_city in {"bangalore", "bengaluru"}:
            aliases = {"bangalore", "bengaluru"}
        else:
            aliases = {target_city} if target_city else set()
        evidence_lower = evidence.casefold()
        target_country = cls._country_in(target_location)
        observed_country = cls._country_in(profile_location or "") or cls._country_in(evidence)
        broad_target = bool(
            target_country
            and (target_city == target_country.casefold() or target_city.startswith("remote"))
        )

        if broad_target:
            # For country-scoped remote roles, require evidence for that
            # country; an unknown or foreign location is not a local match.
            return observed_country == target_country

        if target_city in {"remote", "worldwide", "global", "anywhere"}:
            return None

        if any(alias and alias in evidence_lower for alias in aliases):
            return True
        if not profile_location:
            # A city-specific role needs a city signal in the profile/search
            # evidence. Don't silently treat an unknown location as a match.
            return False
        place = profile_location.casefold()
        if any(alias and alias in place for alias in aliases):
            return True
        postal_prefixes = {
            "bengaluru": ("560",), "bangalore": ("560",),
            "hyderabad": ("500",), "chennai": ("600",),
            "mumbai": ("400",), "pune": ("411",),
            "delhi": ("110",), "gurugram": ("122",), "gurgaon": ("122",),
            "noida": ("201",),
        }
        digits = "".join(char for char in place if char.isdigit())
        if digits and any(digits.startswith(prefix) for prefix in postal_prefixes.get(target_city, ())):
            return True
        # Country/state-only labels are too coarse to confirm or contradict a
        # city. A named different metro/region is an explicit mismatch.
        coarse = {
            "india", "karnataka", "united states", "usa", "united kingdom",
            "uk", "canada", "germany", "france", "australia",
        }
        if place.strip(" .,") in coarse:
            return False
        return False

    @classmethod
    def _country_in(cls, value: str) -> str | None:
        normalized = " ".join(value.casefold().replace(".", " ").split())
        for country, markers in cls.COUNTRY_MARKERS.items():
            for marker in markers:
                marker_normalized = " ".join(marker.casefold().replace(".", " ").split())
                if marker_normalized and re.search(
                    rf"(?<![a-z]){re.escape(marker_normalized)}(?![a-z])",
                    normalized,
                ):
                    return country
        return None

    @staticmethod
    def _extract_name(
        title: str,
    ) -> str | None:

        if not title:
            return None

        # Typical search result:
        # "John Doe - Software Engineer - Microsoft | LinkedIn"

        import re

        cleaned = re.sub(r"\s*\|\s*LinkedIn\s*$", "", title, flags=re.IGNORECASE).strip()
        parts = re.split(r"\s+[\-–—|]\s+", cleaned, maxsplit=1)
        name = parts[0].strip() if parts else ""

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
    def _is_former_employee(title: str, snippet: str, company: str) -> bool:
        import re

        title_text = title.casefold()
        snippet_text = snippet.casefold()
        company_words = [
            word.casefold() for word in re.findall(r"[A-Za-z0-9]+", company)
            if len(word) >= 3
        ]
        if not company_words:
            return False
        company_in_title = any(word in title_text for word in company_words)
        company_in_snippet = any(word in snippet_text for word in company_words)
        if not company_in_snippet:
            return False

        former_marker = bool(re.search(r"\b(ex|former|formerly|previously)\b", title_text))
        if former_marker and not company_in_title:
            return True

        last_company_token = re.escape(company_words[-1])
        date_range = (
            r"(?:19|20)\d{2}\s*[–—-]\s*"
            r"(?:(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s*)?"
            r"(?:19|20)\d{2}"
        )
        company_date = re.search(
            rf"\b{last_company_token}\b.{{0,100}}?{date_range}",
            snippet_text,
            re.IGNORECASE,
        )
        current_company = re.search(
            rf"\b{last_company_token}\b.{{0,100}}?\b(present|current|now)\b",
            snippet_text,
            re.IGNORECASE,
        )
        return not company_in_title and bool(company_date) and not current_company

    @staticmethod
    def _extract_role(
        text: str,
    ) -> str | None:

        roles = [
            "Principal Data Engineer",
            "Staff Data Engineer",
            "Senior Data Engineer",
            "Associate Data Engineer",
            "Data Engineering Manager",
            "Data Engineering Lead",
            "Data Engineer",
            "Analytics Engineer",
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
            "Director of Engineering",
            "Head of Engineering",
            "Technical Recruiter",
            "Recruiter",
            "Talent Acquisition",
        ]

        text_lower = text.lower()

        for role in roles:

            if role.lower() in text_lower:
                return role

        return None
