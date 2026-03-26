import argparse
import asyncio
import os
import re
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from agents import Agent, ModelSettings, Runner, trace
from openai.types.shared.reasoning import Reasoning

from models import (
    IdeaValidation,
    MarketResearch,
    Opportunity,
    StartupIdea,
)

MAX_ATTEMPTS = 5
IDEAS_DIR = "ideas"

idea_creator = Agent(
    name="Idea Creator",
    instructions="""\
You are a startup idea creator. You will receive market research containing validated opportunities with real evidence.

Your task: pick ONE opportunity from the research and craft a concrete startup idea around it.

Rules:
1. The idea MUST directly address a pain point from the research — do not invent new problems.
2. The MVP must be buildable by a solo developer in 1-2 weeks.
3. No PhD-level expertise required.
4. The idea must be marketing-ready: you could post about it today and get waitlist signups.
5. Be specific to the Munich/Germany/Europe context when relevant.

Set opportunity_index to the 0-based index of the opportunity you chose from the research.""",
    model="gpt-5.4-mini",
    output_type=StartupIdea,
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="medium", summary="concise"),
    ),
)

idea_validator = Agent(
    name="Idea Validator",
    instructions="""\
You are a lightweight idea validator. You will receive a startup idea AND the specific market opportunity it was derived from.

Check three things:

1. ALIGNMENT: Does the idea genuinely address the researched pain point? Is it grounded in the evidence, or did the creator drift into speculation?
2. FEASIBILITY: Can a solo developer realistically build the MVP in 1-2 weeks? Flag overambitious scope.
3. MARKETING FIT: Could you credibly post about this idea today and attract signups from the target audience in Munich/Germany?

Set is_valid to true if all three checks pass.
If rejecting, explain clearly in rejection_reason what went wrong and suggest a different angle.
If accepting, set rejection_reason to an empty string.""",
    model="gpt-5.4-mini",
    output_type=IdeaValidation,
    model_settings=ModelSettings(
        reasoning=Reasoning(effort="medium", summary="concise"),
    ),
)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"[\s_]+", "-", text)[:60]


def format_opportunities(opportunities: list[Opportunity]) -> str:
    parts = ["# Market Research Opportunities\n"]
    for i, opp in enumerate(opportunities):
        parts.append(
            f"## Opportunity {i}\n"
            f"**Pain point:** {opp.pain_point}\n"
            f"**Evidence:** {opp.evidence}\n"
            f"**Competitors:** {opp.existing_competitors}\n"
            f"**Market gap:** {opp.market_gap}\n"
            f"**Locale relevance:** {opp.locale_relevance}\n"
        )
    return "\n".join(parts)


def format_opportunity(opp: Opportunity) -> str:
    return (
        f"**Pain point:** {opp.pain_point}\n"
        f"**Evidence:** {opp.evidence}\n"
        f"**Competitors:** {opp.existing_competitors}\n"
        f"**Market gap:** {opp.market_gap}\n"
        f"**Locale relevance:** {opp.locale_relevance}"
    )


def format_idea(idea: StartupIdea) -> str:
    return (
        f"Name: {idea.name}\n"
        f"One-liner: {idea.one_liner}\n"
        f"Problem: {idea.problem}\n"
        f"Solution: {idea.solution}\n"
        f"Target Audience: {idea.target_audience}\n"
        f"MVP Scope: {idea.mvp_scope}\n"
        f"Marketing Angle: {idea.marketing_angle}"
    )


def save_idea(
    idea: StartupIdea,
    validation: IdeaValidation,
    opportunity: Opportunity,
) -> str:
    os.makedirs(IDEAS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    filename = f"{timestamp}-{slugify(idea.name)}.md"
    filepath = os.path.join(IDEAS_DIR, filename)

    content = f"""\
# {idea.name}

> {idea.one_liner}

## Problem

{idea.problem}

## Solution

{idea.solution}

## Target Audience

{idea.target_audience}

## MVP Scope (1-2 weeks)

{idea.mvp_scope}

## Marketing Angle

{idea.marketing_angle}

---

## Research Backing

- **Pain Point:** {opportunity.pain_point}
- **Evidence:** {opportunity.evidence}
- **Competitors:** {opportunity.existing_competitors}
- **Market Gap:** {opportunity.market_gap}
- **Locale Relevance:** {opportunity.locale_relevance}

## Validation

- **Alignment:** {validation.alignment_with_research}
- **Feasibility:** {validation.feasibility_check}
"""

    with open(filepath, "w") as f:
        f.write(content)

    return filepath


def load_research(filepaths: list[str]) -> list[Opportunity]:
    opportunities: list[Opportunity] = []
    for path in filepaths:
        with open(path) as f:
            research = MarketResearch.model_validate_json(f.read())
        print(f"Loaded {len(research.opportunities)} opportunities from {path}")
        opportunities.extend(research.opportunities)
    return opportunities


async def run_ideation(
    opportunities: list[Opportunity],
    num_ideas: int = 1,
):
    research_text = format_opportunities(opportunities)

    with trace("Idea Generation"):
        ideas_found = 0
        used_opportunities: list[int] = []

        consecutive_failures = 0

        while ideas_found < num_ideas:
            attempt = 0
            previous_rejections: list[str] = []

            while attempt < MAX_ATTEMPTS:
                attempt += 1
                print(f"\n{'=' * 50}")
                print(f"Idea {ideas_found + 1} | Attempt {attempt}/{MAX_ATTEMPTS}")
                print(f"{'=' * 50}")

                avoid_note = ""
                if used_opportunities:
                    avoid_note = (
                        f"\n\nAlready used opportunity indices "
                        f"{used_opportunities} — pick a DIFFERENT one."
                    )

                creator_input = research_text + avoid_note
                if previous_rejections:
                    feedback = "\n".join(
                        f"- Attempt {i + 1}: {r}"
                        for i, r in enumerate(previous_rejections)
                    )
                    creator_input += (
                        f"\n\nPrevious ideas were rejected:\n{feedback}\n\n"
                        f"Try a different opportunity or angle."
                    )

                print("Generating idea...")
                idea_result = await Runner.run(idea_creator, creator_input)
                idea = idea_result.final_output
                assert isinstance(idea, StartupIdea)
                print(f"  -> {idea.name}: {idea.one_liner}")

                opp_idx = idea.opportunity_index
                opp_idx = max(0, min(opp_idx, len(opportunities) - 1))
                opportunity = opportunities[opp_idx]

                print("Validating...")
                validation_input = (
                    f"## Idea\n{format_idea(idea)}\n\n"
                    f"## Referenced Opportunity\n{format_opportunity(opportunity)}"
                )
                validation_result = await Runner.run(
                    idea_validator, validation_input
                )
                validation = validation_result.final_output
                assert isinstance(validation, IdeaValidation)

                if validation.is_valid:
                    filepath = save_idea(idea, validation, opportunity)
                    ideas_found += 1
                    used_opportunities.append(opp_idx)
                    consecutive_failures = 0
                    print(f"  VALID — saved to {filepath}\n")
                    break

                print(f"  REJECTED — {validation.rejection_reason}\n")
                previous_rejections.append(validation.rejection_reason)
            else:
                consecutive_failures += 1
                remaining = num_ideas - ideas_found
                print(
                    f"Could not find a valid idea after {MAX_ATTEMPTS} "
                    f"attempts ({remaining} idea(s) still needed).\n"
                )
                if consecutive_failures >= 2:
                    print(
                        "Two consecutive failures — stopping to avoid "
                        "burning tokens. Try adding more research.\n"
                    )
                    break

    print(f"Done — generated {ideas_found} valid idea(s).")


def main():
    parser = argparse.ArgumentParser(
        description="Generate startup ideas from research files",
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Research JSON file(s) to load opportunities from",
    )
    parser.add_argument(
        "--num-ideas", "-n",
        type=int,
        default=1,
        help="Number of valid ideas to generate (default: 1)",
    )
    args = parser.parse_args()

    opportunities = load_research(args.files)
    if not opportunities:
        print("No opportunities found in the provided research files.")
        return

    print(f"\n{len(opportunities)} total opportunities loaded:")
    for i, opp in enumerate(opportunities):
        print(f"  [{i}] {opp.pain_point}")
    print()

    asyncio.run(run_ideation(opportunities, num_ideas=args.num_ideas))


if __name__ == "__main__":
    main()
