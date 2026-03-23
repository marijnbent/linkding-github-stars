from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class GithubRepository:
    id: int
    name: str
    full_name: str
    html_url: str
    description: str | None = None
    topics: list[str] = field(default_factory=list)
    language: str | None = None
    homepage: str | None = None
    stargazers_count: int | None = None
    updated_at: str | None = None
    readme: str | None = None


@dataclass(slots=True)
class Bookmark:
    id: int | None
    url: str
    title: str | None = None
    description: str | None = None
    notes: str | None = None
    tag_names: list[str] = field(default_factory=list)
    unread: bool = False
    shared: bool = False
    is_archived: bool = False


@dataclass(slots=True)
class AIEnrichment:
    summary: str
    tags: list[str]


@dataclass(slots=True)
class BookmarkContent:
    title: str
    url: str
    description: str | None = None
    notes: str | None = None
    source: str = "bookmark"
    extra_context: str | None = None


@dataclass(slots=True)
class SyncReport:
    github_created: int = 0
    github_skipped: int = 0
    github_failed: int = 0
    bookmarks_tagged: int = 0
    bookmarks_skipped: int = 0
    ai_failures: int = 0

