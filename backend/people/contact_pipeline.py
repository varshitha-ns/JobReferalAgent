from typing import List

from people.discovery import PeopleDiscoveryAgent
from people.email_discovery import EmailDiscovery
from people.identity_verification import IdentityVerifier
from people.relevance import ContactRelevance
from people.schemas import (
    PersonProfile,
    VerificationStatus,
)
from people.sources.search_engine import SearchEngine


class ContactPipeline:

    def __init__(
        self,
        target_contacts: int = 5,
        max_candidates: int = 40,
    ):

        self.target_contacts = target_contacts
        self.max_candidates = max_candidates

        self.search_engine = SearchEngine()

        self.discovery = (
            PeopleDiscoveryAgent()
        )

        self.email_discovery = (
            EmailDiscovery()
        )

        self.identity = (
            IdentityVerifier()
        )

        self.relevance = (
            ContactRelevance()
        )

    async def find_contacts(
        self,
        company: str,
        job_title: str,
        location: str | None = None,
    ) -> List[PersonProfile]:

        people = await self.discovery.discover(
            company=company,
            job_title=job_title,
            location=location,
            limit=self.max_candidates,
        )

        valid_contacts = []

        for person in people:

            if len(valid_contacts) >= (
                self.target_contacts
            ):
                break

            # Company verification
            if not self.identity.verify_company(
                person,
                company,
            ):
                person.verification_status = (
                    VerificationStatus.REJECTED
                )
                continue

            self.identity.mark_company_verified(
                person
            )

            # Role/relevance classification
            person = self.relevance.classify(
                person
            )

            # Role verification
            role_valid = (
                self.identity.verify_role(
                    person,
                    job_title,
                )
            )

            if not role_valid:
                # Recruiters and TA professionals
                # don't need the same technical-role
                # match as engineers.
                if person.contact_type.value not in {
                    "recruiter",
                    "talent_acquisition",
                }:
                    person.verification_status = (
                        VerificationStatus.REJECTED
                    )
                    continue

            else:
                self.identity.mark_role_verified(
                    person
                )

            # Email discovery
            person = (
                await self.email_discovery.discover(
                    person,
                    self.search_engine,
                )
            )

            # For now we require an email.
            if not person.public_email:
                continue

            # Public evidence means the address and person were associated
            # by a public source. It does not verify mailbox ownership.
            if person.email_verification_method != (
                "PUBLIC_EVIDENCE"
            ):
                continue

            person.email_verified = False
            person.verification_status = VerificationStatus.EMAIL_FOUND

            valid_contacts.append(
                person
            )

        return valid_contacts
