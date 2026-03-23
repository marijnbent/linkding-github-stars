from __future__ import annotations

import logging
from enum import StrEnum

from .ai import OpenRouterClient
from .config import Settings
from .github import GithubClient
from .linkding import LinkdingClient
from .models import AIEnrichment, Bookmark, BookmarkContent, GithubRepository, SyncReport
from .utils import merge_notes, normalize_tags, render_ai_notes

LOGGER = logging.getLogger(__name__)


class TagScope(StrEnum):
    NONE = "none"
    GITHUB = "github"
    ALL = "all"


class SyncService:
    def __init__(
        self,
        *,
        settings: Settings,
        linkding: LinkdingClient,
        github: GithubClient | None,
        ai: OpenRouterClient | None = None,
    ) -> None:
        self._settings = settings
        self._linkding = linkding
        self._github = github
        self._ai = ai

    def run_once(self, *, tag_scope: TagScope, dry_run: bool = False, force_ai: bool = False) -> SyncReport:
        report = self.sync_github_stars(
            enable_ai=tag_scope != TagScope.NONE,
            dry_run=dry_run,
        )
        if tag_scope == TagScope.ALL:
            all_report = self.tag_existing_bookmarks(dry_run=dry_run, force=force_ai)
            report.bookmarks_tagged += all_report.bookmarks_tagged
            report.bookmarks_skipped += all_report.bookmarks_skipped
            report.ai_failures += all_report.ai_failures
        return report

    def sync_github_stars(self, *, enable_ai: bool, dry_run: bool = False) -> SyncReport:
        if not self._github:
            raise RuntimeError("GitHub sync requested, but no GitHub client is configured")

        report = SyncReport()
        repositories = self._github.list_starred_repositories()

        for repository in repositories:
            try:
                existing = self._linkding.check_bookmark(repository.html_url)
                if existing:
                    report.github_skipped += 1
                    continue

                bookmark = self._build_github_bookmark(repository, enable_ai=enable_ai)
                if dry_run:
                    report.github_created += 1
                    continue

                self._linkding.create_bookmark(bookmark)
                report.github_created += 1
            except Exception:
                LOGGER.exception("Failed to sync GitHub repository %s", repository.full_name)
                report.github_failed += 1
        return report

    def tag_existing_bookmarks(self, *, dry_run: bool = False, force: bool = False) -> SyncReport:
        if not self._ai:
            raise RuntimeError("AI tagging requested, but no AI client is configured")

        report = SyncReport()
        for bookmark in self._linkding.list_bookmarks():
            if self._should_skip_bookmark(bookmark, force=force):
                report.bookmarks_skipped += 1
                continue

            try:
                updated = self._build_ai_updated_bookmark(bookmark)
                if dry_run:
                    report.bookmarks_tagged += 1
                    continue
                self._linkding.update_bookmark(bookmark.id or 0, updated)
                report.bookmarks_tagged += 1
            except Exception:
                LOGGER.exception("Failed to AI-tag bookmark %s", bookmark.url)
                report.ai_failures += 1
        return report

    def _should_skip_bookmark(self, bookmark: Bookmark, *, force: bool) -> bool:
        if bookmark.id is None:
            return True
        if force:
            return False
        return self._settings.ai_processed_tag in bookmark.tag_names

    def _build_github_bookmark(self, repository: GithubRepository, *, enable_ai: bool) -> Bookmark:
        tags = normalize_tags(["github", "github-star", *repository.topics])
        notes = None
        if enable_ai:
            enrichment = self._enrich_github_repository(repository)
            tags = normalize_tags(tags + enrichment.tags + [self._settings.ai_processed_tag])
            notes = render_ai_notes(
                self._settings.ai_summary_label,
                enrichment.summary,
                extra_lines=self._format_github_metadata(repository),
            )
        return Bookmark(
            id=None,
            url=repository.html_url,
            title=repository.full_name,
            description=repository.description,
            notes=notes,
            tag_names=tags,
        )

    def _build_ai_updated_bookmark(self, bookmark: Bookmark) -> Bookmark:
        if not self._ai:
            raise RuntimeError("AI client is not configured")

        enrichment = self._ai.enrich_bookmark(
            BookmarkContent(
                title=bookmark.title or bookmark.url,
                url=bookmark.url,
                description=bookmark.description,
                notes=bookmark.notes,
                source="linkding-bookmark",
            ),
            max_tags=self._settings.max_ai_tags,
        )
        managed_notes = render_ai_notes(
            self._settings.ai_summary_label,
            enrichment.summary,
        )
        return Bookmark(
            id=bookmark.id,
            url=bookmark.url,
            title=bookmark.title,
            description=bookmark.description,
            notes=merge_notes(bookmark.notes, managed_notes),
            tag_names=normalize_tags(
                bookmark.tag_names + enrichment.tags + [self._settings.ai_processed_tag]
            ),
            unread=bookmark.unread,
            shared=bookmark.shared,
            is_archived=bookmark.is_archived,
        )

    def _enrich_github_repository(self, repository: GithubRepository) -> AIEnrichment:
        if not self._ai:
            raise RuntimeError("AI tagging requested, but no AI client is configured")

        context_lines = [
            f"Repository: {repository.full_name}",
            f"Language: {repository.language or 'unknown'}",
            f"Topics: {', '.join(repository.topics) if repository.topics else 'none'}",
            f"Homepage: {repository.homepage or 'none'}",
            f"Stars: {repository.stargazers_count or 'unknown'}",
            f"Updated: {repository.updated_at or 'unknown'}",
            "",
            f"README: {repository.readme or 'No README available.'}",
        ]
        return self._ai.enrich_bookmark(
            BookmarkContent(
                title=repository.full_name,
                url=repository.html_url,
                description=repository.description,
                source="github-star",
                extra_context="\n".join(context_lines),
            ),
            max_tags=self._settings.max_ai_tags,
        )

    @staticmethod
    def _format_github_metadata(repository: GithubRepository) -> list[str]:
        return [
            "Repository metadata:",
            f"- language: {repository.language or 'unknown'}",
            f"- topics: {', '.join(repository.topics) if repository.topics else 'none'}",
            f"- homepage: {repository.homepage or 'none'}",
            f"- stars: {repository.stargazers_count or 'unknown'}",
            f"- updated: {repository.updated_at or 'unknown'}",
        ]
