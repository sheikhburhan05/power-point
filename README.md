# PPTX Slide Recreation with LangChain + Claude

Programmatically extract slide structure from any PowerPoint file, generate new content with Claude (via LangChain), and write it back into an editable PPTX while preserving layout and styling.

## Approach

1. **Extract**: Walk every shape recursively with `python-pptx`, producing a `layout.json` with stable `block_id` paths, geometry, text, style hints, and inferred roles (title, body, label, table_cell).
2. **Generate**: Send the layout to **Claude** through a **LangChain**: structured-output chain. Claude returns one `new_text` per `block_id`, respecting character limits and paragraph structure.
3. **Apply**: Load the original PPTX as a template and replace text at the run level (never `shape.text = ...`) so fonts and formatting survive.
4. **Validate**: Compare mapping coverage, char limits, shape counts, and OOXML integrity; write `validation_report.json`.

The output PPTX is a mutated copy of the input, not a flattened image, so it remains fully editable in PowerPoint.

## Setup

```bash
# Create virtual environment
python3 -m venv venv     
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure API key (for LLM mode)
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY

# Optional: LangSmith tracing for debugging
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=your_key
# LANGSMITH_PROJECT=power-point-pipeline
```

Place your input slide at `input/slide.pptx`

## LangSmith tracing (debug)

Traces every pipeline step (`extract_layout`, `generate_content`, Claude LLM call, `apply_content`, `validate_output`) in [LangSmith](https://smith.langchain.com).

**Option A: via `.env` (always on):**
```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_pt_...
LANGSMITH_PROJECT=power-point-pipeline
```

**Option B: via CLI flag:**
```bash
python main.py run \
  --input input/slide.pptx \
  --topic "AI in Healthcare" \
  --trace \
  --langsmith-project power-point-pipeline \
  --out-dir output/
```

In LangSmith you will see a parent trace `pptx_pipeline_run` with child spans for each step, plus the nested Claude `claude_content_mapping` run with prompts, token usage, and structured output.

## Usage

### Full pipeline (LLM mode)

```bash
python main.py run \
  --input input/slide.pptx \
  --topic "AI in Healthcare" \
  --out-dir output/
```

Use `--source-text` when you have reference material (article, brief, notes) and want Claude to base slide content on that file instead of inventing from the topic alone:

```bash
python main.py run \
  --input input/slide.pptx \
  --topic "AI in Healthcare" \
  --source-text notes/healthcare_brief.md \
  --out-dir output/
```

`--topic` is still required (it sets the theme). `--source-text` is optional — omit it if a short topic is enough.

### Full pipeline (reviewer dummy-data mode, no API key)

```bash
python main.py run \
  --input input/slide.pptx \
  --topic "AI in Healthcare" \
  --content-json examples/dummy_content.json \
  --out-dir output/
```

### Step-by-step

```bash
python main.py extract --input input/slide.pptx --out output/layout.json
python main.py generate --layout output/layout.json --topic "Q3 Results" --out output/content_mapping.json
python main.py generate --layout output/layout.json --topic "Q3 Results" --source-text notes/q3_report.md --out output/content_mapping.json
python main.py apply --input input/slide.pptx --layout output/layout.json --mapping output/content_mapping.json --out output/output.pptx
python main.py validate --layout output/layout.json --mapping output/content_mapping.json --output output/output.pptx --report output/validation_report.json --input input/slide.pptx
```

### Chart support

Category-based charts (column, bar, line, pie) are extracted into `layout.json` under `charts` and updated via `chart_mappings` in `content_mapping.json`:

```bash
# Create a sample slide with a chart
python scripts/create_chart_sample.py

# Run with dummy chart data (no API key)
python main.py run \
  --input input/chart_sample.pptx \
  --content-json examples/dummy_chart_content.json \
  --out-dir output/chart_test/
```

Claude returns both `mappings` (text) and `chart_mappings` (title, categories, series values) when using LLM mode.

## Deliverables

| File | Description |
|------|-------------|
| `output/layout.json` | Extracted slide structure |
| `output/content_mapping.json` | LLM-generated or dummy content per block |
| `output/output.pptx` | Final editable PowerPoint |
| `output/validation_report.json` | Pass/fail report with per-block metrics |
| `main.py` + `src/` | Source code |
| `README.md` | This file |

## Limitations

- **SmartArt / OLE objects**: Detected as non-editable; content is not rewritten.
- **Autofit**: `TEXT_TO_FIT_SHAPE` is set in XML; final visual sizing may refine when opened in PowerPoint.
- **Mixed inline formatting**: Multi-run styles within one block are simplified to the dominant run's style.
- **Charts**: Category-based charts (column, bar, line, pie) support title, category, and series updates via `chart_mappings`. XY/scatter or Excel-linked charts may still be flagged as unsupported.

## Production Agent Roadmap

To evolve this into a production-grade coding agent:

1. **Vision pass**: Use a multimodal model to classify layout regions when heuristics are ambiguous.
2. **LangGraph loop**: Agent graph: extract → generate → apply → validate → retry with feedback until validation passes.
3. **Human-in-the-loop**: Preview diff UI for approving content before apply.
4. **Golden-file regression**: Slide library per layout family with automated fidelity checks.
5. **Enterprise fidelity**: Optional Aspose.Slides for SmartArt, animations, and advanced chart editing.

## Project Structure

```
power-point/
├── main.py                 # CLI entry point
├── input/slide.pptx        # Your input slide
├── output/                 # Generated deliverables
├── examples/
│   └── dummy_content.json  # Offline test mapping
├── scripts/
│   └── create_sample_slide.py
└── src/
    ├── models.py
    ├── extract/layout_extractor.py
    ├── generate/content_generator.py
    ├── apply/slide_applier.py
    └── validate/validator.py
```
