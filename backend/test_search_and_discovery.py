import unittest

from people.discovery import PeopleDiscoveryAgent
from people.sources.search_engine import SearchEngine


class SearchAndDiscoveryTests(unittest.TestCase):
    def test_json_search_results_are_normalized(self):
        results = SearchEngine._parse_json({
            "results": [
                {"title": "Sumit Kumar Prasad - Software Engineer - Microsoft | LinkedIn",
                 "url": "https://www.linkedin.com/in/skprasad-kd/",
                 "content": "Software Engineer at Microsoft"},
                {"title": "Missing URL"},
            ]
        }, 10)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["snippet"], "Software Engineer at Microsoft")

    def test_html_search_results_are_normalized(self):
        results = SearchEngine._parse_html(
            '<div class="result"><h3><a href="https://www.linkedin.com/in/skprasad-kd/">'
            'Sumit Kumar Prasad - Software Engineer - Microsoft</a></h3>'
            '<div class="content">Software Engineer at Microsoft</div></div>',
            10,
        )
        self.assertEqual(len(results), 1)
        self.assertIn("skprasad-kd", results[0]["url"])

    def test_known_profile_is_kept_only_with_company_and_role_evidence(self):
        agent = PeopleDiscoveryAgent()
        profile = agent._create_person(
            result={
                "title": "Sumit Kumar Prasad - Software Engineer - Microsoft | LinkedIn",
                "snippet": "Software Engineer at Microsoft",
                "url": "https://www.linkedin.com/in/skprasad-kd/",
            },
            linkedin_url="https://www.linkedin.com/in/skprasad-kd/",
            company="Microsoft",
        )
        self.assertIsNotNone(profile)
        self.assertEqual(profile.name, "Sumit Kumar Prasad")
        self.assertEqual(profile.current_role, "Software Engineer")
        self.assertIsNone(agent._create_person(
            result={
                "title": "Sumit Kumar Prasad | LinkedIn",
                "snippet": "Profile",
                "url": "https://www.linkedin.com/in/skprasad-kd/",
            },
            linkedin_url="https://www.linkedin.com/in/skprasad-kd/",
            company="Microsoft",
        ))

    def test_discovery_broadens_past_location_qualified_query(self):
        queries = PeopleDiscoveryAgent()._build_queries(
            "Microsoft", "Software Engineer", "Bangalore"
        )
        self.assertIn('"Bangalore"', queries[0])
        self.assertTrue(any('"Technical Recruiter"' in query for query in queries))
        self.assertTrue(any('"Staff Software Engineer"' in query for query in queries))
        self.assertTrue(any('"Bangalore"' not in query for query in queries[1:]))


if __name__ == "__main__":
    unittest.main()
