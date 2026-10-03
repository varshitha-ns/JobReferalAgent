import asyncio

from people.public_finder import PublicEmailFinder


async def main():
    finder = PublicEmailFinder()

    results = await finder.find(
        person_name="Sumit Kumar Prasad",
        company="Microsoft",
        linkedin_url=(
            "https://www.linkedin.com/in/skprasad-kd/"
        ),
        company_domain="microsoft.com",
        max_results=10,
    )

    print("\n========================================")
    print("PUBLIC EMAIL FINDER RESULTS")
    print("========================================")

    if not results:
        print("No public email found.")

    for result in results:
        print("\nEmail:", result["email"])
        print("Verified:", result["verified"])
        print(
            "Verification type:",
            result["verification_type"],
        )
        print(
            "Identity score:",
            result["identity_score"],
        )
        print(
            "Domain verified:",
            result["domain_verified"],
        )
        print(
            "Source:",
            result["source_url"],
        )


if __name__ == "__main__":
    asyncio.run(main())