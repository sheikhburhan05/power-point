"""Run-level text replacement preserving style."""

from __future__ import annotations

from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Pt

from src.models import StyleHint, TextBlock


def _apply_alignment(paragraph, alignment: str | None) -> None:
    if not alignment:
        return
    mapping = {
        "left": PP_ALIGN.LEFT,
        "center": PP_ALIGN.CENTER,
        "right": PP_ALIGN.RIGHT,
        "justify": PP_ALIGN.JUSTIFY,
    }
    if alignment in mapping:
        paragraph.alignment = mapping[alignment]


def _copy_font(source_font, target_font) -> None:
    if source_font.name:
        target_font.name = source_font.name
    if source_font.size:
        target_font.size = source_font.size
    if source_font.bold is not None:
        target_font.bold = source_font.bold
    if source_font.italic is not None:
        target_font.italic = source_font.italic
    try:
        if source_font.color and source_font.color.rgb:
            target_font.color.rgb = source_font.color.rgb
    except Exception:
        pass


def _apply_style_to_run(run, style: StyleHint, fallback_run=None) -> None:
    if fallback_run:
        _copy_font(fallback_run.font, run.font)
    if style.font_name:
        run.font.name = style.font_name
    if style.size_pt:
        run.font.size = Pt(style.size_pt)
    if style.bold is not None:
        run.font.bold = style.bold
    if style.italic is not None:
        run.font.italic = style.italic


def _clear_text_frame(text_frame) -> None:
    text_frame.clear()
    if not text_frame.paragraphs:
        text_frame.add_paragraph()


def replace_text_in_frame(text_frame, new_text: str, block: TextBlock) -> None:
    """Replace all text in a text frame while preserving dominant styling."""
    paragraphs = new_text.split("\n")
    if not paragraphs:
        paragraphs = [""]

    # Pad or trim to match expected paragraph count when possible
    expected = max(1, block.paragraph_count)
    while len(paragraphs) < expected:
        paragraphs.append("")
    if len(paragraphs) > expected and expected == 1:
        paragraphs = [" ".join(paragraphs)]

    fallback_run = None
    if text_frame.paragraphs and text_frame.paragraphs[0].runs:
        fallback_run = text_frame.paragraphs[0].runs[0]

    _clear_text_frame(text_frame)

    for idx, para_text in enumerate(paragraphs[: max(len(paragraphs), expected)]):
        if idx == 0:
            para = text_frame.paragraphs[0]
        else:
            para = text_frame.add_paragraph()
        level = block.bullet_levels[idx] if idx < len(block.bullet_levels) else 0
        para.level = level
        _apply_alignment(para, block.style_hint.alignment)
        run = para.add_run()
        run.text = para_text
        _apply_style_to_run(run, block.style_hint, fallback_run)


def apply_autofit(text_frame, role: str) -> None:
    text_frame.word_wrap = True
    if role in {"title", "label", "table_cell", "subtitle"}:
        text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    elif role == "body":
        text_frame.auto_size = MSO_AUTO_SIZE.NONE
    else:
        text_frame.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
