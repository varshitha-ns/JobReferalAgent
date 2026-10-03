from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse


class IdentityVerifier:
    """
    Determines whether public evidence is actually associated
    with the target person.

    This does NOT verify that a mailbox exists.
    It verifies person/company/source association.
    """

    @staticmethod
    def normalize(value: Optional[str]) -> str:
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
    def tokens(cls, value: Optional[str]):
        normalized = cls.normalize(value)

        if not normalized:
            return set()

        return set(normalized.split())

    @classmethod
    def name_score(
        cls,
        target_name: Optional[str],
        text: str,
    ) -> float:

        target_tokens = cls.tokens(target_name)
        text_tokens = cls.tokens(text)

        if not target_tokens:
            return 0.0

        matched = target_tokens & text_tokens

        return len(matched) / len(target_tokens)

    @classmethod
    def company_score(
        cls,
        company: Optional[str],
        text: str,
    ) -> float:

        if not company:
            return 0.0

        company_normalized = cls.normalize(company)
        text_normalized = cls.normalize(text)

        if company_normalized in text_normalized:
            return 1.0

        company_tokens = cls.tokens(company)
        text_tokens = cls.tokens(text)

        if not company_tokens:
            return 0.0

        matched = company_tokens & text_tokens

        return len(matched) / len(company_tokens)

    @staticmethod
    def domain_from_email(email: str) -> str:
        return email.split("@")[-1].lower().strip()

    @staticmethod
    def domain_matches_company(
        email: str,
        company: Optional[str],
    ) -> Optional[bool]:

        if not company:
            return None

        domain = IdentityVerifier.domain_from_email(email)

        known_domains = {
            "microsoft": {
                "microsoft.com",
                "microsoftonline.com",
            },
            "google": {
                "google.com",
                "googlemail.com",
            },
            "amazon": {
                "amazon.com",
                "amazon.in",
            },
            "amazon web services": {
                "amazon.com",
                "amazonaws.com",
            },
            "meta": {
                "meta.com",
                "fb.com",
            },
            "apple": {
                "apple.com",
            },
            "infosys": {
                "infosys.com",
            },
            "tcs": {
                "tcs.com",
            },
            "wipro": {
                "wipro.com",
            },
            "capgemini": {
                "capgemini.com",
            },
            "accenture": {
                "accenture.com",
            },
        }

        company_key = company.lower().strip()

        allowed = known_domains.get(company_key)

        if not allowed:
            return None

        return domain in allowed

    @classmethod
    def verify(
        cls,
        person: Dict[str, Any],
        candidate: Dict[str, Any],
    ) -> Dict[str, Any]:

        name = person.get("name", "")
        company = person.get("company")

        email = (
            candidate.get("email")
            or ""
        ).lower().strip()

        source_url = candidate.get(
            "source_url",
            "",
        )

        evidence = (
            candidate.get("evidence_text")
            or ""
        )

        source = candidate.get(
            "source",
            "",
        )

        combined_text = " ".join(
            [
                str(candidate.get("person_name", "")),
                str(candidate.get("company", "")),
                evidence,
                source_url,
            ]
        )

        name_score = cls.name_score(
            name,
            combined_text,
        )

        company_score = cls.company_score(
            company,
            combined_text,
        )

        domain_match = cls.domain_matches_company(
            email,
            company,
        )

        source_score = 0.0

        if source == "github_profile":
            source_score = 1.0

        elif source == "github_public_commit":
            source_score = 0.9

        elif source == "public_webpage":
            source_score = 0.8

        elif source == "search_snippet":
            source_score = 0.5

        # -----------------------------------------
        # Identity decision
        # -----------------------------------------

        identity_score = (
            name_score * 0.55
            + company_score * 0.25
            + source_score * 0.20
        )

        reasons = []

        if name_score >= 0.75:
            reasons.append("strong_name_match")
        elif name_score >= 0.5:
            reasons.append("partial_name_match")
        else:
            reasons.append("weak_name_match")

        if company_score >= 0.75:
            reasons.append("strong_company_match")

        if domain_match is True:
            reasons.append("company_email_domain")

        if domain_match is False:
            reasons.append("company_domain_mismatch")

        # -----------------------------------------
        # Final decision
        # -----------------------------------------

        verified = False

        if (
            identity_score >= 0.70
            and name_score >= 0.50
            and domain_match is not False
            and source_score >= 0.80
        ):
            verified = True

        return {
            "verified": verified,
            "identity_score": round(
                identity_score,
                3,
            ),
            "name_score": round(
                name_score,
                3,
            ),
            "company_score": round(
                company_score,
                3,
            ),
            "domain_match": domain_match,
            "source_score": source_score,
            "reasons": reasons,
        }