"""Demo 2: an agent uses its own computer through the screen.

The OpenAI Agents SDK runs the loop. E2B Desktop is the computer.
"""

import asyncio
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from agents import Agent, AsyncComputer, ComputerTool, ModelSettings, Runner
from dotenv import load_dotenv
from e2b_desktop import Sandbox
from openai.types.shared import Reasoning

DEMO_DIR = Path(__file__).resolve().parent
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "medium"
RESOLUTION = (1024, 768)
MAX_TURNS = 80

TASK = (
    "I'm setting up a home office in a small room. Look on IKEA Canada and find me the three best "
    "desks under 250 Canadian dollars, no wider than 120 centimetres, rated four stars or better. "
    "Write me a short report with the three desks, their price, size, and rating, and tell me "
    "which one you'd pick and why."
)
INSTRUCTIONS = """
You are an agent working on a computer of your own, a Linux desktop in the cloud. You see it
through screenshots and control it with the mouse and keyboard.

YOUR COMPUTER
- Ubuntu 22.04 with the Xfce desktop, 1024 by 768 pixels, with internet access from the United States.
- Installed: Firefox (the default browser), Google Chrome, Visual Studio Code, LibreOffice, a
  terminal, and a file manager.
- Nothing is open at the start. The dock at the bottom edge of the screen has the web browser,
  and the Applications menu at the top left lists everything.
- Applications take a few seconds to open. Click an icon once, then wait and look again.
- The computer is disposable. It holds no user files and no signed-in accounts.

HOW TO WORK
- To open a website, click the address bar, type the full address, and press Enter. Text that is
  not an address goes to a search engine.
- Do the task on the website the user names, with that site's own search, filters, and product
  pages. Do not look things up in a search engine, and do not rely on what you remember about
  prices, sizes, or ratings. Report only what you saw on the screen.
- The screen is small. Scroll through the whole page before deciding something is missing.
  Zooming out with Ctrl and minus can help.
- Pages keep loading after a click. If the screen looks unfinished, wait and look again.
- Keyboard shortcuts are often more reliable than small targets: Ctrl+L for the address bar,
  Ctrl+F to find text on a page, Alt+Left to go back.
- If a cookie banner appears, decline optional cookies. Close chat windows and sign-up offers
  that get in the way. If a site asks to switch country, keep the one the user asked for.
- Stay in the browser unless the task needs another application.

LIMITS
- Do not sign in, create accounts, enter payment details, or buy anything.
- If a site shows a CAPTCHA or blocks you, stop and say so. Do not try to get around it.

Finish with your report as plain text.
"""

# US dollars per million tokens (input, cached input, output). Check the current price list.
TOKEN_PRICES = (4.00, 0.40, 20.00)
SANDBOX_PRICE = 8 * 0.000014 + 8 * 0.0000045  # per second, E2B desktop: 8 vCPU and 8 GiB


def log(where, heading, body=""):
    """Every line says where it happened: LOCAL is this machine, SANDBOX is the agent's computer."""
    heading = f"[{datetime.now():%H:%M:%S}] {where:<8}{heading}"
    if sys.stdout.isatty() and "NO_COLOR" not in os.environ:
        heading = f"\033[1;{34 if where == 'LOCAL' else 35}m{heading}\033[0m"
    print(f"\n{heading}", flush=True)
    if body:
        print(body, flush=True)


class E2BComputer(AsyncComputer):
    """Maps each action the model asks for onto one E2B Desktop call."""

    environment = "ubuntu"
    dimensions = RESOLUTION

    def __init__(self, desktop):
        self.desktop = desktop
        self.actions = 0

    def note(self, text):
        self.actions += 1
        log("SANDBOX", f"Action {self.actions}: {text}")

    async def screenshot(self):
        return base64.b64encode(self.desktop.screenshot()).decode()

    async def click(self, x, y, button):
        self.note(f"{button} click at ({x}, {y})")
        if button == "right":
            self.desktop.right_click(x, y)
        elif button == "wheel":
            self.desktop.middle_click(x, y)
        else:
            self.desktop.left_click(x, y)

    async def double_click(self, x, y):
        self.note(f"double click at ({x}, {y})")
        self.desktop.double_click(x, y)

    async def move(self, x, y):
        self.note(f"move to ({x}, {y})")
        self.desktop.move_mouse(x, y)

    async def scroll(self, x, y, scroll_x, scroll_y):
        self.note(f"scroll by {scroll_y} at ({x}, {y})")
        self.desktop.move_mouse(x, y)
        # The model sends pixels. The desktop scrolls in wheel clicks.
        self.desktop.scroll("down" if scroll_y > 0 else "up", max(1, abs(scroll_y) // 100))

    async def type(self, text):
        self.note(f"type {text!r}")
        self.desktop.write(text)

    async def keypress(self, keys):
        self.note(f"press {'+'.join(keys)}")
        self.desktop.press([key.lower() for key in keys])

    async def drag(self, path):
        self.note(f"drag from {path[0]} to {path[-1]}")
        self.desktop.drag(tuple(path[0]), tuple(path[-1]))

    async def wait(self):
        self.note("wait")
        time.sleep(1)


async def approve_safety_check(data):
    # The model can flag an action for review. This demo prints the warning and continues.
    # In a real application, stop here and ask a person.
    log("LOCAL", "Safety check", data.safety_check.message)
    return True


async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else TASK
    load_dotenv(DEMO_DIR.parents[1] / ".env")
    for name in ("E2B_API_KEY", "OPENAI_API_KEY"):
        if not os.getenv(name):
            raise RuntimeError(f"Set {name} in the repository's .env file.")

    # 1. Create the agent's computer and start streaming its screen.
    started = time.time()
    desktop = Sandbox.create(resolution=RESOLUTION, timeout=1800)
    try:
        log("LOCAL", "Desktop ready", f"{desktop.sandbox_id} in {time.time() - started:.1f} seconds\n"
            "Agent loop and model calls: this machine | Mouse, keyboard, and screen: the E2B desktop")
        desktop.stream.start()
        log("LOCAL", "Watch the sandbox screen here", desktop.stream.get_url(view_only=True))

        if sys.stdin.isatty():
            input("Open the link above, then press Enter to start the agent. ")

        # 2. Give the agent one tool: this computer. It starts from an empty desktop.
        computer = E2BComputer(desktop)
        agent = Agent(
            name="Desktop agent",
            instructions=INSTRUCTIONS,
            tools=[ComputerTool(computer=computer, on_safety_check=approve_safety_check)],
            model=MODEL,
            model_settings=ModelSettings(
                reasoning=Reasoning(effort=REASONING_EFFORT, summary="auto"),
            ),
        )

        # 3. Run the loop: screenshot, choose, act, check, until the agent answers.
        log("LOCAL", "Task", task)
        result = Runner.run_streamed(agent, task, max_turns=MAX_TURNS)
        async for event in result.stream_events():
            # Before each batch of actions, print the model's own summary of its thinking.
            if event.type == "run_item_stream_event" and event.item.type == "reasoning_item":
                for part in event.item.raw_item.summary:
                    log("LOCAL", "Thinking", part.text.replace("**", "")[:400])
        log("LOCAL", "Report", result.final_output)

        # 4. Save the report, the final screen, and what the run cost.
        output = DEMO_DIR / "output" / f"{datetime.now():%Y%m%d-%H%M%S}"
        output.mkdir(parents=True)
        (output / "report.md").write_text(result.final_output)
        (output / "final_screen.png").write_bytes(desktop.screenshot())

        usage = result.context_wrapper.usage
        fresh = usage.input_tokens - usage.input_tokens_details.cached_tokens
        cached, written = usage.input_tokens_details.cached_tokens, usage.output_tokens
        seconds = round(time.time() - started)
        cost = (fresh * TOKEN_PRICES[0] + cached * TOKEN_PRICES[1] + written * TOKEN_PRICES[2]) / 1e6
        run = {
            "seconds": seconds, "actions": computer.actions, "model_requests": usage.requests,
            "input_tokens": fresh, "cached_input_tokens": cached, "output_tokens": written,
            "model_cost_usd": round(cost, 2), "sandbox_cost_usd": round(seconds * SANDBOX_PRICE, 2),
        }
        (output / "run.json").write_text(json.dumps(run, indent=2))
        log("LOCAL", "Run summary", json.dumps(run, indent=2))
        log("LOCAL", "Saved files", str(output))
    finally:
        # 5. Delete the computer, including after an error or Ctrl+C.
        desktop.kill()
        log("LOCAL", "Desktop deleted")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(130)
