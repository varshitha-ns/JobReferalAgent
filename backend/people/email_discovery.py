from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, List

from people.github import GitHubSource
from people.identity_verification import IdentityVerifier
from people.public_finder import PublicEmailFinder


logger = logging.getLogger(__name__)


class EmailDiscovery:
    """Collect public work-email evidence and cautious personal-email leads."""

    PUBLIC_PERSONAL_DOMAINS = {
        "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in",
        "hotmail.com", "outlook.com", "live.com", "icloud.com",
        "protonmail.com", "proton.me", "rediffmail.com",
    }

    def __init__(self, github=None, public_finder=None):
        self.github = github or GitHubSource()
        self.public_finder = public_finder or PublicEmailFinder()

    async def discover(self, person: Dict[str, Any]) -> List[Dict[str, Any]]:
        name = person.get("name")
        company = person.get("company")
        if not name or not company:
            return []

        # Resolve the employer's public domain once; never manufacture an
        # address from the person's name or a guessed company domain.
        company_domain = person.get("company_domain")
        if not company_domain:
            try:
                company_domain = await self.public_finder.resolve_company_domain(company)
            except Exception as error:
                logger.warning("Company domain lookup failed for %s: %s", company, error)
                return []
        if not company_domain:
            return []

        lookup_person = {**person, "company_domain": company_domain}
        domain_has_mx = await asyncio.to_thread(
            IdentityVerifier.domain_has_mx, company_domain
        )
        candidates: List[Dict[str, Any]] = []

        try:
            candidates.extend(await self.github.find_public_emails(lookup_person))
        except Exception as error:
            logger.warning("GitHub email source failed for %s: %s", name, error)

        # A strongly name-matched GitHub source plus the confirmed employer
        # domain is already useful public evidence. Avoid extra web queries in
        # that case, which saves time and reduces search-provider throttling.
        has_github_work_email = False
        for candidate in candidates:
            candidate["company_domain"] = company_domain
            if candidate.get("source") not in {"github_profile", "github_public_commit"}:
                continue
            if IdentityVerifier.verify(lookup_person, candidate)["verified"]:
                has_github_work_email = True
                break

        if not has_github_work_email:
            try:
                candidates.extend(await self.public_finder.find_public_emails(lookup_person))
            except Exception as error:
                logger.warning("Public web email source failed for %s: %s", name, error)

        accepted: Dict[str, Dict[str, Any]] = {}
        for candidate in candidates:
            email = (candidate.get("email") or "").lower().strip()
            if not email:
                continue
            candidate["company_domain"] = company_domain
            candidate["domain_has_mx"] = domain_has_mx
            verification = IdentityVerifier.verify(lookup_person, candidate)
            if verification["verified"]:
                candidate["verification"] = verification
                candidate["status"] = "PUBLIC_EVIDENCE"
                candidate["email_type"] = "work"
                candidate["mailbox_verified"] = False
                if email not in accepted:
                    accepted[email] = candidate
                continue

            # GitHub may expose an individual's personal mailbox in a public
            # profile or commit. Keep only consumer-mail providers and require
            # a strong author/profile name match plus a name-like local part.
            # Label this as a lead: GitHub metadata does not prove mailbox
            # ownership, current employment, or that the person reads it.
            source = candidate.get("source")
            source_name = (
                candidate.get("github_name")
                if source == "github_profile"
                else candidate.get("github_commit_author")
            ) or ""
            email_domain = email.rsplit("@", 1)[-1]
            local = "".join(ch for ch in email.split("@", 1)[0].lower() if ch.isalpha())
            name_tokens = [
                token for token in IdentityVerifier.normalize(name).split()
                if len(token) >= 4
            ]
            local_name_match = any(token in local for token in name_tokens)
            source_name_score = IdentityVerifier.name_score(name, source_name)
            profile_company_match = (
                source != "github_profile"
                or IdentityVerifier.company_score(
                    company, candidate.get("github_company")
                ) >= 0.5
            )
            if (
                source in {"github_profile", "github_public_commit"}
                and email_domain in self.PUBLIC_PERSONAL_DOMAINS
                and source_name_score >= 0.8
                and local_name_match
                and profile_company_match
            ):
                candidate["verification"] = {
                    **verification,
                    "verified": False,
                    "status": "PUBLIC_PERSONAL_CANDIDATE",
                    "identity_score": round(source_name_score, 3),
                    "reasons": [
                        "public_github_profile_or_commit_contains_address",
                        "github_author_name_strongly_matches_contact_name",
                        "personal_address_and_mailbox_ownership_not_confirmed",
                    ],
                }
                candidate["status"] = "PUBLIC_PERSONAL_CANDIDATE"
                candidate["email_type"] = "personal_candidate"
                candidate["mailbox_verified"] = False
                if email not in accepted:
                    accepted[email] = candidate
                continue

            if not verification["verified"]:
                logger.info(
                    "Rejected email candidate from %s: %s",
                    candidate.get("source"),
                    verification["reasons"],
                )
                continue

            candidate["verification"] = verification
            candidate["status"] = "PUBLIC_EVIDENCE"
            candidate["mailbox_verified"] = False
            if email not in accepted:
                accepted[email] = candidate

        return list(accepted.values())
