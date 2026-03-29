# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered trend discovery tool using OpenAI's Agents SDK. Multi-agent pipeline: specialized source agents research topics from different angles (forums, reviews, news, institutional data), then a synthesizer merges findings into structured trends.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run research (autonomous — auto-selects top 6 topics)
python research.py "Munich small businesses"

# Run research (guided — you pick topics by number)
python research.py "Munich small businesses" --guided
```

Requires `OPENAI_API_KEY` in `.env`.

```bash
# Lint and test
ruff check .
pytest tests/ -v
```

## Development Notes

- The local package is `research_agents/` (not `agents/`) to avoid shadowing the `openai-agents` SDK which installs as `agents`.
- Tests mock `Runner.run()` — no API calls needed. Run a single test: `pytest tests/test_orchestrator.py::test_name -v`
- Agent prompts are the primary quality lever — iterate on prompts before adding code complexity.

## Architecture

```
research.py → orchestrator.py → research_agents/ → research/*.json
```

- **research.py**: Entry point with argparse. Domain string + optional `--guided` flag.
- **orchestrator.py**: Pipeline logic — Topic Scout → Dispatcher → Source Agents (parallel) → Synthesizer → JSON. Handles both autonomous and guided mode.
- **research_agents/**: Modular agent package. Each agent has its own file:
  - `topic_scout.py` — discovers 8 diverse topics (4 web, 4 model-generated)
  - `topic_scorer.py` — ranks topics, picks top 6 (autonomous mode only)
  - `community_hunter.py` — searches forums, Reddit, HN, communities
  - `review_analyst.py` — searches app stores, review platforms
  - `news_scout.py` — searches news, industry reports
  - `data_researcher.py` — searches government/institutional data
  - `dispatcher.py` — decides which source agents to run per topic
  - `synthesizer.py` — merges raw findings into structured Trends
  - `config.py` — shared WebSearchTool and retry settings
- **models.py**: All Pydantic schemas — Trend, Evidence, RawFinding, TopicResearchOutput, etc.
- **research/**: Output directory, one JSON file per topic containing structured trends.
