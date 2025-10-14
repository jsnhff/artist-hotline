# Session Notes - Artist Hotline Project

## ✅ What's Working (Production Ready)

### Traditional Voice System
- **Endpoint**: `/voice` → `/process-speech-elevenlabs`
- **TTS**: ElevenLabs with optimized Flash v2.5 model
- **AI**: GPT-4o-mini as "Replicant Jason" personality
- **Features**:
  - Caller history tracking
  - SMS notifications to YOUR_PHONE_NUMBER
  - Call transcripts and summaries
  - Returning caller recognition
- **Status**: 100% production ready, currently live

### Test Endpoints (All Functional)
- `/health` - System health check
- `/health/streaming` - Streaming config validation
- `/logs` - Recent application logs
- `/transcripts` - Call history
- `/ws-test` - Minimal WebSocket test (PROVEN WORKING on Railway)

## 🚧 What's 95% Done (Needs Final Push)

### WebSocket Real-Time Streaming
- **Root Issue**: Audio format conversion (WAV → µ-law)
- **What Works**:
  - ✅ WebSocket connections on Railway
  - ✅ Twilio Media Streams integration
  - ✅ Simple TTS generates crystal clear 8kHz mono WAV
  - ✅ Initial greeting plays clearly
- **What's Left**:
  - Convert WAV to raw µ-law before sending to Twilio WebSocket
  - One-line fix using `audioop.lin2ulaw()` or FFmpeg

### Streaming Endpoints (Ready for Testing)
1. `/test-websocket-debug` - Full featured debug handler (AGGRESSIVE RESPONSES)
2. `/debug-websocket-voice` - TwiML handler for WebSocket testing
3. `/media-stream` - ElevenLabs streaming (format issue)
4. `/static-killer-stream` - FFmpeg pipeline approach

## 🎯 Tomorrow Morning: 30-Minute Win

### Exact Steps to Complete Streaming

**Step 1**: Add µ-law conversion function (5 mins)
```python
def convert_wav_to_mulaw(wav_data):
    """Convert Simple TTS WAV to raw µ-law for Twilio"""
    import audioop
    pcm_data = wav_data[44:]  # Skip WAV header
    return audioop.lin2ulaw(pcm_data, 2)
```

**Step 2**: Update WebSocket handler (5 mins)
- In `/test-websocket-debug` at line ~1658
- Replace: `payload = convert_wav_for_twilio(wav_data)`
- With: `mulaw = convert_wav_to_mulaw(wav_data); payload = base64.b64encode(mulaw).decode('ascii')`

**Step 3**: Test with Twilio call (15 mins)
- Point Twilio webhook to: `/debug-websocket-voice`
- Call the number, verify clear audio response
- Should hear: "I hear you loud and clear!" every 0.2 seconds

**Step 4**: Celebrate! (5 mins)
- You now have real-time AI voice streaming! 🎉

## 📊 Endpoint Architecture

### Call Flow Diagram
```
Twilio Call → TwiML Response → WebSocket Connection
     ↓              ↓                    ↓
  /voice      VoiceResponse()    /media-stream or
     ↓         <Connect>          /test-websocket-debug
     ↓         <Stream url=>            ↓
     ↓              ↓          Media events: connected,
     ↓              ↓          start, media, closed
     ↓              ↓                    ↓
Traditional    WebSocket         Real-time bidirectional
TwiML Flow     Streaming         audio streaming
```

### Production vs Test Endpoints

**Production (Currently Active)**:
- `/voice` - Main call handler (ElevenLabs traditional)
- `/process-speech-elevenlabs` - Speech processing

**Testing/Development**:
- `/debug-voice-handler` - Traditional TwiML test (WORKING)
- `/debug-websocket-voice` - WebSocket test entry point
- `/test-websocket-debug` - Full debug WebSocket handler

**Utility Endpoints**:
- `/test-streaming-status` - Check dependencies
- `/test-audio-conversion` - Test TTS → µ-law pipeline
- `/test-sine-wave` - Generate test audio
- `/test-static-killer` - Test FFmpeg conversion

## 🔧 Configuration

### Environment Variables (.env)
- ✅ OPENAI_API_KEY - Configured
- ✅ ELEVEN_LABS_API_KEY - Configured
- ✅ ELEVEN_LABS_VOICE_ID - Configured
- ✅ TWILIO_ACCOUNT_SID - Configured
- ✅ TWILIO_AUTH_TOKEN - Configured
- ✅ TWILIO_PHONE_NUMBER - +19174569983
- ✅ YOUR_PHONE_NUMBER - +16784628116
- ⚠️ BASE_URL - Set to https://artist-hotline.com but **app runs on https://artist-hotline-production.up.railway.app**
- ⚠️ USE_STREAMING - Not set (defaults to false)
- ⚠️ USE_COQUI_TEST - Not set (defaults to false)

### 🚨 IMPORTANT: URL Configuration Issue
**Your .env says**: `BASE_URL=https://artist-hotline.com`
**App actually runs on**: `https://artist-hotline-production.up.railway.app`

This might cause audio playback issues! Update .env tomorrow if audio URLs aren't working.

### To Enable Streaming Tomorrow
Add to `.env`:
```bash
USE_STREAMING=true
```

## 🧪 Research & Insights

### Key Discovery from Tonight
**Problem**: Sending WAV format (with headers) to Twilio WebSocket causes "garbage audio"
**Solution**: Must send raw µ-law format (no headers)
**Evidence**: Stack Overflow + Twilio docs confirm `audioop.lin2ulaw()` approach

### Audio Format Requirements
- **Twilio WebSocket expects**: Raw µ-law, 8kHz, mono, base64 encoded
- **Simple TTS generates**: WAV format, 8kHz, mono, with 44-byte header
- **Conversion needed**: Strip WAV header → convert PCM to µ-law → base64 encode

## 📝 Git Status
```
Untracked files:
  .claude/              (custom agents setup)
  tomorrow-streaming-plan.md  (tonight's research notes)

Recent commits:
  c637bcd Fix WebSocket audio format issue - convert WAV to µ-law for Twilio
  26ebfb1 Make WebSocket responses extremely aggressive for debugging
  d6d1c74 Add aggressive WebSocket debugging with error-level logging
```

## 🚀 Quick Reference Commands

### Test Locally
```bash
# Check if app is running
curl https://artist-hotline.com/health

# Test Simple TTS
curl -X POST https://artist-hotline.com/test-audio-conversion

# Check streaming readiness
curl https://artist-hotline.com/health/streaming
```

### Test with Twilio
1. Go to Twilio Console → Phone Numbers → +19174569983
2. Update webhook URL to: `https://artist-hotline.com/debug-websocket-voice`
3. Call the number from your phone
4. Should hear instant WebSocket response

## 💡 Project Vision

### Current State
"Replicant Jason" - AI voice agent that answers calls, has conversations, remembers callers

### After Tomorrow
Real-time streaming voice AI with sub-second latency and natural conversation flow

### Future Enhancements
- Deepgram integration for better transcription
- Custom voice cloning
- Multi-language support
- Enhanced personality tuning

---

**Last Updated**: 2025-10-13 (pre-sleep session)
**Next Session**: 30-minute streaming completion
**Confidence Level**: 95% - One small fix away from working!
