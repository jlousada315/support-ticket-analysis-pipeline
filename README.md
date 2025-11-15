# Support Ticket Analysis Pipeline

A clean 3-layer architecture for analyzing customer support tickets with AI, extracting insights, and generating executive reports.

## Quick Start

### Setup

```bash
# Install dependencies
uv pip install -e .

# Configure API key
cp .env.example .env
# Edit .env and add: ANTHROPIC_API_KEY=your_key_here
```

### Run

```bash
python src/pipeline.py
```

Output: Reports saved to `data/reports/` (JSON + Markdown)

## Architecture

Three-layer pipeline with clean separation of concerns:

```
CSV Input → Layer 1: Extract → Layer 2: Summarize → Layer 3: Report → Output
```

**Layer 1 - Extract**: Analyzes individual tickets
- Extracts: category, product area, sentiment, priority, themes, summary
- Uses caching to skip re-processing
- Concurrent processing (default: 10 concurrent API calls)

**Layer 2 - Summarize**: Generates daily summaries
- Groups analyses by date
- Extracts key themes, trends, critical issues
- References previous day for context

**Layer 3 - Report**: Creates executive summary
- Combines 7+ days of summaries
- Generates insights, recommended actions, customer quotes
- Exports JSON and Markdown

## Core Modules

| Module | Purpose | Lines |
|--------|---------|-------|
| `models.py` | Pydantic models (8 classes) | 70 |
| `prompts.py` | LLM prompt templates | 87 |
| `client.py` | API wrapper + JSON parser | 130 |
| `cache.py` | File-based caching | 60 |
| `csv_loader.py` | CSV parsing + date extraction | 80 |
| `orchestrator.py` | Layer processors (Extractor, Summarizer, Reporter) | 420 |
| `pipeline.py` | Main entry point & CLI | 190 |
| **Total** | | **~1,050** |

### Key Design Choices

**API Client** (`client.py`)
- Retry logic with exponential backoff
- Timeout handling (60s default)
- Semaphore-based concurrency control
- Robust JSON parsing with code block extraction

**Caching** (`cache.py`)
- Simple file-based JSON cache
- Date-organized directory structure (YYYY-MM/DD/)
- Check-before-process pattern prevents duplicate API calls

**Orchestration** (`orchestrator.py`)
- Three independent processor classes
- Data normalization for LLM response variations
- Progress tracking with visual feedback
- Graceful error handling (fallback analysis for failures)

**Pipeline** (`pipeline.py`)
- ~190 lines: setup, layer coordination, output formatting
- Clear sequential flow: load → extract → summarize → report
- Markdown generation with hierarchical structure

## Data Flow

```
1. Load CSV
   └─ Parse timestamps, extract content & metadata
2. Extract (Layer 1)
   └─ Per-ticket analysis → cached /{YYYY-MM}/{DD}/{ticket_id}.json
3. Summarize (Layer 2)
   └─ Group by date → cached /{date}.json
4. Report (Layer 3)
   └─ Aggregate summaries → saved /report_{start}_{end}.{json,md}
5. Display
   └─ Console summary + full markdown report
```

## Trade-offs

| Decision | Why |
|----------|-----|
| File-based cache | No external dependencies, easy debugging, survives restarts |
| Semaphore limit (10) | Prevents API rate limiting, respects service boundaries |
| Error fallbacks | Continues processing on failures rather than blocking |
| Per-layer normalization | Handles LLM response variations gracefully |
| Markdown over HTML/PDF | Simple, readable, version-controllable output |

## Input/Output

**Input**: `data/sofa-sogood.csv`
- Columns: `original_message`, `ds` (ISO timestamp), `extra` (JSON metadata)

**Output**: `data/reports/`
- `report_{start}_{end}.json` - Structured report
- `report_{start}_{end}.md` - Human-readable markdown

**Cache**: Auto-organized by layer
- `data/analyses/{YYYY-MM}/{DD}/{ticket_id}.json`
- `data/summaries/{date}.json`

