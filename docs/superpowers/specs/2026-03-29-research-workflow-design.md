# Research Workflow Design

## Overview

Refactored research pipeline that discovers market trends through a multi-layered agent workflow. Replaces the current single-agent research script with a modular system of specialized agents that gather raw data from different source types, then synthesize findings into structured trends.

The tool is domain-agnostic (no hardcoded geography). Location and focus area are provided via the CLI prompt.

## Pipeline

```
User input (domain string)
    |
    v
Topic Scout ──> 8 topics (4 web-discovered, 4 model-generated, maximally diverse)
    |
    v
Mode split:
  - Autonomous: Topic Scorer picks top 6
  - Guided (--guided): user picks by number
    |
    v
For each selected topic (in parallel):
    |
    v
  Dispatcher ──> decides which source agents are relevant
    |
    v
  Source agents run in parallel:
    - Community Hunter (forums, Reddit, HN, communities)
    - Review Analyst (App Store, Google Play, Trustpilot, G2)
    - Trend Scanner (news, industry reports, blogs)
    - Data Researcher (government stats, EU reports — only when relevant)
    |
    v
  Synthesizer ──> merges raw findings into structured Trends
    |
    v
  Save JSON to research/{slugified-topic}.json
```

## Data Models

### Core Output

```python
class TrendType(str, Enum):
    unmet_need = "unmet_need"
    dissatisfaction_wave = "dissatisfaction_wave"
    behavioral_shift = "behavioral_shift"
    regulatory_trigger = "regulatory_trigger"
    demographic_shift = "demographic_shift"
    technology_gap = "technology_gap"

class TrendDirection(str, Enum):
    emerging = "emerging"
    accelerating = "accelerating"
    peaking = "peaking"
    declining = "declining"

class Confidence(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class Evidence(BaseModel):
    source_type: str        # forum, review, news, government_data
    source_name: str        # e.g. "r/munich", "Trustpilot", "Handelsblatt"
    content: str            # actual quote, data point, or finding
    url: str                # link to the source

class Trend(BaseModel):
    title: str
    trend_type: TrendType
    direction: TrendDirection
    who_is_affected: str        # specific audience segment
    scale_estimate: str         # rough sense of how many people
    current_workarounds: str    # what people do today
    existing_solutions: str     # what's been tried
    solution_gaps: str          # why existing solutions aren't enough
    evidence: list[Evidence]
    source_diversity: int       # how many source types confirm this (1-4)
    confidence: Confidence
```

### Pipeline Models

```python
class ResearchTopic(BaseModel):
    topic: str
    reasoning: str
    source: str                 # "web_discovery" or "model_generated"

class TopicScoutResult(BaseModel):
    topics: list[ResearchTopic]  # 8 topics

class RawFinding(BaseModel):
    source_type: str
    source_name: str
    content: str
    url: str
    relevance_note: str         # why this finding matters

class SourceAgentResult(BaseModel):
    agent_name: str
    findings: list[RawFinding]

class ResearchMetadata(BaseModel):
    timestamp: str
    domain: str
    sources_used: list[str]     # which source agents ran

class TopicResearchOutput(BaseModel):
    topic: str
    trends: list[Trend]
    metadata: ResearchMetadata
```

## Agents

### 1. Topic Scout (`agents/topic_scout.py`)

- **Model:** gpt-5.4-mini
- **Tools:** WebSearchTool
- **Input:** domain string + list of already-covered topics (from existing research/ files)
- **Output:** TopicScoutResult (8 topics)
- **Behavior:** Does a lightweight web search to discover 4 trending/discussed topics in the domain. Generates 4 more from its own knowledge. Maximizes diversity across all 8. Avoids overlap with already-covered topics.

### 2. Topic Scorer (`agents/topic_scorer.py`)

- **Model:** gpt-5.4-mini
- **Tools:** none (reasoning only)
- **Input:** 8 topics + domain context
- **Output:** ranked list with scores, top 6 selected
- **Behavior:** Only used in autonomous mode. Scores topics on research potential and diversity. Returns top 6.

### 3. Community Hunter (`agents/community_hunter.py`)

- **Model:** gpt-5.4
- **Tools:** WebSearchTool
- **Input:** one topic
- **Output:** SourceAgentResult
- **Behavior:** Searches Reddit, HN, Quora, niche forums, local communities. Looks for complaints, workarounds, DIY solutions, frustration patterns. Skeptical of viral social media posts — prioritizes authentic discussion threads with real detail.

### 4. Review Analyst (`agents/review_analyst.py`)

- **Model:** gpt-5.4
- **Tools:** WebSearchTool
- **Input:** one topic
- **Output:** SourceAgentResult
- **Behavior:** Searches App Store, Google Play, Trustpilot, G2, Google Reviews. Looks for recurring negative patterns across multiple reviews, not isolated complaints.

### 5. Trend Scanner (`agents/trend_scanner.py`)

- **Model:** gpt-5.4
- **Tools:** WebSearchTool
- **Input:** one topic
- **Output:** SourceAgentResult
- **Behavior:** Searches news sites, industry reports, blogs, thought pieces. Looks for market movements, regulatory changes, emerging shifts, and directional signals.

### 6. Data Researcher (`agents/data_researcher.py`)

- **Model:** gpt-5.4
- **Tools:** WebSearchTool
- **Input:** one topic
- **Output:** SourceAgentResult
- **Behavior:** Searches government stats, EU reports, institutional data. Only dispatched when the topic has a regulatory, demographic, or economic angle.

### 7. Synthesizer (`agents/synthesizer.py`)

- **Model:** gpt-5.4 (needs strong reasoning for cross-referencing)
- **Tools:** none
- **Input:** all SourceAgentResults for one topic
- **Output:** list of Trends with evidence merged, source diversity scored, confidence assessed
- **Behavior:** Merges raw findings from all source agents. Identifies patterns across sources. Structures them into Trend objects. Scores source diversity and confidence based on evidence quality and variety.

## Dispatcher

Not a separate agent. A lightweight gpt-5.4-mini call in the orchestrator that takes a topic and returns which source agents to dispatch.

Rules:
- Community Hunter and Trend Scanner: run for almost every topic
- Review Analyst: run when existing products/services are involved
- Data Researcher: run when there's a regulatory/demographic/economic angle

## Orchestrator (`orchestrator.py`)

```
async def run_research(domain: str, guided: bool = False):
    1. Scan research/ directory for existing JSON files, extract covered topics
    2. Run Topic Scout → 8 topics
    3. If guided: print topics, user picks by number
       If autonomous: run Topic Scorer → top 6
    4. For each selected topic (in parallel via asyncio.gather):
       a. Run dispatcher → relevant source agent names
       b. Run source agents in parallel → list of SourceAgentResults
       c. Run synthesizer → list of Trends
       d. Save TopicResearchOutput as JSON to research/{slugified-topic}.json
    5. Print summary
```

Topics are researched in parallel. Within each topic, source agents also run in parallel.

## CLI (`cli.py`)

```bash
# Autonomous mode (topic scorer picks top 6)
python cli.py "Munich small businesses"

# Guided mode (user picks topics by number)
python cli.py "Munich small businesses" --guided
```

Positional arg: domain string. Optional flag: `--guided`.

## File Structure

```
agents/
  topic_scout.py
  topic_scorer.py
  community_hunter.py
  review_analyst.py
  trend_scanner.py
  data_researcher.py
  synthesizer.py
orchestrator.py
models.py
cli.py
research/              # output directory, one JSON per topic
```

## Output

One JSON file per topic in `research/`, named `{slugified-topic}.json`. Contains `TopicResearchOutput` with the topic name, list of trends, and metadata (timestamp, domain, which source agents were used).

Already-covered topics are detected by scanning existing files in `research/` — no separate tracking file needed.

## Dependencies

- openai-agents (OpenAI Agents SDK)
- pydantic

## Out of Scope

- Ideation workflow (separate future effort)
- Sanity check / adversarial review (can be added to synthesizer prompt later if output quality needs filtering)
- Hardcoded geographic focus (user provides location context in the domain string if desired)