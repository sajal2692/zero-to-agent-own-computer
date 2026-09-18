# Give Your Agent Its Own Computer

This repo goes with my September 23, 2026 O'Reilly session, **Give Your Agent
Its Own Computer**, part of *Zero to Agent in 30*.

In the session, I give an agent a computer of its own in the cloud. It can use
that computer through the shell or through the screen, and we watch it work
through a task on a remote desktop.

## The demos

| Demo | What it shows | Built with |
|---|---|---|
| `demos/01_shell_data_analysis` | An agent uses its computer through the shell. It downloads real data, installs what it needs, and writes a PDF report. | LangChain Deep Agents, E2B sandbox |
| `demos/02_desktop_agents_sdk` | An agent uses its computer through the screen. It opens a browser, researches desks on IKEA Canada, and writes a short report. | OpenAI Agents SDK, E2B Desktop |
| `demos/03_desktop_plain_loop` | The same desktop task with the loop written out by hand, with no agent framework. | OpenAI Responses API, E2B Desktop |

In every demo the agent loop runs on your machine and the work happens on the agent's
computer. Each log line starts with `LOCAL` or `SANDBOX` so you can see which is which.

## Run them

You need Python 3.12, [uv](https://docs.astral.sh/uv/), an [E2B](https://e2b.dev) API key, and
an OpenAI API key with access to a computer use model. E2B's free plan is enough. The OpenAI
calls cost money, roughly 25 cents for demo 1 and 50 cents to a dollar for a desktop run.

```bash
git clone https://github.com/sajal2692/zero-to-agent-own-computer.git
cd zero-to-agent-own-computer
cp .env.example .env    # then add your two keys
uv sync
uv run python demos/01_shell_data_analysis/agent.py
uv run python demos/02_desktop_agents_sdk/agent.py
uv run python demos/03_desktop_plain_loop/agent.py
```

The desktop demos print a link. Open it in a browser to watch the agent's screen, then press
Enter to start. Each run saves its report and a cost summary under that demo's `output/` folder,
and deletes the computer at the end, including after Ctrl+C.

The desktop demos browse a real shopping site. Run them as a single supervised session, the way
you would browse yourself.

## Data

Demo 1 uses the [college majors data](https://github.com/fivethirtyeight/data/tree/master/college-majors)
from FiveThirtyEight, licensed CC BY 4.0. It comes from the American Community Survey for 2010
to 2012, so treat the numbers as an example and not as current salary information.
