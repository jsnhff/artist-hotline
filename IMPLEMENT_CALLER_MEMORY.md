# Quick Guide: Implement Caller Memory (30 minutes)

## What's Already Done ✅

1. ✅ `caller_memory.py` - Complete caller tracking system
2. ✅ `CONVERSATION_IMPROVEMENTS.md` - Full implementation plan
3. ✅ Phone number now passed to WebSocket via custom parameters
4. ✅ Response variety system ready to use

## What's Left to Do (3 simple edits)

### Edit 1: Get phone number in WebSocket (Line ~1694)

**File:** `main.py` line 1694
**Find this:**
```python
elif event == 'start':
    stream_sid = data['start']['streamSid']
    call_sid = data['start']['callSid']
    logger.info(f"WebSocket stream started - Stream: {stream_sid}, Call: {call_sid}")
```

**Replace with:**
```python
elif event == 'start':
    stream_sid = data['start']['streamSid']
    call_sid = data['start']['callSid']

    # Get caller phone number from custom parameters
    custom_params = data['start'].get('customParameters', {})
    phone_number = custom_params.get('phoneNumber', 'unknown')

    logger.info(f"WebSocket stream started - Stream: {stream_sid}, Call: {call_sid}, From: {phone_number}")
```

### Edit 2: Use personalized greeting (Line ~1706-1708)

**File:** `main.py` line 1706-1708
**Find this:**
```python
# Send greeting using ElevenLabs streaming with proper audio conversion
logger.info("🔊 Sending greeting via ElevenLabs streaming")
greeting_message = "Hey! This is Synthetic Jason... I'm basically Jason Huff but weirder and more obsessed with art. What wild idea should we dream up together?"
```

**Replace with:**
```python
# Generate personalized greeting based on caller history
from caller_memory import generate_greeting, update_caller
greeting_message = generate_greeting(phone_number)
logger.info(f"🔊 Sending {'returning caller' if 'back' in greeting_message.lower() else 'first-time'} greeting")
```

### Edit 3: Add response variety to system prompt (Line ~1813-1814)

**File:** `main.py` line 1813-1814
**Find this:**
```python
if not hasattr(websocket, 'conversation_history'):
    websocket.conversation_history = [
        {"role": "system", "content": "You are Synthetic Jason, an AI version of artist Jason Huff. You're weird, obsessed with art, and love discussing creative ideas. Keep responses under 30 words. You already introduced yourself at the start of the call, so don't introduce yourself again - just respond naturally to what the user says."}
    ]
```

**Replace with:**
```python
if not hasattr(websocket, 'conversation_history'):
    from caller_memory import get_response_style_prompt

    # Get dynamic response style to prevent repetitive questions
    style_instruction = get_response_style_prompt()

    base_prompt = "You are Synthetic Jason, an AI version of artist Jason Huff. You're weird, obsessed with art, and love discussing creative ideas. Keep responses under 30 words."
    full_prompt = f"{base_prompt} {style_instruction}"

    websocket.conversation_history = [
        {"role": "system", "content": full_prompt}
    ]
```

### Bonus Edit 4: Save call memory at end (Add after line ~1852)

**File:** `main.py` after the WebSocket conversation loop ends
**Add this before `except WebSocketDisconnect:`:**

```python
# Save caller memory when call ends
if hasattr(websocket, 'phone_number') and websocket.phone_number != 'unknown':
    try:
        from caller_memory import update_caller
        update_caller(websocket.phone_number)
        logger.info(f"📝 Saved call memory for {websocket.phone_number}")
    except Exception as e:
        logger.error(f"Failed to save caller memory: {e}")
```

---

## Testing

**Test 1: First call**
1. Call the number
2. Should hear: "Hey! This is Synthetic Jason... I'm basically Jason Huff..."
3. Have a conversation
4. Note: Check logs to see response variety

**Test 2: Call again immediately**
1. Call again within 5 minutes
2. Should hear: "Oh, you're back already! Forget something?"
3. Personalized returning caller greeting!

**Test 3: Response variety**
1. Have multiple exchanges
2. Notice: Not every response ends with a question
3. Variety in conversation style

---

## Expected Results

### Before (Current):
```
User: "Tell me about AI art"
AI: "AI art is fascinating! What aspect interests you most?"

User: "The ethics of it"
AI: "The ethics are complex! Want to explore that more?"

User: "Sure"
AI: "Great! What ethical concerns do you have?"
```
Every response = question. Gets repetitive! ❌

### After (With improvements):
```
User: "Tell me about AI art"
AI: "AI art is wild! The whole authenticity debate fascinates me."

User: "The ethics of it"
AI: "Oh man, the ethics! It's basically rewiring how we think about authorship and creativity."

User: "Sure"
AI: "Let's brainstorm something! How about an AI-generated piece that credits its training data?"
```
Mixed styles, more natural, less repetitive! ✅

---

## Files Reference

- `caller_memory.py` - All the logic you need
- `caller_memory.json` - Will be created automatically (caller data)
- `main.py` - Make the 3-4 edits above
- `CONVERSATION_IMPROVEMENTS.md` - Full plan with future enhancements

---

## Commit After Testing

```bash
git add main.py caller_memory.json
git commit -m "Integrate caller memory - personalized greetings and response variety"
git push
```

---

## Cost Impact

**$0** - No additional API costs, just file storage!

---

## Future Enhancements (Later)

See `CONVERSATION_IMPROVEMENTS.md` for:
- Topic tracking (remember what you talked about)
- Personality modes (different vibes)
- Memorable moments (callbacks to fun exchanges)
- Redis integration (for scale)

---

**This will make your voice assistant feel WAY more alive!** 🎨✨
