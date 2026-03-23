from __future__ import annotations

import base64
import logging

import httpx

from .models import GithubRepository

LOGGER = logging.getLogger(__name__)


class GithubClient:
    def __init__(
        self,
        *,
        token: str,
        base_url: str,
        timeout: float,
        user_agent: str,
        client: httpx.Client | None = None,
        anonymous_client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self._owns_anonymous_client = anonymous_client is None
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": user_agent,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        self._anonymous_client = anonymous_client or httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": user_agent,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()
        if self._owns_anonymous_client:
            self._anonymous_client.close()

    def list_starred_repositories(self) -> list[GithubRepository]:
        repositories: list[GithubRepository] = []
        page = 1
        while True:
            response = self._client.get(
                "/user/starred",
                params={"per_page": 100, "page": page},
            )
            response.raise_for_status()
            payload = response.json()
            if not payload:
                break

            for item in payload:
                owner = item["owner"]["login"]
                name = item["name"]
                repositories.append(
                    GithubRepository(
                        id=item["id"],
                        name=name,
                        full_name=item["full_name"],
                        html_url=item["html_url"],
                        description=item.get("description"),
                        topics=item.get("topics") or [],
                        language=item.get("language"),
                        homepage=item.get("homepage"),
                        stargazers_count=item.get("stargazers_count"),
                        updated_at=item.get("updated_at"),
                        readme=self._fetch_readme(owner, name),
                    )
                )
            page += 1
        return repositories

    def _fetch_readme(self, owner: str, name: str) -> str | None:
        response = self._client.get(f"/repos/{owner}/{name}/readme")
        if response.status_code == 404:
            return None
        if response.status_code == 403:
            anonymous_response = self._anonymous_client.get(f"/repos/{owner}/{name}/readme")
            if anonymous_response.status_code == 404:
                return None
            if not anonymous_response.is_error:
                LOGGER.info(
                    "Fetched README for %s/%s via anonymous GitHub access after token 403",
                    owner,
                    name,
                )
                response = anonymous_response
            else:
                LOGGER.warning(
                    "Skipping README for %s/%s after token 403 and anonymous response %s",
                    owner,
                    name,
                    anonymous_response.status_code,
                )
                return None
        elif response.is_error:
            LOGGER.warning(
                "Skipping README for %s/%s due to GitHub response %s",
                owner,
                name,
                response.status_code,
            )
            return None
        payload = response.json()
        content = payload.get("content")
        if not content:
            return None
        encoding = payload.get("encoding")
        if encoding != "base64":
            return None
        return base64.b64decode(content).decode("utf-8", errors="ignore")
