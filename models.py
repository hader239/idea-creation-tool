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
    agent_name: str = ""
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
