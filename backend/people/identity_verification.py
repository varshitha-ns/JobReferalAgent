from people.schemas import (
    PersonProfile,
    VerificationStatus,
)


class IdentityVerifier:

    def verify_company(
        self,
        person: PersonProfile,
        expected_company: str,
    ) -> bool:

        if not person.current_company:
            return False

        return self._same_company(
            person.current_company,
            expected_company,
        )

    def verify_role(
        self,
        person: PersonProfile,
        job_title: str,
    ) -> bool:

        if not person.current_role:
            return False

        role = person.current_role.lower()
        target = job_title.lower()

        job_keywords = set(
            self._normalize_words(target)
        )

        person_keywords = set(
            self._normalize_words(role)
        )

        # Ignore generic words.
        ignored = {
            "software",
            "engineer",
            "engineering",
            "developer",
            "senior",
            "junior",
            "staff",
            "principal",
            "the",
            "and",
        }

        job_keywords -= ignored
        person_keywords -= ignored

        # Direct role match.
        if target in role:
            return True

        # Any meaningful overlap.
        return bool(
            job_keywords.intersection(
                person_keywords
            )
        )

    def mark_company_verified(
        self,
        person: PersonProfile,
    ) -> PersonProfile:

        person.verification_status = (
            VerificationStatus.COMPANY_VERIFIED
        )

        return person

    def mark_role_verified(
        self,
        person: PersonProfile,
    ) -> PersonProfile:

        person.verification_status = (
            VerificationStatus.ROLE_VERIFIED
        )

        return person

    @staticmethod
    def _same_company(
        first: str,
        second: str,
    ) -> bool:

        first_normalized = (
            first.lower()
            .replace(",", "")
            .replace(".", "")
            .strip()
        )

        second_normalized = (
            second.lower()
            .replace(",", "")
            .replace(".", "")
            .strip()
        )

        return (
            first_normalized == second_normalized
            or first_normalized in second_normalized
            or second_normalized in first_normalized
        )

    @staticmethod
    def _normalize_words(
        text: str,
    ) -> list[str]:

        cleaned = (
            text.lower()
            .replace("/", " ")
            .replace("-", " ")
            .replace(",", " ")
        )

        return [
            word
            for word in cleaned.split()
            if word
        ]