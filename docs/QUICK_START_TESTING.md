# Quick Start: Testing Your Voice Assistant

Test your conversation logic in 30 seconds without making a phone call!

## TL;DR

```bash
# Chat with the AI interactively
python call_simulator.py

# Test all greeting variations
python call_simulator.py --test-greetings

# Run a test conversation
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt
```

## What You'll See

```
📞 SIMULATED CALL STARTED
📱 From: +15555551234
👤 First-time caller!

🎤 AI GREETING:
   Hey! This is Synthetic Jason... I'm basically Jason Huff but weirder...

💬 CONVERSATION (type 'quit' to end call)

👤 YOU: I'm thinking about AI art
🗣️  Filler word: 'Hmm.' (played instantly)
🤔 Thinking... (generating response)

🎤 AI: AI art is wild! The whole authenticity debate fascinates me.
✅ Response without question (good variety!)
```

## What It Tests

✅ **Caller Memory** - First-time vs returning caller greetings
✅ **Response Variety** - Checks if responses avoid repeated questions
✅ **Filler Words** - Shows instant acknowledgment
✅ **Conversation Logic** - Same GPT prompts as production
✅ **Response Styles** - See which style was selected (statements, excited, provocative, etc.)

## Common Use Cases

### 1. Quick Logic Check

Before deploying changes:
```bash
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt
```

Look for ✅ "Response without question" - should be ~50%+ of responses.

### 2. Test Caller Memory

First call:
```bash
python call_simulator.py --phone "+15555550001"
# Type a few messages, then quit
```

Immediate callback:
```bash
python call_simulator.py --phone "+15555550001"
# Greeting should say "Oh, you're back already!"
```

### 3. Interactive Debugging

```bash
python call_simulator.py
```

Type your messages and see responses in real-time. Perfect for:
- Testing specific conversation flows
- Debugging prompt issues
- Checking response quality

## Reading the Output

```
🗣️  Filler word: 'Hmm.' (played instantly)
```
→ This word would play immediately when silence detected (1-2s)

```
🎨 Response Style: DO NOT end with a question. Just respond with statements...
```
→ Shows which response style was randomly selected for this conversation

```
✅ Response without question (good variety!)
```
→ Good! Response doesn't end with `?`

```
⚠️  Response contains question mark (style variety may not be working)
```
→ Warning - response has `?`. Should only happen ~10-15% of time.

## Cost

**~$0.001-0.002 per test conversation** (GPT-4o-mini only)

vs. **~$0.10-0.15 per real phone call** (Twilio + Whisper + ElevenLabs)

**100x cheaper testing!**

## Next Steps

1. ✅ Test logic with simulator
2. ✅ Verify everything works as expected
3. ✅ Deploy to production (git push)
4. ✅ Make one real phone call to verify end-to-end

The simulator catches 90% of issues before they hit production!

## Full Documentation

See [CALL_SIMULATOR.md](CALL_SIMULATOR.md) for:
- All command-line options
- Creating custom test scripts
- Troubleshooting
- Advanced testing scenarios
