import unittest

from people.public_finder import PublicEmailFinder


class EmptyGitHub:
    async def find_public_email(self, **kwargs):
        return None


class EmailEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.finder = PublicEmailFinder(github_source=EmptyGitHub())

    def test_rejects_unrelated_address_and_missing_company_domain(self):
        result = self.finder._evaluate_email(
            email="other.person@microsoft.com",
            person_name="Sumit Kumar Prasad",
            company="Microsoft",
            domain="microsoft.com",
            source_url="https://example.org/team",
            source_text="Sumit Kumar Prasad works at Microsoft. Contact other.person@microsoft.com",
        )
        self.assertIsNone(result)
        self.assertIsNone(self.finder._evaluate_email(
            email="sumit.prasad@microsoft.com",
            person_name="Sumit Kumar Prasad",
            company="Microsoft",
            domain=None,
            source_url="https://example.org/team",
            source_text="Sumit Kumar Prasad sumit.prasad@microsoft.com",
        ))

    def test_public_evidence_is_not_claimed_as_verified(self):
        result = self.finder._evaluate_email(
            email="sumit.prasad@microsoft.com",
            person_name="Sumit Kumar Prasad",
            company="Microsoft",
            domain="microsoft.com",
            source_url="https://example.org/team",
            source_text="Sumit Kumar Prasad sumit.prasad@microsoft.com",
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["verification_type"], "PUBLIC_EVIDENCE")
        self.assertFalse(result["verified"])

    def test_pattern_requires_two_observed_name_email_pairs(self):
        detect = PublicEmailFinder._detect_pattern
        self.assertIsNone(detect(
            [("Sumit Kumar Prasad", "sumit.prasad@microsoft.com")],
            "microsoft.com",
        ))
        pattern = detect([
            ("Sumit Kumar Prasad", "sumit.prasad@microsoft.com"),
            ("Rosa Anil George", "rosa.george@microsoft.com"),
        ], "microsoft.com")
        self.assertEqual(pattern["pattern"], "first.last")
        self.assertEqual(len(pattern["pairs"]), 2)


if __name__ == "__main__":
    unittest.main()
