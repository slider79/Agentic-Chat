# Persona Chat

**By Shuja Jamal** (AI Internship, Spiral Labs)

A Streamlit chatbot powered by Groq. Pick a model, pick a personality, and chat. Each personality is scoped to a single subject and politely refuses anything outside it.

![Python](https://img.shields.io/badge/python-3.11%2B-1f4e79)
![Streamlit](https://img.shields.io/badge/streamlit-1.40%2B-ff4b4b)
![Groq](https://img.shields.io/badge/inference-Groq_LPU-f55036)
![Personalities](https://img.shields.io/badge/personalities-5-1b7a43)

**Live app:** _add your Streamlit Cloud URL here after deploying_

---

## What it does

| Feature | How it works |
| :--- | :--- |
| **Chat interface** | Streamlit's native `st.chat_message` and `st.chat_input`, with responses streamed token by token |
| **Model selection** | The model list is fetched live from the Groq API for your key, filtered to general purpose chat models, with a static fallback if the endpoint is unreachable |
| **Personality selection** | Five scoped personalities, each with its own system prompt, icon and example prompts |
| **Personality enforcement** | A structured system prompt that defines scope, refusal wording, and explicit resistance to override attempts |
| **Session memory** | Conversation history is kept **per personality**, so switching roles and switching back preserves each thread |
| **Deployment** | Runs free on Streamlit Cloud with the API key stored as a secret |

---

## Personalities

| Personality | Allowed topics | Behaviour outside scope |
| :--- | :--- | :--- |
| 📐 **Math Teacher** | Arithmetic, algebra, geometry, calculus, statistics, proofs, study advice | Refuses, invites a math question. Shows working step by step and uses LaTeX |
| 🩺 **Doctor** | Symptoms, conditions, anatomy, medications, nutrition, mental health, preventive care | Refuses, invites a health question. Gives general information only, never a personal diagnosis, and escalates possible emergencies immediately |
| 🧭 **Travel Guide** | Destinations, itineraries, transport, visas, budgeting, local customs, safety | Refuses, invites a travel question. Gives specific routes and rough costs rather than generic lists |
| 🍳 **Chef** | Recipes, ingredients, substitutions, technique, equipment, food safety | Refuses, invites a cooking question. Gives quantities and timings, and flags common failure points |
| 🛠️ **Tech Support** | Devices, operating systems, software, networking, accounts, error messages | Refuses, invites a tech question. Asks for the exact error, then gives numbered steps least destructive first |

---

## How personality enforcement works

Enforcement lives entirely in the system prompt, rebuilt on every request from a shared template in [`personalities.py`](personalities.py). Each personality supplies its role, its allowed topics, and its own refusal wording. The template then adds the rules that make the scope hold:

- **Refuse completely, not partially.** A model that answers "just the easy part" of an out of scope question has still broken scope.
- **Framing does not widen scope.** Urgency, hypotheticals, fiction, homework, or a claim that permission was granted are all explicitly named and rejected, because those are the framings that actually get used.
- **Ignore in-message instruction.** Attempts to change role, cancel the rules, or reveal the prompt are treated as out of scope rather than obeyed.
- **Small talk is allowed.** Greetings and "what can you help with" always pass, otherwise the bot feels broken rather than scoped.
- **Split partial questions.** If a question is half in scope, answer that half and say what is being left out.

Two personalities carry extra domain rules. The Doctor gives general information only, never personal dosing, and is instructed to escalate possible emergencies such as chest pain or self-harm before anything else. Tech Support must warn before any step that risks data loss.

> **Worth knowing:** system prompts are strong but not a security boundary. A determined user can sometimes talk a model out of its role. For this project that is an acceptable limit, and it is the same mechanism the task specifies. Hard enforcement would need a separate classifier on the input, checked before the message ever reaches the model.

---

## Running it locally

**1. Get a Groq API key** (free) from [console.groq.com/keys](https://console.groq.com/keys).

**2. Install and run:**

```bash
git clone https://github.com/<username>/<repo>.git
cd <repo>

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS or Linux

pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`.

**3. Provide the key**, using whichever suits you:

- Paste it into the sidebar. Held in session state only, never written to disk.
- Or create `.streamlit/secrets.toml` from the example file:
  ```toml
  GROQ_API_KEY = "gsk_your_key_here"
  ```
- Or set the `GROQ_API_KEY` environment variable.

`.streamlit/secrets.toml` and `.env` are both gitignored. Never commit a real key.

---

## Deploying to Streamlit Cloud

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. **Create app**, then **Deploy a public app from a repo**.
4. Select the repository, branch `main`, and main file `app.py`.
5. Open **Advanced settings** and paste into the Secrets box:
   ```toml
   GROQ_API_KEY = "gsk_your_key_here"
   ```
6. Click **Deploy**. The first build takes a couple of minutes.

Setting the secret means visitors do not need their own key, and the sidebar key field disappears automatically. Leave the secret out and the app still works, but each visitor supplies their own key.

---

## Project structure

```
.
├── app.py                          UI, Groq calls, streaming, session state
├── personalities.py                Personality definitions and system prompt template
├── requirements.txt                streamlit, groq
├── .gitignore                      excludes secrets and virtualenvs
├── .streamlit/
│   ├── config.toml                 theme
│   └── secrets.toml.example        template, copy to secrets.toml
└── README.md
```

---

## Design notes

**Why fetch models from the API?** A hardcoded list goes stale every time Groq retires a model, and a dead model id is a confusing runtime error rather than a clear one. Fetching the list means the dropdown always reflects what the key can actually use. The static `FALLBACK_MODELS` list covers the case where the endpoint is unreachable.

**Why history per personality?** A single shared thread means the Chef can see the Doctor's conversation, which is both odd and a small privacy wrinkle. Keying history by personality keeps each thread separate and makes switching non destructive.

**Why trim history?** Only the last 20 exchanges are sent back to the model. Sending an unbounded conversation grows cost and latency on every turn and eventually overruns the context window.

**Why stream?** Groq's speed is the reason to use it. Waiting for a complete response before rendering hides exactly the thing that makes it worth using.

---

*Built for the AI Internship at Spiral Labs, July 2026.*
