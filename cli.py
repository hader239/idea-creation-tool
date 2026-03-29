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
