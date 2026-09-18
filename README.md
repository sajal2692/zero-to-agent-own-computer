# Give Your Agent Its Own Computer

This repo goes with my September 23, 2026 O'Reilly session, **Give Your Agent
Its Own Computer**, part of *Zero to Agent in 30*.

In the session, I give an agent a computer of its own in the cloud. It can use
that computer through the shell or through the screen, and we watch it do a real
task each way.

## The demos

| Demo | What it shows | Built with |
|---|---|---|
| `demos/01_shell_data_analysis` | The agent uses its computer through the shell. It downloads real data, installs what it needs, and writes a PDF report. | LangChain Deep Agents, E2B sandbox |
| `demos/02_desktop_agents_sdk` | The agent uses its computer through the screen. It opens a browser, researches desks on IKEA Canada, and writes a short report. | OpenAI Agents SDK, E2B Desktop |
| `demos/03_desktop_plain_loop` | The same desktop task with the loop written out by hand, with no agent framework. | OpenAI Responses API, E2B Desktop |

Each demo is one script that reads top to bottom. The prompt, the model, and the
settings are at the top of the file.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- An [E2B](https://e2b.dev) API key. The free plan is enough.
- An OpenAI API key with access to `gpt-5.6-sol` and `gpt-5.6-terra`. These calls cost money.
  See [Costs](#costs).
- A web browser, to watch the agent's desktop in demos 2 and 3.

## Setup

```bash
git clone https://github.com/sajal2692/zero-to-agent-own-computer.git
cd zero-to-agent-own-computer
cp .env.example .env
uv sync
```

Open `.env` and add your two keys. Git ignores this file.

## Run the demos

### Demo 1: through the shell

```bash
uv run python demos/01_shell_data_analysis/agent.py
```

The agent gets this task:

> I'm helping my niece choose a college major. The FiveThirtyEight college majors data is in
> this GitHub folder. Download the CSV files and work out which majors pay best and which pay
> worst for recent graduates, and where a graduate degree makes the biggest difference. Check
> whether the high earners also have low unemployment. Write me a one-page PDF report with a
> couple of charts.

What to look for:

- It downloads the files and installs its own Python packages on the sandbox.
- It writes and runs an analysis script, and fixes it when a command fails.
- It looks at its finished page as an image and fixes anything cut off.
- The script brings `report.pdf` back to your machine, then deletes the sandbox.

### Demo 2: through the screen

```bash
uv run python demos/02_desktop_agents_sdk/agent.py
```

The script prints a link. Open it in a browser to watch the agent's desktop, then press Enter
in the terminal to start. The agent gets this task:

> I'm setting up a home office in a small room. Look on IKEA Canada and find me the three best
> desks under 250 Canadian dollars, no wider than 120 centimetres, rated four stars or better.
> Write me a short report with the three desks, their price, size, and rating, and tell me
> which one you'd pick and why.

What to look for:

- It starts from an empty desktop and opens the browser itself.
- It deals with the cookie banner and pop-ups before it starts the task.
- Each round is a screenshot, a decision, a few actions, and a check of the new screen.
- It reports only what it saw on the site, and ends with a short written report.

### Demo 3: the same loop by hand

```bash
uv run python demos/03_desktop_plain_loop/agent.py
```

Same task and same desktop as demo 2. This script has no agent framework. It calls OpenAI's
computer use tool directly, so you can read the loop line by line: observe, choose, act, check.

### Try your own task

The desktop scripts take a task as an argument:

```bash
uv run python demos/02_desktop_agents_sdk/agent.py "Find the opening hours of the Art Gallery of Ontario this Saturday."
```

For demo 1, edit `TASK` at the top of the script.

## Reading the logs

In every demo the agent loop runs on your machine, and the work happens on the agent's
computer. Each log line says which:

- `LOCAL` is your machine: creating and deleting the computer, the task, the model's thinking,
  the final report, and the cost summary.
- `SANDBOX` is the agent's computer: each command and file operation in demo 1, and each click,
  scroll, and keypress in demos 2 and 3.

## What a run leaves behind

Each run saves a timestamped folder under that demo's `output/` directory:

- `report.pdf` for demo 1, or `report.md` and `final_screen.png` for demos 2 and 3
- `run.json`, with the time taken, token counts, and the cost of the run

Git ignores the `output/` folders. The sandbox is deleted at the end of every run, including
after an error or Ctrl+C.

## Costs

These are typical figures from my own runs in September 2026. Yours will vary.

| Demo | Model | Time | OpenAI cost |
|---|---|---|---|
| 1, shell | `gpt-5.6-terra` | 2 to 3 minutes | about 20 cents |
| 2 and 3, desktop | `gpt-5.6-sol` | 2 to 6 minutes | 20 cents to 1 dollar |

E2B usage comes out of the free plan's one-time credit. A desktop sandbox costs about half a
dollar an hour, and a run uses a few cents. The free plan limits a sandbox to one hour.

The price constants at the top of each script feed the cost summary. Check them against the
current price lists.

## Things to know

- The desktop demos browse a real shopping site. Run them as a single supervised session, the
  way you would browse yourself. If a site blocks the agent or shows a CAPTCHA, it stops and
  says so.
- The agent never signs in, creates accounts, or buys anything. Those rules are in the
  instructions at the top of the desktop scripts, along with a description of its computer.
- Agents vary from run to run. The same task can take a different route and a different
  amount of time.

## Data and credits

Nothing in this repo is synthetic. Demo 1 downloads the
[college majors data](https://github.com/fivethirtyeight/data/tree/master/college-majors) from
FiveThirtyEight, licensed CC BY 4.0. It comes from the American Community Survey for 2010 to
2012, so treat the numbers as an example and not as current salary information.
