# Bug Tracker & Known Issues

## Current Issue: Call Hanging Up During Greeting

**Date:** 2025-10-18
**Symptom:** Call disconnects before intro/greeting finishes playing
**User Impact:** Can't complete conversations

### Root Causes Identified

1. **Filler word interfering with greeting**
   - Filler word plays during silence detection
   - May be interrupting the greeting audio stream
   - Need to skip filler words during greeting

2. **last_response_time not updated after greeting**
   - Greeting plays but `last_response_time` not set
   - Silence detection may trigger immediately after
   - Cooldown period not working correctly

3. **greeting_complete flag never set to True**
   - Flag initialized to False at line 1710
   - Never updated after greeting finishes
   - Can't skip silence detection during greeting

4. **No protection against silence detection during TTS**
   - When AI is talking, silence detection still runs
   - Can trigger filler words or new responses mid-speech
   - Need to block silence detection while TTS is playing

### Fix Strategy

1. Set `websocket.last_response_time` AFTER greeting completes
2. Set `websocket.greeting_complete = True` after greeting
3. Skip filler words if greeting not complete
4. Add flag to prevent silence detection during TTS playback

---

## Bug Pattern: Timing and State Management

**Recurring Issue:** Changes to conversation flow break timing
**Why it keeps happening:**
- Multiple places track "last response time"
- Flags like `greeting_complete` initialized but not maintained
- No centralized state management
- Silence detection runs independently of TTS playback state

**Prevention:**
1. Create single source of truth for call state
2. Add state machine for call phases (greeting → listening → responding)
3. Block conflicting operations (no silence detection during TTS)
4. Add comprehensive logging at state transitions

---

## Historical Bugs

### Bug #1: Responses Always End in Questions
**Date:** 2025-10-17
**Cause:** Response variety prompts too weak
**Fix:** Changed from "don't always ask questions" to "DO NOT end with a question"
**Status:** ✅ Fixed

### Bug #2: Junk Phrase Filter Too Aggressive
**Date:** 2025-10-18
**Cause:** Filter included "you", "right", "thank you" - filtered real speech
**Fix:** Only filter standalone filler words (um, uh, hmm)
**Status:** ✅ Fixed

### Bug #3: Call Hangs Up During Greeting
**Date:** 2025-10-18
**Cause:** Multiple issues with timing and state management
**Fix:** Added is_playing_tts flag, greeting_complete state, proper timing
**Status:** ✅ Fixed

### Bug #4: Silence Detection Fires After Disconnect (Race Condition)
**Date:** 2025-10-19
**Cause:** Silence detection task continues running even after user hangs up
**Symptom:** User asks question, hangs up, system generates response to closed connection
**Fix:** Cancel silence_task on disconnect (both 'closed' event and WebSocketDisconnect exception)
**Status:** ✅ Fixed

---

## Testing Checklist (Before Deploying)

After making changes to conversation flow:

- [ ] Test with call simulator first
- [ ] Check all `last_response_time` updates
- [ ] Verify state flags are set/unset properly
- [ ] Test greeting plays completely
- [ ] Test first user message after greeting
- [ ] Test rapid back-and-forth conversation
- [ ] Test long pauses (10+ seconds)
- [ ] Check Railway logs for errors

---

## Known Technical Debt

1. **Multiple timing variables** - `last_response_time`, `last_audio_time`, `greeting_complete`
   - Should consolidate into state machine
   - Hard to track when each should be updated

2. **No centralized call state** - State scattered across websocket attributes
   - `websocket.greeting_complete`
   - `websocket.last_response_time`
   - `websocket.audio_chunk_count`
   - Should create CallState class

3. **Silence detection runs independently** - No awareness of TTS playback
   - Can trigger during AI speech
   - Should block during TTS, only run during listening phase

4. **Error handling incomplete** - Exceptions logged but not recovered
   - If ElevenLabs fails, call might hang
   - Should have fallback TTS or retry logic

---

## Improvement Roadmap

### Phase 1: Fix Current Hangup Issue (NOW)
- [ ] Update `last_response_time` after greeting
- [ ] Set `greeting_complete = True`
- [ ] Skip filler words during greeting
- [ ] Add TTS playback flag

### Phase 2: Better Logging (NEXT)
- [ ] Log all state transitions
- [ ] Log timing of each phase
- [ ] Add request IDs to track individual calls
- [ ] Create debug mode with verbose logging

### Phase 3: State Machine (FUTURE)
- [ ] Create CallState enum (GREETING, LISTENING, PROCESSING, SPEAKING)
- [ ] Centralize state management
- [ ] Block invalid state transitions
- [ ] Clear state change logging

### Phase 4: Better Testing (FUTURE)
- [ ] Add timing tests to simulator
- [ ] Test state transitions
- [ ] Automated regression tests
- [ ] Load testing for concurrent calls

---

## Debug Commands

```bash
# Get recent logs
railway logs --tail 100

# Search for errors
railway logs --tail 500 | grep -i "error\|exception\|failed"

# Check WebSocket connections
railway logs --tail 200 | grep -i "websocket\|stream"

# Test locally with simulator
python call_simulator.py --test-conversation test_scripts/quick_checkin.txt
```

---

## Contact & Debugging Tips

**When a bug happens:**
1. Note the EXACT behavior (what happened, what was expected)
2. Check Railway logs immediately (bugs often clear in logs)
3. Try to reproduce with call simulator
4. Check recent commits - was anything timing-related changed?
5. Look for similar historical bugs in this document

**Good bug report:**
- "Call hung up after 'Banana bread toot' - before I could respond"
- Includes: What you heard, when it disconnected, any error messages

**Bad bug report:**
- "It's broken" - Not enough detail to diagnose
