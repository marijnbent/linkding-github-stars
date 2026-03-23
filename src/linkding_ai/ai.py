from __future__ import annotations

from typing import Any

import httpx

from .models import AIEnrichment, BookmarkContent
from .utils import compact_text, extract_json_object, normalize_tags


class OpenRouterClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float,
        app_name: str,
        site_url: str | None,
        client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": site_url or "https://localhost",
            "X-Title": app_name,
        }
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers=headers,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def enrich_bookmark(self, content: BookmarkContent, *, max_tags: int) -> AIEnrichment:
        prompt = self._build_prompt(content=content, max_tags=max_tags)
        response = self._client.post(
            "/chat/completions",
            json={
                "model": self._model,
                "temperature": 0.2,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You generate bookmark summaries and tags. "
                            "Return strict JSON with keys summary and tags."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        payload = response.json()
        message = payload["choices"][0]["message"]
        parsed = self._parse_content(message)
        summary = compact_text(str(parsed.get("summary") or ""), limit=600)
        tags_value = parsed.get("tags") or []
        if not isinstance(tags_value, list):
            raise ValueError("AI response did not contain a tag list")
        tags = normalize_tags([str(tag) for tag in tags_value])[:max_tags]
        return AIEnrichment(summary=summary, tags=tags)

    def _parse_content(self, message: dict[str, Any]) -> dict[str, object]:
        content = message.get("content")
        if isinstance(content, str):
            return extract_json_object(content)
        if isinstance(content, list):
            combined = "\n".join(
                part.get("text", "")
                for part in content
                if isinstance(part, dict)
            )
            return extract_json_object(combined)
        raise ValueError("Unexpected AI response content format")

    @staticmethod
    def _build_prompt(*, content: BookmarkContent, max_tags: int) -> str:
        sections = [
            "Analyze this bookmark and produce JSON.",
            f"Source: {content.source}",
            f"Title: {compact_text(content.title, limit=300)}",
            f"URL: {content.url}",
            f"Description: {compact_text(content.description, limit=1000)}",
            f"Existing notes: {compact_text(content.notes, limit=1500)}",
            f"Extra context: {compact_text(content.extra_context, limit=3000)}",
            "",
            "Rules:",
            "- summary must be 1-3 sentences, concrete, and useful for rediscovery.",
            f"- tags must be a JSON array with at most {max_tags} short lowercase topical tags.",
            "- avoid generic tags like bookmark, github, repo, link, article, tech unless truly essential.",
            "- prefer topic/domain/use-case tags.",
            "",
            'Return only JSON like {"summary": "...", "tags": ["tag-one"]}.',
        ]
        return "\n".join(sections)

