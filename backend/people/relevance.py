from people.schemas import (
    ContactType,
    PersonProfile,
)


class ContactRelevance:

    def classify(
        self,
        person: PersonProfile,
    ) -> PersonProfile:

        role = (
            person.current_role or ""
        ).lower()

        if "talent acquisition" in role:
            person.contact_type = (
                ContactType.TALENT_ACQUISITION
            )

        elif "recruiter" in role:
            person.contact_type = (
                ContactType.RECRUITER
            )

        elif any(term in role for term in (
            "engineering manager", "software engineering manager",
            "data engineering manager",
            "director of engineering", "head of engineering", "vp engineering",
        )):
            person.contact_type = (
                ContactType.ENGINEERING_MANAGER
            )

        elif (
            "technical lead" in role
            or "tech lead" in role
            or "engineering lead" in role
            or "lead software engineer" in role
        ):
            person.contact_type = (
                ContactType.TECH_LEAD
            )

        elif any(level in role for level in ("principal", "staff", "senior")) and any(
            craft in role for craft in ("engineer", "developer")
        ):
            person.contact_type = (
                ContactType.SENIOR_ENGINEER
            )

        elif any(term in role for term in (
            "software engineer", "ai engineer", "machine learning engineer",
            "ml engineer", "data engineer", "analytics engineer", "developer",
        )):
            person.contact_type = (
                ContactType.ENGINEER
            )

        else:
            person.contact_type = (
                ContactType.OTHER
            )

        person.relevance_reasons.append(
            f"Contact type: "
            f"{person.contact_type.value}"
        )

        return person

    @staticmethod
    def priority(person: PersonProfile, job_title: str = "") -> float:
        """Estimate how useful this person is as a referral route.

        This is a ranking hint from a public title, not a claim that the person
        will refer the applicant. Team peers remain valuable, but leads and
        senior engineers are ranked first; recruiting staff are secondary.
        """
        scores = {
            ContactType.ENGINEERING_MANAGER: 0.90,
            ContactType.TECH_LEAD: 0.88,
            ContactType.SENIOR_ENGINEER: 0.86,
            ContactType.ENGINEER: 0.74,
            ContactType.RECRUITER: 0.65,
            ContactType.TALENT_ACQUISITION: 0.62,
            ContactType.OTHER: 0.30,
        }
        score = scores.get(person.contact_type, 0.30)
        if person.public_email:
            # A sourced route is valuable, but cannot make an unrelated
            # person outrank a strong technical referral contact.
            score += 0.12
        role = (person.current_role or "").lower()
        job = (job_title or "").lower()
        specialized = (
            "data", "ai", "machine learning", "ml", "genai", "analytics",
            "adf", "sql", "python",
        )
        if any(term in role for term in specialized) and any(term in job for term in specialized):
            score += 0.16
        if role and job and role in job:
            score += 0.03
        return min(score, 1.0)

    @classmethod
    def sort_key(cls, person: PersonProfile, job_title: str = "") -> tuple:
        # Point-of-contact strength leads; sourced email breaks close ties.
        return (
            0 if person.location_verified is True else 1,
            -cls.priority(person, job_title),
            not bool(person.public_email),
            (person.name or "").casefold(),
        )
