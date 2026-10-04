from __future__ import annotations

import logging
from typing import List

from people.discovery import PeopleDiscoveryAgent
from people.email_discovery import EmailDiscovery
from people.github import GitHubSource
from people.identity_verification import IdentityVerifier
from people.public_finder import PublicEmailFinder
from people.relevance import ContactRelevance
from people.schemas import (
    ContactEvidence,
    PersonProfile,
    VerificationStatus,
)
from people.sources.search_engine import SearchEngine


logger = logging.getLogger(__name__)


class ContactPipeline:
    """Find up to five relevant referral contacts and their public routes."""

    def __init__(self, target_contacts: int = 5, max_candidates: int = 40):
        self.target_contacts = min(max(target_contacts, 1), 5)
        self.max_candidates = max(max_candidates, self.target_contacts)
        self.search_engine = SearchEngine()
        self.discovery = PeopleDiscoveryAgent()
        self.discovery.search_engine = self.search_engine
        public_finder = PublicEmailFinder(search_engine=self.search_engine)
        github = GitHubSource(search_engine=self.search_engine)
        self.email_discovery = EmailDiscovery(
            github=github,
            public_finder=public_finder,
        )
        self.identity = IdentityVerifier()
        self.relevance = ContactRelevance()

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

        # Do contact checks in referral-priority order so scarce public
        # evidence and the final five slots favor people who can route a
        # referral. Email availability breaks ties rather than outranking role.
        qualified: List[PersonProfile] = []
        for person in people:
            if not self.identity.verify_company(person, company):
                person.verification_status = VerificationStatus.REJECTED
                continue
            self.identity.mark_company_verified(person)
            self.relevance.classify(person)
            if not self.identity.verify_role(person, job_title):
                person.verification_status = VerificationStatus.REJECTED
                continue
            self.identity.mark_role_verified(person)
            qualified.append(person)
        people = sorted(
            qualified,
            key=lambda item: self.relevance.sort_key(item, job_title),
        )

        email_contacts: List[PersonProfile] = []
        fallback_contacts: List[PersonProfile] = []
        seen_emails = set()
        for person in people:
            if len(email_contacts) >= self.target_contacts:
                break

            person_data = {
                "name": person.name,
                "company": company,
                "title": person.current_role,
                "linkedin_url": person.linkedin_url,
            }
            try:
                candidates = await self.email_discovery.discover(person_data)
            except Exception as error:
                logger.warning("Email discovery failed for %s: %s", person.name, error)
                candidates = []

            # One distinct address per employee. Prefer a profile/page address
            # over a historical commit address when both have the same identity.
            source_priority = {
                "public_webpage": 0,
                "search_snippet": 1,
                "github_profile": 2,
                "github_public_commit": 3,
            }
            candidates.sort(key=lambda item: source_priority.get(item.get("source", ""), 9))
            selected = next(
                (
                    item for item in candidates
                    if item.get("email")
                    and item["email"].lower() not in seen_emails
                    and item.get("status") in {
                        "PUBLIC_EVIDENCE", "PUBLIC_PERSONAL_CANDIDATE"
                    }
                ),
                None,
            )
            if selected:
                person.public_email = selected["email"].lower()
                seen_emails.add(person.public_email)
                person.email_verified = False
                person.email_domain_has_mx = (
                    selected.get("domain_has_mx")
                    if selected.get("email_type") == "work"
                    else None
                )
                person.email_verification_method = selected.get("status")
                person.email_type = selected.get("email_type", "work")
                person.verification_status = VerificationStatus.EMAIL_FOUND
                if selected.get("email_type") == "personal_candidate":
                    person.relevance_reasons.append(
                        "A public GitHub profile or commit lists this personal email; verify it belongs to the person before use."
                    )
                    evidence_text = (
                        "Public GitHub evidence associates a similar author/profile name with this personal address. "
                        "Mailbox ownership and current availability are not confirmed."
                    )
                else:
                    person.relevance_reasons.append(
                        "A public source associates this person's name with an employer-domain email."
                    )
                    evidence_text = (
                        "Public source associates the person's name with this company-domain email. "
                        "Mailbox ownership/current availability is not confirmed."
                    )
                person.contact_evidence.append(
                    ContactEvidence(
                        source_url=selected.get("source_url") or "",
                        source_type=selected.get("source", "public_source"),
                        evidence=evidence_text,
                    )
                )
                if selected.get("github_username"):
                    person.github_url = f"https://github.com/{selected['github_username']}"
                email_contacts.append(person)
            elif person.linkedin_url:
                person.relevance_reasons.append(
                    "No suitable public email was found; use the person's LinkedIn profile to request a referral."
                )
                # Keep collecting email leads from the remaining relevant
                # candidates; use these profiles only to fill empty result slots.
                if len(fallback_contacts) < self.target_contacts:
                    fallback_contacts.append(person)

        # Prefer people with a sourced address. If public email evidence is
        # scarce, fill the remainder with relevant profiles and LinkedIn URLs.
        return sorted(
            email_contacts + fallback_contacts,
            key=lambda item: self.relevance.sort_key(item, job_title),
        )[:self.target_contacts]
