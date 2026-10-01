from schemas.job import JobData, JobProfile
from services.ollama_client import OllamaClient


class LLMJobAnalyzer:
    def __init__(self):
        self.ollama = OllamaClient()

    async def analyze(self, job: JobData) -> JobProfile:

        system_prompt = """
You are a job analysis AI agent.

Your task is to analyze a software engineering job description
and convert it into structured information.

You must return ONLY valid JSON.

Do not add markdown.
Do not add explanations.
Do not add ```json.
Do not invent information that is not present in the job description.

Use this exact JSON structure:

{
  "company": string or null,
  "title": string,
  "location": string or null,
  "experience": string or null,
  "required_skills": [],
  "preferred_skills": [],
  "responsibilities": [],
  "qualifications": [],
  "source_url": string,
  "source_domain": string,
  "raw_text_length": integer
}

Rules:

1. Extract the company only when it can reasonably be identified.
2. Preserve the job title accurately.
3. Extract required technical and professional skills.
4. Separate required skills from preferred/nice-to-have skills.
5. Extract the major responsibilities.
6. Extract education, experience and qualification requirements.
7. Do not confuse responsibilities with skills.
8. Do not invent salary, location, experience or qualifications.
9. If information is unavailable, use null or an empty list.
10. Keep the output concise and structured.
"""

        user_prompt = f"""
Analyze the following job posting.

URL:
{job.url}

Title:
{job.title}

Hostname:
{job.hostname}

Job Description:
{job.description}
"""

        result = await self.ollama.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        return JobProfile.model_validate(result)