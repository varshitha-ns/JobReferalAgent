import asyncio

from people.public_finder import PublicEmailFinder


async def main():

    finder = PublicEmailFinder()

    queries = [
        '"Sumit Kumar Prasad" "Microsoft" email',
        '"Sumit Kumar Prasad" "Microsoft" contact',
        '"Sumit Kumar Prasad" "Microsoft" "@microsoft.com"',
        '"Sumit Kumar Prasad" "Microsoft" GitHub email',
    ]

    for query in queries:

        print("\n")
        print("=" * 80)
        print("QUERY:")
        print(query)
        print("=" * 80)

        results = await finder.search(
            query=query,
            limit=10,
        )

        for index, result in enumerate(results, 1):

            print("\n" + "-" * 80)

            print(f"RESULT #{index}")

            print("TITLE:")
            print(result.get("title"))

            print("\nURL:")
            print(result.get("url"))

            print("\nSNIPPET:")
            print(result.get("snippet"))

            print("-" * 80)


if __name__ == "__main__":
    asyncio.run(main())