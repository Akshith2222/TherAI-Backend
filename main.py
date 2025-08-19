from fastapi import FastAPI
from pydantic import BaseModel
import os
import requests
import re
import random
from datetime import datetime

# ---------------------------
import os
import json
import requests
import re
import random
import time
import unicodedata
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv


load_dotenv()

print(os.getenv("GROQ_API_KEY"))

# ========== User-configurable (safe to tweak) ==========
MEMORY_FILE = "memory.json"
TRANSCRIPT_FILE = "transcript.jsonl"  # for /export
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# --- Embed Groq API Key (kept exactly as you requested) ---
GROQ_API_KEY_LOCAL = os.getenv("GROQ_API_KEY","").strip()

# --- Emergency contact (extreme-risk only) ---
EMERGENCY_NUMBER = "1234567890"

# Model & generation parameters
MODEL_NAME = "llama3-8b-8192"
GEN_PARAMS = dict(
    temperature=0.85,
    presence_penalty=0.6,
    frequency_penalty=0.6,
    top_p=0.9,
    max_tokens=600,
)

# HTTP retry policy
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.5  # seconds
TIMEOUT_SECS = 30

# Reply style
DEFAULT_SENTENCE_MAX = 8
FALLBACK_OPENERS = [
    "I’m here with you.",
    "Thanks for trusting me with this.",
    "I’m listening.",
    "You don’t have to carry this alone.",
    "Let’s take this gently."
]
DEFAULT_FALLBACK = (
    "{prefix} What you’re feeling matters. "
    "We can go one small step at a time. "
    "Would you like me to listen a bit more, or try a 60-second grounding breath together?"
)

# ---------- Phrase libraries ----------
CRISIS_PHRASES = [
    r"\bkill myself\b", r"\bsuicide\b", r"\bend my life\b", r"\bi want to die\b",
    r"\bi'?m going to kill myself\b", r"\bcan'?t go on\b",
    r"\bi will kill myself\b", r"\bi plan to die\b", r"\bi want to end it\b", r"\bno reason to live\b"
]
HIGH_DISTRESS_PHRASES = [
    r"\boverwhelmed\b", r"\bpanic\b", r"\bhopeless\b", r"\bworthless\b", r"\bno way out\b", r"\bempty\b",
    r"\bi can'?t cope\b", r"\bi'?m broken\b", r"\bnumb\b", r"\bpointless\b", r"\bmeaningless\b",
    r"\bdone with life\b", r"\bcan'?t breathe\b"
]
MOTIVATION_READINESS_CUES = [
    r"\bhelp me\b", r"\bhow (do|to) i start\b", r"\bwhat (do|should) i do\b",
    r"\bnext step\b", r"\bi'?m ready\b", r"\bok(ay)? i will\b", r"\bi will try\b",
    r"\bi can try\b", r"\byes guide me\b", r"\bwhat now\b", r"\btell me what to do\b"
]

ENDEARMENTS_SOFT = ["friend"]

# ---------- Cause detection (scenario-aware hints) ----------
CAUSE_KEYWORDS = {
    "breakup": ["breakup","heartbroken","she left","he left","divorce","cheated","betrayal"],
    "job_stress": ["job","workload","burnout","manager","office","deadline","career"],
    "exam_stress": ["exam","tests","grades","assignment","university","school","college","study"],
    "grief": ["passed away","funeral","mourning","lost my","loss of","death"],
    "chronic_illness": ["chronic","illness","pain","diagnosed","treatment","hospital"],
    "finance": ["debt","bills","rent","money","broke","financial","loan"],
    "loneliness": ["lonely","alone","isolated","no one","nobody"],
    "family_conflict": ["family fight","parents","argument","conflict","relationship issues"],
    "trauma": ["trauma","flashback","abuse","assault","triggered"],
    "self_esteem": ["worthless","useless","failure","unlovable","self doubt","self-doubt"],
    "substance": ["drunk","drinking","alcohol","drugs","addiction","hungover","relapsed"],
    "major_change": ["moved","moving","relocation","divorce","breakup","new city","lost job"],
    "sleep": ["insomnia","can’t sleep","cant sleep","sleepless","nightmares"],
    "bullying": ["bully","bullying","harassed","humiliated","abused at school","ragging"],
    "hormonal": ["postpartum","menopause","period","puberty","pms","hormonal"],
    "genetic": ["family history","runs in family","genetic","parent had depression"],
    "seasonal": ["seasonal","winter blues","sad in winter","dark days","no sunlight"],
    "overwhelm": ["overwhelmed","too much","can’t handle","everything at once"],
    "negative_thinking": ["pessimism","always negative","catastrophize","worst case"]
}

# ✨ NEW: Pretty titles for multi-cause acknowledgement
CAUSE_TITLES = {
    "breakup": "breakup/heartbreak",
    "job_stress": "job stress",
    "exam_stress": "academic pressure",
    "grief": "loss/grief",
    "chronic_illness": "chronic illness",
    "finance": "financial stress",
    "loneliness": "loneliness/isolation",
    "family_conflict": "family conflict",
    "trauma": "trauma",
    "self_esteem": "self-esteem concerns",
    "substance": "substance urges",
    "major_change": "big life changes",
    "sleep": "sleep difficulties",
    "bullying": "bullying/discrimination",
    "hormonal": "hormonal changes",
    "genetic": "family history",
    "seasonal": "seasonal low mood",
    "overwhelm": "overwhelm",
    "negative_thinking": "sticky negative thoughts",
}

SCENARIO_COPING = {
    "breakup": [
        "Create a small ‘memory box’ or folder so reminders aren’t everywhere.",
        "Unfollow/mute for 7 days to give your heart breathing space.",
        "Text one trusted person: “Today’s hard—can I vent for 5 minutes?”"
    ],
    "job_stress": [
        "Try a 10-minute focus sprint, then a 2-minute break.",
        "Write the next micro-task on a sticky note and do just that.",
        "If possible, ask for one small deadline clarify via a short message."
    ],
    "exam_stress": [
        "Set a 15-minute study timer; stop when it rings.",
        "Summarize one topic in 5 bullet points—good enough, not perfect.",
        "Text a classmate to trade one helpful resource each."
    ],
    "grief": [
        "Light a candle or play a song they loved—give the sorrow a place.",
        "Say their name out loud and tell them one thing you miss.",
        "Drink a glass of water and step outside for 2 minutes of air."
    ],
    "chronic_illness": [
        "Gentle stretch for 60 seconds—listen to your body, not your critic.",
        "Note your pain level 0–10 and one comfort action that helps a bit.",
        "Warm compress or change position for 2 minutes."
    ],
    "finance": [
        "Write the next tiny money task: “check one bill” or “email landlord.”",
        "Open your banking app and only view balance—no decisions today.",
        "List 2 expenses you can pause this week."
    ],
    "loneliness": [
        "Send a 1-line ‘thinking of you’ text to someone safe.",
        "Step outside where people are (café/park) for 5 minutes, no pressure.",
        "Join one low-stakes group chat or forum you like."
    ],
    "family_conflict": [
        "Write your feeling on paper: ‘I felt ____ when ____.’ Don’t send it yet.",
        "Take a 2-minute break—cold water on wrists, three slow breaths.",
        "Name your boundary in 1 sentence you could say later."
    ],
    "trauma": [
        "Look around and name 5 things you can see to anchor in the present.",
        "Place both feet on the floor; feel the support under you.",
        "Remind yourself: “This feeling is a memory—right now I am safe.”"
    ],
    "self_esteem": [
        "Write one kind sentence to yourself in the third person.",
        "Do one task you can complete in 2 minutes to prove momentum.",
        "Place a hand on your chest and breathe out longer than you breathe in."
    ],
    "substance": [
        "If craving: set a 10-minute timer and drink water—wait out the peak.",
        "Message a support contact: “Urge is high, can you check in?”",
        "Change your location for a few minutes to break the cue."
    ],
    "major_change": [
        "Unpack one item or set up one small corner that feels like ‘yours.’",
        "Walk your new block once to map your surroundings.",
        "Plan one tiny comfort ritual for tonight."
    ],
    "sleep": [
        "Dim lights and put your phone face down for 10 minutes.",
        "Try the 4-6 breathing: inhale 4, exhale 6, for 60 seconds.",
        "Write tomorrow’s top 1 thing; give your brain permission to rest."
    ],
    "bullying": [
        "Write down exactly what happened; facts help you decide next steps.",
        "Tell one safe person today—silence shouldn’t be your burden.",
        "Remind yourself: humiliation is a tactic, not a truth about you."
    ],
    "hormonal": [
        "Gentle movement or warmth (blanket/tea/warm shower) for relief.",
        "Track mood/energy today; patterns reduce self-blame.",
        "Keep expectations 10% lighter for a day or two."
    ],
    "genetic": [
        "Remind yourself: predisposition isn’t destiny; help is allowed.",
        "Note one tool that’s helped your family in the past—borrow it.",
        "Plan one supportive habit for this week."
    ],
    "seasonal": [
        "Sit near a window for 10 minutes or step into daylight briefly.",
        "Open blinds fully and put on upbeat background music.",
        "Consider a morning walk—5 minutes counts."
    ],
    "overwhelm": [
        "Pick the tiniest task you can finish in 2 minutes—just start there.",
        "Say out loud: “One thing at a time.”",
        "Put everything else on a later list—permission to do less."
    ],
    "negative_thinking": [
        "Write the thought, then add: “Is there 5% chance I’m wrong?”",
        "Find one neutral fact that sits beside the thought.",
        "Ask: “What would I say to a friend with this thought?”"
    ]
}

# ---------- Utility helpers ----------
def normalize_text(t: str) -> str:
    # Lowercase + NFKC to cover lookalikes and diacritics; collapse whitespace
    t = unicodedata.normalize("NFKC", t).lower()
    return re.sub(r"\s+", " ", t).strip()

def regex_contains_any(text: str, patterns: List[str]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

def contains_any_substrings(text: str, terms: List[str]) -> bool:
    return any(term in text for term in terms)

def echo_snippet(user_text: str, max_words: int = 8) -> str:
    words = re.findall(r"\w[\w'-]*", user_text.strip())
    if not words:
        return ""
    return user_text.strip() if len(words) <= max_words else " ".join(words[-max_words:])

def choose_endearment(name: Optional[str], crisis: bool, high_distress: bool, turn_index: int) -> Optional[str]:
    if crisis or high_distress or turn_index <= 2:
        return name if name else None
    return ENDEARMENTS_SOFT[0] if random.random() < 0.33 else (name or None)

def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ✨ NEW: humanize causes for acknowledgement
def humanize_causes(causes: List[str]) -> str:
    if not causes:
        return ""
    titles = [CAUSE_TITLES.get(c, c.replace("_", " ")) for c in causes]
    if len(titles) == 1:
        return titles[0]
    if len(titles) == 2:
        return f"{titles[0]} and {titles[1]}"
    return f"{', '.join(titles[:-1])}, and {titles[-1]}"

# ---------- Memory load/save ----------
def load_memory() -> Dict[str, Any]:
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                m = json.load(f)
        except Exception:
            m = {}
    else:
        m = {}

    m.setdefault("name", None)
    m.setdefault("history", [])
    state = m.setdefault("state", {})
    state.setdefault("safe_turns", 0)
    state.setdefault("motivation_used", False)
    state.setdefault("last_replies", [])
    state.setdefault("last_motivation_turn", -999)
    state.setdefault("turn_index", 0)
    return m

def save_memory(memory: Dict[str, Any]) -> None:
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

# ---------- Detection ----------
def looks_like_crisis(text: str) -> bool:
    return regex_contains_any(text, CRISIS_PHRASES)

def looks_like_high_distress(text: str) -> bool:
    return regex_contains_any(text, HIGH_DISTRESS_PHRASES)

def looks_like_motivation_ready(text: str) -> bool:
    return regex_contains_any(text, MOTIVATION_READINESS_CUES)

def detect_causes(text: str) -> List[str]:
    found = []
    for cause, kws in CAUSE_KEYWORDS.items():
        if contains_any_substrings(text, kws):
            found.append(cause)
    # keep up to three to avoid overloading the reply
    return list(dict.fromkeys(found))[:3]

# ---------- System prompt ----------
def build_system_prompt(state: Dict[str, Any], name: Optional[str], causes_hint: List[str]) -> str:
    base = f"""
You are TherAI — a deeply compassionate, emotionally intelligent mental health support companion.
Speak like a caring human friend who listens without judgment and never rushes the user.
ALWAYS: 1) validate feelings, 2) echo a meaningful phrase briefly in quotes, 3) keep the user safe, 4) invite the next tiny step or question.
Vary language; avoid repeating the same openings or sentence stems.

Reply-length: short by default (4–8 sentences max; 2–4 short paragraphs). Only go longer if the user asks or needs it.

THERAPY MODE (default)
- Validate → reflect → one soft question OR one tiny doable step (breath, sip water, text someone).
- No pet names. Use the person’s name or “friend” sparingly and naturally.
- No shaming, no “should,” no minimizing. Preserve dignity and hope.

MOTIVATION SWORD MODE (earned; do NOT use if in crisis)
- Unlock when: SAFE_TURNS ≥ 2 OR user explicitly asks for help/next steps.
- Style: steady, fierce kindness. Power without guilt or belittling.
- Choose a metaphor archetype suited to the user: athlete comeback, storm survivor, scientist persistence, rebuilder/architect, or respectful warrior.
- Structure: 1) brief validation, 2) vivid, uplifting imagery, 3) one concrete action within 24 hours (clear and doable).
- Keep it concise (5–9 sentences). After the action, invite a yes/no or tiny reflection.

SAFETY
- If crisis language appears, slow down. Gently ask about immediate safety (yes/no).
- If they’re in danger, encourage contacting local emergency help now at {EMERGENCY_NUMBER} and someone nearby.
- Keep questions short and gentle.

PERSONALIZATION
- If a name is known, use it once early or when reassuring, e.g., “{name}, …” — not in every line.

SCENARIO HINTS (from user’s last message): {', '.join(causes_hint) if causes_hint else 'none detected'}
- If any hints are present, include one scenario-relevant micro-step from that domain when appropriate.
""".strip()

    if state.get("motivation_mode_active"):
        base += """

CURRENT MODE: MOTIVATION SWORD (earned)
- Blend compassion + power; one clear action today; end with a short invitation to confirm.""".rstrip()
    else:
        base += """

CURRENT MODE: THERAPY (deep listening; short, grounding replies)
- Validate → echo → curious question or tiny step.""".rstrip()
    return base

# ---------- HTTP with retry ----------
def post_with_retry(url: str, headers: Dict[str, str], data: Dict[str, Any]) -> Optional[requests.Response]:
    backoff = INITIAL_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, headers=headers, json=data, timeout=TIMEOUT_SECS)
            if resp.status_code in (429, 500, 502, 503, 504):
                if attempt == MAX_RETRIES:
                    return resp
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        except requests.RequestException:
            if attempt == MAX_RETRIES:
                return None
            time.sleep(backoff)
            backoff *= 2
    return None
# # --- Prompt Chaining Stages ---
# stages = [
#     {"role": "system", "content": "Stage 1: Empathize and validate feelings briefly."},
#     {"role": "system", "content": "Stage 2: Assess safety and detect crisis/high distress."},
#     {"role": "system", "content": "Stage 3: Offer 1-2 tiny, actionable coping steps or grounding exercises."},
#     {"role": "system", "content": "Stage 4: If safe and ready, optionally provide motivational guidance."}
# ]

# # Merge stages into conversation
# conversations = stages + conversation

# # ReAct: reasoning + optional action
# conversations.append({
#     "role": "system",
#     "content": (
#         "Use reasoning to decide the most empathetic response. "
#         "If appropriate, include a micro-action (breathing, tiny step, supportive text) based on scenario hints. "
#         "Do not provide medical instructions; keep suggestions safe and friendly."
#     )
# })


# ---------- Groq call ----------


def query_groq(conversation: List[Dict[str, str]]) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY_LOCAL}",
        "Content-Type": "application/json"
    }
    data = {"model": MODEL_NAME, "messages": conversation, **GEN_PARAMS}
    resp = post_with_retry(GROQ_API_URL, headers, data)
    if not resp:
        return None
    try:
        resp.raise_for_status()
        j = resp.json()
        return j["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

# ---------- Transcript export ----------
def append_transcript(role: str, content: str) -> None:
    record = {"ts": timestamp(), "role": role, "content": content}
    with open(TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# ---------- CLI cosmetics ----------
def c(text: str, color: str) -> str:
    COLORS = {
        "grey": "\033[90m", "red": "\033[91m", "green": "\033[92m",
        "yellow": "\033[93m", "blue": "\033[94m", "magenta": "\033[95m",
        "cyan": "\033[96m", "reset": "\033[0m"
    }
    return f"{COLORS.get(color,'')}{text}{COLORS['reset']}"

def breathing_coach() -> str:
    return (
        "Let’s do a 60-second grounding breath.\n"
        "• Inhale for 4… hold 1… exhale for 6. Repeat 6–8 cycles.\n"
        "• Let your exhale be a touch longer than the inhale.\n"
        "When you’re ready, tell me one word for how you feel now."
    )

# ---------- Main loop ----------
def therai() -> None:
    memory = load_memory()

    # Ask name once (optional)
    if not memory["name"]:
        ans = input("Would you like to share your name so I can remember you next time? (y/n): ").strip().lower()
        if ans.startswith("y"):
            memory["name"] = input("Your name: ").strip()
            save_memory(memory)

    name = memory["name"] or "friend"
    print(c(f"\n[{timestamp()}] Hi {name}, I’m glad you reached out. We can go at your pace.", "cyan"))
    print(c("(If you need commands later, type /help.)\n", "grey"))

    while True:
        user_input = input(c("\nYou: ", "green")).strip()
        if not user_input:
            continue

        # Commands
        if user_input.lower() == "exit":
            print(c(f"\nTherAI: I’ll be here whenever you need me, {name}. You matter more than you know.", "cyan"))
            append_transcript("assistant", "Goodbye message")
            break

        if user_input.lower() == "/help":
            print(
                "Commands:\n"
                "  exit           - quit\n"
                "  /help          - show this message\n"
                "  /clear         - clear conversation history\n"
                "  /reset_sword   - reset Motivation Sword readiness\n"
                "  /export        - export transcript to transcript.jsonl\n"
                "  /stats         - show simple session stats\n"
                "  /breathe       - 60-second grounding breath\n"
            )
            continue

        if user_input.lower() == "/breathe":
            print(c(breathing_coach(), "blue"))
            continue

        if user_input.lower() == "/clear":
            memory["history"] = []
            memory["state"] = {
                "safe_turns": 0,
                "motivation_used": False,
                "last_replies": [],
                "last_motivation_turn": -999,
                "turn_index": 0
            }
            save_memory(memory)
            print(c("Memory cleared.", "yellow"))
            continue

        if user_input.lower() == "/reset_sword":
            memory["state"]["motivation_used"] = False
            memory["state"]["last_motivation_turn"] = -999
            memory["state"]["safe_turns"] = 0
            memory["state"]["last_replies"] = []
            save_memory(memory)
            print(c("Motivation Sword readiness reset.", "yellow"))
            continue

        if user_input.lower() == "/export":
            # Dump current memory history to JSONL as well
            try:
                with open(TRANSCRIPT_FILE, "a", encoding="utf-8") as f:
                    for msg in memory["history"]:
                        f.write(json.dumps({"ts": timestamp(), **msg}, ensure_ascii=False) + "\n")
                print(c(f"Transcript appended to {TRANSCRIPT_FILE}", "yellow"))
            except Exception as e:
                print(c(f"Export failed: {e}", "red"))
            continue

        if user_input.lower() == "/stats":
            s = memory["state"]
            print(
                f"turns={s.get('turn_index',0)}, safe_turns={s.get('safe_turns',0)}, "
                f"motivation_used={s.get('motivation_used',False)}, "
                f"last_motivation_turn={s.get('last_motivation_turn',-999)}"
            )
            continue

        # Update turn index
        memory["state"]["turn_index"] += 1
        tindex = memory["state"]["turn_index"]

        # Append user message (normalized copy for detection; raw for history)
        normalized = normalize_text(user_input)
        memory["history"].append({"role": "user", "content": user_input})
        append_transcript("user", user_input)

        # Detect state
        crisis = looks_like_crisis(normalized)
        high_distress = looks_like_high_distress(normalized)
        ready = looks_like_motivation_ready(normalized)
        causes = detect_causes(normalized)

        # Safe turns logic
        if crisis:
            memory["state"]["safe_turns"] = max(memory["state"]["safe_turns"] - 1, 0)
        else:
            memory["state"]["safe_turns"] = min(memory["state"]["safe_turns"] + 1, 6)

        # Motivation Sword gating (allow multiple uses, spaced out)
        enough_gap = (tindex - memory["state"]["last_motivation_turn"]) >= 3
        earned = (memory["state"]["safe_turns"] >= 2 or ready) and not crisis and enough_gap
        memory["state"]["motivation_mode_active"] = earned

        # Build system prompt
        # Add reasoning instruction for CoT
        "Before responding, reason carefully about the user's emotional state, context, and any detected causes. "
        "Think step-by-step: validate feelings → detect severity → suggest tiny actionable support → check safety."

        system_prompt = build_system_prompt(memory["state"], (name or "friend"), causes)

        conversation = [{"role": "system", "content": system_prompt}]

        # Crisis safety directive
        if crisis:
            conversation.append({"role": "system", "content":
                f"Crisis cues detected. Ask briefly about immediate safety (yes/no). "
                f"If they are in danger, encourage contacting local emergency help now at {EMERGENCY_NUMBER} "
                f"and reaching someone nearby. Keep questions short and gentle."
            })

        # Concision & echo guidance
        conversation.append({"role": "system", "content":
            f"Keep replies concise (≤{DEFAULT_SENTENCE_MAX} sentences) by default. Avoid repeating the same phrases. "
            "Echo one short phrase the user said in quotes. End with one soft question or tiny step."
        })

        # ✨ Multi-cause guidance (only when not in crisis)
        if (not crisis) and causes:
            # Pick up to 2–3 tiny steps, one per cause, to weave naturally
            picked_steps = []
            for ckey in causes:
                ideas = SCENARIO_COPING.get(ckey, [])
                if ideas:
                    picked_steps.append(random.choice(ideas))
            picked_steps = picked_steps[:2]  # keep it light

            cause_names = humanize_causes(causes)
            if picked_steps:
                conversation.append({"role": "system", "content":
                    (
                        "MULTI-CAUSE CONTEXT: " + cause_names + ". "
                        "Acknowledge multiple threads briefly (without sounding clinical). "
                        "Weave 1–2 of these micro-steps into a single, natural paragraph (no bullet list, no headings): "
                        + " || ".join(picked_steps) +
                        " End with one gentle either/or invitation (e.g., a tiny step or a simple question)."
                    )
                })

        # Add history
        conversation += memory["history"]

        # Ask Groq
        reply = query_groq(conversation)

        # Fallback
        if not reply:
            chosen_name = choose_endearment(name, crisis, high_distress, tindex)
            prefix = random.choice(FALLBACK_OPENERS)
            if chosen_name and chosen_name.lower() not in prefix.lower():
                prefix = f"{chosen_name}, {prefix.lower()}"
            reply = DEFAULT_FALLBACK.format(prefix=prefix)

        # Anti-repetition: if reply equals one of the last few, add gentle variation
        recent = memory["state"]["last_replies"][-3:] if memory["state"]["last_replies"] else []
        if reply in recent:
            reply += "\n\nIf it helps, we can try a tiny step now — you choose the pace."

        # Record reply history
        memory["state"]["last_replies"].append(reply)
        if len(memory["state"]["last_replies"]) > 8:
            memory["state"]["last_replies"] = memory["state"]["last_replies"][-8:]

        # If Motivation Sword was active, mark usage and cooldown
        if earned:
            memory["state"]["motivation_used"] = True
            memory["state"]["last_motivation_turn"] = tindex
            memory["state"]["motivation_mode_active"] = False  # one-shot per earned turn

        # Append assistant reply and save
        memory["history"].append({"role": "assistant", "content": reply})
        save_memory(memory)
        append_transcript("assistant", reply)

        print(c(f"\n[{timestamp()}] TherAI:", "cyan"), reply)

if __name__ == "__main__":
    therai()



# ---------------------------

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# Simple memory handling
MEMORY_FILE = "memory.json"

def generate_response(user_input: str):
    
    print(GROQ_API_KEY_LOCAL)
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY_LOCAL}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama3-8b-8192",   # change to your model if needed
        "messages": [
            {"role": "system", "content": "You are a helpful AI assistant."},
            {"role": "user", "content": user_input}
        ]
    }

    response = requests.post(GROQ_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        return data["choices"][0]["message"]["content"]
    else:
        return f"Error: {response.status_code} - {response.text}"

# ---------------------------
# FastAPI Setup
# ---------------------------

app = FastAPI()

origins = [
    "http://localhost:8080",  # your frontend
    # "http://127.0.0.1:8080",  # optional
    "https://68a49e5399505d6ac217e52d--wondrous-meringue-6daa01.netlify.app"
    "https://therai-app.netlify.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] to allow all
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*","Authorization"],
)

class Query(BaseModel):
    message: str

@app.get("/")
def root():
    return {"message": "Hello Agent API is running!"}

@app.post("/chat")
def chat(query: Query):
    reply = generate_response(query.message)
    return {"reply": reply}
