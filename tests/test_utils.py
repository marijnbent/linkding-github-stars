from linkding_ai.utils import (
    MANAGED_NOTES_END,
    MANAGED_NOTES_START,
    merge_notes,
    normalize_tags,
    render_ai_notes,
)


def test_normalize_tags_deduplicates_and_sanitizes() -> None:
    tags = normalize_tags(["Python", "python", "Machine Learning", "C++", " ", "Dev/Tools"])
    assert tags == ["python", "machine-learning", "c++", "dev/tools"]


def test_merge_notes_replaces_existing_managed_block() -> None:
    original = (
        "My manual note.\n\n"
        f"{MANAGED_NOTES_START}\n"
        "AI Summary:\n"
        "Old summary\n"
        f"{MANAGED_NOTES_END}"
    )
    replacement = render_ai_notes("AI Summary", "New summary")

    merged = merge_notes(original, replacement)

    assert "My manual note." in merged
    assert "Old summary" not in merged
    assert "New summary" in merged

