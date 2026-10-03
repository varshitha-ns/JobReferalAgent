from people.public_finder import PublicEmailFinder
from people.schemas import (
    ContactEvidence,
    PersonProfile,
    VerificationStatus,
)


class EmailDiscovery:
    """Adapt the evidence-based finder to the contact pipeline schema."""

    def __init__(self, finder=None):
        self.finder = finder or PublicEmailFinder()

    async def discover(self, person: PersonProfile, search_engine) -> PersonProfile:
        # Keep dependency injection from ContactPipeline and its tests.
        self.finder.search_engine = search_engine
        results = await self.finder.find(
            person_name=person.name,
            company=person.current_company or "",
            linkedin_url=person.linkedin_url,
            max_results=10,
        )

        direct_evidence = next(
            (item for item in results if item.get("verification_type") == "PUBLIC_EVIDENCE"),
            None,
        )
        if not direct_evidence:
            # Pattern-inferred addresses remain visible from PublicEmailFinder
            # but are never promoted to a person's contact address here.
            return person

        person.public_email = direct_evidence["email"]
        person.email_verified = False
        person.verification_status = VerificationStatus.EMAIL_FOUND
        person.email_verification_method = "PUBLIC_EVIDENCE"
        source_url = direct_evidence.get("source_url") or ""
        person.contact_evidence.append(
            ContactEvidence(
                source_url=source_url,
                source_type=direct_evidence.get("source", "public_web"),
                evidence=direct_evidence.get(
                    "evidence",
                    "Publicly exposed email with person-specific evidence; ownership is unverified.",
                ),
            )
        )
        return person

