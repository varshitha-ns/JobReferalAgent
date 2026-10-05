import asyncio
import unittest

from analyzer.llm_job_analyzer import LLMJobAnalyzer
from people.discovery import PeopleDiscoveryAgent
from people.identity_verification import IdentityVerifier
from people.public_finder import PublicEmailFinder
from people.schemas import ContactEvidence, PersonProfile
from schemas.job import JobData


MAERSK_URL = (
    "https://bebee.com/in/jobs/associate-software-engineer-"
    "ap-moller-maersk-india-bengaluru-560064--t7xk-824437199"
)
MAERSK_TEXT = """Associate Software Engineer
A.P. Moller - Maersk
India, India. Full time. On-site.
Job description:
Designs, develops, tests, delivers and maintains business applications."""


class FakeOllama:
    def __init__(self):
        self.calls = 0

    async def generate(self, **_kwargs):
        self.calls += 1
        # Reproduce the malformed extraction from the real listing test.
        return {
            "company": "A.P. Moller - Maers: India",
            "title": "Associate Software Engineer",
            "location": "India",
            "required_skills": "Python, SQL",
            "unexpected_model_key": "ignored",
        }


class FakeSearch:
    def __init__(self):
        self.calls = 0

    async def search(self, query, limit=10):
        self.calls += 1
        return [{"url": "https://www.maersk.com/about", "title": "Maersk", "snippet": "Official website"}]


class MaerskRegressionTests(unittest.TestCase):
    def test_job_analysis_overrides_corrupt_model_fields(self):
        analyzer = LLMJobAnalyzer()
        analyzer.ollama = FakeOllama()
        job = JobData(
            url=MAERSK_URL,
            title="Associate Software Engineer",
            description=MAERSK_TEXT,
            hostname="bebee.com",
        )
        profile = asyncio.run(analyzer.analyze(job))
        self.assertEqual(profile.company, "A.P. Moller - Maersk")
        self.assertEqual(profile.location, "Bengaluru, India")
        self.assertEqual(profile.title, "Associate Software Engineer")
        self.assertEqual(profile.required_skills, ["Python, SQL"])
        self.assertFalse(hasattr(profile, "unexpected_model_key"))

    def test_complete_page_identity_skips_slow_optional_llm(self):
        analyzer = LLMJobAnalyzer()
        fake_ollama = FakeOllama()
        analyzer.ollama = fake_ollama
        job = JobData(
            url="https://www.coinbase.com/careers/positions/example",
            title="Machine Learning Engineer",
            description="Build ML systems.",
            hostname="www.coinbase.com",
            company="Coinbase",
            location="Remote - India",
        )
        profile = asyncio.run(analyzer.analyze(job))
        self.assertEqual(profile.company, "Coinbase")
        self.assertEqual(profile.title, "Machine Learning Engineer")
        self.assertEqual(profile.location, "Remote - India")
        self.assertEqual(fake_ollama.calls, 0)

    def test_company_source_match_uses_distinctive_brand(self):
        person = PersonProfile(
            name="Abhinav Kumar",
            current_company="A.P. Moller - Maersk",
            current_role="Software Engineer",
            contact_evidence=[ContactEvidence(
                source_url="https://in.linkedin.com/in/example",
                source_type="public_search_result",
                evidence="Abhinav Kumar - Software Engineer at Maersk",
            )],
        )
        self.assertTrue(IdentityVerifier.verify_company(person, "A.P. Moller - Maersk"))

    def test_foreign_city_is_rejected_and_bengaluru_is_kept(self):
        discovery = PeopleDiscoveryAgent()
        foreign = {
            "title": "Adrian Hermida Camacho - Engineering Manager | LinkedIn",
            "url": "https://es.linkedin.com/in/adrianhc",
            "snippet": "Engineering Manager at Maersk · Location: Greater Cádiz Metropolitan Area",
        }
        local = {
            "title": "Abhinav Kumar - Software Engineer at Maersk | LinkedIn",
            "url": "https://in.linkedin.com/in/abhinav-kumar",
            "snippet": "Software Engineer at Maersk · Location: Bengaluru",
        }
        self.assertIsNone(discovery._create_person(
            foreign, "https://www.linkedin.com/in/adrianhc/", "Maersk", "Bengaluru, India"
        ))
        person = discovery._create_person(
            local, "https://www.linkedin.com/in/abhinav-kumar/", "Maersk", "Bengaluru, India"
        )
        self.assertIsNotNone(person)
        self.assertEqual(person.location, "Bengaluru")
        self.assertIs(person.location_verified, True)

    def test_en_dash_name_and_former_employer_are_handled(self):
        self.assertEqual(
            PeopleDiscoveryAgent._extract_name(
                "Jyothi S Jayanna – Masters in Web Engineering at TUC | Ex ..."
            ),
            "Jyothi S Jayanna",
        )
        self.assertTrue(PeopleDiscoveryAgent._is_former_employee(
            "Jyothi S Jayanna – Masters in Web Engineering at TUC | Ex ...",
            "Associate Software Engineer at A.P. Moller - Maersk Sept. 2023–Apr. 2025 Bengaluru",
            "A.P. Moller - Maersk",
        ))
        self.assertTrue(PeopleDiscoveryAgent._is_former_employee(
            "Suhas Gorur Ravi Kumar - Data Architect | Senior Azure Data Engineer",
            "Data Engineer A.P. Moller - Maersk Jul 2021 - Aug 2022 1 year 2 months",
            "A.P. Moller - Maersk",
        ))

    def test_unknown_company_domain_is_discovered_and_cached(self):
        async def run():
            fake_search = FakeSearch()
            finder = PublicEmailFinder(search_engine=fake_search)
            first = await finder.resolve_company_domain("A.P. Moller - Maersk")
            second = await finder.resolve_company_domain("A.P. Moller - Maersk")
            self.assertEqual(first, "maersk.com")
            self.assertEqual(second, "maersk.com")
            self.assertEqual(fake_search.calls, 1)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
