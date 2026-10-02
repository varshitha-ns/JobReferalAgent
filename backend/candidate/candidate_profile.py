from pydantic import BaseModel, Field
from typing import List, Optional


class Education(BaseModel):
    institution: str
    degree: str
    specialization: str
    graduation_year: int
    cgpa: Optional[float] = None


class Experience(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: str
    description: List[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    technologies: List[str] = Field(default_factory=list)
    description: List[str] = Field(default_factory=list)


class Certification(BaseModel):
    name: str
    provider: Optional[str] = None


class Achievement(BaseModel):
    description: str


class CandidateProfile(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None

    linkedin: Optional[str] = None
    github: Optional[str] = None

    summary: str

    education: List[Education] = Field(default_factory=list)

    experience: List[Experience] = Field(default_factory=list)

    projects: List[Project] = Field(default_factory=list)

    programming_languages: List[str] = Field(default_factory=list)

    web_backend: List[str] = Field(default_factory=list)

    machine_learning: List[str] = Field(default_factory=list)

    deep_learning: List[str] = Field(default_factory=list)

    generative_ai: List[str] = Field(default_factory=list)

    databases_tools_cloud: List[str] = Field(default_factory=list)

    cloud_devops: List[str] = Field(default_factory=list)

    certifications: List[Certification] = Field(default_factory=list)

    achievements: List[Achievement] = Field(default_factory=list)

    coding_problems_solved: Optional[int] = None