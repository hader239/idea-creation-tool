# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered startup idea generator using OpenAI's Agents SDK. Two-stage pipeline: research agent discovers market pain points (focused on Munich/Germany/Europe), then ideation agent generates and validates startup ideas grounded in that research.

## Commands

```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run research agent (loops indefinitely, Ctrl+C to stop)
python research.py

# Run ideation agent
python ideate.py research/*.json              # single idea from all research
python ideate.py research/some-file.json -n 3 # 3 ideas from specific file
```

Requires `OPENAI_API_KEY` in `.env`. No test suite or linter configured.

## Architecture

```
research.py → research/*.json → ideate.py → ideas/*.md
```

- **research.py**: Two chained agents — `topic_generator` (gpt-5.4-mini) picks narrow topics, `researcher` (gpt-5.4) does web search to find real pain points. Outputs structured JSON. Tracks used topics in `used_topics.txt` to avoid duplicates.
- **ideate.py**: Two chained agents — `idea_creator` picks an opportunity and crafts an idea, `idea_validator` checks alignment/feasibility/marketing fit. Retry logic (max 5 attempts per idea, stops after 2 consecutive failures). Outputs markdown files.
- **models.py**: Pydantic schemas shared by both scripts — `Opportunity`, `MarketResearch`, `ResearchTopic`, `StartupIdea`, `IdeaValidation`.

The two scripts are currently independent (run separately, connected only through the research JSON files on disk). The commit history notes they are "not yet meaningfully connected."

## Key Design Decisions

- Ideas must be MVP-buildable by a solo developer in 1-2 weeks
- Geographic focus: Munich, Bavaria, Germany, Europe — targeting students, small businesses, expats, freelancers, tradespeople
- Web search uses Munich geolocation context
- File naming: `YYYY-MM-DD-{slugified-name}.json` / `.md`
