import logging
import re
from urllib.parse import unquote, urlparse

from schemas.job import JobData, JobProfile
from services.ollama_client import OllamaClient


logger = logging.getLogger(__name__)


class LLMJobAnalyzer:

    # Common URL location tokens used when a job board's visible location is
    # only a country. Structured job-location metadata takes precedence.
    URL_CITIES = {
        "bengaluru": "Bengaluru, India", "bangalore": "Bengaluru, India",
        "mumbai": "Mumbai, India", "hyderabad": "Hyderabad, India",
        "chennai": "Chennai, India", "pune": "Pune, India",
        "gurugram": "Gurugram, India", "gurgaon": "Gurugram, India",
        "noida": "Noida, India", "new-delhi": "New Delhi, India",
        "kolkata": "Kolkata, India", "ahmedabad": "Ahmedabad, India",
        "kochi": "Kochi, India", "coimbatore": "Coimbatore, India",
    }

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

        # Referral discovery only needs a reliable company and title. If the
        # page extractor already supplied both, don't make contact search wait
        # for an often-slow local model to produce optional skills/summary.
        if job.company and job.title.strip():
            logger.info("Using extracted job identity; skipping optional Ollama analysis")
            result = {}
        else:
            try:
                result = await self.ollama.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                )
            except Exception as error:
                # Preserve deterministic company/title/location extraction if
                # the optional local LLM is unavailable.
                logger.warning("Ollama job analysis failed; using page metadata: %s", error)
                result = {}
        if not isinstance(result, dict):
            result = {}

        defaults = {
            "company": None,
            "title": job.title,
            "location": None,
            "experience": None,
            "required_skills": [],
            "preferred_skills": [],
            "responsibilities": [],
            "qualifications": [],
        }
        # Ignore unexpected model keys and fill omitted keys before validation.
        result = {key: result.get(key, default) for key, default in defaults.items()}

        # Keep malformed model output from breaking the whole job flow. Small
        # local models sometimes emit a string where the schema requires a
        # list, or numbers/objects for text fields.
        for key in ("required_skills", "preferred_skills", "responsibilities", "qualifications"):
            value = result[key]
            if isinstance(value, str):
                result[key] = [value.strip()] if value.strip() else []
            elif isinstance(value, list):
                result[key] = [item.strip() for item in value if isinstance(item, str) and item.strip()]
            else:
                result[key] = []
        for key in ("company", "location", "experience"):
            value = result[key]
            result[key] = value.strip() if isinstance(value, str) and value.strip() else None

        # Keep page-derived fields authoritative. Small local models can merge
        # the employer with a nearby location or truncate punctuation-heavy
        # names (for example, "A.P. Moller - Maers: India").
        company_hint = job.company or self._extract_company_line(job.title, job.description)
        model_company = result.get("company")
        if company_hint:
            result["company"] = company_hint
        elif not self._company_is_in_source(model_company, job.title, job.description):
            result["company"] = None

        result["title"] = job.title.strip() or result.get("title", "")
        url_location = self._location_from_url(job.url)
        provided_location = (job.location or "").strip()
        coarse_locations = {
            "india", "karnataka", "tamil nadu", "telangana", "maharashtra",
            "delhi", "united states", "usa", "united kingdom", "uk",
        }
        first_location_part = self._normalized(provided_location.split(",", 1)[0])
        precise_location = provided_location if first_location_part not in coarse_locations else None
        result["location"] = precise_location or url_location or provided_location or result.get("location")

        # Add deterministic source information ourselves.
        result["source_url"] = job.url
        result["source_domain"] = job.hostname
        result["raw_text_length"] = len(job.description)

        return JobProfile.model_validate(result)

    @staticmethod
    def _normalized(value: str) -> str:
        return " ".join(re.sub(r"[^a-z0-9]+", " ", value.casefold()).split())

    @classmethod
    def _extract_company_line(cls, title: str, description: str) -> str | None:
        lines = [line.strip(" \t•|·") for line in description.splitlines() if line.strip()]
        normalized_title = cls._normalized(title)
        title_indices = [
            index for index, line in enumerate(lines)
            if cls._normalized(line) == normalized_title
        ]
        excluded = re.compile(
            r"^(job description|description|full[- ]time|part[- ]time|contract|"
            r"on[- ]site|hybrid|remote|technology|until\b|\d+\s+months? ago\b|"
            r"india(?:,\s*india)?|bengaluru(?:,.*)?|bangalore(?:,.*)?)$",
            re.IGNORECASE,
        )
        for index in title_indices:
            for line in lines[index + 1:index + 5]:
                if len(line) > 100 or excluded.match(line.strip()):
                    continue
                # Skip metadata and prose, while allowing punctuation-heavy
                # legal names such as "A.P. Moller - Maersk".
                if re.search(r"\b(days?|weeks?|months?|years?) ago\b|\b(until \d|full[- ]time|on[- ]site|easy apply|applicants?)\b", line, re.I):
                    continue
                if len(re.findall(r"[A-Za-z]{2,}", line)) <= 8:
                    return line
        return None

    @classmethod
    def _company_is_in_source(cls, company: object, title: str, description: str) -> bool:
        if not isinstance(company, str) or not company.strip():
            return False
        expected = {token for token in cls._normalized(company).split() if len(token) >= 3}
        source = set(cls._normalized(f"{title}\n{description}").split())
        return bool(expected) and expected.issubset(source)

    @classmethod
    def _location_from_url(cls, url: str) -> str | None:
        path = unquote(urlparse(url).path).casefold().replace("_", "-")
        return next(
            (label for token, label in cls.URL_CITIES.items()
             if re.search(rf"(?:^|[-/]){re.escape(token)}(?:[-/]|$)", path)),
            None,
        )
