from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field


class ContactType(str, Enum):
    ENGINEER = "engineer"
    SENIOR_ENGINEER = "senior_engineer"
    TECH_LEAD = "tech_lead"
    ENGINEERING_MANAGER = "engineering_manager"
    RECRUITER = "recruiter"
    TALENT_ACQUISITION = "talent_acquisition"
    OTHER = "other"


class VerificationStatus(str, Enum):
    DISCOVERED = "discovered"
    COMPANY_VERIFIED = "company_verified"
    ROLE_VERIFIED = "role_verified"
    EMAIL_FOUND = "email_found"
    EMAIL_VERIFIED = "email_verified"
    REJECTED = "rejected"


class ContactEvidence(BaseModel):
    source_url: str
    source_type: str
    evidence: str


class PersonProfile(BaseModel):
    name: str

    current_company: Optional[str] = None
    current_role: Optional[str] = None
    location: Optional[str] = None

    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None

    public_email: Optional[str] = None

    contact_type: ContactType = ContactType.OTHER

    relevance_reasons: List[str] = Field(
        default_factory=list
    )

    contact_evidence: List[ContactEvidence] = Field(
        default_factory=list
    )

    verification_status: VerificationStatus = (
        VerificationStatus.DISCOVERED
    )

    email_verified: bool = False

    email_verification_method: Optional[str] = None