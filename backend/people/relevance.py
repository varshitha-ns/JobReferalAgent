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

        elif "engineering manager" in role:
            person.contact_type = (
                ContactType.ENGINEERING_MANAGER
            )

        elif (
            "technical lead" in role
            or "tech lead" in role
        ):
            person.contact_type = (
                ContactType.TECH_LEAD
            )

        elif "principal engineer" in role:
            person.contact_type = (
                ContactType.SENIOR_ENGINEER
            )

        elif "staff engineer" in role:
            person.contact_type = (
                ContactType.SENIOR_ENGINEER
            )

        elif "senior software engineer" in role:
            person.contact_type = (
                ContactType.SENIOR_ENGINEER
            )

        elif "software engineer" in role:
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