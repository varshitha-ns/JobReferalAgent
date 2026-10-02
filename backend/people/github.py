import re
from typing import Optional

import httpx


class GitHubPublicProfile:

    def __init__(self):
        self.api_url = "https://api.github.com"

    async def find_public_email(
        self,
        name: str,
        company: str | None = None,
    ) -> Optional[dict]:

        query_parts = [name]

        if company:
            query_parts.append(company)

        query = " ".join(query_parts)

        params = {
            "q": query,
            "per_page": 5,
        }

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
        ) as client:

            response = await client.get(
                f"{self.api_url}/search/users",
                params=params,
                headers=headers,
            )

        response.raise_for_status()

        users = response.json().get(
            "items",
            [],
        )

        for user in users:

            username = user.get("login")

            if not username:
                continue

            profile = await self._get_user(
                username
            )

            if not profile:
                continue

            email = profile.get("email")

            if email:
                return {
                    "username": username,
                    "profile_url": profile.get(
                        "html_url"
                    ),
                    "email": email,
                    "name": profile.get(
                        "name"
                    ),
                    "company": profile.get(
                        "company"
                    ),
                }

        return None

    async def _get_user(
        self,
        username: str,
    ) -> Optional[dict]:

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        }

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
        ) as client:

            response = await client.get(
                f"{self.api_url}/users/{username}",
                headers=headers,
            )

        if response.status_code != 200:
            return None

        return response.json()