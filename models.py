from pydantic import BaseModel


class Opportunity(BaseModel):
    pain_point: str
    evidence: str
    existing_competitors: str
    market_gap: str
    locale_relevance: str


class MarketResearch(BaseModel):
    prompt: str = ""
    timestamp: str = ""
    opportunities: list[Opportunity]


class ResearchTopic(BaseModel):
    topic: str
    reasoning: str


class StartupIdea(BaseModel):
    name: str
    one_liner: str
    problem: str
    solution: str
    target_audience: str
    mvp_scope: str
    marketing_angle: str
    opportunity_index: int


class IdeaValidation(BaseModel):
    is_valid: bool
    alignment_with_research: str
    feasibility_check: str
    rejection_reason: str
