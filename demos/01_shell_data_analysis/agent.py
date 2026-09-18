"""Demo 1: an agent uses its own computer through the shell.

LangChain Deep Agents runs the loop on your machine.
Its file and command tools run on an E2B sandbox.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.profiles import GeneralPurposeSubagentProfile, HarnessProfile, register_harness_profile
from dotenv import load_dotenv
from e2b import Sandbox
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_e2b import E2BSandbox
from langchain_openai import ChatOpenAI

DEMO_DIR = Path(__file__).resolve().parent
MODEL = "gpt-5.6-terra"
REASONING_EFFORT = "medium"
WORKDIR = "/home/user"
LOCAL_TOOLS = {"write_todos"}  # the agent's to-do list lives in the loop, not on the sandbox

TASK = (
    "I'm helping my niece choose a college major. The FiveThirtyEight college majors data is in "
    "this GitHub folder: https://github.com/fivethirtyeight/data/tree/master/college-majors. "
    "Download the CSV files and work out which majors pay best and which pay worst for recent "
    "graduates, and where a graduate degree makes the biggest difference. Check whether the high "
    "earners also have low unemployment. Write me a one-page PDF report with a couple of charts. "
    "The data is from 2010 to 2012, so say that in the report. "
    "Before you finish, look at the finished page as an image and fix anything cut off or overlapping. "
    f"Save the report as {WORKDIR}/report.pdf."
)
SYSTEM_PROMPT = (
    "You are a data analyst. Your file and command tools run on a Linux computer of your own. "
    "Install any packages you need. Finish with a short summary of what you found."
)

# US dollars per million tokens (input, cached input, output). Check the current price list.
TOKEN_PRICES = (2.00, 0.20, 12.00)
SANDBOX_PRICE = 2 * 0.000014 + 0.5 * 0.0000045  # per second, E2B base sandbox: 2 vCPU and 512 MB


def log(where, heading, body=""):
    """Every line says where it happened: LOCAL is this machine, SANDBOX is the agent's computer."""
    heading = f"[{datetime.now():%H:%M:%S}] {where:<8}{heading}"
    if sys.stdout.isatty() and "NO_COLOR" not in os.environ:
        heading = f"\033[1;{34 if where == 'LOCAL' else 35}m{heading}\033[0m"
    print(f"\n{heading}", flush=True)
    if body:
        print(body, flush=True)


def readable(content):
    """Make tool input and output fit on screen: no image data, no progress bars, no walls of text."""
    if isinstance(content, list):  # images come back as content blocks
        content = "\n".join(
            "[image]" if block.get("type") == "image" else str(block.get("text", block))
            for block in content
        )
    text = "\n".join(line.split("\r")[-1] for line in str(content).splitlines())
    return text if len(text) <= 1200 else text[:1200] + "\n... (trimmed)"


def main():
    load_dotenv(DEMO_DIR.parents[1] / ".env")
    for name in ("E2B_API_KEY", "OPENAI_API_KEY"):
        if not os.getenv(name):
            raise RuntimeError(f"Set {name} in the repository's .env file.")

    # 1. Create the agent's computer.
    started = time.time()
    sandbox = Sandbox.create(timeout=1800)
    try:
        log("LOCAL", "Computer ready", f"{sandbox.sandbox_id} in {time.time() - started:.1f} seconds\n"
            "Agent loop and model calls: this machine | File and command tools: the E2B sandbox")

        # 2. Connect the LOCAL agent to the REMOTE tools.
        backend = E2BSandbox(sandbox=sandbox, workdir=WORKDIR)
        model = ChatOpenAI(model=MODEL, reasoning={"effort": REASONING_EFFORT, "summary": "auto"})
        # Keep this small example to one agent, with no delegated subagents.
        register_harness_profile(f"openai:{MODEL}", HarnessProfile(
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ))
        agent = create_deep_agent(
            model=model,
            backend=backend,
            system_prompt=SYSTEM_PROMPT,
            middleware=[ModelCallLimitMiddleware(run_limit=40, exit_behavior="error")],
        )

        # 3. Run the loop and print every tool call and result as it happens.
        log("LOCAL", "Task", TASK)
        fresh = cached = written = requests = 0
        answer = ""
        for update in agent.stream(
            {"messages": [{"role": "user", "content": TASK}]},
            config={"recursion_limit": 300}, stream_mode="updates",
        ):
            for state in update.values():
                for message in (state or {}).get("messages", []):
                    if isinstance(message, AIMessage):
                        usage = message.usage_metadata or {}
                        read = usage.get("input_token_details", {}).get("cache_read", 0)
                        requests += 1
                        cached += read
                        fresh += usage.get("input_tokens", 0) - read
                        written += usage.get("output_tokens", 0)
                        for block in message.content_blocks:
                            if block["type"] == "reasoning" and block.get("reasoning"):
                                log("LOCAL", "Thinking", block["reasoning"].replace("**", "")[:400])
                        if message.text:
                            answer = message.text
                            log("LOCAL", "Agent", message.text)
                        for call in message.tool_calls:
                            where = "LOCAL" if call["name"] in LOCAL_TOOLS else "SANDBOX"
                            log(where, f"Tool call: {call['name']}", readable("\n".join(
                                f"{key}: {value}" for key, value in call["args"].items()
                            )))
                    elif isinstance(message, ToolMessage):
                        where = "LOCAL" if message.name in LOCAL_TOOLS else "SANDBOX"
                        log(where, f"Result: {message.name}", readable(message.content))

        # 4. Bring the report back from the agent's computer.
        output = DEMO_DIR / "output" / f"{datetime.now():%Y%m%d-%H%M%S}"
        output.mkdir(parents=True)
        (output / "report.pdf").write_bytes(sandbox.files.read(f"{WORKDIR}/report.pdf", format="bytes"))
        log("LOCAL", "Report downloaded from the sandbox", str(output / "report.pdf"))
        (output / "answer.md").write_text(answer)

        # 5. Work out what the run cost.
        seconds = round(time.time() - started)
        cost = (fresh * TOKEN_PRICES[0] + cached * TOKEN_PRICES[1] + written * TOKEN_PRICES[2]) / 1e6
        run = {
            "seconds": seconds, "model_requests": requests,
            "input_tokens": fresh, "cached_input_tokens": cached, "output_tokens": written,
            "model_cost_usd": round(cost, 2), "sandbox_cost_usd": round(seconds * SANDBOX_PRICE, 2),
        }
        (output / "run.json").write_text(json.dumps(run, indent=2))
        log("LOCAL", "Run summary", json.dumps(run, indent=2))
    finally:
        # 6. Delete the computer, including after an error or Ctrl+C.
        sandbox.kill()
        log("LOCAL", "Computer deleted")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
