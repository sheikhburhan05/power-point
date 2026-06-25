"""Apply chart content mappings to PPTX charts."""

from __future__ import annotations

from pptx.chart.data import CategoryChartData

from src.apply.shape_resolver import resolve_shape
from src.models import ChartMapping


def apply_chart_to_shape(shape, mapping: ChartMapping) -> None:
    if not shape.has_chart:
        raise ValueError("Shape is not a chart")

    chart = shape.chart
    chart_data = CategoryChartData()
    chart_data.categories = mapping.categories

    for series in mapping.series:
        chart_data.add_series(series.name, tuple(series.values))

    chart.replace_data(chart_data)

    if mapping.title:
        chart.has_title = True
        chart.chart_title.text_frame.text = mapping.title


def apply_chart_mapping(slide, mapping: ChartMapping, rel_path: str) -> None:
    shape = resolve_shape(slide, rel_path)
    if not shape.has_chart:
        raise ValueError(f"No chart at path {rel_path}")
    apply_chart_to_shape(shape, mapping)
