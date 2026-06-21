"""Entry point: load the .env, kick off the crew, print the result.

Run it with:
    python -m crew_starter.main
or:
    python -m crew_starter.main "your topic here"
"""

import sys

from dotenv import load_dotenv

from crew_starter.crew import CrewStarter


def run() -> None:
    # Loads OPENAI_API_KEY (and MODEL) from .env into the environment.
    load_dotenv()

    # The {topic} placeholder in the YAML files is filled from these inputs.
    topic = sys.argv[1] if len(sys.argv) > 1 else "the CRISP-DM data-mining process"
    inputs = {"topic": topic}

    result = CrewStarter().crew().kickoff(inputs=inputs)

    print("\n" + "=" * 60)
    print("FINAL RESULT")
    print("=" * 60)
    print(result)


if __name__ == "__main__":
    run()
