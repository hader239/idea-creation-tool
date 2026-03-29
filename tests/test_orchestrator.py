import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from models import (
    Confidence,
    DispatchDecision,
    Evidence,
    RawFinding,
    ResearchMetadata,
    SourceAgentResult,
    SynthesisResult,
    TopicResearchOutput,
    Trend,
    TrendDirection,
    TrendType,
)
from orchestrator import (
    build_scout_input,
    dispatch_source_agents,
    format_source_results,
    load_covered_topics,
    research_topic,
    run_source_agent,
    save_research,
    slugify,
)
from research_agents import SOURCE_AGENTS

# --- Helper fixtures ---

def make_trend(**overrides):
    defaults = dict(
        title="Test trend",
        trend_type=TrendType.unmet_need,
        direction=TrendDirection.emerging,
        who_is_affected="test users",
        scale_estimate="~1000",
        current_workarounds="manual process",
        existing_solutions="none",
        solution_gaps="no solution exists",
        evidence=[Evidence(
            source_type="forum",
            source_name="r/test",
            content="people complaining",
            url="https://reddit.com/r/test/1",
        )],
        source_diversity=1,
        confidence=Confidence.low,
    )
    defaults.update(overrides)
    return Trend(**defaults)


def make_finding(**overrides):
    defaults = dict(
        source_type="forum",
        source_name="r/test",
        content="test finding",
        url="https://example.com",
        relevance_note="relevant",
    )
    defaults.update(overrides)
    return RawFinding(**defaults)


def make_source_result(agent_name="community_hunter", num_findings=3):
    return SourceAgentResult(
        agent_name=agent_name,
        findings=[make_finding() for _ in range(num_findings)],
    )


def make_runner_result(final_output):
    result = MagicMock()
    result.final_output = final_output
    return result


# --- slugify ---

def test_slugify_normal():
    assert slugify("Munich small businesses") == "munich-small-businesses"


def test_slugify_special_chars():
    assert slugify("problems with Ü and ö!") == "problems-with-ü-and-ö"


def test_slugify_truncates():
    long_text = "a" * 200
    assert len(slugify(long_text)) == 80


def test_slugify_empty_fallback():
    assert slugify("!!!") == "unnamed-topic"


# --- load_covered_topics ---

def test_load_covered_topics_no_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.RESEARCH_DIR", str(tmp_path / "nonexistent"))
    assert load_covered_topics() == []


def test_load_covered_topics_with_files(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.RESEARCH_DIR", str(tmp_path))
    data = {"topic": "Munich restaurants", "trends": []}
    (tmp_path / "topic1.json").write_text(json.dumps(data))
    (tmp_path / "topic2.json").write_text(json.dumps({"topic": "Student housing"}))
    (tmp_path / "not-json.txt").write_text("ignore me")

    topics = load_covered_topics()
    assert set(topics) == {"Munich restaurants", "Student housing"}


def test_load_covered_topics_skips_malformed(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.RESEARCH_DIR", str(tmp_path))
    (tmp_path / "bad.json").write_text("{invalid json")
    (tmp_path / "good.json").write_text(json.dumps({"topic": "valid"}))

    topics = load_covered_topics()
    assert topics == ["valid"]


# --- build_scout_input ---

def test_build_scout_input_no_covered():
    result = build_scout_input("Munich startups", [])
    assert result == "Domain: Munich startups"


def test_build_scout_input_with_covered():
    result = build_scout_input("Munich startups", ["topic A", "topic B"])
    assert "Already covered topics" in result
    assert "- topic A" in result
    assert "- topic B" in result


# --- format_source_results ---

def test_format_source_results_with_findings():
    results = [make_source_result("community_hunter", 2)]
    text = format_source_results(results)
    assert "community_hunter" in text
    assert "test finding" in text


def test_format_source_results_empty_findings():
    results = [SourceAgentResult(agent_name="review_analyst", findings=[])]
    text = format_source_results(results)
    assert "No findings" in text


# --- save_research ---

def test_save_research(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.RESEARCH_DIR", str(tmp_path))
    output = TopicResearchOutput(
        topic="Test Topic",
        trends=[make_trend()],
        metadata=ResearchMetadata(
            timestamp="2026-01-01",
            domain="test",
            sources_used=["community_hunter"],
        ),
    )
    filepath = save_research(output)
    assert os.path.exists(filepath)

    with open(filepath) as f:
        data = json.load(f)
    assert data["topic"] == "Test Topic"
    assert len(data["trends"]) == 1


# --- dispatch_source_agents (mocked Runner) ---

@pytest.mark.asyncio
async def test_dispatch_returns_valid_agents():
    decision = DispatchDecision(agents=["community_hunter", "news_scout"])
    with patch("orchestrator.Runner.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = make_runner_result(decision)
        result = await dispatch_source_agents("test topic")
    assert result == ["community_hunter", "news_scout"]


@pytest.mark.asyncio
async def test_dispatch_filters_invalid_agents():
    decision = DispatchDecision(agents=["community_hunter", "fake_agent"])
    with patch("orchestrator.Runner.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = make_runner_result(decision)
        result = await dispatch_source_agents("test topic")
    assert result == ["community_hunter"]


@pytest.mark.asyncio
async def test_dispatch_fallback_on_empty():
    decision = DispatchDecision(agents=["fake_agent"])
    with patch("orchestrator.Runner.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = make_runner_result(decision)
        result = await dispatch_source_agents("test topic")
    assert len(result) == 2
    assert all(name in SOURCE_AGENTS for name in result)


# --- run_source_agent (mocked Runner) ---

@pytest.mark.asyncio
async def test_run_source_agent_overrides_name():
    agent_result = make_source_result("wrong_name", 2)
    with patch("orchestrator.Runner.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = make_runner_result(agent_result)
        result = await run_source_agent("community_hunter", "test topic")
    assert result.agent_name == "community_hunter"
    assert len(result.findings) == 2


# --- research_topic (mocked Runner) ---

@pytest.mark.asyncio
async def test_research_topic_full_flow(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.RESEARCH_DIR", str(tmp_path))

    dispatch_decision = DispatchDecision(agents=["community_hunter", "news_scout"])
    source_result = make_source_result("community_hunter", 3)
    synthesis = SynthesisResult(trends=[make_trend()])

    call_count = 0

    async def mock_run(agent, input, **kwargs):
        nonlocal call_count
        call_count += 1
        if agent.name == "Dispatcher":
            return make_runner_result(dispatch_decision)
        elif agent.name == "Synthesizer":
            return make_runner_result(synthesis)
        else:
            return make_runner_result(source_result)

    with patch("orchestrator.Runner.run", side_effect=mock_run):
        result = await research_topic("test topic", "test domain")

    assert result.topic == "test topic"
    assert len(result.trends) == 1
    assert result.metadata.domain == "test domain"
    assert "community_hunter" in result.metadata.sources_used
    # 1 dispatcher + 2 source agents + 1 synthesizer = 4 calls
    assert call_count == 4


# --- error resilience ---

@pytest.mark.asyncio
async def test_research_topic_survives_source_agent_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.RESEARCH_DIR", str(tmp_path))

    dispatch_decision = DispatchDecision(
        agents=["community_hunter", "news_scout", "review_analyst"]
    )
    source_result = make_source_result("community_hunter", 2)
    synthesis = SynthesisResult(trends=[make_trend()])

    async def mock_run(agent, input, **kwargs):
        if agent.name == "Dispatcher":
            return make_runner_result(dispatch_decision)
        elif agent.name == "Synthesizer":
            return make_runner_result(synthesis)
        elif agent.name == "News Scout":
            raise RuntimeError("API timeout")
        else:
            return make_runner_result(source_result)

    with patch("orchestrator.Runner.run", side_effect=mock_run):
        result = await research_topic("test topic", "test domain")

    # Should still succeed with 2 out of 3 source agents
    assert len(result.trends) == 1


@pytest.mark.asyncio
async def test_research_topic_fails_when_all_agents_fail(tmp_path, monkeypatch):
    monkeypatch.setattr("orchestrator.RESEARCH_DIR", str(tmp_path))

    dispatch_decision = DispatchDecision(agents=["community_hunter"])

    async def mock_run(agent, input, **kwargs):
        if agent.name == "Dispatcher":
            return make_runner_result(dispatch_decision)
        raise RuntimeError("all broken")

    with patch("orchestrator.Runner.run", side_effect=mock_run):
        with pytest.raises(RuntimeError, match="All source agents failed"):
            await research_topic("test topic", "test domain")
