import re
from typing import Optional

from people.schemas import (
    ContactEvidence,
    PersonProfile,
    VerificationStatus,
)


EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+"
    r"@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)


class EmailDiscovery:

    async def discover(
        self,
        person: PersonProfile,
        search_engine,
    ) -> PersonProfile:

        queries = self._build_queries(
            person
        )

        for query in queries:

            results = await search_engine.search(
                query=query,
                limit=10,
            )

            for result in results:

                email = self._extract_valid_email(
                    result
                )

                if not email:
                    continue

                # IMPORTANT:
                # Do not accept an email merely because
                # it appeared in a search result.
                #
                # It must pass our identity checks.

                if not self._result_matches_person(
                    person,
                    result,
                    email,
                ):
                    continue

                person.public_email = email

                person.verification_status = (
                    VerificationStatus.EMAIL_FOUND
                )

                person.email_verification_method = (
                    "public_source_identity_match"
                )

                person.contact_evidence.append(
                    ContactEvidence(
                        source_url=result["url"],
                        source_type="public_web_email",
                        evidence=(
                            f"Email {email} was found "
                            f"with person-specific evidence."
                        ),
                    )
                )

                return person

        return person

    def _build_queries(
        self,
        person: PersonProfile,
    ) -> list[str]:

        company = (
            person.current_company or ""
        )

        name = person.name

        return [
            f'"{name}" "{company}" email',
            f'"{name}" "{company}" contact',
            f'"{name}" "{company}" "@{self._company_domain(company)}"',
        ]

    @staticmethod
    def _extract_valid_email(
        result: dict,
    ) -> Optional[str]:

        text = (
            result.get("title", "")
            + " "
            + result.get("snippet", "")
        )

        emails = EMAIL_PATTERN.findall(
            text
        )

        if not emails:
            return None

        for email in emails:

            domain = email.split("@")[-1].lower()

            if domain not in {
                "example.com",
                "example.org",
                "example.net",
            }:
                return email

        return None

    @staticmethod
    def _result_matches_person(
        person: PersonProfile,
        result: dict,
        email: str,
    ) -> bool:

        text = (
            result.get("title", "")
            + " "
            + result.get("snippet", "")
        ).lower()

        name_parts = [
            part.lower()
            for part in person.name.split()
            if len(part) > 2
        ]

        company = (
            person.current_company or ""
        ).lower()

        # Require the result to contain
        # enough identity evidence.
        name_matches = sum(
            part in text
            for part in name_parts
        )

        company_matches = (
            company in text
            if company
            else False
        )

        # At least two name components OR
        # full name + company.
        return (
            name_matches >= 2
            or (
                name_matches >= 1
                and company_matches
            )
        )

    @staticmethod
    def _company_domain(
        company: str,
    ) -> str:

        normalized = re.sub(
            r"[^a-z0-9]",
            "",
            company.lower(),
        )

        return f"{normalized}.com"