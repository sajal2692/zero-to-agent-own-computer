"""Demo 3: the same desktop task as demo 2, with the loop written out by hand.

No agent framework. The script calls OpenAI's computer use tool directly and
runs each action on an E2B Desktop: observe, choose, act, check, repeat.
"""

import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from e2b_desktop import Sandbox
from openai import OpenAI

DEMO_DIR = Path(__file__).resolve().parent
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "medium"
RESOLUTION = (1024, 768)
MAX_ROUNDS = 80

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


def act(desktop, action):
    """Run one action the model chose on the desktop."""
    kind = action.type
    if kind == "click":
        clicks = {"right": desktop.right_click, "wheel": desktop.middle_click}
        clicks.get(action.button, desktop.left_click)(action.x, action.y)
    elif kind == "double_click":
        desktop.double_click(action.x, action.y)
    elif kind == "move":
        desktop.move_mouse(action.x, action.y)
    elif kind == "scroll":
        desktop.move_mouse(action.x, action.y)
        # The model sends pixels. The desktop scrolls in wheel clicks.
        desktop.scroll("down" if action.scroll_y > 0 else "up", max(1, abs(action.scroll_y) // 100))
    elif kind == "type":
        desktop.write(action.text)
    elif kind == "keypress":
        desktop.press([key.lower() for key in action.keys])
    elif kind == "drag":
        desktop.drag((action.path[0].x, action.path[0].y), (action.path[-1].x, action.path[-1].y))
    elif kind == "wait":
        time.sleep(1)
    # A "screenshot" action needs nothing here. Every round ends with a fresh screenshot.


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else TASK
    load_dotenv(DEMO_DIR.parents[1] / ".env")
    for name in ("E2B_API_KEY", "OPENAI_API_KEY"):
        if not os.getenv(name):
            raise RuntimeError(f"Set {name} in the repository's .env file.")
    client = OpenAI()

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

        # 2. Send the task. The agent starts from an empty desktop and asks for its first actions.
        log("LOCAL", "Task", task)
        settings = {
            "model": MODEL, "tools": [{"type": "computer"}], "instructions": INSTRUCTIONS,
            "reasoning": {"effort": REASONING_EFFORT, "summary": "auto"},
        }
        response = client.responses.create(input=task, **settings)
        fresh = cached = written = requests = actions = 0

        for _ in range(MAX_ROUNDS):
            requests += 1
            cached += response.usage.input_tokens_details.cached_tokens
            fresh += response.usage.input_tokens - response.usage.input_tokens_details.cached_tokens
            written += response.usage.output_tokens

            # 3. CHOOSE: the model asks for actions. No more actions means it has answered.
            for item in response.output:
                if item.type == "reasoning":  # the model's own summary of its thinking
                    for part in item.summary:
                        log("LOCAL", "Thinking", part.text.replace("**", "")[:400])
            calls = [item for item in response.output if item.type == "computer_call"]
            if not calls:
                break

            outputs = []
            for call in calls:
                # 4. ACT: run each action on the desktop, in order.
                for action in call.actions or [call.action]:
                    actions += 1
                    details = action.model_dump(exclude={"type"}, exclude_none=True)
                    log("SANDBOX", f"Action {actions}: {action.type}", json.dumps(details) if details else "")
                    act(desktop, action)

                # The model can flag an action for review. This demo prints the warning and
                # continues. In a real application, stop here and ask a person.
                checks = call.pending_safety_checks or []
                for check in checks:
                    log("LOCAL", "Safety check", check.message)

                # 5. OBSERVE: take a new screenshot so the model can check the result.
                screenshot = base64.b64encode(desktop.screenshot()).decode()
                outputs.append({
                    "type": "computer_call_output",
                    "call_id": call.call_id,
                    "acknowledged_safety_checks": [check.model_dump() for check in checks],
                    "output": {
                        "type": "computer_screenshot",
                        "image_url": f"data:image/png;base64,{screenshot}",
                    },
                })

            # 6. REPEAT: send the screenshots back and get the next actions.
            response = client.responses.create(
                input=outputs, previous_response_id=response.id, **settings
            )
        else:
            raise RuntimeError(f"The agent did not finish within {MAX_ROUNDS} rounds.")

        log("LOCAL", "Report", response.output_text)

        # 7. Save the report, the final screen, and what the run cost.
        output = DEMO_DIR / "output" / f"{datetime.now():%Y%m%d-%H%M%S}"
        output.mkdir(parents=True)
        (output / "report.md").write_text(response.output_text)
        (output / "final_screen.png").write_bytes(desktop.screenshot())

        seconds = round(time.time() - started)
        cost = (fresh * TOKEN_PRICES[0] + cached * TOKEN_PRICES[1] + written * TOKEN_PRICES[2]) / 1e6
        run = {
            "seconds": seconds, "actions": actions, "model_requests": requests,
            "input_tokens": fresh, "cached_input_tokens": cached, "output_tokens": written,
            "model_cost_usd": round(cost, 2), "sandbox_cost_usd": round(seconds * SANDBOX_PRICE, 2),
        }
        (output / "run.json").write_text(json.dumps(run, indent=2))
        log("LOCAL", "Run summary", json.dumps(run, indent=2))
        log("LOCAL", "Saved files", str(output))
    finally:
        # 8. Delete the computer, including after an error or Ctrl+C.
        desktop.kill()
        log("LOCAL", "Desktop deleted")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
