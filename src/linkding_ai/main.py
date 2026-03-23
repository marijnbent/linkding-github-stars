from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

import typer

from .ai import OpenRouterClient
from .config import Settings, get_settings
from .github import GithubClient
from .linkding import LinkdingClient
from .service import SyncService, TagScope

app = typer.Typer(help="Sync GitHub stars into Linkding and enrich bookmarks with AI tags.")


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@contextmanager
def build_service(settings: Settings) -> Iterator[SyncService]:
    linkding = LinkdingClient(
        base_url=settings.linkding_base_url,
        token=settings.linkding_token,
        timeout=settings.request_timeout,
        user_agent=settings.user_agent,
    )
    github = None
    if settings.github_token:
        github = GithubClient(
            token=settings.github_token,
            base_url=settings.github_api_base_url,
            timeout=settings.request_timeout,
            user_agent=settings.user_agent,
        )
    ai = None
    if settings.openrouter_api_key and settings.openrouter_model:
        ai = OpenRouterClient(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
            timeout=settings.request_timeout,
            app_name=settings.openrouter_app_name,
            site_url=settings.openrouter_site_url,
        )
    try:
        yield SyncService(settings=settings, linkding=linkding, github=github, ai=ai)
    finally:
        linkding.close()
        if github:
            github.close()
        if ai:
            ai.close()


def require_ai(settings: Settings, tag_scope: TagScope) -> None:
    if tag_scope == TagScope.NONE:
        return
    if not settings.openrouter_api_key or not settings.openrouter_model:
        raise typer.BadParameter(
            "AI tagging needs OPENROUTER_API_KEY and OPENROUTER_MODEL unless --tag-scope none is used."
        )


def require_github(settings: Settings) -> None:
    if not settings.github_token:
        raise typer.BadParameter("GitHub sync needs GITHUB_TOKEN.")


def emit_report(report_name: str, report) -> None:
    typer.echo(
        (
            f"{report_name}: "
            f"github_created={report.github_created} "
            f"github_skipped={report.github_skipped} "
            f"github_failed={report.github_failed} "
            f"bookmarks_tagged={report.bookmarks_tagged} "
            f"bookmarks_skipped={report.bookmarks_skipped} "
            f"ai_failures={report.ai_failures}"
        )
    )


@app.command("run-once")
def run_once(
    tag_scope: TagScope = typer.Option(TagScope.GITHUB, help="AI tagging scope for this run."),
    dry_run: bool = typer.Option(False, help="Compute changes without writing to Linkding."),
    force_ai: bool = typer.Option(False, help="Re-tag bookmarks even if already marked as AI processed."),
) -> None:
    """Run a single sync cycle."""

    configure_logging()
    settings = get_settings()
    require_github(settings)
    require_ai(settings, tag_scope)
    with build_service(settings) as service:
        report = service.run_once(tag_scope=tag_scope, dry_run=dry_run, force_ai=force_ai)
    emit_report("run-once", report)


@app.command("sync-github-stars")
def sync_github_stars(
    with_ai: bool = typer.Option(True, "--with-ai/--without-ai", help="AI-enrich imported GitHub stars."),
    dry_run: bool = typer.Option(False, help="Compute changes without writing to Linkding."),
) -> None:
    """Sync GitHub stars into Linkding."""

    configure_logging()
    settings = get_settings()
    require_github(settings)
    if with_ai:
        require_ai(settings, TagScope.GITHUB)
    with build_service(settings) as service:
        report = service.sync_github_stars(enable_ai=with_ai, dry_run=dry_run)
    emit_report("sync-github-stars", report)


@app.command("tag-bookmarks")
def tag_bookmarks(
    dry_run: bool = typer.Option(False, help="Compute changes without writing to Linkding."),
    force: bool = typer.Option(False, help="Re-tag bookmarks that already have the AI processed tag."),
) -> None:
    """AI-tag existing Linkding bookmarks."""

    configure_logging()
    settings = get_settings()
    require_ai(settings, TagScope.ALL)
    with build_service(settings) as service:
        report = service.tag_existing_bookmarks(dry_run=dry_run, force=force)
    emit_report("tag-bookmarks", report)


@app.command("serve")
def serve(
    tag_scope: TagScope = typer.Option(TagScope.GITHUB, help="AI tagging scope for each scheduled run."),
) -> None:
    """Run the sync loop forever using SYNC_INTERVAL seconds between runs."""

    configure_logging()
    settings = get_settings()
    require_github(settings)
    require_ai(settings, tag_scope)

    while True:
        with build_service(settings) as service:
            report = service.run_once(tag_scope=tag_scope, dry_run=False, force_ai=False)
        emit_report("serve", report)
        time.sleep(settings.sync_interval)


if __name__ == "__main__":
    app()
