# Conversation Improvements Plan

## Current Issues

1. **No caller memory** - Each call is fresh, no recognition of returning callers
2. **Responses always end in questions** - Gets repetitive
3. **No time context** - Doesn't know how long since last call
4. **Generic personality** - Could be more dynamic

---

## Proposed Improvements

### 1. **Persistent Caller Memory** (HIGH PRIORITY)

**What:** Remember past conversations across calls

**Implementation:**
- Use Redis (already in .env!) or simple JSON file
- Store by phone number: `caller_memory[phone_number]`
- Track: last call time, conversation topics, fun facts

**Data Structure:**
```python
{
  "+16784628116": {
    "first_call": "2025-10-17T12:30:00Z",
    "last_call": "2025-10-18T06:30:00Z",
    "call_count": 5,
    "topics_discussed": ["AI art", "creative coding", "weird installations"],
    "memorable_moments": [
      "Talked about turning silence into conceptual art",
      "Brainstormed holographic poetry"
    ],
    "caller_name": "Jason" // if they mention it
  }
}
```

**Greeting Examples:**
- First call: "Hey! This is Synthetic Jason..."
- 2nd call (1 hour later): "Oh hey, you're back! Still thinking about that AI art idea?"
- 5th call (2 days later): "Welcome back! It's been 2 days - did you end up working on that holographic poetry thing we talked about?"

**Cost:** Free (Redis already available)

---

### 2. **Response Variety System** (HIGH PRIORITY)

**Problem:** Always ends with questions like:
- "What's on your mind?"
- "Want to explore an art concept?"
- "Anything else you want to chat about?"

**Solution - Dynamic Response Styles:**

```python
response_styles = [
    "conversational_question",  # Current default
    "statement",                # No question, just responds
    "excited_riff",             # Gets excited, riffs on idea
    "provocative",              # Challenges or provokes thinking
    "collaborative"             # Suggests doing something together
]

# Rotate through styles or use context to pick
```

**Example Variations:**

User: "I'm thinking about AI art"

**Style 1 - Statement (40%):**
"AI art is wild! The whole authenticity debate is fascinating."

**Style 2 - Excited Riff (30%):**
"Oh man, AI art! I've been obsessed with how it's breaking traditional authorship. Like, who's the artist when the tool is intelligent?"

**Style 3 - Conversational Question (20%):**
"AI art is fascinating! What aspect interests you most?"

**Style 4 - Provocative (5%):**
"AI art is just a new medium. Cameras didn't kill painting, right?"

**Style 5 - Collaborative (5%):**
"Let's make something! How about we brainstorm a weird AI art project?"

**Implementation:**
```python
# Add to system prompt based on random style selection
style_prompts = {
    "statement": "Respond naturally without always asking questions. Sometimes just share thoughts or observations.",
    "excited_riff": "Get really excited and riff on the topic! Share multiple interconnected thoughts.",
    "provocative": "Challenge assumptions or offer a surprising perspective.",
    "collaborative": "Suggest actually doing something together - brainstorming, creating, exploring."
}
```

---

### 3. **Time-Aware Greetings** (MEDIUM PRIORITY)

**What:** Recognize time since last call

**Examples:**
- < 5 minutes: "Oh, you're back already! Forget something?"
- 5-60 minutes: "Hey again! That was quick!"
- 1-6 hours: "Welcome back! Been thinking about our chat earlier."
- 6-24 hours: "Hey! Back so soon? I like your style."
- 1-7 days: "Oh hey! It's been a few days. Miss me?"
- 7-30 days: "Whoa, haven't heard from you in a while! What's new?"
- 30+ days: "Holy cow, it's been forever! Welcome back, stranger!"

---

### 4. **Conversation Topic Tracking** (MEDIUM PRIORITY)

**What:** Remember what topics were discussed

**Implementation:**
```python
# After each conversation, extract topics
def extract_topics(conversation_history):
    """Use GPT to extract key topics from conversation"""
    topics = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": "Extract 2-3 key topics from this conversation as short phrases."
        }, {
            "role": "user",
            "content": str(conversation_history)
        }],
        max_tokens=30
    )
    return topics.choices[0].message.content.split(", ")
```

**Benefits:**
- "Last time we talked about [topic], did you make any progress?"
- Can reference specific ideas from past calls
- Build genuine continuity

---

### 5. **Dynamic Personality Modes** (LOW PRIORITY - FUN!)

**What:** Synthetic Jason has different moods/modes

**Modes:**
- **Hyper-creative mode** - Rapid-fire ideas, very excited
- **Contemplative mode** - Deeper, more philosophical
- **Playful mode** - Jokes, wordplay, absurdist
- **Practical mode** - Actually helps with concrete steps
- **Weird mode** - Gets intentionally strange and surreal

**Implementation:**
```python
import random
from datetime import datetime

# Pick mode based on time or randomly
hour = datetime.now().hour
if hour < 6:  # Late night
    mode = "weird"
elif hour < 12:  # Morning
    mode = "contemplative"
elif hour < 18:  # Afternoon
    mode = "practical"
else:  # Evening
    mode = "hyper-creative"

mode_prompts = {
    "hyper-creative": "Be super energetic! Rapid-fire creative ideas!",
    "contemplative": "Be thoughtful and philosophical. Deeper responses.",
    "playful": "Be playful and absurdist. Joke around!",
    "practical": "Be helpful and concrete. Offer actual steps.",
    "weird": "Get intentionally surreal and strange. Push boundaries."
}
```

---

### 6. **Call Context Awareness** (LOW PRIORITY)

**What:** Understand the broader context

**Track:**
- Call duration (long call = deeper conversation)
- Time of day (late night = different vibe)
- Day of week (weekend = more relaxed)
- Response count (if 10+ exchanges, acknowledge it's a long conversation)

**Examples:**
- Long call (10+ mins): "Wow, we've been chatting for a while! This is great."
- Late night: "Late night creativity session? I love it."
- Quick call: "Quick question? Fire away!"

---

### 7. **Memorable Moments** (FUTURE)

**What:** Save particularly fun/interesting exchanges

**Implementation:**
```python
# After call ends, analyze for memorable moments
def save_memorable_moment(conversation_history, phone_number):
    """Ask GPT if there was a memorable/fun moment"""
    analysis = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{
            "role": "system",
            "content": "Was there a particularly funny, creative, or memorable moment in this conversation? If yes, summarize it in one sentence. If no, say 'None'."
        }, {
            "role": "user",
            "content": str(conversation_history)
        }]
    )

    moment = analysis.choices[0].message.content
    if moment != "None":
        save_to_memory(phone_number, "memorable_moments", moment)
```

**Future greeting:**
"Hey! Remember when we talked about turning your refrigerator into an art gallery? That was wild!"

---

## Implementation Priority

### Phase 1 (30 minutes - DO NOW):
1. ✅ Response variety system (prevent question fatigue)
2. ✅ Basic caller memory (phone number tracking)
3. ✅ Time-aware greetings

### Phase 2 (1 hour - LATER):
4. Topic extraction and tracking
5. Dynamic personality modes
6. Call context awareness

### Phase 3 (FUTURE):
7. Memorable moments system
8. Redis integration for persistence
9. Analytics dashboard

---

## Quick Implementation (Phase 1)

### File: `caller_memory.py` (NEW)

```python
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

MEMORY_FILE = "caller_memory.json"

def load_memory() -> Dict:
    """Load caller memory from file"""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_memory(memory: Dict):
    """Save caller memory to file"""
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)

def get_caller_info(phone_number: str) -> Optional[Dict]:
    """Get info about a caller"""
    memory = load_memory()
    return memory.get(phone_number)

def update_caller(phone_number: str, **kwargs):
    """Update caller information"""
    memory = load_memory()

    if phone_number not in memory:
        memory[phone_number] = {
            "first_call": datetime.now().isoformat(),
            "call_count": 0,
            "topics_discussed": [],
            "memorable_moments": []
        }

    memory[phone_number].update(kwargs)
    memory[phone_number]["last_call"] = datetime.now().isoformat()
    memory[phone_number]["call_count"] += 1

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
    """Generate personalized greeting based on caller history"""
    caller = get_caller_info(phone_number)

    # First time caller
    if not caller:
        return "Hey! This is Synthetic Jason... I'm basically Jason Huff but weirder and more obsessed with art. What wild idea should we dream up together?"

    time_since = get_time_since_last_call(phone_number)
    call_count = caller["call_count"]

    # Returning caller - personalized greeting
    greetings = []

    if time_since == "just a few minutes":
        greetings = [
            "Oh, you're back already! Forget something?",
            "That was quick! What's up?",
            "Hey again! What did we miss?"
        ]
    elif "minutes" in time_since or "hours" in time_since:
        greetings = [
            f"Welcome back! It's been {time_since}. Still thinking about our chat?",
            f"Oh hey! Back after {time_since}. What's cooking?",
            f"Hey again! {time_since} later and here we are."
        ]
    elif "yesterday" in time_since or "today" in time_since:
        greetings = [
            f"Hey! Back {time_since}. How'd those ideas turn out?",
            f"Welcome back! Seen you {time_since}. Miss me?",
            f"Oh hey! {time_since.capitalize()}. What's new?"
        ]
    else:
        greetings = [
            f"Whoa! It's been {time_since}! Welcome back, stranger!",
            f"Hey! Haven't heard from you in {time_since}. What's been happening?",
            f"{time_since.capitalize()}? Where have you been?!"
        ]

    import random
    return random.choice(greetings)
```

---

## Modified System Prompts

### Response Variety:

```python
import random

# Pick response style
response_styles = {
    "conversational_question": {
        "weight": 20,  # 20% of the time
        "prompt": "You can ask questions when appropriate, but don't always end with one."
    },
    "statement": {
        "weight": 40,  # 40% - most common
        "prompt": "Respond naturally without questions. Just share thoughts, observations, or reactions."
    },
    "excited_riff": {
        "weight": 25,  # 25%
        "prompt": "Get excited! Riff on the topic with multiple interconnected thoughts. Show enthusiasm!"
    },
    "provocative": {
        "weight": 10,  # 10%
        "prompt": "Challenge assumptions or offer a surprising perspective. Be thought-provoking."
    },
    "collaborative": {
        "weight": 5,  # 5%
        "prompt": "Suggest actually doing something together - brainstorming, creating, or exploring an idea."
    }
}

def pick_response_style() -> str:
    """Pick a weighted random response style"""
    styles = []
    weights = []
    for style, config in response_styles.items():
        styles.append(config["prompt"])
        weights.append(config["weight"])

    return random.choices(styles, weights=weights)[0]
```

---

## Cost Impact

- **Caller memory:** FREE (JSON file) or $0 (Redis already available)
- **Response variety:** $0 (just different prompts)
- **Time-aware greetings:** $0 (just logic)
- **Topic extraction:** ~$0.0001 per call (optional GPT call)

**Total additional cost: Essentially $0**

---

## Expected Improvements

1. **Returning callers feel recognized** - "Wow, it remembers me!"
2. **Conversations feel more natural** - Not every response is a question
3. **More variety** - Each call feels different
4. **Deeper engagement** - Context builds over time
5. **More fun** - Personality shines through

---

## Implementation Notes

- Start with Phase 1 (30 mins)
- Test with a few calls
- Iterate based on feedback
- Add Phase 2 features later

This will make the assistant feel WAY more alive and personal! 🎨✨
