from __future__ import annotations

from typing import Any

import httpx

from .models import Bookmark


class LinkdingClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float,
        user_agent: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "Authorization": f"Token {token}",
                "Content-Type": "application/json",
                "User-Agent": user_agent,
            },
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def check_bookmark(self, url: str) -> Bookmark | None:
        response = self._client.get("/api/bookmarks/check/", params={"url": url})
        response.raise_for_status()
        payload = response.json()
        bookmark = payload.get("bookmark")
        if not bookmark:
            return None
        return self._parse_bookmark(bookmark)

    def create_bookmark(self, bookmark: Bookmark) -> Bookmark:
        response = self._client.post(
            "/api/bookmarks/",
            params={"disable_scraping": "true"},
            json=self._serialize_bookmark(bookmark),
        )
        response.raise_for_status()
        return self._parse_bookmark(response.json())

    def update_bookmark(self, bookmark_id: int, bookmark: Bookmark) -> Bookmark:
        response = self._client.patch(
            f"/api/bookmarks/{bookmark_id}/",
            json=self._serialize_bookmark(bookmark, include_url=False),
        )
        response.raise_for_status()
        return self._parse_bookmark(response.json())

    def list_bookmarks(self) -> list[Bookmark]:
        bookmarks: list[Bookmark] = []
        offset = 0
        limit = 100

        while True:
            response = self._client.get(
                "/api/bookmarks/",
                params={"limit": limit, "offset": offset},
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])
            bookmarks.extend(self._parse_bookmark(item) for item in results)
            if not payload.get("next"):
                break
            offset += limit
        return bookmarks

    @staticmethod
    def _parse_bookmark(payload: dict[str, Any]) -> Bookmark:
        return Bookmark(
            id=payload.get("id"),
            url=payload["url"],
            title=payload.get("title"),
            description=payload.get("description"),
            notes=payload.get("notes"),
            tag_names=payload.get("tag_names") or [],
            unread=payload.get("unread", False),
            shared=payload.get("shared", False),
            is_archived=payload.get("is_archived", False),
        )

    @staticmethod
    def _serialize_bookmark(bookmark: Bookmark, *, include_url: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "title": bookmark.title or "",
            "description": bookmark.description or "",
            "notes": bookmark.notes or "",
            "tag_names": bookmark.tag_names,
            "unread": bookmark.unread,
            "shared": bookmark.shared,
            "is_archived": bookmark.is_archived,
        }
        if include_url:
            payload["url"] = bookmark.url
        return payload

