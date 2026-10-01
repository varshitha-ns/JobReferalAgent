from schemas.job import JobData, JobProfile
from services.ollama_client import OllamaClient


class LLMJobAnalyzer:

    def __init__(self):
        self.ollama = OllamaClient()

    async def analyze(self, job: JobData) -> JobProfile:

        system_prompt = """
You are a job posting information extraction system.

Return ONLY one valid JSON object.

The JSON MUST contain ONLY these keys:

company
title
location
experience
required_skills
preferred_skills
responsibilities
qualifications

Rules:

- Do not create any other keys.
- Do not add explanations.
- Do not use markdown.
- Do not use code fences.
- Do not invent information.
- Use null when a single-value field is unavailable.
- Use [] when a list field has no information.

Required JSON structure:

{
  "company": null,
  "title": "",
  "location": null,
  "experience": null,
  "required_skills": [],
  "preferred_skills": [],
  "responsibilities": [],
  "qualifications": []
}
"""

        user_prompt = f"""
Analyze this job posting.

JOB TITLE:
{job.title}

JOB DESCRIPTION:
{job.description}
"""

        result = await self.ollama.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        # Add deterministic information ourselves.
        result["source_url"] = job.url
        result["source_domain"] = job.hostname
        result["raw_text_length"] = len(job.description)

        return JobProfile.model_validate(result)