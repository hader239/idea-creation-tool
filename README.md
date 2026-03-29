# Trend Discovery Tool

AI-powered trend discovery using OpenAI's Agents SDK. A multi-agent pipeline researches topics from different angles (forums, reviews, news, institutional data), then synthesizes findings into structured trends.

## How it works

```
research.py → orchestrator.py → research_agents/ → research/*.json
```

1. **Topic Scout** discovers 8 research topics (4 from web search, 4 model-generated)
2. **Topic Scorer** picks the top 6 (autonomous mode) or you choose (guided mode)
3. **Dispatcher** decides which source agents are relevant per topic
4. **Source agents** run in parallel — Community Hunter, Review Analyst, News Scout, Data Researcher
5. **Synthesizer** merges raw findings into structured Trend objects with evidence, confidence scores, and classification
6. Output saved as one JSON file per topic in `research/`

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

```bash
# Autonomous mode — auto-selects top 6 topics
python research.py "Munich small businesses"

# Guided mode — you pick topics by number
python research.py "Munich small businesses" --guided
```

The tool is domain-agnostic — pass any domain string. Include location context if you want geographically focused results.

Research accumulates over time: the topic scout sees previously covered topics and avoids duplicates.

## Output

Each run produces JSON files in `research/`, one per topic. Each file contains structured trends with:

- Trend type (unmet need, dissatisfaction wave, behavioral shift, regulatory trigger, demographic shift, technology gap)
- Direction (emerging, accelerating, peaking, declining)
- Evidence from multiple source types
- Confidence scoring based on source diversity

## Development

```bash
# Lint
ruff check .

# Test (19 tests, mocked Runner — no API calls)
pytest tests/ -v
```
