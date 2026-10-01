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

    print("========================================")
    print("FASTAPI JOB ANALYSIS STARTED")
    print("Title:", job.title)
    print("========================================")

    try:
        print("Calling LLMJobAnalyzer...")

        profile = await analyzer.analyze(job)

        print("LLMJobAnalyzer completed successfully.")

        return {
            "success": True,
            "message": "Job analyzed successfully",
            "job": profile,
        }

    except Exception as error:

        print("========================================")
        print("FASTAPI JOB ANALYSIS ERROR")
        print("Exception type:", type(error).__name__)
        print("Exception:", repr(error))
        print("========================================")

        raise HTTPException(
            status_code=500,
            detail={
                "error_type": type(error).__name__,
                "error": repr(error),
            },
        )