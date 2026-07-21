"""Headless checks for the app's session behaviour.

Run with:  python tests/test_app.py

These use Streamlit's AppTest harness, which executes app.py in-process and
lets us drive widgets without a browser. The important case is the regression
covered by test_key_survives_a_message: an API key entered by the user must
still be there after sending a prompt.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(ROOT / "app.py")
FAKE_KEY = "gsk_fake_key_for_testing_0000000000000000"

failures: list[str] = []


def check(condition: bool, label: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {label}")
    if not condition:
        failures.append(label)


def start(**session) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    for key, value in session.items():
        at.session_state[key] = value
    return at.run()


def test_prompts_for_key_when_absent() -> None:
    print("\nWithout a key, the app asks for one")
    at = start()
    check(any("API key" in i.value for i in at.info), "shows the 'add a key' notice")
    check(len(at.chat_input) == 0, "hides the chat input")


def test_key_unlocks_the_chat() -> None:
    print("\nWith a key, the chat is available")
    at = start(groq_api_key=FAKE_KEY)
    check(not at.info, "no 'add a key' notice")
    check(len(at.chat_input) == 1, "chat input is present")


def test_key_survives_a_message() -> None:
    """Regression: sending a prompt used to wipe the key and bounce the user
    back to the key screen. The key lived under the text_input's own widget
    key, and Streamlit clears widget state once a widget stops rendering."""
    print("\nRegression: the key survives sending a prompt")
    at = start(groq_api_key=FAKE_KEY)

    at.chat_input[0].set_value("What is the derivative of x squared?").run()

    still_set = "groq_api_key" in at.session_state and at.session_state["groq_api_key"] == FAKE_KEY
    check(still_set, "key is still in session state")
    check(not at.info, "user is NOT bounced back to the key screen")
    check(len(at.chat_input) == 1, "chat input is still available")
    # The fake key is rejected, so an error is the correct outcome here.
    check(bool(at.error), "a clear error is shown instead of failing silently")
    check(not at.exception, "no unhandled exception")


def test_history_is_per_personality() -> None:
    print("\nHistory is kept separately per personality")
    at = start(
        groq_api_key=FAKE_KEY,
        histories={
            "math_teacher": [
                {"role": "user", "content": "what is 2+2"},
                {"role": "assistant", "content": "4"},
            ],
            "chef": [],
        },
    )
    rendered = [m.markdown[0].value for m in at.chat_message if m.markdown]
    check("4" in rendered, "math_teacher thread is replayed")

    at.radio[0].set_value("chef").run()
    rendered = [m.markdown[0].value for m in at.chat_message if m.markdown]
    check("4" not in rendered, "chef does not see the math_teacher thread")
    check(
        at.session_state["histories"]["math_teacher"][1]["content"] == "4",
        "math_teacher thread is preserved after switching away",
    )


def test_every_personality_builds_a_prompt() -> None:
    print("\nEvery personality produces a usable system prompt")
    from personalities import PERSONALITIES, build_system_prompt

    for key, personality in PERSONALITIES.items():
        prompt = build_system_prompt(personality)
        ok = (
            personality.name in prompt
            and personality.allowed[:40] in prompt
            and "ONLY discuss" in prompt
            and "{" not in prompt  # every placeholder was substituted
        )
        check(ok, f"{key}: scope, refusal and rules present")


if __name__ == "__main__":
    for test in (
        test_prompts_for_key_when_absent,
        test_key_unlocks_the_chat,
        test_key_survives_a_message,
        test_history_is_per_personality,
        test_every_personality_builds_a_prompt,
    ):
        test()

    print()
    if failures:
        print(f"{len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print("All checks passed.")
