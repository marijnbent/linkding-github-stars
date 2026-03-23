from __future__ import annotations

import json
import re
from collections import OrderedDict


MANAGED_NOTES_START = "<!-- linkding-ai:start -->"
MANAGED_NOTES_END = "<!-- linkding-ai:end -->"


def normalize_tags(tags: list[str]) -> list[str]:
    normalized: "OrderedDict[str, str]" = OrderedDict()
    for tag in tags:
        cleaned = re.sub(r"\s+", "-", tag.strip().lower())
        cleaned = re.sub(r"[^a-z0-9:_\-./+]", "", cleaned)
        cleaned = cleaned.strip("-")
        if cleaned and cleaned not in normalized:
            normalized[cleaned] = cleaned
    return list(normalized.values())


def compact_text(value: str | None, limit: int = 4000) -> str:
    if not value:
        return ""
    compacted = re.sub(r"\s+", " ", value).strip()
    return compacted[:limit]


def render_ai_notes(summary_label: str, summary: str, extra_lines: list[str] | None = None) -> str:
    lines = [MANAGED_NOTES_START, f"{summary_label}:", summary.strip()]
    if extra_lines:
        lines.extend(["", *extra_lines])
    lines.append(MANAGED_NOTES_END)
    return "\n".join(lines).strip()


def merge_notes(existing_notes: str | None, managed_block: str) -> str:
    if not existing_notes:
        return managed_block

    pattern = re.compile(
        rf"{re.escape(MANAGED_NOTES_START)}.*?{re.escape(MANAGED_NOTES_END)}",
        re.DOTALL,
    )
    if pattern.search(existing_notes):
        merged = pattern.sub(managed_block, existing_notes)
    else:
        merged = f"{existing_notes.rstrip()}\n\n{managed_block}"
    return merged.strip()


def extract_json_object(text: str) -> dict[str, object]:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))

