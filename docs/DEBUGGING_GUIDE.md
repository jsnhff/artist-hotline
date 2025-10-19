# Professional Debugging Guide

## Overview

This guide provides comprehensive debugging tools and procedures to prevent recurring bugs and quickly diagnose issues.

## Tools Available

### 1. Call Tracer (`debug_tracer.py`)

**Purpose:** Track individual calls through their lifecycle with state validation

**Features:**
- Unique call ID tracking
- State machine with validation (prevents invalid transitions)
- Performance metrics
- Structured logging with context
- Automatic error detection

**Usage in Production:**
```python
from debug_tracer import create_tracer, CallState

# Create tracer at call start
tracer = create_tracer(call_sid, phone_number, stream_sid)

# Transition states with validation
tracer.transition(CallState.GREETING, reason="starting greeting")

# Log events with context
tracer.log_event("greeting_complete", duration=5.2)

# Measure performance
tracer.measure("greeting_duration", start_time)

# Check state before operations
if tracer.check_state(CallState.LISTENING, "play filler word"):
    # Safe to play filler word
    pass

# Check if disconnected before operations
if not tracer.is_disconnected():
    # Safe to send audio
    pass
```

**States:**
- `CONNECTING` → `GREETING` → `LISTENING` → `PROCESSING` → `SPEAKING` → `LISTENING` (loop)
- Can go to `ERROR` or `DISCONNECTING` from most states
- `DISCONNECTED` is terminal (no operations after this)

**Benefits:**
- Catches invalid state transitions (e.g., trying to speak while disconnected)
- Traces individual calls through logs
- Performance metrics automatic
- Print summary at end of call

---

### 2. Log Analyzer (`log_analyzer.py`)

**Purpose:** Parse Railway logs to find patterns, issues, and trace calls

**Usage:**
```bash
# General analysis
railway logs --tail 500 | python log_analyzer.py

# Find all errors
railway logs --tail 1000 | python log_analyzer.py --find-errors

# Track specific call
railway logs --tail 500 | python log_analyzer.py --call-sid CA1234567...

# Performance metrics
railway logs --tail 500 | python log_analyzer.py --performance
```

**What It Finds:**
- **Race conditions** - Operations after disconnect
- **Audio errors** - FFmpeg conversion failures
- **State errors** - Invalid state transitions
- **WebSocket issues** - Connection problems
- **Timing issues** - Delays and bottlenecks

**Example Output:**
```
LOG ANALYSIS REPORT
============================================================

Total Entries: 423
Unique Calls: 5
Errors: 3
Warnings: 12

❌ ERRORS (3):
  [23:13:30] Failed to convert audio chunk 3: Decoding failed...
  [23:13:20] Twilio WebSocket not connected, skipping chunk

🔍 ISSUES FOUND:

Race Conditions: 2
  [23:13:20] Silence detected after disconnect - skipping
  [23:13:21] Playing TTS to disconnected websocket

Audio Errors: 1
  [23:13:30] FFmpeg conversion failed for chunk 3
```

---

### 3. Call Simulator (`call_simulator.py`)

**Purpose:** Test conversation logic without phone calls

**Limitations:** Does NOT test:
- Audio conversion (Whisper, ElevenLabs, FFmpeg)
- WebSocket state management
- Timing issues
- Real Twilio integration

**Use For:**
- Testing GPT prompts
- Verifying caller memory
- Checking response variety
- Quick conversation flow tests

**NOT for debugging:**
- Hangups
- Audio quality issues
- Timing problems
- WebSocket errors

---

## Common Issues and How to Debug

### Issue 1: Call Hangs Up Unexpectedly

**Steps:**
1. Get the call SID from user or recent calls
2. Analyze logs:
   ```bash
   railway logs --tail 500 | python log_analyzer.py --call-sid CA...
   ```
3. Look for:
   - State transitions (did it reach DISCONNECTING properly?)
   - Errors before disconnect
   - Timing (how long was the call?)

**Common Causes:**
- Operations after disconnect (race condition)
- Audio conversion failure
- WebSocket closed unexpectedly

**Prevention:**
- Always check `tracer.is_disconnected()` before operations
- Use state checks before audio operations
- Set TTS flags to block interference

---

### Issue 2: Audio Cutting Out or Distorted

**Steps:**
1. Check logs for FFmpeg errors:
   ```bash
   railway logs --tail 500 | grep -i "ffmpeg\|audio.*error"
   ```
2. Look for "Failed to convert audio chunk"
3. Check if chunks are being skipped

**Common Causes:**
- FFmpeg conversion errors (partial MP3 chunks)
- WebSocket disconnected mid-stream
- Buffer size issues

**Debug:**
- Add logging around audio conversion
- Check chunk sizes
- Verify MP3 stream is complete before conversion

---

### Issue 3: Silence Detection Fires During TTS

**Steps:**
1. Check if `is_playing_tts` flag is set
2. Look for "⏸️ Skipping silence detection" logs
3. Verify state transitions

**Prevention:**
```python
# Before playing TTS
websocket.is_playing_tts = True

try:
    await stream_speech_to_twilio(text, websocket, stream_sid)
finally:
    websocket.is_playing_tts = False  # ALWAYS reset, even on error
```

---

### Issue 4: Greeting Not Playing Completely

**Debug Process:**
1. Check if `greeting_complete` flag is set:
   ```bash
   railway logs --tail 200 | grep "greeting_complete\|Greeting complete"
   ```
2. Look for silence detection during greeting
3. Check `last_response_time` is updated

**Prevention:**
- Set `greeting_complete = True` after greeting
- Update `last_response_time` after greeting
- Block silence detection until greeting complete

---

## Debugging Workflow

### When Bug Occurs

1. **Note exact behavior**
   - What happened?
   - What was expected?
   - Any error messages?

2. **Check Railway logs immediately**
   ```bash
   railway logs --tail 500 > debug_$(date +%Y%m%d_%H%M%S).log
   ```

3. **Analyze logs**
   ```bash
   cat debug_*.log | python log_analyzer.py --find-errors
   ```

4. **Check for known patterns**
   - Review `docs/BUG_TRACKER.md`
   - Look for similar historical bugs
   - Check if it matches known issue types

5. **Try to reproduce**
   - Can you make it happen again?
   - Is it consistent or intermittent?
   - Does it happen with specific actions?

6. **Create minimal test case**
   - What's the simplest way to trigger it?
   - Can call_simulator reproduce it? (if logic issue)
   - Need real phone call? (if timing/audio issue)

---

## Before Deploying Changes

**Always run this checklist:**

- [ ] Test with call_simulator (if conversation logic changed)
- [ ] Verify all state flags are set/unset properly
- [ ] Check `last_response_time` updates
- [ ] Ensure `is_playing_tts` flag usage
- [ ] Add logging for new state transitions
- [ ] Review recent bugs in BUG_TRACKER.md
- [ ] Check for similar past issues
- [ ] Test locally if possible
- [ ] Make ONE test call after deploy
- [ ] Check Railway logs immediately after

---

## Integration with Main Code

### Adding Call Tracing to WebSocket Handler

```python
# At WebSocket start
from debug_tracer import create_tracer, CallState, remove_tracer

tracer = create_tracer(call_sid, phone_number, stream_sid)

try:
    # Greeting phase
    tracer.transition(CallState.GREETING)
    greeting_start = time.time()
    await stream_speech_to_twilio(greeting, websocket, stream_sid)
    tracer.measure("greeting_duration", greeting_start)
    tracer.transition(CallState.LISTENING)

    # Main loop
    while True:
        # Before processing
        if tracer.is_disconnected():
            break

        tracer.transition(CallState.PROCESSING)
        # ... transcribe, GPT call ...

        tracer.transition(CallState.SPEAKING)
        # ... TTS ...

        tracer.transition(CallState.LISTENING)

except Exception as e:
    tracer.log_error("websocket_error", str(e))
    tracer.transition(CallState.ERROR)

finally:
    tracer.transition(CallState.DISCONNECTING)
    tracer.transition(CallState.DISCONNECTED)
    remove_tracer(call_sid)  # Prints summary
```

---

## Real Issues From Recent Logs

### Found: Race Condition After Disconnect

**Log Evidence:**
```
23:13:19 - WebSocket disconnected
23:13:20 - Silence detected, transcribing audio...
23:13:21 - Twilio WebSocket not connected, skipping chunk
```

**Problem:** Silence detection task still running after disconnect

**Solution:**
- Check `tracer.is_disconnected()` before operations
- Cancel silence detection tasks on disconnect
- Block operations if websocket state is DISCONNECTED

### Found: FFmpeg Conversion Errors

**Log Evidence:**
```
ERROR - Failed to convert audio chunk 3: Decoding failed. ffmpeg returned error code: 1
[mp3 @ 0x...] Invalid frame size (418): Could not seek to 418.
```

**Problem:** Partial MP3 chunks from ElevenLabs streaming

**Solution:**
- Buffer complete frames before conversion
- Add retry logic for partial chunks
- Validate MP3 stream before FFmpeg

---

## Performance Monitoring

### Key Metrics to Track

1. **Greeting Duration** - Should be < 8s
2. **Transcription Time** - Whisper should be < 2s
3. **GPT Response Time** - Should be < 2s
4. **TTS Streaming Time** - ElevenLabs should start within 1s
5. **Total Response Time** - User message to AI response should be < 6s

### Measuring:
```python
tracer.measure("greeting_duration", greeting_start)
tracer.measure("transcription_time", transcribe_start)
tracer.measure("gpt_time", gpt_start)
tracer.measure("tts_time", tts_start)
```

At end of call, `tracer.summary()` includes all metrics.

---

## Quick Reference

### Debug Commands

```bash
# Get recent logs
railway logs --tail 200

# Analyze for issues
railway logs --tail 500 | python log_analyzer.py

# Track specific call
railway logs --tail 500 | python log_analyzer.py --call-sid CA...

# Find errors only
railway logs --tail 1000 | python log_analyzer.py --find-errors

# Test conversation logic
python call_simulator.py

# Test with script
python call_simulator.py --test-conversation test_scripts/ai_art_discussion.txt
```

### State Checks

```python
# Before any operation
if tracer.is_disconnected():
    logger.warning("Skipping operation - call disconnected")
    return

# Before specific operations
if not tracer.check_state(CallState.LISTENING, "play filler word"):
    return  # Error already logged

# Transition with validation
if not tracer.transition(CallState.SPEAKING):
    # Invalid transition, error logged
    return
```

---

## Future Improvements

1. **Real-time dashboard** - Web UI showing active calls and states
2. **Automated regression tests** - Run on every deploy
3. **Performance alerts** - Notify if metrics exceed thresholds
4. **Call replay** - Reproduce exact call sequence from logs
5. **Integration tests** - Test actual WebSocket + audio pipeline

See `docs/BUG_TRACKER.md` for full improvement roadmap.
