from __future__ import annotations

import json

import httpx

from linkding_ai.models import Bookmark
from linkding_ai.linkding import LinkdingClient


def test_check_bookmark_parses_linkding_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/api/bookmarks/check/"
        payload = {
            "bookmark": {
                "id": 7,
                "url": "https://example.com",
                "title": "Example",
                "description": "Description",
                "notes": "Notes",
                "tag_names": ["one", "two"],
                "unread": False,
                "shared": False,
                "is_archived": False,
            },
        }
        return httpx.Response(200, content=json.dumps(payload))

    client = LinkdingClient(
        base_url="https://linkding.example.com",
        token="token",
        timeout=5.0,
        user_agent="test-agent",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://linkding.example.com",
        ),
    )

    bookmark = client.check_bookmark("https://example.com")

    assert bookmark is not None
    assert bookmark.id == 7
    assert bookmark.url == "https://example.com"
    assert bookmark.tag_names == ["one", "two"]


def test_create_bookmark_retries_retryable_statuses() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        assert request.method == "POST"
        assert request.url.path == "/api/bookmarks/"
        if attempts["count"] < 3:
            return httpx.Response(502, content="bad gateway", request=request)

        payload = {
            "id": 8,
            "url": "https://example.com/new",
            "title": "Example",
            "description": "Description",
            "notes": "Notes",
            "tag_names": ["github-star"],
            "unread": False,
            "shared": False,
            "is_archived": False,
        }
        return httpx.Response(201, content=json.dumps(payload), request=request)

    client = LinkdingClient(
        base_url="https://linkding.example.com",
        token="token",
        timeout=5.0,
        user_agent="test-agent",
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://linkding.example.com",
        ),
    )

    bookmark = client.create_bookmark(
        Bookmark(
            id=None,
            url="https://example.com/new",
            title="Example",
            description="Description",
            notes="Notes",
            tag_names=["github-star"],
        )
    )

    assert attempts["count"] == 3
    assert bookmark.id == 8
    assert bookmark.url == "https://example.com/new"
