import asyncio

from people.github import GitHubPublicSource


async def main():

    finder = GitHubPublicSource()

    result = await finder.find_public_email(
    person_name="Sumit Kumar Prasad",
    company="Microsoft",
    linkedin_url="https://www.linkedin.com/in/skprasad-kd/",
)

    print("\n========================================")
    print("GITHUB EMAIL RESULT")
    print("========================================")

    if not result:
        print("No public GitHub email found.")
        return

    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())