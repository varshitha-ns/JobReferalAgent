import asyncio

from analyzer.llm_job_analyzer import LLMJobAnalyzer
from schemas.job import JobData


async def main():

    job = JobData(
        url="https://example.com/jobs/software-engineer",
        title="Software Engineer",
        description=(
            "We are looking for a Software Engineer with experience "
            "in Python, FastAPI, React and MongoDB. "
            "The candidate will develop REST APIs and backend services. "
            "Docker is preferred. "
            "A Bachelor's degree in Computer Science or a related "
            "field is required."
        ),
        hostname="example.com",
    )

    analyzer = LLMJobAnalyzer()

    print("========================================")
    print("Starting Job Analyzer")
    print("========================================")

    result = await analyzer.analyze(job)

    print("========================================")
    print("JOB ANALYSIS RESULT")
    print("========================================")
    print(result)


asyncio.run(main())