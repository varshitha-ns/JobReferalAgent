import asyncio

from people.discovery import PeopleDiscoveryAgent


async def main():

    agent = PeopleDiscoveryAgent()

    people = await agent.discover(
        company="Microsoft",
        job_title="Software Engineer",
        location="Bangalore",
        limit=5,
    )

    print("=" * 60)
    print("PEOPLE DISCOVERY RESULTS")
    print("=" * 60)

    for person in people:

        print()
        print("Name:", person.name)
        print("Company:", person.current_company)
        print("Role:", person.current_role)
        print("LinkedIn:", person.linkedin_url)
        print("Email:", person.public_email)

        print("Reasons:")

        for reason in person.relevance_reasons:
            print(" -", reason)

        print("Evidence:")

        for evidence in person.contact_evidence:
            print(
                " -",
                evidence.source_type,
                evidence.source_url,
            )


if __name__ == "__main__":
    asyncio.run(main())