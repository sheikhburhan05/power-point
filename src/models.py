"""Pydantic models for layout extraction and content mapping."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["title", "subtitle", "body", "label", "table_cell", "other"]


class StyleHint(BaseModel):
    font_name: str | None = None
    size_pt: float | None = None
    bold: bool | None = None
    italic: bool | None = None
    alignment: str | None = None
    color_rgb: str | None = None
    color_theme: str | None = None
    color_type: str | None = None  # rgb | scheme | preset | inherit
    color_brightness: float | None = None  # scheme/tint modifier (-1..1), e.g. -0.9 for near-black bg2


class TextBlock(BaseModel):
    block_id: str
    role: Role
    original_text: str
    char_limit: int
    paragraph_count: int
    bullet_levels: list[int] = Field(default_factory=list)
    style_hint: StyleHint = Field(default_factory=StyleHint)
    left_in: float = 0.0
    top_in: float = 0.0
    width_in: float = 0.0
    height_in: float = 0.0
    is_placeholder: bool = False
    placeholder_type: str | None = None


class NonTextShape(BaseModel):
    block_id: str
    shape_type: str
    editable: bool = False
    left_in: float = 0.0
    top_in: float = 0.0
    width_in: float = 0.0
    height_in: float = 0.0


class ChartSeries(BaseModel):
    name: str
    values: list[float]


class ChartBlock(BaseModel):
    block_id: str
    role: Literal["chart"] = "chart"
    chart_type: str
    title: str = ""
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    category_count: int = 0
    series_count: int = 0
    left_in: float = 0.0
    top_in: float = 0.0
    width_in: float = 0.0
    height_in: float = 0.0


class SlideLayout(BaseModel):
    slide_index: int
    layout_name: str
    slide_xml_path: str
    blocks: list[TextBlock] = Field(default_factory=list)
    charts: list[ChartBlock] = Field(default_factory=list)
    non_text_shapes: list[NonTextShape] = Field(default_factory=list)


class LayoutDoc(BaseModel):
    source_file: str
    slides: list[SlideLayout] = Field(default_factory=list)


class BlockMapping(BaseModel):
    block_id: str
    new_text: str
    reasoning: str | None = None


class ChartMapping(BaseModel):
    block_id: str
    title: str = ""
    categories: list[str] = Field(default_factory=list)
    series: list[ChartSeries] = Field(default_factory=list)
    reasoning: str | None = None


class ContentMapping(BaseModel):
    topic: str
    mappings: list[BlockMapping] = Field(default_factory=list)
    chart_mappings: list[ChartMapping] = Field(default_factory=list)


class StructuredBullet(BaseModel):
    header: str
    content: str


class StructuredSection(BaseModel):
    subtitle: str
    bullets: list[StructuredBullet] = Field(default_factory=list)


class StructuredContentDoc(BaseModel):
    """Pre-written slide content — mapped to layout blocks without LLM."""

    title: str
    content_sections: list[StructuredSection] = Field(default_factory=list)


class BlockValidation(BaseModel):
    block_id: str
    original_len: int
    new_len: int
    within_char_limit: bool
    mapped: bool
    empty: bool
    block_kind: Literal["text", "chart"] = "text"


class ValidationReport(BaseModel):
    passed: bool
    coverage_pct: float
    mapped_blocks: int
    total_text_blocks: int
    mapped_charts: int = 0
    total_charts: int = 0
    unmapped_block_ids: list[str] = Field(default_factory=list)
    empty_block_ids: list[str] = Field(default_factory=list)
    block_results: list[BlockValidation] = Field(default_factory=list)
    shape_count_unchanged: bool = True
    editable_check: bool = True
    manual_review_needed: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
