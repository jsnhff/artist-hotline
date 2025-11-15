# Quick Reference: Potential Issues from Latency Optimizations

## HIGH PRIORITY - Watch Closely

### 1. Premature Interruptions (Changes #1 + #5)
**Symptoms:**
- Users complain about being cut off mid-sentence
- Conversations feel rushed or choppy
- System responds before user finishes thought

**Root Cause:**
- Silence detection at 1.4s (was 1.9s) + RMS threshold at 70 (was 80)
- Natural pauses trigger response too quickly

**Quick Fix:**
```python
# Line 1826: if time_since_speech >= 1.7:  # Compromise
# Line 1783: is_speech = rms > 75  # Compromise
```

### 2. Background Noise False Positives
**Symptoms:**
- System responds to non-speech sounds
- Transcription of ambient noise
- Unexpected triggers during silence

**Root Cause:**
- RMS threshold too sensitive (70 vs 80)

**Quick Fix:**
```python
# Line 1783: is_speech = rms > 75  # or back to 80
```

## MEDIUM PRIORITY - Monitor

### 3. WebSocket Overload
**Symptoms:**
- Increased disconnection rate
- Audio streaming interruptions
- "Connection closed" errors in logs

**Root Cause:**
- Halved chunk delays might overwhelm slow connections

**Quick Fix:**
```python
# Lines 520, 1640: await asyncio.sleep(0.015)  # Midpoint
```

### 4. Streaming Implementation Errors
**Symptoms:**
- Incomplete GPT responses
- Missing text in responses
- Truncated sentences

**Root Cause:**
- Streaming chunk handling issues

**Monitor:** Check if all chunks properly collected before joining

## MONITORING COMMANDS

```bash
# Check for interruption patterns
grep "Checking silence:" logs.txt | grep -E "[0-9]\.[0-9]s"

# Monitor RMS values
grep "Audio RMS:" logs.txt | awk '{print $4}' | sort -n | uniq -c

# Track WebSocket disconnections
grep -i "websocket.*closed\|disconnect" logs.txt | wc -l

# Check response timings
grep "Time to respond:\|Latency:" logs.txt
```

## ROLLBACK PRIORITIES

If issues arise, rollback in this order:

1. **First:** Revert RMS threshold (Line 1783: back to 80)
2. **Second:** Increase silence detection (Line 1826: back to 1.9)
3. **Third:** Increase chunk delays (Lines 520, 1640: back to 0.02)
4. **Last Resort:** Full git revert

## KEY FILES & LINE NUMBERS

- **Silence Detection:** Lines 1821, 1826
- **RMS Threshold:** Line 1783
- **Whisper API:** Lines 657-662
- **GPT Streaming:** Lines 1913-1927
- **Audio Chunking:** Lines 520, 1640

## SUCCESS METRICS

Good deployment if:
- Latency drops to 3-3.5s (from 4-5s)
- <2% increase in disconnections
- <5 user complaints in first hour
- Transcription accuracy maintained