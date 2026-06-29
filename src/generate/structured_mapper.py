"""Map structured input JSON (title, sections, bullets) to ContentMapping."""

from __future__ import annotations

from pathlib import Path

from langsmith import traceable

from src.models import (
    BlockMapping,
    ContentMapping,
    LayoutDoc,
    StructuredContentDoc,
    TextBlock,
)


def load_structured_content(path: str | Path) -> StructuredContentDoc:
    return StructuredContentDoc.model_validate_json(Path(path).read_text(encoding="utf-8"))


def _block_sort_key(block: TextBlock) -> tuple:
    slide_idx = int(block.block_id.split("/")[0])
    return (slide_idx, block.top_in, block.left_in, block.block_id)


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3].rstrip() + "..."


def _is_column_header(block: TextBlock) -> bool:
    return (
        block.role == "body"
        and block.char_limit <= 40
        and block.style_hint.color_rgb == "575757"
        and block.style_hint.alignment == "center"
    )


def _is_chevron_label(block: TextBlock) -> bool:
    return block.role == "label" and block.style_hint.color_rgb == "FFFFFF"


def _is_description_body(block: TextBlock) -> bool:
    return (
        block.role == "body"
        and block.char_limit == 60
        and block.style_hint.color_type == "scheme"
        and block.style_hint.color_theme == "BACKGROUND_2"
    )


def _is_legend_or_footer(block: TextBlock) -> bool:
    if block.top_in >= 6.2:
        return True
    if block.block_id.startswith("0/shapes[6]"):
        return True
    return False


def _column_side(block: TextBlock) -> str:
    return "left" if block.left_in < 5.0 else "right"


def _pick_title(blocks: list[TextBlock], used: set[str]) -> TextBlock | None:
    pool = [b for b in blocks if b.block_id not in used and b.role == "title"]
    pool.sort(key=_block_sort_key)
    return pool[0] if pool else None


def _pick_column_headers(
    blocks: list[TextBlock], used: set[str]
) -> tuple[TextBlock | None, TextBlock | None]:
    pool = [
        b
        for b in blocks
        if b.block_id not in used and _is_column_header(b) and not _is_legend_or_footer(b)
    ]
    pool.sort(key=lambda b: (b.left_in, b.top_in))
    left = next((b for b in pool if _column_side(b) == "left"), None)
    right = next((b for b in pool if _column_side(b) == "right"), None)
    return left, right


def _pick_chevron_labels(
    blocks: list[TextBlock], used: set[str], side: str
) -> list[TextBlock]:
    pool = [
        b
        for b in blocks
        if b.block_id not in used
        and _is_chevron_label(b)
        and _column_side(b) == side
        and not _is_legend_or_footer(b)
    ]
    pool.sort(key=lambda b: (b.top_in, b.left_in))
    return pool


def _pick_description_bodies(
    blocks: list[TextBlock], used: set[str], side: str
) -> list[TextBlock]:
    pool = [
        b
        for b in blocks
        if b.block_id not in used
        and _is_description_body(b)
        and _column_side(b) == side
        and not _is_legend_or_footer(b)
    ]
    pool.sort(key=lambda b: (b.top_in, b.left_in))
    return pool


@traceable(name="map_structured_content", run_type="chain")
def map_structured_content(
    layout: LayoutDoc,
    structured: StructuredContentDoc,
) -> ContentMapping:
    """Map pre-written structured JSON onto slide blocks without LLM generation."""
    blocks = sorted(
        [b for slide in layout.slides for b in slide.blocks],
        key=_block_sort_key,
    )
    used: set[str] = set()
    mappings: list[BlockMapping] = []

    title_block = _pick_title(blocks, used)
    if title_block:
        used.add(title_block.block_id)
        mappings.append(
            BlockMapping(
                block_id=title_block.block_id,
                new_text=_truncate(structured.title, title_block.char_limit),
                reasoning="structured:title",
            )
        )

    left_header, right_header = _pick_column_headers(blocks, used)
    sections = structured.content_sections
    if left_header and len(sections) >= 1:
        used.add(left_header.block_id)
        mappings.append(
            BlockMapping(
                block_id=left_header.block_id,
                new_text=_truncate(sections[0].subtitle, left_header.char_limit),
                reasoning="structured:subtitle",
            )
        )
    if right_header and len(sections) >= 2:
        used.add(right_header.block_id)
        mappings.append(
            BlockMapping(
                block_id=right_header.block_id,
                new_text=_truncate(sections[1].subtitle, right_header.char_limit),
                reasoning="structured:subtitle",
            )
        )

    for section_idx, side in enumerate(("left", "right")):
        if section_idx >= len(sections):
            break
        section = sections[section_idx]
        chevrons = _pick_chevron_labels(blocks, used, side)
        bodies = _pick_description_bodies(blocks, used, side)

        for bullet, chevron in zip(section.bullets, chevrons):
            used.add(chevron.block_id)
            mappings.append(
                BlockMapping(
                    block_id=chevron.block_id,
                    new_text=_truncate(bullet.header, chevron.char_limit),
                    reasoning="structured:header",
                )
            )

        for bullet, body in zip(section.bullets, bodies):
            used.add(body.block_id)
            mappings.append(
                BlockMapping(
                    block_id=body.block_id,
                    new_text=_truncate(bullet.content, body.char_limit),
                    reasoning="structured:body",
                )
            )

    for block in blocks:
        if block.block_id in used:
            continue
        mappings.append(
            BlockMapping(
                block_id=block.block_id,
                new_text=block.original_text,
                reasoning="structured:preserve_original",
            )
        )

    return ContentMapping(topic=structured.title, mappings=mappings)
