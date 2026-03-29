import asyncio
import json
import os
import re
from datetime import datetime

from agents import Runner, trace

from models import (
    DispatchDecision,
    ResearchMetadata,
    ResearchTopic,
    SourceAgentResult,
    SynthesisResult,
    TopicResearchOutput,
    TopicScorerResult,
    TopicScoutResult,
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
    slug = re.sub(r"[\s_]+", "-", text)[:80]
    return slug or "unnamed-topic"


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
    if not isinstance(decision, DispatchDecision):
        raise TypeError(f"Dispatcher returned {type(decision).__name__}, expected DispatchDecision")
    valid = [name for name in decision.agents if name in SOURCE_AGENTS]
    if not valid:
        valid = ["community_hunter", "news_scout"]
    return valid


async def run_source_agent(agent_name: str, topic: str) -> SourceAgentResult:
    agent = SOURCE_AGENTS[agent_name]
    result = await Runner.run(agent, topic)
    output = result.final_output
    if not isinstance(output, SourceAgentResult):
        got = type(output).__name__
        raise TypeError(f"{agent_name} returned {got}, expected SourceAgentResult")
    output = output.model_copy(update={"agent_name": agent_name})
    print(f"    {agent_name} done ({len(output.findings)} findings)")
    return output


async def research_topic(topic: str, domain: str) -> TopicResearchOutput:
    print(f"\n  Dispatching agents for: {topic}")
    agent_names = await dispatch_source_agents(topic)
    print(f"  Agents: {', '.join(agent_names)}")

    print(f"  Running {len(agent_names)} source agent(s) in parallel...")
    raw_results = await asyncio.gather(
        *[run_source_agent(name, topic) for name in agent_names],
        return_exceptions=True,
    )
    source_results = []
    for r in raw_results:
        if isinstance(r, Exception):
            print(f"  WARNING: source agent failed: {r}")
        else:
            source_results.append(r)

    if not source_results:
        raise RuntimeError(f"All source agents failed for topic: {topic}")

    total_findings = sum(len(r.findings) for r in source_results)
    print(f"  Collected {total_findings} raw findings, synthesizing...")

    synthesis_input = (
        f"Topic: {topic}\n\n"
        f"{format_source_results(list(source_results))}"
    )
    synthesis_result = await Runner.run(synthesizer, synthesis_input)
    synthesis = synthesis_result.final_output
    if not isinstance(synthesis, SynthesisResult):
        got = type(synthesis).__name__
        raise TypeError(f"Synthesizer returned {got}, expected SynthesisResult")

    return TopicResearchOutput(
        topic=topic,
        trends=synthesis.trends,
        metadata=ResearchMetadata(
            timestamp=datetime.now().isoformat(),
            domain=domain,
            sources_used=[r.agent_name for r in source_results],
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
        if not isinstance(topics, TopicScoutResult):
            got = type(topics).__name__
            raise TypeError(f"Topic Scout returned {got}, expected TopicScoutResult")
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
            if not isinstance(scored, TopicScorerResult):
                got = type(scored).__name__
                raise TypeError(f"Topic Scorer returned {got}, expected TopicScorerResult")
            selected = [
                ResearchTopic(topic=st.topic, reasoning=st.reasoning, source=st.source)
                for st in scored.ranked_topics[:6]
            ]
            print("Selected topics:")
            for t in selected:
                print(f"  - {t.topic}")

        print(f"\nResearching {len(selected)} topic(s) in parallel...")
        raw_results = await asyncio.gather(
            *[research_topic(t.topic, domain) for t in selected],
            return_exceptions=True,
        )
        results = []
        for r in raw_results:
            if isinstance(r, Exception):
                print(f"  WARNING: topic research failed: {r}")
            else:
                results.append(r)

        print(f"\n{'=' * 60}")
        print("RESEARCH COMPLETE")
        print(f"{'=' * 60}")
        for output in results:
            filepath = save_research(output)
            print(f"  {len(output.trends)} trend(s) -> {filepath}")
        total = sum(len(r.trends) for r in results)
        print(f"\nTotal: {total} trend(s) across {len(results)} topic(s)")
