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
