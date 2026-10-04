from __future__ import annotations

import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from people.schemas import PersonProfile, VerificationStatus

try:
    import dns.resolver
except ImportError:
    dns = None


class IdentityVerifier:
    """Checks source evidence; it does not probe or certify mailboxes."""

    KNOWN_COMPANY_DOMAINS = {
        "microsoft": {"microsoft.com", "microsoftonline.com"},
        "google": {"google.com", "googlemail.com"},
        "amazon": {"amazon.com", "amazon.in"},
        "amazon web services": {"amazon.com", "amazonaws.com"},
        "meta": {"meta.com", "fb.com"},
        "apple": {"apple.com"},
        "infosys": {"infosys.com"},
        "tcs": {"tcs.com"},
        "wipro": {"wipro.com"},
        "capgemini": {"capgemini.com"},
        "accenture": {"accenture.com"},
    }
    PRIMARY_COMPANY_DOMAINS = {
        "microsoft": "microsoft.com",
        "google": "google.com",
        "amazon": "amazon.com",
        "amazon web services": "amazon.com",
        "meta": "meta.com",
        "apple": "apple.com",
        "infosys": "infosys.com",
        "tcs": "tcs.com",
        "wipro": "wipro.com",
        "capgemini": "capgemini.com",
        "accenture": "accenture.com",
    }

    GENERIC_ROLE_WORDS = {
        "software", "engineer", "engineering", "developer", "senior",
        "junior", "associate", "staff", "principal", "the", "and", "of", "at",
    }
    _MX_CACHE: Dict[str, Optional[bool]] = {}

    @staticmethod
    def normalize(value: Optional[str]) -> str:
        value = (value or "").lower()
        return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", value)).strip()

    @classmethod
    def tokens(cls, value: Optional[str]) -> set[str]:
        return set(cls.normalize(value).split())

    @classmethod
    def name_score(cls, target_name: Optional[str], evidence_text: str) -> float:
        expected = cls.tokens(target_name)
        actual = cls.tokens(evidence_text)
        return len(expected & actual) / len(expected) if expected else 0.0

    @classmethod
    def company_score(cls, company: Optional[str], evidence_text: str) -> float:
        expected = cls.tokens(company)
        actual = cls.tokens(evidence_text)
        return len(expected & actual) / len(expected) if expected else 0.0

    @classmethod
    def known_domains(cls, company: Optional[str]) -> set[str]:
        return cls.KNOWN_COMPANY_DOMAINS.get((company or "").lower().strip(), set())

    @classmethod
    def primary_domain(cls, company: Optional[str]) -> Optional[str]:
        return cls.PRIMARY_COMPANY_DOMAINS.get((company or "").lower().strip())

    @staticmethod
    def domain_has_mx(domain: str) -> Optional[bool]:
        """Check domain mail routing only; this cannot verify a mailbox."""
        domain = domain.lower().strip().rstrip(".")
        if domain in IdentityVerifier._MX_CACHE:
            return IdentityVerifier._MX_CACHE[domain]
        if dns is None:
            return None
        try:
            dns.resolver.resolve(domain, "MX", lifetime=4)
            result = True
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            result = False
        except Exception:
            result = None
        IdentityVerifier._MX_CACHE[domain] = result
        return result

    @classmethod
    def domain_matches_company(
        cls,
        email: str,
        company: Optional[str],
        company_domain: Optional[str] = None,
    ) -> Optional[bool]:
        domain = email.rsplit("@", 1)[-1].lower().strip().rstrip(".")
        expected_domains = {company_domain.lower().strip().rstrip(".")} if company_domain else cls.known_domains(company)
        if not expected_domains:
            return None
        return domain in expected_domains

    @staticmethod
    def email_matches_name(email: str, name: str) -> bool:
        if "@" not in email:
            return False
        pieces = [part.lower() for part in re.findall(r"[A-Za-z]+", name)]
        if len(pieces) < 2:
            return False
        first, last = pieces[0], pieces[-1]
        middle = pieces[1:-1]
        local_raw = email.split("@", 1)[0].lower()
        local = re.sub(r"[^a-z0-9]", "", local_raw)
        forms = {first + last, last + first, first[0] + last}
        if middle:
            forms.add(first + "".join(middle) + last)
            forms.add(first + "".join(part[0] for part in middle) + last)
        for separator in (".", "_", "-"):
            forms.update({
                separator.join([first, last]),
                separator.join([first[0], last]),
            })
            if middle:
                forms.add(separator.join([first, *middle, last]))
                forms.add(separator.join([first, *(part[0] for part in middle), last]))
        return local in forms or local_raw in forms

    @classmethod
    def verify_company(cls, person: PersonProfile, expected_company: str) -> bool:
        # Company must be present in the actual public profile search evidence;
        # current_company alone may have been populated from the query.
        text = " ".join(item.evidence for item in person.contact_evidence)
        expected = cls.tokens(expected_company)
        actual = cls.tokens(text)
        return bool(expected) and expected.issubset(actual)

    @classmethod
    def verify_role(cls, person: PersonProfile, job_title: str) -> bool:
        role = person.current_role or ""
        role_tokens = cls.tokens(role)
        job_tokens = cls.tokens(job_title)
        meaningful = (role_tokens - cls.GENERIC_ROLE_WORDS) & (job_tokens - cls.GENERIC_ROLE_WORDS)
        if job_tokens and role_tokens and (job_tokens.issubset(role_tokens) or meaningful):
            return True
        # Search snippets often show "Software Engineer" while a posting is
        # titled "Associate Software Engineer, AI". Match the engineering
        # family even when the snippet omits level or specialization; discovery
        # has already required a public profile result at the target company.
        engineering_terms = {"engineer", "engineering", "developer"}
        if role_tokens & engineering_terms and job_tokens & engineering_terms:
            return True
        if any(term in role.lower() for term in (
            "engineering manager", "engineering lead", "technical lead",
            "tech lead", "staff engineer", "principal engineer",
        )):
            return True
        # Recruiters and talent-acquisition staff can be relevant even when
        # their role does not match the technical job title.
        return any(term in role.lower() for term in ("recruit", "talent acquisition"))

    @staticmethod
    def mark_company_verified(person: PersonProfile) -> PersonProfile:
        person.verification_status = VerificationStatus.COMPANY_VERIFIED
        return person

    @staticmethod
    def mark_role_verified(person: PersonProfile) -> PersonProfile:
        person.verification_status = VerificationStatus.ROLE_VERIFIED
        return person

    @classmethod
    def verify(cls, person: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Require source-origin identity and email/domain matches.

        Never count candidate.person_name or candidate.company as evidence:
        callers often copy those values from the search target.
        """
        name = person.get("name", "")
        company = person.get("company", "")
        email = (candidate.get("email") or "").lower().strip()
        source = candidate.get("source", "")
        source_url = candidate.get("source_url", "")
        actual_profile_name = candidate.get("github_name") or candidate.get("github_commit_author") or ""
        evidence_text = candidate.get("evidence_text") or ""
        actual_company = candidate.get("github_company") or ""

        # Evidence text must come from the fetched/snippet source, not fields
        # copied from the lookup request.
        source_text = " ".join([str(evidence_text), str(actual_profile_name), str(actual_company)])
        expected_name = cls.tokens(name)
        source_name_tokens = cls.tokens(actual_profile_name) if actual_profile_name else cls.tokens(evidence_text)
        if not expected_name:
            name_score = 0.0
        else:
            name_score = len(expected_name & source_name_tokens) / len(expected_name)

        company_domain = candidate.get("company_domain")
        domain_match = cls.domain_matches_company(email, company, company_domain)
        email_name_match = cls.email_matches_name(email, name)

        if source == "github_profile":
            company_match = cls.company_score(company, actual_company) >= 0.5
            source_ok = bool(actual_profile_name) and company_match
        elif source == "github_public_commit":
            source_ok = bool(candidate.get("github_commit_author"))
        elif source in {"public_webpage", "search_snippet"}:
            tokens = cls.tokens(evidence_text)
            name_parts = re.findall(r"[A-Za-z]+", name)
            required = {name_parts[0].lower(), name_parts[-1].lower()} if len(name_parts) >= 2 else set()
            source_ok = bool(required) and required.issubset(tokens)
        else:
            source_ok = False

        # A person's published GitHub commit can expose a corporate alias
        # (for example, a shortened username) that does not follow a simple
        # first.last naming pattern. Accept it only when the commit's author
        # name strongly matches the already company-verified contact and the
        # address uses the employer's confirmed domain.
        github_host = (urlparse(source_url).hostname or "").lower()
        github_source = source in {"github_profile", "github_public_commit"}
        github_source_url_ok = github_host in {"github.com", "www.github.com"}
        github_corporate_alias = (
            source == "github_public_commit"
            and github_source_url_ok
            and name_score >= 0.8
            and domain_match is True
        )
        github_profile_association = (
            source == "github_profile"
            and github_source_url_ok
            and name_score >= 0.8
            and domain_match is True
            and cls.company_score(company, actual_company) >= 0.5
        )
        email_person_match = (
            email_name_match
            or github_corporate_alias
            or github_profile_association
        )

        verified_association = (
            bool(email)
            and email_person_match
            and domain_match is True
            and source_ok
            and name_score >= 0.5
        )

        reasons = []
        if not email_person_match:
            reasons.append("email_local_part_does_not_match_person")
        elif not email_name_match:
            reasons.append("github_identity_and_company_domain_support_corporate_alias")
        if domain_match is not True:
            reasons.append("company_email_domain_not_confirmed")
        if not source_ok:
            reasons.append("source_does_not_tie_email_to_person")
        if verified_association:
            reasons.append("public_source_associates_person_and_company_email")

        parsed = urlparse(source_url)
        if source_url and (
            parsed.scheme != "https"
            or (github_source and not github_source_url_ok)
        ):
            verified_association = False
            reasons.append("source_url_is_not_trusted_https_source")

        return {
            "verified": verified_association,
            "status": "PUBLIC_EVIDENCE" if verified_association else "REJECTED",
            "mailbox_verified": False,
            "identity_score": round(name_score, 3),
            "domain_match": domain_match,
            "email_name_match": email_name_match,
            "reasons": reasons,
            "evidence": source_text[:1000],
        }
