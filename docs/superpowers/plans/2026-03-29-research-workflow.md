# Research Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-agent research pipeline that discovers market trends through specialized source agents, synthesizes findings, and outputs structured JSON.

**Architecture:** Modular agent design — each agent lives in its own file under `research_agents/`. An orchestrator wires them into a parallel pipeline: Topic Scout → Dispatcher → Source Agents (parallel) → Synthesizer → JSON output. Two CLI modes: autonomous (top 6 topics auto-selected) and guided (user picks topics).

**Tech Stack:** Python, openai-agents SDK (v0.13.1), Pydantic

**Spec:** `docs/superpowers/specs/2026-03-29-research-workflow-design.md`

**Important:** The local agent package is named `research_agents/` (not `agents/`) to avoid shadowing the `openai-agents` SDK which installs as `agents`.

---

## File Structure

```
research_agents/
  __init__.py           # Re-exports all agents + SOURCE_AGENTS dict
  config.py             # Shared WebSearchTool, retry settings
  topic_scout.py        # Topic discovery agent
  topic_scorer.py       # Topic ranking agent (autonomous mode)
  community_hunter.py   # Forums/Reddit/HN source agent
  review_analyst.py     # App Store/Trustpilot source agent
  news_scout.py         # News/industry reports source agent
  data_researcher.py    # Government/institutional data source agent
  dispatcher.py         # Lightweight agent that picks relevant source agents
  synthesizer.py        # Merges raw findings into structured Trends
models.py               # All Pydantic models
orchestrator.py         # Pipeline logic, parallel execution
cli.py                  # Entry point with argparse
```

---

### Task 1: Data Models

**Files:**
- Create: `models.py` (full rewrite of existing file)

- [ ] **Step 1: Write all Pydantic models**

Replace the contents of `models.py` with:

```python
from enum import Enum

from pydantic import BaseModel


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
    source_type: str
    source_name: str
    content: str
    url: str


class Trend(BaseModel):
    title: str
    trend_type: TrendType
    direction: TrendDirection
    who_is_affected: str
    scale_estimate: str
    current_workarounds: str
    existing_solutions: str
    solution_gaps: str
    evidence: list[Evidence]
    source_diversity: int
    confidence: Confidence


class ResearchTopic(BaseModel):
    topic: str
    reasoning: str
    source: str


class TopicScoutResult(BaseModel):
    topics: list[ResearchTopic]


class ScoredTopic(BaseModel):
    topic: str
    reasoning: str
    source: str
    score: int


class TopicScorerResult(BaseModel):
    ranked_topics: list[ScoredTopic]


class RawFinding(BaseModel):
    source_type: str
    source_name: str
    content: str
    url: str
    relevance_note: str


class SourceAgentResult(BaseModel):
    agent_name: str
    findings: list[RawFinding]


class DispatchDecision(BaseModel):
    agents: list[str]


class SynthesisResult(BaseModel):
    trends: list[Trend]


class ResearchMetadata(BaseModel):
    timestamp: str
    domain: str
    sources_used: list[str]


class TopicResearchOutput(BaseModel):
    topic: str
    trends: list[Trend]
    metadata: ResearchMetadata
```

- [ ] **Step 2: Verify models load**

Run: `python -c "from models import *; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add models.py
git commit -m "feat: rewrite models for new research pipeline"
```

---

### Task 2: Shared Config + Topic Agents

**Files:**
- Create: `research_agents/__init__.py`
- Create: `research_agents/config.py`
- Create: `research_agents/topic_scout.py`
- Create: `research_agents/topic_scorer.py`

- [ ] **Step 1: Create package and shared config**

Create `research_agents/__init__.py` (empty for now, populated in Task 4):

```python
```

Create `research_agents/config.py`:

```python
from agents import ModelRetrySettings, WebSearchTool, retry_policies

web_search = WebSearchTool(search_context_size="high")

retry_settings = ModelRetrySettings(
    max_retries=5,
    backoff={
        "initial_delay": 1.0,
        "max_delay": 120.0,
        "multiplier": 2.0,
        "jitter": True,
    },
    policy=retry_policies.any(
        retry_policies.provider_suggested(),
        retry_policies.retry_after(),
        retry_policies.http_status([429, 500, 502, 503]),
    ),
)
```

- [ ] **Step 2: Write Topic Scout agent**

Create `research_agents/topic_scout.py`:

```python
from agents import Agent, ModelSettings

from models import TopicScoutResult
from research_agents.config import web_search

topic_scout = Agent(
    name="Topic Scout",
    instructions="""\
You are a research topic discovery agent. Given a broad domain, you find specific \
research topics worth investigating for market trends.

Your task: produce exactly 8 specific, narrow research topics.

Split:
- 4 topics from web search: search for trending discussions, recent complaints, \
news, and emerging conversations in the domain. These should reflect what people \
are actually talking about RIGHT NOW.
- 4 topics from your own knowledge: use your understanding of markets, technology, \
and human behavior to suggest angles that web search might miss. Think laterally — \
adjacent industries, upstream/downstream problems, demographic shifts.

Rules:
- Each topic must be specific and actionable (e.g., "frustrations Munich freelancers \
have with quarterly VAT filing" — not "German tax problems")
- Maximize DIVERSITY across all 8 topics: different industries, audiences, problem \
types, and scales
- Set source to "web_discovery" for web-found topics and "model_generated" for \
your own topics
- In the reasoning field, explain in one sentence why this topic is worth researching

If a list of already-covered topics is provided, avoid generating topics that \
overlap with them. Find genuinely new angles.""",
    model="gpt-5.4-mini",
    tools=[web_search],
    output_type=TopicScoutResult,
    model_settings=ModelSettings(temperature=1.0),
)
```

- [ ] **Step 3: Write Topic Scorer agent**

Create `research_agents/topic_scorer.py`:

```python
from agents import Agent, ModelSettings

from models import TopicScorerResult

topic_scorer = Agent(
    name="Topic Scorer",
    instructions="""\
You are a research topic evaluator. You receive a list of research topics and must \
score and rank them.

Score each topic 1-10 based on:
- Research potential: how likely is it that web searches will surface real data, \
complaints, reviews, and discussions on this topic?
- Specificity: is this narrow enough to produce concrete, actionable findings?
- Interest: how likely is this topic to reveal surprising or valuable trends?

Return the top 6 topics ranked by score (highest first). Prefer a diverse set — \
if two topics are very similar, keep the stronger one and drop the other.

Copy the topic, reasoning, and source fields exactly from the input.""",
    model="gpt-5.4-mini",
    output_type=TopicScorerResult,
)
```

- [ ] **Step 4: Verify imports**

Run: `python -c "from research_agents.topic_scout import topic_scout; from research_agents.topic_scorer import topic_scorer; print('OK')"`
Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add research_agents/
git commit -m "feat: add shared config, topic scout and topic scorer agents"
```

---

### Task 3: Source Agents

**Files:**
- Create: `research_agents/community_hunter.py`
- Create: `research_agents/review_analyst.py`
- Create: `research_agents/news_scout.py`
- Create: `research_agents/data_researcher.py`

- [ ] **Step 1: Write Community Hunter agent**

Create `research_agents/community_hunter.py`:

```python
from agents import Agent, ModelSettings

from models import SourceAgentResult
from research_agents.config import retry_settings, web_search

community_hunter = Agent(
    name="Community Hunter",
    instructions="""\
You are a community research specialist. Search forums, communities, and discussion \
platforms for authentic discussions about the given topic.

Sources to search:
- Reddit (especially niche and local subreddits — search for specific subreddit \
names relevant to the topic)
- Hacker News discussions and Show HN posts
- Quora threads
- Stack Exchange sites (when relevant)
- Niche forums and local communities (German-language forums, Fachforen, regional \
community boards)
- Facebook groups and Discord servers (via web search for public content)

What to look for:
- Complaints and frustrations people express in their own words
- DIY solutions and workarounds people have built (spreadsheets, scripts, WhatsApp \
groups, manual processes)
- Requests for tools or services that don't exist yet
- Discussions about switching away from existing solutions and why
- Threads with real back-and-forth where multiple people confirm the same problem

What to AVOID:
- Viral posts with shallow engagement — one popular rant is not a trend
- Marketing content disguised as community discussion
- Posts older than 2 years unless they show a persistent, unsolved problem
- Single comments without supporting discussion

For EACH finding, you MUST provide:
- source_type: "forum"
- source_name: the specific platform and community (e.g., "r/munich", "HN", \
"gutefrage.net")
- content: a direct quote or detailed summary of what was said
- url: the URL of the post or thread
- relevance_note: one sentence on why this matters for trend discovery

Aim for 8-15 high-quality findings. Quality over quantity — skip weak signals.""",
    model="gpt-5.4",
    tools=[web_search],
    output_type=SourceAgentResult,
    model_settings=ModelSettings(
        retry=retry_settings,
    ),
)
```

- [ ] **Step 2: Write Review Analyst agent**

Create `research_agents/review_analyst.py`:

```python
from agents import Agent, ModelSettings

from models import SourceAgentResult
from research_agents.config import retry_settings, web_search

review_analyst = Agent(
    name="Review Analyst",
    instructions="""\
You are a product review analyst. Search app stores and review platforms for \
patterns in user feedback about products and services related to the given topic.

Sources to search:
- Apple App Store reviews
- Google Play Store reviews
- Trustpilot
- G2
- Capterra
- Google Reviews (for local businesses and services)
- Amazon reviews (when physical products are relevant)

What to look for:
- Recurring complaints that appear across MULTIPLE reviews of the same product
- Recurring complaints across MULTIPLE competing products (indicates a market-wide gap)
- Features users consistently request but don't get
- Patterns in 1-3 star reviews — what specifically makes people unhappy?
- Comparisons users make ("I switched from X because..." or "unlike X, this doesn't...")

What to AVOID:
- One-off complaints (a single angry review is not a pattern)
- Reviews about pricing, shipping, or customer support unless they reveal a \
structural problem
- Fake or incentivized reviews (look for verified purchase indicators, detail level)
- Reviews about products unrelated to the research topic

For EACH finding, you MUST provide:
- source_type: "review"
- source_name: the platform and product name (e.g., "Trustpilot - Lieferando", \
"App Store - N26")
- content: the recurring pattern observed, with example quotes if possible
- url: link to the product's review page
- relevance_note: one sentence on what this pattern reveals

Aim for 5-12 findings. Only include patterns you saw repeated across multiple reviews.""",
    model="gpt-5.4",
    tools=[web_search],
    output_type=SourceAgentResult,
    model_settings=ModelSettings(
        retry=retry_settings,
    ),
)
```

- [ ] **Step 3: Write News Scout agent**

Create `research_agents/news_scout.py`:

```python
from agents import Agent, ModelSettings

from models import SourceAgentResult
from research_agents.config import retry_settings, web_search

news_scout = Agent(
    name="News Scout",
    instructions="""\
You are a news and industry research specialist. Search news sites, industry \
reports, and professional publications for signals about market movements related \
to the given topic.

Sources to search:
- Major news outlets and business publications (TechCrunch, Bloomberg, Handelsblatt, \
Wirtschaftswoche, The Information, Reuters)
- Industry-specific news sites and trade publications
- Company blogs, product announcements, and thought leadership pieces
- Market research summaries (Statista, CB Insights, McKinsey, PwC)
- Regulatory announcements and policy change news (EU, national, state level)

What to look for:
- Market shifts: companies entering/exiting, pivots, new product launches
- Regulatory changes: new laws, upcoming compliance deadlines, enforcement actions
- Investment signals: funding rounds, acquisitions, market size estimates
- Industry reports with concrete data points and growth projections
- Expert opinions on where a market is headed

What to AVOID:
- Press releases that are pure marketing without substance
- Outdated articles (prefer last 12 months unless showing a long-term trend)
- Speculation without data or sources
- Duplicate coverage of the same event across outlets (pick the best source)

For EACH finding, you MUST provide:
- source_type: "news"
- source_name: the publication name (e.g., "TechCrunch", "Handelsblatt")
- content: the key facts, data points, or quotes from the article
- url: the article URL
- relevance_note: one sentence on what market signal this represents

Aim for 5-10 findings. Prioritize articles with concrete data over opinion pieces.""",
    model="gpt-5.4",
    tools=[web_search],
    output_type=SourceAgentResult,
    model_settings=ModelSettings(
        retry=retry_settings,
    ),
)
```

- [ ] **Step 4: Write Data Researcher agent**

Create `research_agents/data_researcher.py`:

```python
from agents import Agent, ModelSettings

from models import SourceAgentResult
from research_agents.config import retry_settings, web_search

data_researcher = Agent(
    name="Data Researcher",
    instructions="""\
You are a data and institutional research specialist. Find government statistics, \
EU reports, and institutional data related to the given topic.

Sources to search:
- National statistics offices (Statistisches Bundesamt, Destatis, Eurostat)
- EU reports, directives, and policy documents
- OECD, World Bank, and similar international institution data
- Academic research summaries and university studies
- Government ministry announcements and white papers
- Chamber of commerce reports (IHK, Handwerkskammer)

What to look for:
- Demographic data: population segments growing or declining, migration patterns, \
age distribution shifts
- Economic indicators: market sizes, spending patterns, industry growth rates
- Policy changes: new regulations with compliance requirements, upcoming deadlines, \
EU directives being transposed into national law
- Official statistics that quantify the SCALE of a problem (e.g., "X% of small \
businesses report difficulty with...")
- Institutional reports that identify gaps in current services or infrastructure

What to AVOID:
- Data without clear sourcing or methodology
- Projections based on questionable assumptions
- Data older than 3 years unless it shows a clear long-term trend
- Academic papers that are too theoretical to connect to real-world trends

For EACH finding, you MUST provide:
- source_type: "government_data"
- source_name: the institution (e.g., "Eurostat", "Destatis", "OECD")
- content: the specific data point, statistic, or finding
- url: link to the report or dataset
- relevance_note: one sentence on how this data relates to the research topic

Aim for 3-8 findings. Focus on concrete, citable data points.""",
    model="gpt-5.4",
    tools=[web_search],
    output_type=SourceAgentResult,
    model_settings=ModelSettings(
        retry=retry_settings,
    ),
)
```

- [ ] **Step 5: Verify imports**

Run: `python -c "from research_agents.community_hunter import community_hunter; from research_agents.review_analyst import review_analyst; from research_agents.news_scout import news_scout; from research_agents.data_researcher import data_researcher; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add research_agents/
git commit -m "feat: add community hunter, review analyst, news scout, data researcher agents"
```

---

### Task 4: Synthesizer + Dispatcher + Package Init

**Files:**
- Create: `research_agents/synthesizer.py`
- Create: `research_agents/dispatcher.py`
- Modify: `research_agents/__init__.py`

- [ ] **Step 1: Write Synthesizer agent**

Create `research_agents/synthesizer.py`:

```python
from agents import Agent, ModelSettings
from openai.types.shared.reasoning import Reasoning

from models import SynthesisResult

synthesizer = Agent(
    name="Synthesizer",
    instructions="""\
You are a research synthesizer. You receive raw findings from multiple research \
agents who searched different types of sources (forums, reviews, news, government \
data) about a single topic.

Your task: identify TRENDS by cross-referencing findings across sources, then \
structure them into Trend objects.

How to synthesize:
1. Read ALL findings from all source agents carefully
2. Look for PATTERNS: when multiple findings from different sources point to the \
same underlying shift, that's a trend
3. A single finding can contribute to multiple trends if relevant
4. Group related findings together — a Reddit complaint + a negative app review + \
a news article about the same problem = one strong trend

Scoring:
- source_diversity: count how many distinct source TYPES support this trend. \
A forum post and a Reddit thread are both "forum" = 1. A forum post + a news \
article = 2. Maximum is 4 (forum + review + news + government_data).
- confidence:
  - high: 3+ source types, concrete data points, specific examples with URLs
  - medium: 2 source types OR 1 source type with multiple strong findings
  - low: single source or vague evidence

Classification (trend_type):
- unmet_need: growing demand for something that has no good solution yet
- dissatisfaction_wave: rising frustration with existing products or services
- behavioral_shift: people changing HOW they do something (e.g., moving from \
agencies to DIY tools, from desktop to mobile, from offline to online)
- regulatory_trigger: a new or upcoming law/regulation creating new needs or \
killing old solutions
- demographic_shift: a growing population segment with distinct, unserved needs
- technology_gap: technology exists that could solve a problem but nobody has \
applied it to this domain yet

Direction:
- emerging: early signals, few sources, mostly recent discussions
- accelerating: growing volume of evidence, multiple sources confirming
- peaking: widespread awareness, many existing solutions, may be saturating
- declining: evidence of the trend fading or being solved

For who_is_affected, be SPECIFIC: not "small businesses" but "independent \
restaurant owners with 1-3 locations" or "freelance software developers filing \
taxes in Germany."

Output ALL trends you can identify. Do not filter — include everything from high \
confidence to low confidence. It is better to surface a weak signal than to miss it.""",
    model="gpt-5.4",
    output_type=SynthesisResult,
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
    ),
)
```

- [ ] **Step 2: Write Dispatcher agent**

Create `research_agents/dispatcher.py`:

```python
from agents import Agent

from models import DispatchDecision

dispatcher = Agent(
    name="Dispatcher",
    instructions="""\
You decide which research agents should be dispatched for a given topic. \
Return ONLY the relevant agent names as a list.

Available agents:
- community_hunter: searches forums, Reddit, HN, Quora, niche communities. \
Dispatched for ALMOST EVERY topic — skip only if the topic is purely about \
government policy with no public discussion.
- review_analyst: searches app stores, Trustpilot, G2, Google Reviews. \
Dispatch when the topic involves existing software, apps, services, or \
businesses that have reviewable products.
- news_scout: searches news sites, industry reports, blogs. \
Dispatched for ALMOST EVERY topic — skip only if the topic is hyper-niche \
with zero media coverage.
- data_researcher: searches government stats, EU reports, institutional data. \
Dispatch ONLY when the topic has a clear regulatory, demographic, policy, \
or macroeconomic dimension.

Return between 2 and 4 agent names. When in doubt, include the agent.""",
    model="gpt-5.4-mini",
    output_type=DispatchDecision,
)
```

- [ ] **Step 3: Update package __init__.py**

Write `research_agents/__init__.py`:

```python
from research_agents.community_hunter import community_hunter
from research_agents.data_researcher import data_researcher
from research_agents.dispatcher import dispatcher
from research_agents.news_scout import news_scout
from research_agents.review_analyst import review_analyst
from research_agents.synthesizer import synthesizer
from research_agents.topic_scorer import topic_scorer
from research_agents.topic_scout import topic_scout

SOURCE_AGENTS = {
    "community_hunter": community_hunter,
    "review_analyst": review_analyst,
    "news_scout": news_scout,
    "data_researcher": data_researcher,
}

__all__ = [
    "topic_scout",
    "topic_scorer",
    "community_hunter",
    "review_analyst",
    "news_scout",
    "data_researcher",
    "dispatcher",
    "synthesizer",
    "SOURCE_AGENTS",
]
```

- [ ] **Step 4: Verify full package imports**

Run: `python -c "from research_agents import SOURCE_AGENTS, topic_scout, synthesizer, dispatcher; print(f'{len(SOURCE_AGENTS)} source agents'); print('OK')"`
Expected:
```
4 source agents
OK
```

- [ ] **Step 5: Commit**

```bash
git add research_agents/
git commit -m "feat: add synthesizer, dispatcher, and wire up package exports"
```

---

### Task 5: Orchestrator

**Files:**
- Create: `orchestrator.py`

- [ ] **Step 1: Write the orchestrator**

Create `orchestrator.py`:

```python
import asyncio
import json
import os
import re
from datetime import datetime

from agents import Runner, trace

from models import (
    DispatchDecision,
    ResearchMetadata,
    SourceAgentResult,
    SynthesisResult,
    TopicResearchOutput,
    TopicScorerResult,
    TopicScoutResult,
    ResearchTopic,
    RawFinding,
)
from research_agents import (
    SOURCE_AGENTS,
    dispatcher,
    synthesizer,
    topic_scorer,
    topic_scout,
)

RESEARCH_DIR = "research"


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text)[:80]


def load_covered_topics() -> list[str]:
    if not os.path.isdir(RESEARCH_DIR):
        return []
    topics = []
    for filename in os.listdir(RESEARCH_DIR):
        if not filename.endswith(".json"):
            continue
        filepath = os.path.join(RESEARCH_DIR, filename)
        try:
            with open(filepath) as f:
                data = json.load(f)
            topic = data.get("topic", "")
            if topic:
                topics.append(topic)
        except (json.JSONDecodeError, OSError):
            continue
    return topics


def build_scout_input(domain: str, covered_topics: list[str]) -> str:
    prompt = f"Domain: {domain}"
    if covered_topics:
        covered = "\n".join(f"- {t}" for t in covered_topics)
        prompt += f"\n\nAlready covered topics (avoid these):\n{covered}"
    return prompt


def build_scorer_input(topics: TopicScoutResult, domain: str) -> str:
    lines = [f"Domain: {domain}\n\nTopics to score and rank:\n"]
    for i, t in enumerate(topics.topics):
        lines.append(f"{i + 1}. {t.topic} (source: {t.source})\n   Reasoning: {t.reasoning}")
    return "\n".join(lines)


def guided_topic_selection(topics: TopicScoutResult) -> list[ResearchTopic]:
    print("\nDiscovered topics:")
    for i, t in enumerate(topics.topics):
        tag = "web" if t.source == "web_discovery" else "model"
        print(f"  [{i}] ({tag}) {t.topic}")
        print(f"       {t.reasoning}")

    selection = input("\nEnter topic numbers to research (comma-separated): ")
    indices = [int(x.strip()) for x in selection.split(",") if x.strip().isdigit()]
    selected = [topics.topics[i] for i in indices if 0 <= i < len(topics.topics)]

    if not selected:
        print("No valid topics selected.")
        return []

    print(f"\nSelected {len(selected)} topic(s):")
    for t in selected:
        print(f"  - {t.topic}")
    return selected


def format_source_results(results: list[SourceAgentResult]) -> str:
    parts = []
    for result in results:
        parts.append(f"## Findings from {result.agent_name}\n")
        if not result.findings:
            parts.append("No findings from this source.\n")
            continue
        for finding in result.findings:
            parts.append(
                f"- **{finding.source_name}** ({finding.source_type})\n"
                f"  {finding.content}\n"
                f"  URL: {finding.url}\n"
                f"  Relevance: {finding.relevance_note}\n"
            )
    return "\n".join(parts)


def save_research(output: TopicResearchOutput) -> str:
    os.makedirs(RESEARCH_DIR, exist_ok=True)
    filename = f"{slugify(output.topic)}.json"
    filepath = os.path.join(RESEARCH_DIR, filename)
    with open(filepath, "w") as f:
        f.write(output.model_dump_json(indent=2))
    return filepath


async def dispatch_source_agents(topic: str) -> list[str]:
    result = await Runner.run(dispatcher, topic)
    decision = result.final_output
    assert isinstance(decision, DispatchDecision)
    valid = [name for name in decision.agents if name in SOURCE_AGENTS]
    if not valid:
        valid = ["community_hunter", "news_scout"]
    return valid


async def run_source_agent(agent_name: str, topic: str) -> SourceAgentResult:
    agent = SOURCE_AGENTS[agent_name]
    result = await Runner.run(agent, topic)
    output = result.final_output
    assert isinstance(output, SourceAgentResult)
    output.agent_name = agent_name
    return output


async def research_topic(topic: str, domain: str) -> TopicResearchOutput:
    print(f"\n  Dispatching agents for: {topic}")
    agent_names = await dispatch_source_agents(topic)
    print(f"  Agents: {', '.join(agent_names)}")

    print(f"  Running {len(agent_names)} source agent(s) in parallel...")
    source_results = await asyncio.gather(
        *[run_source_agent(name, topic) for name in agent_names]
    )

    total_findings = sum(len(r.findings) for r in source_results)
    print(f"  Collected {total_findings} raw findings, synthesizing...")

    synthesis_input = (
        f"Topic: {topic}\n\n"
        f"{format_source_results(list(source_results))}"
    )
    synthesis_result = await Runner.run(synthesizer, synthesis_input)
    synthesis = synthesis_result.final_output
    assert isinstance(synthesis, SynthesisResult)

    return TopicResearchOutput(
        topic=topic,
        trends=synthesis.trends,
        metadata=ResearchMetadata(
            timestamp=datetime.now().isoformat(),
            domain=domain,
            sources_used=agent_names,
        ),
    )


async def run_research(domain: str, guided: bool = False):
    with trace("Research Pipeline"):
        covered = load_covered_topics()
        if covered:
            print(f"Found {len(covered)} already-covered topic(s)")

        print(f"\nScouting topics for: {domain}")
        scout_input = build_scout_input(domain, covered)
        scout_result = await Runner.run(topic_scout, scout_input)
        topics = scout_result.final_output
        assert isinstance(topics, TopicScoutResult)
        print(f"Discovered {len(topics.topics)} topics")

        if guided:
            selected = guided_topic_selection(topics)
            if not selected:
                return
        else:
            print("Scoring and selecting top 6 topics...")
            scorer_input = build_scorer_input(topics, domain)
            scorer_result = await Runner.run(topic_scorer, scorer_input)
            scored = scorer_result.final_output
            assert isinstance(scored, TopicScorerResult)
            selected = [
                ResearchTopic(topic=st.topic, reasoning=st.reasoning, source=st.source)
                for st in scored.ranked_topics[:6]
            ]
            print("Selected topics:")
            for t in selected:
                print(f"  - {t.topic}")

        print(f"\nResearching {len(selected)} topic(s) in parallel...")
        results = await asyncio.gather(
            *[research_topic(t.topic, domain) for t in selected]
        )

        print(f"\n{'=' * 60}")
        print("RESEARCH COMPLETE")
        print(f"{'=' * 60}")
        for output in results:
            filepath = save_research(output)
            print(f"  {len(output.trends)} trend(s) -> {filepath}")
        total = sum(len(r.trends) for r in results)
        print(f"\nTotal: {total} trend(s) across {len(results)} topic(s)")
```

- [ ] **Step 2: Verify orchestrator imports**

Run: `python -c "from orchestrator import run_research; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add orchestrator.py
git commit -m "feat: add orchestrator with parallel pipeline and dispatch logic"
```

---

### Task 6: CLI

**Files:**
- Create: `cli.py`

- [ ] **Step 1: Write the CLI entry point**

Create `cli.py`:

```python
import argparse
import asyncio

from dotenv import load_dotenv

load_dotenv()

from orchestrator import run_research


def main():
    parser = argparse.ArgumentParser(
        description="Discover market trends through multi-agent research",
    )
    parser.add_argument(
        "domain",
        help="Broad research domain (e.g., 'Munich small businesses')",
    )
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Manually select which topics to research",
    )
    args = parser.parse_args()

    asyncio.run(run_research(args.domain, guided=args.guided))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI help**

Run: `python cli.py --help`
Expected output showing domain argument and --guided flag.

- [ ] **Step 3: Commit**

```bash
git add cli.py
git commit -m "feat: add CLI entry point"
```

---

### Task 7: Cleanup + Update Docs

**Files:**
- Remove: `research.py`
- Remove: `ideate.py`
- Remove: `used_topics.txt`
- Remove: old `research/*.json` files (if any)
- Modify: `requirements.txt`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update requirements.txt**

Add `python-dotenv` (already used but was missing from requirements):

```
openai-agents
pydantic
python-dotenv
```

- [ ] **Step 2: Remove old scripts**

```bash
rm research.py ideate.py
rm -f used_topics.txt
```

The old `ideate.py` will be redesigned separately. The old `research.py` is fully replaced by the new pipeline.

- [ ] **Step 3: Clean up old research data**

If any old-format JSON files exist in `research/`, remove them — they use the old `MarketResearch` schema and are incompatible with the new `TopicResearchOutput` format:

```bash
rm -f research/*.json
```

- [ ] **Step 4: Update CLAUDE.md**

Update the commands and architecture sections to reflect the new pipeline:

```markdown
## Commands

\```bash
# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run research (autonomous — auto-selects top 6 topics)
python cli.py "Munich small businesses"

# Run research (guided — you pick topics by number)
python cli.py "Munich small businesses" --guided
\```

Requires `OPENAI_API_KEY` in `.env`. No test suite or linter configured.

## Architecture

\```
cli.py → orchestrator.py → research_agents/ → research/*.json
\```

- **cli.py**: Entry point with argparse. Domain string + optional `--guided` flag.
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
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: remove old scripts, update requirements and docs"
```
