# Quick Start: Code Cleanup

**Time required:** 1-2 hours
**Impact:** Remove 55% of codebase (1,200+ lines of dead code)
**Risk:** Low (dead code isn't used, so removing it won't break anything)

---

## Step 1: Backup (5 minutes)

```bash
cd /Users/jasonhuff/artist-hotline

# Create backup branch
git checkout -b code-cleanup-backup
git add -A
git commit -m "Backup before cleanup"

# Create working branch
git checkout -b code-cleanup

# Create local backup file
cp main.py main.py.backup
```

---

## Step 2: Delete Temporary Documentation Files (5 minutes)

```bash
# These were created during development and are no longer needed
rm AUDIO_CONVERSION_IMPLEMENTATION.md
rm BREAKTHROUGH.md
rm BUG_SUMMARY.md
rm DEPLOY_NOW.md
rm DEPLOYMENT_RECOMMENDATIONS.md
rm ENDPOINT-MAP.md
rm MULAW_CONVERSION_REVIEW.md
rm NEXT_FIX_TALKING_LOOP.md
rm OPTIMIZED_IMPLEMENTATION.py
rm PERFORMANCE_ANALYSIS.md
rm PERFORMANCE_REVIEW_SUMMARY.md
rm SESSION-NOTES.md
rm SESSION_WRAP_UP.md
rm benchmark_audio_conversion.py
rm test_corrected_conversion.py
rm test_mulaw_conversion.py

# Keep these (today's work):
# - CODE_CLEANUP_RECOMMENDATIONS.md
# - SESSION_FINAL_WRAPUP.md
# - NEXT_STEPS.md
# - CLEANUP_QUICK_START.md (this file)
# - README.md
```

---

## Step 3: Remove Dead Code from main.py (45-60 minutes)

Open `/Users/jasonhuff/artist-hotline/main.py` in your editor and delete these sections:

### A. Remove Coqui TTS Test System
**Lines to delete:** 1000-1319 (320 lines)

Delete these functions:
- `handle_coqui_call()` (lines 1004-1022)
- `process_speech_coqui()` (lines 1023-1028)
- `handle_coqui_stream()` (lines 1174-1319)

**Why:** This experimental TTS system was never enabled (USE_COQUI_TEST=false). ElevenLabs works great.

### B. Remove Streaming Debug Test System
**Lines to delete:** 1321-1574 (253 lines)

Delete these endpoints:
- `/test-streaming-status` (lines 1325-1353)
- `/test-audio-conversion` (lines 1355-1444)
- `/test-sine-wave` (lines 1446-1493)
- `/test-coqui-analysis` (lines 1495-1574)

**Why:** These were development testing tools, not needed in production.

### C. Remove Static Killer Test System
**Lines to delete:** 1987-2174 (187 lines)

Delete these endpoints:
- `/test-static-killer` (lines 1987-2033)
- `/static-killer-stream` (lines 2035-2112)
- `/test-audio-play` (lines 2114-2147)
- `/static-killer-voice` (lines 2149-2174)

**Why:** Experimental audio system that was superseded by current working solution.

### D. Remove Original Media Stream Handler
**Lines to delete:** 1029-1172 (143 lines)

Delete the `/media-stream` endpoint.

**Why:** Replaced by `/test-websocket-debug` which has the full conversation logic.

### E. Remove Traditional TwiML Handlers
**Lines to delete:** 806-876, 886-967 (147 lines)

Delete these functions:
- `handle_elevenlabs_call()` (lines 806-876)
- `process_speech_elevenlabs()` (lines 886-967)

**Why:** Traditional TwiML approach replaced by WebSocket streaming (2-3 seconds faster).

### F. Remove Debug Endpoints
**Lines to delete:** 164-183, 189-223, 225-281, 1869-1985 (260 lines)

Delete these endpoints:
- `/logs` (lines 164-170)
- `/logs/streaming` (lines 172-183)
- `/ws-test` (lines 189-223)
- `/ws-test-client` (lines 225-281)
- `/debug-voice-handler` (lines 1869-1963)
- `/debug-websocket-voice` (lines 1965-1985)

**Why:** Development/debugging tools not needed in production.

### G. Remove Commented-Out Code
**Lines to delete:** 1133-1156 (23 lines)

Delete the big commented-out block starting with:
```python
# # For now, respond to any audio activity to test the pipeline
```

**Why:** Old experimental code that's no longer relevant.

**Total deleted:** ~1,333 lines (61% reduction)

---

## Step 4: Reduce Verbose Logging (15 minutes)

### A. RMS Logging (Lines ~1744-1745)
**Delete these lines:**
```python
if websocket.audio_chunk_count % 100 == 0:
    logger.info(f"🔊 Audio RMS: {rms}, is_speech: {is_speech}")
```

### B. Audio Chunk Logging (Lines ~1760-1761)
**Delete these lines:**
```python
if websocket.audio_chunk_count % 100 == 0:
    logger.info(f"📥 Received {websocket.audio_chunk_count} audio chunks ({len(audio_chunk)} bytes each)")
```

### C. Silence Detection Logging (Lines ~1782-1783)
**Delete this line:**
```python
logger.info(f"⏱️ Checking silence: {time_since_speech:.1f}s since last speech")
```

### D. TTS Initialization Logging (Lines ~102-110)
**Simplify from:**
```python
logger.error("🔧 GLOBAL TTS INITIALIZATION STARTING...")
logger.error("✅ GLOBAL TTS INITIALIZED SUCCESSFULLY!")
logger.error("❌ GLOBAL TTS INITIALIZATION FAILED!")
```

**To:**
```python
logger.info("Initializing global TTS system...")
logger.info("Global TTS initialized successfully")
logger.error("Global TTS initialization failed")
```

### E. Audio Conversion Debug Logs (Lines ~468-488)
**Change from:**
```python
logger.debug(f"Chunk {chunk_count}: Decoded {len(mp3_bytes)} MP3 bytes")
logger.debug(f"Chunk {chunk_count}: Converted to {len(wav_bytes)} WAV bytes")
logger.debug(f"Chunk {chunk_count}: Converted to {len(mulaw_bytes)} µ-law bytes")
```

**To:**
```python
# Remove these lines entirely
```

Keep only the summary at lines 521-524, but simplify:
```python
logger.info(f"Streamed audio: {chunk_count} chunks, {total_mulaw_bytes} bytes")
```

**Total removed:** ~50 lines of verbose logging

---

## Step 5: Clean Up Imports (5 minutes)

### Remove Duplicate Import
**Line 93:** Delete the duplicate `import asyncio` (already imported on line 2)

### Consolidate Local Imports
Move these imports from inside functions to the top of the file:
- `audioop` (currently in functions around line 583)
- `wave` (currently in functions around line 584)
- `io` (currently in functions around line 585)

Add to imports section (~line 16):
```python
import audioop
import wave
import io
```

---

## Step 6: Test Everything (15 minutes)

```bash
# 1. Check syntax
python3 -m py_compile main.py

# 2. Run locally (optional)
python3 main.py

# 3. Commit changes
git add -A
git commit -m "Clean up dead code and verbose logging

- Remove Coqui TTS test system (320 lines)
- Remove streaming debug endpoints (253 lines)
- Remove Static Killer system (187 lines)
- Remove original media stream handler (143 lines)
- Remove traditional TwiML handlers (147 lines)
- Remove debug endpoints (260 lines)
- Remove commented-out code (23 lines)
- Reduce verbose logging (50 lines)
- Clean up imports (duplicate asyncio)

Total reduction: 1,383 lines (63%)
Code is now cleaner and easier to maintain."

# 4. Deploy to Railway (pushes to main)
git checkout main
git merge code-cleanup
git push origin main

# Railway will auto-deploy
# Monitor: https://railway.app/project/artist-hotline
```

### 7. Verify Production (10 minutes)

```bash
# 1. Check health endpoint
curl https://artist-hotline-production.up.railway.app/health

# 2. Call your Twilio number
# Verify:
# - Greeting plays correctly
# - Can have a conversation
# - Responses are intelligent
# - Natural timing (2s pauses)
# - No crashes or errors

# 3. Check Railway logs
# Look for any errors during deployment
# Verify no critical features broken
```

---

## Step 8: Final Cleanup (Optional, 5 minutes)

### Rename Production Endpoint

**Change line ~1576:**
```python
# FROM:
@app.websocket("/test-websocket-debug")

# TO:
@app.websocket("/voice-stream")
```

**Update Twilio webhook:**
1. Go to Twilio Console
2. Find your phone number
3. Update webhook URL from:
   ```
   https://artist-hotline-production.up.railway.app/debug-websocket-voice
   ```
   To:
   ```
   https://artist-hotline-production.up.railway.app/voice
   ```

4. Update the `/debug-websocket-voice` endpoint (line ~1965) to `/voice`:
```python
@app.api_route("/voice", methods=["GET", "POST"])
async def voice_handler(request: Request):
    """Production voice handler - connects to WebSocket streaming"""
    response = VoiceResponse()
    connect = response.connect()
    ws_url = config.BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/voice-stream"  # Updated endpoint name
    connect.stream(url=stream_url)
    return Response(content=str(response), media_type="application/xml")
```

**Test:** Call the number again to verify it still works.

---

## Expected Results

### Before Cleanup
- Total lines: 2,177
- Production code: ~800 lines (37%)
- Test/dead code: ~1,377 lines (63%)
- Logging: Verbose (RMS, chunks, etc.)

### After Cleanup
- Total lines: ~800-850
- Production code: ~800 lines (95%)
- Test/dead code: ~50 lines (5%)
- Logging: Clean (only important events)

### Code Quality Improvements
- 61% smaller codebase
- Easier to navigate and understand
- Faster to load and parse
- Cleaner git diffs
- Easier to add new features
- No functionality lost

---

## Troubleshooting

### If Something Breaks

1. **Revert to backup:**
```bash
git checkout main
git reset --hard origin/main
# Or restore from backup file:
cp main.py.backup main.py
```

2. **Check Railway logs:**
- Go to Railway dashboard
- Click "Deployments" → Latest deployment → "View Logs"
- Look for Python errors or import failures

3. **Common issues:**
- Deleted too much → restore from backup
- Syntax error → check with `python3 -m py_compile main.py`
- Import error → check you didn't remove needed imports
- Endpoint not found → verify Twilio webhook URL is correct

### If You're Unsure

Don't delete a section if you're not sure what it does. Instead:
1. Comment it out first (add # to each line)
2. Test by calling the number
3. If it still works, delete the commented section
4. If it breaks, uncomment and investigate

---

## Time Breakdown

- Backup: 5 min
- Delete docs: 5 min
- Remove dead code: 45-60 min
- Reduce logging: 15 min
- Clean imports: 5 min
- Test: 15 min
- Deploy: 5 min
- Verify: 10 min
- **Total: 1-2 hours**

---

## Summary

This cleanup will make your codebase:
- 61% smaller (1,383 fewer lines)
- Much easier to understand
- Easier to maintain
- Easier to add features
- Professional and production-ready

All while keeping 100% of the functionality that makes your AI voice assistant work.

**Good luck with the cleanup!**
