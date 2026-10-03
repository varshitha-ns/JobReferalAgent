import asyncio

from people.github import GitHubSource


async def main():

    source = GitHubSource()

    person = {
        "name": "Sumit Kumar Prasad",
        "company": "Microsoft",
        "linkedin_url": (
            "https://www.linkedin.com/in/skprasad-kd/"
        ),
    }

    results = await source.find_public_emails(
        person
    )

    print("\n")
    print("========================================")
    print("FINAL RESULTS")
    print("========================================")

    if not results:

        print(
            "No verified/public GitHub email evidence found."
        )

    for result in results:

        print(
            f"Email: {result['email']}"
        )

        print(
            f"Source: {result['source']}"
        )

        print(
            f"URL: {result['source_url']}"
        )

        print(
            f"Identity score: "
            f"{result['identity_score']:.2f}"
        )


if __name__ == "__main__":
    asyncio.run(main())