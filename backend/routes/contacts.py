from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from people.contact_pipeline import ContactPipeline


router = APIRouter(prefix="/contacts", tags=["Contacts"])


class ContactSearchRequest(BaseModel):
    company: str = Field(min_length=1, max_length=160)
    job_title: str = Field(min_length=1, max_length=240)
    location: Optional[str] = Field(default=None, max_length=160)
    limit: int = Field(default=5, ge=1, le=5)


@router.post("/find")
async def find_contacts(request: ContactSearchRequest):
    try:
        pipeline = ContactPipeline(target_contacts=request.limit)
        contacts = await pipeline.find_contacts(
            company=request.company,
            job_title=request.job_title,
            location=request.location,
        )
        search_available = pipeline.search_engine.last_error is None
        return {
            "success": True,
            "requested": request.limit,
            "found": len(contacts),
            "contacts": [contact.model_dump(mode="json") for contact in contacts],
            "search_available": search_available,
            "search_error": pipeline.search_engine.last_error,
            "message": (
                "Relevant people and available public outreach routes found. Email mailbox ownership is not verified."
                if contacts
                else (
                    "Local public search is unavailable. Start SearXNG and retry."
                    if not search_available
                    else "No relevant people were found in the public search results."
                )
            ),
        }
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail={
                "error_type": type(error).__name__,
                "error": str(error),
            },
        ) from error
