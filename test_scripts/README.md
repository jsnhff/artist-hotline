# Test Conversation Scripts

Pre-written conversation scripts for testing the call simulator.

## Available Scripts

### `ai_art_discussion.txt`
Tests response variety with deep AI art questions. Should show varied response styles without repetitive questions.

**Expected behavior:**
- Mix of statements, excited riffs, and provocative responses
- 50% should NOT end with questions
- Conversation should feel natural and varied

### `quick_checkin.txt`
Tests short exchanges and filler words. Simulates quick back-and-forth.

**Expected behavior:**
- Filler words should appear for each exchange
- Responses should be concise (under 30 words)
- Should handle brief user inputs well

### `creative_brainstorm.txt`
Tests collaborative and excited response styles. Simulates idea generation.

**Expected behavior:**
- More excited/collaborative responses
- Should riff on ideas
- Build on user's creative suggestions

## Creating Your Own Scripts

Create a `.txt` file with:
- One user message per line
- Lines starting with `#` are comments (ignored)
- Blank lines are ignored

Example:
```
# My custom test script
Hello there
Tell me about your art
That's interesting
```

## Usage

Run a script with:
```bash
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt
```

Or run with specific phone number to test caller memory:
```bash
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt --phone "+15555551234"
```
