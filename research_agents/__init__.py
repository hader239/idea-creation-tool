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
