"""Persona Chat: a Streamlit chatbot powered by Groq.

Users pick a Groq-hosted model and a chatbot personality. Each personality is
scoped to one domain and refuses questions outside it. Conversation history is
kept per personality for the life of the browser session.
"""

from __future__ import annotations

import os

import streamlit as st
from groq import Groq, APIError, AuthenticationError

from personalities import PERSONALITIES, build_system_prompt

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

APP_TITLE = "Persona Chat"
APP_ICON = "💬"

# Used when the models endpoint cannot be reached. Kept deliberately short and
# limited to general-purpose chat models.
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "gemma2-9b-it",
]

# Models served by Groq that are not general-purpose chat models.
NON_CHAT_HINTS = ("whisper", "tts", "guard", "embed", "vision", "prompt-guard")

MAX_HISTORY_TURNS = 20  # user+assistant pairs sent back to the model


st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="centered",
    initial_sidebar_state="expanded",
)


# --------------------------------------------------------------------------
# API key
# --------------------------------------------------------------------------


# The key entered by the user is mirrored into this session_state entry.
#
# It deliberately does NOT match the text_input's own key. Streamlit clears a
# widget's state once that widget stops being rendered, and the input is hidden
# as soon as a key is present, so storing the key under the widget's own key
# would wipe it on the very next rerun.
KEY_STATE = "groq_api_key"
KEY_WIDGET = "api_key_input"


def _remember_typed_key() -> None:
    """Copy the typed key into durable session state."""
    typed = (st.session_state.get(KEY_WIDGET) or "").strip()
    if typed:
        st.session_state[KEY_STATE] = typed


def key_source() -> tuple[str | None, str]:
    """Resolve the Groq API key and report where it came from."""
    if st.session_state.get(KEY_STATE):
        return st.session_state[KEY_STATE], "session"

    try:
        key = st.secrets.get("GROQ_API_KEY")
        if key:
            return str(key), "secrets"
    except Exception:
        # No secrets.toml present; fall through to the environment.
        pass

    env_key = os.environ.get("GROQ_API_KEY")
    if env_key:
        return env_key, "environment"

    return None, "none"


def get_api_key() -> str | None:
    return key_source()[0]


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_models(api_key: str) -> list[str]:
    """Ask Groq which models this key can use, filtered to chat models."""
    client = Groq(api_key=api_key)
    listing = client.models.list()
    ids = [
        m.id
        for m in listing.data
        if not any(hint in m.id.lower() for hint in NON_CHAT_HINTS)
    ]
    # Surface the reliable general-purpose models first.
    preferred = [m for m in FALLBACK_MODELS if m in ids]
    rest = sorted(m for m in ids if m not in preferred)
    return preferred + rest


def available_models(api_key: str | None) -> tuple[list[str], str | None]:
    """Return (models, warning). Falls back to a static list on failure."""
    if not api_key:
        return FALLBACK_MODELS, None
    try:
        models = fetch_models(api_key)
        return (models, None) if models else (FALLBACK_MODELS, "No chat models returned; using defaults.")
    except AuthenticationError:
        return FALLBACK_MODELS, "That API key was rejected by Groq."
    except APIError as exc:
        return FALLBACK_MODELS, f"Could not load the model list ({exc.__class__.__name__}); using defaults."


# --------------------------------------------------------------------------
# Conversation state
# --------------------------------------------------------------------------


def history_for(personality_key: str) -> list[dict]:
    """Get (creating if needed) the message list for one personality."""
    st.session_state.setdefault("histories", {})
    return st.session_state["histories"].setdefault(personality_key, [])


def build_messages(personality, history: list[dict]) -> list[dict]:
    """Assemble the payload: system prompt plus recent conversation."""
    trimmed = history[-(MAX_HISTORY_TURNS * 2):]
    return [{"role": "system", "content": build_system_prompt(personality)}, *trimmed]


# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------

with st.sidebar:
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.caption("A personality-scoped chatbot running on Groq.")

    api_key, source = key_source()

    if not api_key:
        st.subheader("Groq API key")
        st.text_input(
            "Paste your key to begin",
            type="password",
            key=KEY_WIDGET,
            placeholder="gsk_...",
            label_visibility="collapsed",
            on_change=_remember_typed_key,
        )
        st.caption(
            "Free key from [console.groq.com](https://console.groq.com/keys). "
            "Held for this browser session only and never written to disk."
        )
        # Pick up a key typed on this same run.
        _remember_typed_key()
        api_key, source = key_source()
    elif source == "session":
        col_key, col_clear = st.columns([3, 1])
        with col_key:
            st.caption("🔑 Key set for this session.")
        with col_clear:
            if st.button("Clear", use_container_width=True, help="Forget this API key"):
                st.session_state.pop(KEY_STATE, None)
                st.session_state.pop(KEY_WIDGET, None)
                fetch_models.clear()
                st.rerun()
    else:
        st.caption(f"🔑 Key loaded from {source}.")

    st.divider()

    models, model_warning = available_models(api_key)
    if model_warning:
        st.warning(model_warning, icon="⚠️")

    model = st.selectbox(
        "Model",
        models,
        index=0,
        help="Every model here is served by Groq on their LPU hardware.",
    )

    personality_key = st.radio(
        "Personality",
        list(PERSONALITIES),
        format_func=lambda k: f"{PERSONALITIES[k].icon}  {PERSONALITIES[k].name}",
        help="Each personality answers only within its own subject area.",
    )
    personality = PERSONALITIES[personality_key]
    st.caption(personality.tagline)

    with st.expander("Response settings"):
        temperature = st.slider(
            "Temperature", 0.0, 1.5, 0.6, 0.1,
            help="Lower is more focused and repeatable, higher is more varied.",
        )
        max_tokens = st.slider("Max response length (tokens)", 256, 4096, 1024, 256)

    st.divider()

    turns = len(history_for(personality_key)) // 2
    st.caption(f"{turns} exchange{'s' if turns != 1 else ''} with {personality.name} this session.")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Clear chat", use_container_width=True):
            st.session_state.get("histories", {})[personality_key] = []
            st.rerun()
    with col_b:
        if st.button("Clear all", use_container_width=True):
            st.session_state["histories"] = {}
            st.rerun()

    st.divider()
    st.caption(
        "Built by Shuja Jamal for the AI Internship at Spiral Labs. "
        "Conversations live in your browser session and disappear when you close the tab."
    )


# --------------------------------------------------------------------------
# Main pane
# --------------------------------------------------------------------------

st.title(f"{personality.icon} {personality.name}")
st.caption(personality.greeting)

history = history_for(personality_key)

if not api_key:
    st.info("Add a Groq API key in the sidebar to start chatting.", icon="🔑")
    st.stop()

# Replay the conversation for this personality.
for message in history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Example prompts, shown only on an empty conversation.
if not history and personality.examples:
    st.write("")
    st.caption("Try one of these:")
    cols = st.columns(len(personality.examples))
    for col, example in zip(cols, personality.examples):
        with col:
            if st.button(example, use_container_width=True, key=f"ex_{personality_key}_{example}"):
                st.session_state["pending_prompt"] = example
                st.rerun()

prompt = st.chat_input(f"Message {personality.name}…") or st.session_state.pop("pending_prompt", None)

if prompt:
    history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            client = Groq(api_key=api_key)
            stream = client.chat.completions.create(
                model=model,
                messages=build_messages(personality, history),
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            chunks = (
                chunk.choices[0].delta.content or ""
                for chunk in stream
            )
            reply = st.write_stream(chunks)
            history.append({"role": "assistant", "content": reply})

        except AuthenticationError:
            history.pop()
            st.error("Groq rejected that API key. Check it and try again.", icon="🔑")
        except APIError as exc:
            history.pop()
            message = getattr(exc, "message", None) or str(exc)
            st.error(f"Groq returned an error: {message}", icon="⚠️")
        except Exception as exc:  # noqa: BLE001 - surface anything else to the user
            history.pop()
            st.error(f"Something went wrong: {exc}", icon="⚠️")
