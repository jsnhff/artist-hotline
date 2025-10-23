"""
Caller memory system for persistent conversation context across calls.

Tracks:
- Call history (first call, last call, count)
- Time since last call
- Topics discussed (future)
- Memorable moments (future)
"""

import json
import os
import random
from datetime import datetime
from typing import Dict, List, Optional

MEMORY_FILE = "caller_memory.json"


def load_memory() -> Dict:
    """Load caller memory from file"""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_memory(memory: Dict):
    """Save caller memory to file"""
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)


def get_caller_info(phone_number: str) -> Optional[Dict]:
    """Get info about a caller"""
    memory = load_memory()
    return memory.get(phone_number)


def update_caller(phone_number: str, topics: List[str] = None):
    """Update caller information after a call"""
    memory = load_memory()

    if phone_number not in memory:
        memory[phone_number] = {
            "first_call": datetime.now().isoformat(),
            "call_count": 0,
            "topics_discussed": [],
            "memorable_moments": []
        }

    memory[phone_number]["last_call"] = datetime.now().isoformat()
    memory[phone_number]["call_count"] += 1

    if topics:
        # Add new topics, keep unique
        existing_topics = set(memory[phone_number].get("topics_discussed", []))
        existing_topics.update(topics)
        memory[phone_number]["topics_discussed"] = list(existing_topics)[:10]  # Keep last 10

    save_memory(memory)
    return memory[phone_number]


def get_time_since_last_call(phone_number: str) -> Optional[str]:
    """Get human-readable time since last call"""
    caller = get_caller_info(phone_number)
    if not caller or "last_call" not in caller:
        return None

    last_call = datetime.fromisoformat(caller["last_call"])
    diff = datetime.now() - last_call

    minutes = diff.total_seconds() / 60
    hours = minutes / 60
    days = hours / 24

    if minutes < 5:
        return "just a few minutes"
    elif minutes < 60:
        return f"{int(minutes)} minutes"
    elif hours < 6:
        return f"{int(hours)} hours"
    elif hours < 24:
        return "earlier today"
    elif days < 2:
        return "yesterday"
    elif days < 7:
        return f"{int(days)} days"
    elif days < 30:
        return "a few weeks"
    else:
        return "over a month"


def generate_greeting(phone_number: str) -> str:
    """
    Generate personalized greeting based on caller history.

    Returns appropriate greeting based on:
    - Whether this is first call or returning caller
    - How long since last call
    - Number of previous calls
    """
    caller = get_caller_info(phone_number)

    # First time caller
    if not caller:
        return "Hey! This is Synthetic Jason, an AI version of artist Jason Huff. I can talk about your art projects, creative ideas, AI art, internet culture, whatever's on your mind. Fair warning: I'm a bit slow to respond since I'm thinking things through. So what are you working on?"

    time_since = get_time_since_last_call(phone_number)
    call_count = caller["call_count"]

    # Returning caller - personalized greeting based on time elapsed
    greetings = []

    if time_since == "just a few minutes":
        greetings = [
            "Oh, you're back already! Forget something?",
            "That was quick! What's up?",
            "Hey again! What did we miss?"
        ]
    elif "minutes" in time_since:
        # On early calls, remind about response time
        if call_count <= 2:
            greetings = [
                f"Welcome back! It's been {time_since}. Remember I'm slow to respond but I'm thinking. What's on your mind?",
                f"Oh hey! Back after {time_since}. Still takes me a bit to respond, but I'm here. What are you working on?",
            ]
        else:
            greetings = [
                f"Welcome back! It's been {time_since}. Still thinking about our chat?",
                f"Oh hey! Back after {time_since}. What's cooking?",
                f"Hey again! {time_since} later and here we are."
            ]
    elif "hours" in time_since:
        greetings = [
            f"Hey! It's been {time_since}. Back for more creative chaos?",
            f"Welcome back! {time_since} later. What's on your mind?",
            f"Oh hey! {time_since} since we last talked. Miss me?"
        ]
    elif "today" in time_since or "yesterday" in time_since:
        greetings = [
            f"Hey! Back {time_since}. How'd those ideas turn out?",
            f"Welcome back! Seen you {time_since}. What's new?",
            f"Oh hey! {time_since.capitalize()}. Ready for more weird art talk?"
        ]
    elif "days" in time_since:
        greetings = [
            f"Whoa! It's been {time_since}! Welcome back!",
            f"Hey! Haven't heard from you in {time_since}. What's been happening?",
            f"{time_since.capitalize()} already? Time flies! What's up?"
        ]
    else:  # weeks or month+
        greetings = [
            f"Holy cow, it's been {time_since}! Welcome back, stranger!",
            f"Whoa! {time_since}?! Where have you been?!",
            f"Hey! {time_since.capitalize()} is way too long! What's new?"
        ]

    return random.choice(greetings)


def get_response_style_prompt() -> str:
    """
    Get a weighted random response style prompt to vary conversation patterns.

    Balances between statements and questions for natural, engaging conversation.
    """
    response_styles = [
        # Thoughtful exploration with clarifying questions
        ("Ask a clarifying question to dig deeper into their thinking. Be curious and engaged.", 25),

        # Build on their idea collaboratively
        ("Build on their idea! Add your own thoughts and ask how they see it developing further.", 20),

        # Bold statements that spark discussion
        ("Make a bold statement or observation. Challenge their assumptions in an exciting way.", 20),

        # Excited enthusiasm with questions
        ("Get super excited about what they said! Ask them to elaborate or share more.", 15),

        # Reflective response with deeper thinking
        ("Take a moment to think deeper about what they said. Share an insight and invite their perspective.", 10),

        # Just react naturally - no question
        ("Respond naturally with your thoughts and reactions. No need to ask a question.", 10),
    ]

    prompts, weights = zip(*response_styles)
    return random.choices(prompts, weights=weights)[0]


def get_filler_word() -> str:
    """
    Get a quick filler word to play immediately when silence is detected.

    This makes the response feel instant (1s filler + 3-4s for real response = feels faster!)
    """
    filler_words = [
        "Hmm.",
        "Oh!",
        "Yeah.",
        "Right.",
        "Okay.",
        "Interesting.",
        "Totally.",
        "For sure.",
        "I hear you.",
        "Mmhmm.",
    ]
    return random.choice(filler_words)
