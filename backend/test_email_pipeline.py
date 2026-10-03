import asyncio

from people.email_discovery import EmailDiscovery


async def main():

    people = [
        {
            "name": "Sumit Kumar Prasad",
            "company": "Microsoft",
            "title": "Software Engineer",
            "linkedin_url": (
                "https://www.linkedin.com/in/skprasad-kd/"
            ),
        }
    ]

    discovery = EmailDiscovery()

    for person in people:

        print()
        print("#" * 80)
        print("PERSON")
        print("#" * 80)

        print(
            person["name"]
        )

        print(
            person["company"]
        )

        print(
            person["title"]
        )

        results = await discovery.discover(
            person
        )

        print()
        print("#" * 80)
        print("RESULT")
        print("#" * 80)

        if not results:

            print(
                "NO VERIFIED PUBLIC EMAIL"
            )

        for result in results:

            print(
                "Email:",
                result["email"],
            )

            print(
                "Source:",
                result.get("source"),
            )

            print(
                "URL:",
                result.get("source_url"),
            )

            print(
                "Status:",
                result.get("status"),
            )

            print(
                "Verification:",
                result.get(
                    "verification"
                ),
            )


if __name__ == "__main__":
    asyncio.run(main())