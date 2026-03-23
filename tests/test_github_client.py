from __future__ import annotations

import json

import httpx

from linkding_ai.github import GithubClient


def test_list_starred_repositories_falls_back_to_anonymous_readme() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/starred":
            page = request.url.params.get("page")
            if page and page != "1":
                return httpx.Response(200, content="[]")
            payload = [
                {
                    "id": 1,
                    "name": "project",
                    "full_name": "marijn/project",
                    "html_url": "https://github.com/marijn/project",
                    "owner": {"login": "marijn"},
                    "topics": ["python"],
                }
            ]
            return httpx.Response(200, content=json.dumps(payload))
        if request.url.path == "/repos/marijn/project/readme":
            auth = request.headers.get("Authorization")
            if auth:
                return httpx.Response(403, content=json.dumps({"message": "Forbidden"}))
            return httpx.Response(
                200,
                content=json.dumps(
                    {
                        "content": "IyBQcm9qZWN0Cg==",
                        "encoding": "base64",
                    }
                ),
            )
        return httpx.Response(200, content="[]")

    client = GithubClient(
        token="token",
        base_url="https://api.github.com",
        timeout=5.0,
        user_agent="test-agent",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
        ),
        anonymous_client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
        ),
    )

    repositories = client.list_starred_repositories()

    assert len(repositories) == 1
    assert repositories[0].readme == "# Project\n"


def test_list_starred_repositories_skips_unreadable_readme() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/starred":
            page = request.url.params.get("page")
            if page and page != "1":
                return httpx.Response(200, content="[]")
            payload = [
                {
                    "id": 1,
                    "name": "project",
                    "full_name": "marijn/project",
                    "html_url": "https://github.com/marijn/project",
                    "owner": {"login": "marijn"},
                    "topics": ["python"],
                }
            ]
            return httpx.Response(200, content=json.dumps(payload))
        if request.url.path == "/repos/marijn/project/readme":
            return httpx.Response(403, content=json.dumps({"message": "Forbidden"}))
        return httpx.Response(200, content="[]")

    client = GithubClient(
        token="token",
        base_url="https://api.github.com",
        timeout=5.0,
        user_agent="test-agent",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
        ),
        anonymous_client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.github.com",
        ),
    )

    repositories = client.list_starred_repositories()

    assert len(repositories) == 1
    assert repositories[0].readme is None
