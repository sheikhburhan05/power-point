#!/usr/bin/env python3
"""CLI for PPTX slide recreation pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from dotenv import load_dotenv
from langsmith import traceable

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.apply.slide_applier import apply_content
from src.extract.layout_extractor import extract_layout
from src.generate.content_generator import generate_content, load_content_mapping
from src.generate.structured_mapper import load_structured_content, map_structured_content
from src.tracing import configure_tracing, tracing_status
from src.validate.validator import validate_output

load_dotenv(ROOT / ".env")

app = typer.Typer(help="PPTX slide recreation with LangChain + Claude")


def _init_tracing(trace: bool, project: str) -> None:
    configure_tracing(enabled=trace if trace else None, project=project)
    status = tracing_status()
    if not status["enabled"]:
        return
    if not status["has_api_key"]:
        typer.echo(
            "Warning: LANGSMITH_TRACING is on but LANGSMITH_API_KEY is missing. "
            "Add it to .env to send traces.",
            err=True,
        )
        return
    typer.echo(
        f"LangSmith tracing enabled — project: {status['project']} "
        f"(view at https://smith.langchain.com)"
    )


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        data.model_dump_json(indent=2) if hasattr(data, "model_dump_json") else json.dumps(data, indent=2),
        encoding="utf-8",
    )


@app.command()
def extract(
    input: Path = typer.Option(..., "--input", "-i", help="Input PPTX file"),
    out: Path = typer.Option(..., "--out", "-o", help="Output layout.json path"),
) -> None:
    """Extract slide layout structure to JSON."""
    layout = extract_layout(input)
    _write_json(out, layout)
    typer.echo(f"Extracted {sum(len(s.blocks) for s in layout.slides)} text blocks -> {out}")


def _resolve_mapping(
    layout,
    *,
    topic: str | None,
    source_text: Path | None,
    content_json: Path | None,
    structured_content: Path | None,
):
    if content_json:
        typer.echo(f"Loaded content mapping from {content_json}")
        return load_content_mapping(content_json)
    if structured_content:
        doc = load_structured_content(structured_content)
        typer.echo(f"Mapped structured content from {structured_content} (no LLM)")
        return map_structured_content(layout, doc)
    if not topic and not source_text:
        raise typer.BadParameter(
            "Provide one of: --topic, --source-text, --structured-content, or --content-json"
        )
    source = source_text.read_text(encoding="utf-8") if source_text else None
    if topic and source_text:
        typer.echo(f"Generated content via Claude for topic: {topic} (with {source_text})")
    elif topic:
        typer.echo(f"Generated content via Claude for topic: {topic}")
    else:
        typer.echo(f"Generated content via Claude from source: {source_text}")
    return generate_content(layout, topic=topic, source_text=source)


@app.command()
def generate(
    layout_path: Path = typer.Option(..., "--layout", "-l"),
    out: Path = typer.Option(..., "--out", "-o"),
    topic: str | None = typer.Option(None, "--topic", "-t", help="Topic for Claude generation"),
    source_text: Path | None = typer.Option(None, "--source-text", "-s"),
    content_json: Path | None = typer.Option(
        None, "--content-json", help="Pre-built content_mapping.json (block_id -> new_text)"
    ),
    structured_content: Path | None = typer.Option(
        None,
        "--structured-content",
        help="Pre-written content JSON (title + sections + bullets); no LLM",
    ),
    trace: bool = typer.Option(False, "--trace", help="Enable LangSmith tracing"),
    langsmith_project: str = typer.Option("power-point-pipeline", "--langsmith-project"),
) -> None:
    """Generate content mapping via Claude, structured JSON, or pre-built mapping."""
    _init_tracing(trace, langsmith_project)
    from src.models import LayoutDoc

    layout = LayoutDoc.model_validate_json(layout_path.read_text(encoding="utf-8"))
    mapping = _resolve_mapping(
        layout,
        topic=topic,
        source_text=source_text,
        content_json=content_json,
        structured_content=structured_content,
    )
    _write_json(out, mapping)
    typer.echo(f"Wrote {out}")


@app.command()
def apply(
    input: Path = typer.Option(..., "--input", "-i"),
    layout_path: Path = typer.Option(..., "--layout", "-l"),
    mapping_path: Path = typer.Option(..., "--mapping", "-m"),
    out: Path = typer.Option(..., "--out", "-o"),
) -> None:
    """Apply content mapping to PPTX template."""
    from src.models import LayoutDoc

    layout = LayoutDoc.model_validate_json(layout_path.read_text(encoding="utf-8"))
    mapping = load_content_mapping(mapping_path)
    result = apply_content(input, layout, mapping, out)
    typer.echo(f"Wrote {result}")


@app.command()
def validate(
    layout_path: Path = typer.Option(..., "--layout", "-l"),
    mapping_path: Path = typer.Option(..., "--mapping", "-m"),
    output: Path = typer.Option(..., "--output", "-o"),
    report: Path = typer.Option(..., "--report", "-r"),
    input: Path | None = typer.Option(None, "--input", "-i"),
) -> None:
    """Validate output PPTX against layout and mapping."""
    from src.models import LayoutDoc

    layout = LayoutDoc.model_validate_json(layout_path.read_text(encoding="utf-8"))
    mapping = load_content_mapping(mapping_path)
    result = validate_output(layout, mapping, output, input_pptx=input)
    _write_json(report, result)
    status = "PASSED" if result.passed else "FAILED"
    typer.echo(f"Validation {status} ({result.coverage_pct}% coverage) -> {report}")


@traceable(name="pptx_pipeline_run", run_type="chain")
def _run_pipeline(
    input: Path,
    out_dir: Path,
    topic: str | None,
    source_text: Path | None,
    content_json: Path | None,
    structured_content: Path | None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    layout_path = out_dir / "layout.json"
    mapping_path = out_dir / "content_mapping.json"
    output_pptx = out_dir / "output.pptx"
    report_path = out_dir / "validation_report.json"

    typer.echo("Step 1/4: Extracting layout...")
    layout = extract_layout(input)
    _write_json(layout_path, layout)

    typer.echo("Step 2/4: Generating content...")
    mapping = _resolve_mapping(
        layout,
        topic=topic,
        source_text=source_text,
        content_json=content_json,
        structured_content=structured_content,
    )
    _write_json(mapping_path, mapping)

    typer.echo("Step 3/4: Applying content to PPTX...")
    apply_content(input, layout, mapping, output_pptx)

    typer.echo("Step 4/4: Validating...")
    report = validate_output(layout, mapping, output_pptx, input_pptx=input)
    _write_json(report_path, report)

    typer.echo(f"\nDone. Outputs in {out_dir}/")
    typer.echo("  layout.json")
    typer.echo("  content_mapping.json")
    typer.echo("  output.pptx")
    typer.echo("  validation_report.json")
    typer.echo(f"Validation: {'PASSED' if report.passed else 'FAILED'} ({report.coverage_pct}%)")


@app.command()
def run(
    input: Path = typer.Option(..., "--input", "-i"),
    out_dir: Path = typer.Option(Path("output"), "--out-dir", "-d"),
    topic: str | None = typer.Option(None, "--topic", "-t", help="Topic for Claude generation"),
    source_text: Path | None = typer.Option(None, "--source-text", "-s"),
    content_json: Path | None = typer.Option(
        None, "--content-json", help="Pre-built content_mapping.json"
    ),
    structured_content: Path | None = typer.Option(
        None,
        "--structured-content",
        help="Pre-written JSON: title + content_sections + bullets (no LLM)",
    ),
    trace: bool = typer.Option(False, "--trace", help="Enable LangSmith tracing"),
    langsmith_project: str = typer.Option("power-point-pipeline", "--langsmith-project"),
) -> None:
    """Run full pipeline: extract -> generate -> apply -> validate."""
    _init_tracing(trace, langsmith_project)
    _run_pipeline(
        input, out_dir, topic, source_text, content_json, structured_content
    )


if __name__ == "__main__":
    app()
