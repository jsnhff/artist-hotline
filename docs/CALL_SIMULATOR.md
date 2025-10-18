# Call Simulator - Testing Voice Assistant Logic

A tool to test your voice assistant's conversation logic without making actual phone calls.

## Why Use This?

- **Fast testing** - No need to call your Twilio number repeatedly
- **Debug easily** - See all logs and responses in terminal
- **Test caller memory** - Simulate returning callers with different time gaps
- **Verify response variety** - Check if responses avoid repeated questions
- **Free testing** - Uses OpenAI API directly (pennies per test vs Twilio+ElevenLabs)

## Quick Start

### 1. Interactive Mode (Chat with the AI)

```bash
python call_simulator.py
```

This starts an interactive conversation where you can type messages and see AI responses in real-time.

**Example session:**
```
📞 SIMULATED CALL STARTED
📱 From: +15555551234
👤 First-time caller!

🎤 AI GREETING:
   Hey! This is Synthetic Jason... I'm basically Jason Huff but weirder and more obsessed with art. What wild idea should we dream up together?

💬 CONVERSATION (type 'quit' to end call)

👤 YOU: I'm thinking about AI art
🗣️  Filler word: 'Hmm.' (played instantly)
🤔 Thinking... (generating response)

🎤 AI: AI art is wild! The whole authenticity debate fascinates me.
✅ Response without question (good variety!)

👤 YOU: quit

📞 CALL ENDED
```

### 2. Test Greetings (Verify caller memory)

```bash
python call_simulator.py --test-greetings
```

Shows how greetings change for:
- First-time callers
- Returning callers (with different time gaps)
- Multiple greeting variations

### 3. Run Test Scripts (Automated testing)

```bash
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt
```

Runs a pre-written conversation script to test specific scenarios.

## Features

### ✅ What It Tests

1. **Caller Memory**
   - Personalized greetings based on call history
   - Time-aware greetings ("Oh, you're back already!" vs "It's been 3 days!")
   - Call count tracking

2. **Response Variety**
   - Detects if responses always end with questions
   - Shows response style for each exchange
   - Warns when question marks appear (style variety issue)

3. **Conversation Flow**
   - Filler words (instant acknowledgment)
   - GPT response generation
   - Conversation history management (keeps last 10 messages)

4. **Real API Integration**
   - Uses actual OpenAI GPT-4o-mini API
   - Same prompts and logic as production
   - Tests your actual caller_memory.py functions

### ❌ What It Doesn't Test

- Twilio WebSocket connection
- Audio quality (Whisper transcription, ElevenLabs TTS)
- Network latency
- µ-law audio conversion
- Silence detection (RMS-based)

## Command Line Options

```bash
# Interactive mode with default test number
python call_simulator.py

# Test with specific phone number (for caller memory testing)
python call_simulator.py --phone "+16784628116"

# Test greeting variations
python call_simulator.py --test-greetings

# Run conversation script
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt

# Run script with specific caller
python call_simulator.py --test-conversation test_scripts/quick_checkin.txt --phone "+15555550001"
```

## Test Scenarios

### Scenario 1: First-Time Caller

```bash
# Use a phone number that's not in caller_memory.json
python call_simulator.py --phone "+15555550001"
```

**Expected:**
- Generic greeting: "Hey! This is Synthetic Jason..."
- No mention of "back" or "again"
- Conversation history starts fresh

### Scenario 2: Returning Caller (Immediate)

```bash
# Call with same number twice in a row
python call_simulator.py --phone "+15555550002"
# ... have conversation, then quit

# Immediately call again
python call_simulator.py --phone "+15555550002"
```

**Expected:**
- Personalized greeting: "Oh, you're back already! Forget something?"
- Recognizes it's been just a few minutes
- Caller count incremented

### Scenario 3: Test Response Variety

```bash
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt
```

**Look for:**
- ✅ "Response without question (good variety!)"
- ⚠️ "Response contains question mark" (if variety isn't working)
- At least 50% of responses should NOT have questions

### Scenario 4: Test All Response Styles

Have a longer conversation (10+ exchanges) and check the response styles:
- Should see mix of: statements, excited riffs, provocative, collaborative
- Should NOT see the same style repeated every time

## Creating Test Scripts

Create a `.txt` file in `test_scripts/`:

```txt
# My Test Script
# Lines starting with # are comments

Hello there
I want to talk about art
Tell me more about your process
That's really interesting
What should I try making?
```

Then run:
```bash
python call_simulator.py --test-conversation test_scripts/my_test.txt
```

## Troubleshooting

### "OPENAI_API_KEY environment variable not set!"

Set your OpenAI API key:
```bash
export OPENAI_API_KEY='sk-...'
```

Or add to your `.env` file and load it before running.

### "Response contains question mark" warnings

This means the response variety system isn't working. Check:
1. `caller_memory.py` - Verify `get_response_style_prompt()` weights
2. System prompts should say "DO NOT end with a question" for 50%+ of styles
3. Try running multiple times - 10% of responses are allowed to have questions

### Caller memory not working

Check `caller_memory.json` in your project root:
```bash
cat caller_memory.json
```

Should show phone numbers and call history. If empty or missing, the file will be created on first call.

## Output Explanation

```
🗣️  Filler word: 'Hmm.' (played instantly)
```
Shows which filler word would play immediately when silence detected.

```
🎨 Response style: DO NOT end with a question. Just respond with statements...
```
Shows which response style was randomly selected for this conversation.

```
✅ Response without question (good variety!)
```
Confirms the response doesn't end with `?` (good variety).

```
⚠️  Response contains question mark (style variety may not be working)
```
Warning that response has `?` - may indicate style prompts aren't strong enough.

## Cost

**OpenAI API usage:**
- ~$0.0001-0.0002 per exchange (GPT-4o-mini)
- A 10-exchange test conversation: ~$0.001-0.002
- Much cheaper than actual phone calls with Twilio+ElevenLabs

**vs. Real phone call testing:**
- Twilio: $0.0085/min
- Whisper: $0.006/min
- ElevenLabs: $0.30/1M chars (~$0.01-0.02/min)
- Real call (5 min): ~$0.10-0.15

Simulator saves money and time!

## Integration with Development

Use this during:
1. **Feature development** - Test new conversation logic before deploying
2. **Debugging** - Reproduce issues without phone calls
3. **CI/CD** - Run automated conversation tests (future)
4. **Prompt tuning** - Iterate on response styles quickly

## Next Steps

After testing with simulator:
1. Verify logic works as expected
2. Make any needed adjustments
3. Deploy to production
4. Test with real phone call to verify end-to-end

The simulator helps you catch 90% of issues before touching production!
