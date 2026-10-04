from typing import List, Optional

from pydantic import BaseModel, Field


class JobData(BaseModel):
    url: str
    title: str
    description: str
    hostname: str
    company: Optional[str] = None
    location: Optional[str] = None


class JobProfile(BaseModel):
    model_config = {
        "extra": "forbid"
    }

    company: Optional[str] = None
    title: str
    location: Optional[str] = None
    experience: Optional[str] = None

    required_skills: List[str] = Field(default_factory=list)
    preferred_skills: List[str] = Field(default_factory=list)

    responsibilities: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)

    source_url: str
    source_domain: str

    raw_text_length: int = 0
