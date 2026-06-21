# CrewAI Starter

A minimal, first-run [CrewAI](https://docs.crewai.com/) project. Two agents — a
researcher and a writer — cooperate on a topic you give them. The point is to get
CrewAI installed and running end-to-end before building the full five-agent
CRISP-DM system described in the case (see `D:\SummerSchool`).

## What is CrewAI, in one paragraph

CrewAI is a Python framework for building **teams of LLM agents**. You define
*agents* (each a role the model plays), give them *tasks*, and group them into a
*crew* that runs the tasks in order. The framework handles talking to the LLM,
passing each task's output to the next, and tracking token usage — so you focus on
*what* the agents do, not the plumbing.

## Project layout

```
requirements.txt              dependencies (crewai + python-dotenv)
.env.example                  template for your API key — copy to .env
src/crew_starter/
  config/agents.yaml          the two agents (role / goal / backstory)
  config/tasks.yaml           the two tasks (what each agent produces)
  crew.py                     wires agents + tasks into a runnable Crew
  main.py                     entry point: loads .env and runs the crew
```

## Setup (Windows, PowerShell)

```powershell
# 1. Create and activate a virtual environment (isolates this project's packages)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your OpenAI key
Copy-Item .env.example .env
#   then open .env and paste your real OPENAI_API_KEY
```

> On macOS/Linux the only differences are `source .venv/bin/activate` and
> `cp .env.example .env`.

## Run it

```powershell
cd src
python -m crew_starter.main
# or give it your own topic:
python -m crew_starter.main "gradient boosting"
```

You'll see each agent "think" out loud (that's `verbose=True`), then a final
summary printed at the end.

## Where to go next

This starter is intentionally tiny. The actual case asks for **five agents**
walking a Kaggle problem through CRISP-DM. When you're comfortable with how
agents, tasks, and the crew fit together here, grow this into that system:
add the remaining roles to `agents.yaml`, give them tasks, and introduce the
loop logic the case describes.

## Note on Python version

CrewAI currently supports Python 3.10–3.13. If `pip install` fails on a newer
interpreter (e.g. 3.14), create the venv with a 3.13 build instead:
`py -3.13 -m venv .venv`.
