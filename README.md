# Startup Idea Generator

An AI-powered workflow that researches market opportunities and generates validated startup ideas using OpenAI's Agents SDK. Focused on Munich / Germany / Europe.

## How it works

The workflow is split into two independent steps:

1. **Research** (`research.py`) -- a gpt-5.4 agent with web search finds real pain points and market gaps. Results are saved as JSON files you can review and accumulate over time.
2. **Ideation** (`ideate.py`) -- a gpt-5.4-mini agent generates startup ideas grounded in the research, and a second gpt-5.4-mini agent validates them. No web search needed -- cheap and fast.

```
research.py ──saves──> research/*.json
                            │
ideate.py ───reads──────────┘──saves──> ideas/*.md
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your OpenAI API key to `.env`:

```
OPENAI_API_KEY=sk-...
```

## Usage

### Step 1: Research

Run the researcher with a focused prompt. Each run creates a new JSON file in `research/`.

```bash
python research.py "student pain points in Munich"
python research.py "small business compliance tools in Germany"
python research.py "gaps in European digital services"
```

Review the output, delete weak files, run more searches -- build up a research library.

### Step 2: Ideate

Point the ideation script at one or more research files:

```bash
# From a single research file
python ideate.py research/2026-03-26-student-pain-points.json

# Combine multiple research files
python ideate.py research/*.json

# Generate multiple ideas
python ideate.py research/*.json --num-ideas 3
```

Valid ideas are saved to `ideas/` as markdown files with the full idea description, research backing, and validation notes.

## Configuration

Edit the constants at the top of each script:

- `RESEARCH_DIR` -- output directory for research files (default: `research`)
- `IDEAS_DIR` -- output directory for idea files (default: `ideas`)
- `MAX_ATTEMPTS` -- max generation/validation cycles per idea (default: 5)
