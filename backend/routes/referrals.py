from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from referrals.drafter import create_referral_draft


router = APIRouter(prefix="/referrals", tags=["Referrals"])


class ReferralDraftRequest(BaseModel):
    company: str = Field(min_length=1, max_length=160)
    job_title: str = Field(min_length=1, max_length=240)
    job_description: str = Field(default="", max_length=15000)
    job_url: str = Field(default="", max_length=2000)
    contact_name: str = Field(min_length=1, max_length=160)
    contact_role: Optional[str] = Field(default=None, max_length=240)


@router.post("/draft")
def referral_draft(request: ReferralDraftRequest):
    return {
        "success": True,
        **create_referral_draft(
            company=request.company.strip(),
            job_title=request.job_title.strip(),
            job_description=request.job_description,
            job_url=request.job_url,
            contact_name=request.contact_name.strip(),
            contact_role=request.contact_role,
        ),
    }
