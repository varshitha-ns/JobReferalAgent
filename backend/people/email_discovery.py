from __future__ import annotations

from typing import Any, Dict, List

from people.github import GitHubSource
from people.public_finder import PublicEmailFinder


class EmailDiscovery:

    def __init__(self):

        self.github = GitHubSource()

        self.public_finder = (
            PublicEmailFinder()
        )

    async def discover(
        self,
        person: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        print()
        print("=" * 70)
        print("EMAIL DISCOVERY PIPELINE")
        print("=" * 70)

        all_candidates = []

        # =====================================================
        # SOURCE 1: GITHUB
        # =====================================================

        try:

            github_results = (
                await self.github.find_public_emails(
                    person
                )
            )

            all_candidates.extend(
                github_results
            )

        except Exception as error:

            print(
                "GitHub discovery failed:",
                type(error).__name__,
                str(error),
            )

        # =====================================================
        # SOURCE 2: PUBLIC WEB
        # =====================================================

        try:

            public_results = (
                await self.public_finder.find_public_emails(
                    person
                )
            )

            all_candidates.extend(
                public_results
            )

        except Exception as error:

            print(
                "Public web discovery failed:",
                type(error).__name__,
                str(error),
            )

        # =====================================================
        # FINAL DEDUPLICATION
        # =====================================================

        unique = {}

        for candidate in all_candidates:

            email = (
                candidate.get("email")
                or ""
            ).lower().strip()

            if not email:
                continue

            # Prefer an already verified
            # candidate if duplicate sources
            # discovered the same email.
            if email not in unique:

                unique[email] = candidate

            elif (
                candidate.get("status")
                == "verified_public"
            ):

                unique[email] = candidate

        final = list(
            unique.values()
        )

        print()
        print("=" * 70)
        print("FINAL EMAIL DISCOVERY RESULT")
        print("=" * 70)

        for candidate in final:

            print(
                f"{candidate['email']} "
                f"| {candidate.get('source')} "
                f"| {candidate.get('status')}"
            )

        print(
            f"Verified contacts: {len(final)}"
        )

        return final