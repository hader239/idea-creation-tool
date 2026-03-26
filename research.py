import asyncio
import os
import re
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from agents import Agent, ModelRetrySettings, ModelSettings, Runner, WebSearchTool, retry_policies, trace
from openai.types.shared.reasoning import Reasoning

from models import MarketResearch, ResearchTopic

RESEARCH_DIR = "research"
USED_TOPICS_FILE = "used_topics.txt"

web_search = WebSearchTool(
    search_context_size="high",
    user_location={
        "type": "approximate",
        "city": "Munich",
        "country": "DE",
        "region": "Bavaria",
    },
)

topic_generator = Agent(
    name="Topic Generator",
    instructions="""\
You are a startup research topic generator focused on Munich / Bavaria / Germany / Europe.

Your task: generate ONE specific, narrow research topic to investigate for startup opportunities. The topic should be a focused area where real pain points might exist.

Good topics are specific and actionable:
- "Pain points freelancers in Germany face with tax filing and Finanzamt"
- "Problems Munich students have finding short-term furnished housing"
- "Frustrations small restaurant owners in Munich have with online ordering platforms"
- "Difficulties expats in Germany face with Anmeldung and visa bureaucracy"
- "Gaps in loyalty and rewards programs for independent shops in German cities"

Bad topics are too broad:
- "Business ideas in Germany"
- "Munich startups"
- "European tech"

Think about: local businesses, students, expats, freelancers, tradespeople (Handwerker), parents, renters, small landlords, local event organizers, sports clubs (Vereine), healthcare navigation, public transport, sustainability, food/delivery, legal/compliance, and more.

In your reasoning field, briefly explain why this topic is worth researching.""",
    model="gpt-5.4-mini",
    output_type=ResearchTopic,
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="low", summary="concise"),
    ),
)

researcher = Agent(
    name="Market Researcher",
    instructions="""\
You are a market researcher specializing in the Munich / Bavaria / Germany / Europe region.

Your task: find 5-8 concrete startup opportunities by searching the web for REAL pain points and underserved markets. Focus on:

- Problems small businesses in Munich face (loyalty programs, local delivery, booking, invoicing, compliance with German regulations like DSGVO/Kassensicherungsverordnung)
- Student pain points at LMU, TUM, and other Munich universities (housing, part-time work, study tools, social life, bureaucracy like Anmeldung/visa)
- Gaps in existing European/German digital services that US-centric products don't cover well
- Trending complaints on Reddit (r/munich, r/germany, r/de), HackerNews, Indie Hackers, German forums, and social media

For each opportunity, provide:
- The specific pain point
- Evidence: what real people are saying and where (forums, posts, videos)
- Existing competitors in the DACH/European market (if any)
- The market gap: why current solutions fall short
- Why this is particularly relevant to Munich/Germany/Europe

Only include opportunities where an MVP could realistically be built by one developer in 1-2 weeks.""",
    model="gpt-5.4",
    tools=[web_search],
    output_type=MarketResearch,
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="high", summary="auto"),
        retry=ModelRetrySettings(
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
        ),
    ),
)


def load_used_topics() -> list[str]:
    if not os.path.exists(USED_TOPICS_FILE):
        return []
    with open(USED_TOPICS_FILE) as f:
        return [line.strip() for line in f if line.strip()]


def save_topic(topic: str):
    with open(USED_TOPICS_FILE, "a") as f:
        f.write(topic + "\n")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text)[:60]


async def run_research(prompt: str) -> str:
    with trace("Market Research"):
        print(f"Researching: {prompt}")
        print("(searching the web for real pain points and market gaps)\n")

        result = await Runner.run(researcher, prompt)
        research = result.final_output
        assert isinstance(research, MarketResearch)

        research.prompt = prompt
        research.timestamp = datetime.now().isoformat()

        os.makedirs(RESEARCH_DIR, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}-{slugify(prompt)}.json"
        filepath = os.path.join(RESEARCH_DIR, filename)

        with open(filepath, "w") as f:
            f.write(research.model_dump_json(indent=2))

        print(f"Found {len(research.opportunities)} opportunities:")
        for i, opp in enumerate(research.opportunities):
            print(f"  [{i}] {opp.pain_point}")
        print(f"\nSaved to {filepath}")

        return filepath


async def run_loop():
    previous_topics = load_used_topics()
    if previous_topics:
        print(f"Loaded {len(previous_topics)} previously explored topics "
              f"from {USED_TOPICS_FILE}")

    round_num = 0

    while True:
        round_num += 1
        print(f"\n{'#' * 60}")
        print(f"  ROUND {round_num}")
        print(f"{'#' * 60}\n")

        topic_input = "Generate a research topic."
        if previous_topics:
            explored = "\n".join(f"- {t}" for t in previous_topics)
            topic_input = (
                f"Generate a research topic.\n\n"
                f"Already explored (avoid these):\n{explored}"
            )

        print("Generating research topic...")
        topic_result = await Runner.run(topic_generator, topic_input)
        topic = topic_result.final_output
        assert isinstance(topic, ResearchTopic)
        print(f"  Topic: {topic.topic}")
        print(f"  Why: {topic.reasoning}\n")

        previous_topics.append(topic.topic)
        save_topic(topic.topic)

        await run_research(topic.topic)

        print(f"\nRound {round_num} complete. "
              f"{len(previous_topics)} topics explored so far.")


if __name__ == "__main__":
    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        files = []
        if os.path.isdir(RESEARCH_DIR):
            files = [f for f in os.listdir(RESEARCH_DIR) if f.endswith(".json")]
        print(f"\n\nStopped. {len(files)} research file(s) in {RESEARCH_DIR}/.")
