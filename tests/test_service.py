from __future__ import annotations

from dataclasses import replace

from linkding_ai.config import Settings
from linkding_ai.models import AIEnrichment, Bookmark, BookmarkContent, GithubRepository
from linkding_ai.service import SyncService, TagScope


class FakeGithubClient:
    def __init__(self, repositories: list[GithubRepository]) -> None:
        self._repositories = repositories

    def list_starred_repositories(self) -> list[GithubRepository]:
        return self._repositories


class FakeLinkdingClient:
    def __init__(
        self,
        *,
        existing_by_url: dict[str, Bookmark] | None = None,
        bookmarks: list[Bookmark] | None = None,
    ) -> None:
        self.existing_by_url = existing_by_url or {}
        self.bookmarks = bookmarks or []
        self.created: list[Bookmark] = []
        self.updated: list[tuple[int, Bookmark]] = []

    def check_bookmark(self, url: str) -> Bookmark | None:
        return self.existing_by_url.get(url)

    def create_bookmark(self, bookmark: Bookmark) -> Bookmark:
        created = replace(bookmark, id=100 + len(self.created))
        self.created.append(created)
        self.existing_by_url[bookmark.url] = created
        return created

    def update_bookmark(self, bookmark_id: int, bookmark: Bookmark) -> Bookmark:
        updated = replace(bookmark, id=bookmark_id)
        self.updated.append((bookmark_id, updated))
        return updated

    def list_bookmarks(self) -> list[Bookmark]:
        return self.bookmarks


class FakeAIClient:
    def enrich_bookmark(self, content: BookmarkContent, *, max_tags: int) -> AIEnrichment:
        if content.source == "github-star":
            return AIEnrichment(summary="Useful GitHub project summary.", tags=["automation", "python"])
        return AIEnrichment(summary="Useful bookmark summary.", tags=["research", "tools"][:max_tags])


def build_settings() -> Settings:
    return Settings(
        linkding_base_url="https://linkding.example.com",
        linkding_token="token",
        github_token="ghp_example",
        openrouter_api_key="or-key",
        openrouter_model="openai/gpt-4.1-mini",
        sync_interval=3600,
    )


def test_sync_github_stars_creates_ai_enriched_bookmark() -> None:
    repository = GithubRepository(
        id=1,
        name="project",
        full_name="marijn/project",
        html_url="https://github.com/marijn/project",
        description="A neat project",
        topics=["cli", "sync"],
        language="Python",
        stargazers_count=42,
        updated_at="2026-03-20T12:00:00Z",
        readme="# Project\nUseful details",
    )
    linkding = FakeLinkdingClient()
    service = SyncService(
        settings=build_settings(),
        linkding=linkding,
        github=FakeGithubClient([repository]),
        ai=FakeAIClient(),
    )

    report = service.sync_github_stars(enable_ai=True)

    assert report.github_created == 1
    assert report.github_skipped == 0
    assert len(linkding.created) == 1
    created = linkding.created[0]
    assert created.url == repository.html_url
    assert "github" in created.tag_names
    assert "github-star" in created.tag_names
    assert "automation" in created.tag_names
    assert "ai-tagged" in created.tag_names
    assert "Useful GitHub project summary." in (created.notes or "")


def test_sync_github_stars_skips_existing_bookmark() -> None:
    repository = GithubRepository(
        id=1,
        name="project",
        full_name="marijn/project",
        html_url="https://github.com/marijn/project",
    )
    existing = Bookmark(id=9, url=repository.html_url, tag_names=["github"])
    linkding = FakeLinkdingClient(existing_by_url={repository.html_url: existing})
    service = SyncService(
        settings=build_settings(),
        linkding=linkding,
        github=FakeGithubClient([repository]),
        ai=FakeAIClient(),
    )

    report = service.sync_github_stars(enable_ai=True)

    assert report.github_created == 0
    assert report.github_skipped == 1
    assert not linkding.created


def test_tag_existing_bookmarks_updates_only_unprocessed_entries() -> None:
    bookmarks = [
        Bookmark(id=1, url="https://example.com/one", title="One", tag_names=["reading"]),
        Bookmark(id=2, url="https://example.com/two", title="Two", tag_names=["ai-tagged"]),
    ]
    linkding = FakeLinkdingClient(bookmarks=bookmarks)
    service = SyncService(
        settings=build_settings(),
        linkding=linkding,
        github=None,
        ai=FakeAIClient(),
    )

    report = service.tag_existing_bookmarks()

    assert report.bookmarks_tagged == 1
    assert report.bookmarks_skipped == 1
    bookmark_id, updated = linkding.updated[0]
    assert bookmark_id == 1
    assert "research" in updated.tag_names
    assert "ai-tagged" in updated.tag_names
    assert "Useful bookmark summary." in (updated.notes or "")


def test_run_once_with_none_scope_disables_ai_for_github_sync() -> None:
    repository = GithubRepository(
        id=1,
        name="project",
        full_name="marijn/project",
        html_url="https://github.com/marijn/project",
    )
    linkding = FakeLinkdingClient()
    service = SyncService(
        settings=build_settings(),
        linkding=linkding,
        github=FakeGithubClient([repository]),
        ai=FakeAIClient(),
    )

    report = service.run_once(tag_scope=TagScope.NONE)

    assert report.github_created == 1
    created = linkding.created[0]
    assert "ai-tagged" not in created.tag_names
    assert created.notes is None
