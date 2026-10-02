import asyncio

from people.discovery import PeopleDiscoveryAgent
from people.email_discovery import PublicEmailDiscovery
from people.github import GitHubPublicProfile
from people.sources.search_engine import SearchEngine
from people.schemas import ContactEvidence

async def main():

    company = "Microsoft"
    job_title = "Software Engineer"
    location = "Bangalore"

    search_engine = SearchEngine()

    people_agent = PeopleDiscoveryAgent()

    email_agent = PublicEmailDiscovery()

    github_agent = GitHubPublicProfile()

    print("=" * 70)
    print("REAL CONTACT DISCOVERY")
    print("=" * 70)

    people = await people_agent.discover(
        company=company,
        job_title=job_title,
        location=location,
        limit=5,
    )

    print(
        f"\nFound {len(people)} LinkedIn profiles."
    )

    for person in people:

        print("\n" + "-" * 70)

        print("Name:", person.name)
        print("Role:", person.current_role)
        print("Company:", person.current_company)
        print("LinkedIn:", person.linkedin_url)

        # Public web email
        person = await email_agent.search_public_email(
            person,
            search_engine,
        )

        # Public GitHub email
        if not person.public_email:

            github_result = (
                await github_agent.find_public_email(
                    name=person.name,
                    company=person.current_company,
                )
            )

            if github_result:

                person.public_email = (
                    github_result["email"]
                )

                person.github_url = (
                    github_result["profile_url"]
                )

                person.email_verification_method = (
                    "github_public_profile"
                )

                person.contact_evidence.append(
    ContactEvidence(
        source_url=github_result["profile_url"],
        source_type="github_public_profile",
        evidence=(
            "Email publicly visible on "
            "GitHub profile."
        ),
    )
)

        print(
            "Email:",
            person.public_email
            or "No public email found",
        )

        print(
            "GitHub:",
            person.github_url
            or "Not found",
        )

        print(
            "Email status:",
            (
                person.email_verification_method
                or "not available"
            ),
        )

        print("Evidence:")

        for evidence in person.contact_evidence:
            print(
                f"  [{evidence.source_type}] "
                f"{evidence.source_url}"
            )


if __name__ == "__main__":
    asyncio.run(main())