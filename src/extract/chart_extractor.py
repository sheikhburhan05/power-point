"""Extract chart structure from PPTX shapes."""

from __future__ import annotations

from src.models import ChartBlock, ChartSeries


def _chart_type_name(chart) -> str:
    try:
        return chart.chart_type.name if chart.chart_type is not None else "UNKNOWN"
    except Exception:
        return "UNKNOWN"


def _chart_title(chart) -> str:
    try:
        if chart.has_title:
            return chart.chart_title.text_frame.text.strip()
    except Exception:
        pass
    return ""


def _chart_categories(chart) -> list[str]:
    try:
        if not chart.plots:
            return []
        return [str(cat) for cat in chart.plots[0].categories]
    except Exception:
        return []


def _chart_series(chart) -> list[ChartSeries]:
    result: list[ChartSeries] = []
    try:
        for series in chart.series:
            name = str(series.name) if series.name is not None else "Series"
            values = [float(v) for v in series.values]
            result.append(ChartSeries(name=name, values=values))
    except Exception:
        pass
    return result


def extract_chart_block(shape, block_id: str, geom: dict) -> ChartBlock | None:
    """Extract editable chart data when the chart uses categories."""
    if not shape.has_chart:
        return None

    chart = shape.chart
    categories = _chart_categories(chart)
    series = _chart_series(chart)
    if not categories or not series:
        return None

    return ChartBlock(
        block_id=block_id,
        chart_type=_chart_type_name(chart),
        title=_chart_title(chart),
        categories=categories,
        series=series,
        category_count=len(categories),
        series_count=len(series),
        **geom,
    )
