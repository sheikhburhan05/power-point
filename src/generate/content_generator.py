"""LangChain + Claude content generation."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langsmith import traceable

from src.generate.prompts import CONTENT_PROMPT
from src.models import ContentMapping, LayoutDoc


def _layout_summary(layout: LayoutDoc) -> str:
    payload: dict = {"text_blocks": [], "charts": []}
    for slide in layout.slides:
        for block in slide.blocks:
            payload["text_blocks"].append(
                {
                    "block_id": block.block_id,
                    "role": block.role,
                    "original_text": block.original_text,
                    "char_limit": block.char_limit,
                    "paragraph_count": block.paragraph_count,
                    "bullet_levels": block.bullet_levels,
                }
            )
        for chart in slide.charts:
            payload["charts"].append(
                {
                    "block_id": chart.block_id,
                    "role": chart.role,
                    "chart_type": chart.chart_type,
                    "title": chart.title,
                    "categories": chart.categories,
                    "series": [s.model_dump() for s in chart.series],
                    "category_count": chart.category_count,
                    "series_count": chart.series_count,
                }
            )
    return json.dumps(payload, indent=2)


@traceable(name="generate_content", run_type="chain")
def generate_content(
    layout: LayoutDoc,
    topic: str,
    source_text: str | None = None,
    model: str = "claude-sonnet-4-6",
) -> ContentMapping:
    block_count = sum(len(s.blocks) for s in layout.slides)
    chart_count = sum(len(s.charts) for s in layout.slides)
    llm = ChatAnthropic(model=model, temperature=0.3)
    structured_llm = llm.with_structured_output(ContentMapping)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CONTENT_PROMPT),
            (
                "human",
                "Topic: {topic}\n\n"
                "Source material (optional):\n{source_text}\n\n"
                "Slide structure to fill:\n{layout_json}",
            ),
        ]
    )
    chain = prompt | structured_llm
    result = chain.invoke(
        {
            "topic": topic,
            "source_text": source_text or "(none — generate from topic)",
            "layout_json": _layout_summary(layout),
        },
        config={
            "run_name": "claude_content_mapping",
            "tags": ["pptx", "claude", "structured-output"],
            "metadata": {
                "topic": topic,
                "model": model,
                "block_count": block_count,
                "chart_count": chart_count,
                "slide_count": len(layout.slides),
                "has_source_text": bool(source_text),
            },
        },
    )
    if isinstance(result, ContentMapping):
        result.topic = topic
        return result
    return ContentMapping.model_validate(result)


def load_content_mapping(path: str | Path) -> ContentMapping:
    return ContentMapping.model_validate_json(Path(path).read_text(encoding="utf-8"))
