from fastapi import APIRouter

from schemas.job import JobData


router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"]
)


@router.post("/analyze")
def analyze_job(job: JobData):
    return {
        "success": True,
        "message": "Job received successfully",
        "job": job
    }