from fastapi import APIRouter, HTTPException

from analyzer.llm_job_analyzer import LLMJobAnalyzer
from schemas.job import JobData


router = APIRouter(
    prefix="/jobs",
    tags=["Jobs"],
)

analyzer = LLMJobAnalyzer()


@router.post("/analyze")
async def analyze_job(job: JobData):

    try:
        profile = await analyzer.analyze(job)

        return {
            "success": True,
            "message": "Job analyzed successfully",
            "job": profile,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Job analysis failed: {str(error)}",
        )