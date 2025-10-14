# Endpoint Architecture Map

## 🎯 Production Endpoints (Live)

### `/voice` (POST/GET)
- **Purpose**: Main Twilio webhook for incoming calls
- **Handler**: `handle_elevenlabs_call()`
- **Flow**: Traditional request/response with ElevenLabs TTS
- **Response**: TwiML with `<Play>` tags for audio
- **Status**: ✅ Production ready

### `/process-speech-elevenlabs` (POST)
- **Purpose**: Process user speech from Gather
- **Handler**: `process_speech_elevenlabs()`
- **Features**: AI response, caller history, SMS notifications
- **Status**: ✅ Production ready

### `/call-status` (POST)
- **Purpose**: Twilio call status webhook
- **Handler**: `handle_call_status()`
- **Action**: Send call summary SMS when call completes
- **Status**: ✅ Production ready

---

## 🧪 WebSocket Streaming Endpoints (Testing)

### `/test-websocket-debug` (WebSocket)
- **Purpose**: **PRIMARY DEBUG HANDLER** - Most feature complete
- **Handler**: `test_websocket_debug()`
- **Features**:
  - Aggressive response testing (every 0.2s)
  - Simple TTS integration
  - µ-law conversion via `convert_wav_for_twilio()`
  - Detailed error logging
- **Status**: 🟡 99% ready (needs format fix)
- **Use for**: Testing real Twilio calls

### `/debug-websocket-voice` (POST/GET)
- **Purpose**: TwiML entry point for WebSocket testing
- **Handler**: `debug_websocket_voice_handler()`
- **Response**: `<Connect><Stream url="/test-websocket-debug">`
- **Status**: ✅ Ready to use
- **Twilio Webhook**: Point here to test streaming

### `/media-stream` (WebSocket)
- **Purpose**: ElevenLabs streaming integration
- **Handler**: `handle_media_stream()`
- **Features**: Real-time ElevenLabs WebSocket → Twilio
- **Status**: 🟡 Needs format conversion fix
- **Note**: Currently sends WAV instead of µ-law

### `/static-killer-stream` (WebSocket)
- **Purpose**: FFmpeg pipeline approach
- **Handler**: `static_killer_stream()`
- **Features**: Chunked streaming with timing
- **Status**: 🟡 Alternative approach if audioop fails

---

## 🔧 Utility & Test Endpoints

### Health & Status
- `/health` - Basic health check
- `/health/streaming` - Streaming configuration status
- `/logs` - Recent application logs (last 100)
- `/logs/streaming` - Streaming-specific logs (last 50)

### Audio Testing
- `/test-streaming-status` - Check TTS and FFmpeg dependencies
- `/test-audio-conversion` - Test Simple TTS → µ-law pipeline
- `/test-sine-wave` - Generate known-good µ-law test audio
- `/test-coqui-analysis` - Analyze TTS output in detail
- `/test-static-killer` - Test FFmpeg conversion pipeline
- `/test-audio-play` - Generate WAV for direct playback testing

### WebSocket Testing
- `/ws-test` - Minimal WebSocket connectivity test (PROVEN WORKING)
- `/ws-test-client` - Browser client for WebSocket testing

### Traditional Voice Testing
- `/debug-voice-handler` (POST/GET) - Traditional TwiML test system
  - Uses Simple TTS with `<Play>` tags
  - Proven to work with crystal clear audio
  - Good for validating TTS without WebSocket complexity

---

## 📊 Call Flow Diagrams

### Traditional Flow (Production)
```
Incoming Call
    ↓
Twilio → POST /voice
    ↓
Generate greeting audio (ElevenLabs)
    ↓
Return TwiML: <Play>{audio_url}</Play>
                <Gather action="/process-speech-elevenlabs">
    ↓
User speaks
    ↓
Twilio → POST /process-speech-elevenlabs
    ↓
AI generates response (GPT-4o-mini)
    ↓
Generate audio (ElevenLabs)
    ↓
Return TwiML: <Play>{audio_url}</Play>
                <Gather> (loop)
```

### WebSocket Streaming Flow (Testing)
```
Incoming Call
    ↓
Twilio → POST /debug-websocket-voice
    ↓
Return TwiML: <Connect>
                <Stream url="wss://artist-hotline.com/test-websocket-debug">
    ↓
WebSocket Connection Established
    ↓
Twilio sends: {"event": "connected"}
              {"event": "start", "streamSid": "..."}
    ↓
Send initial greeting via WebSocket
    ↓
Twilio sends: {"event": "media", "payload": base64_mulaw}
    ↓
Buffer audio chunks
    ↓
When enough audio received:
    - Generate AI response (GPT-4o-mini)
    - Generate speech (Simple TTS → WAV)
    - Convert to µ-law ← **CURRENT ISSUE**
    - Base64 encode
    - Send: {"event": "media", "streamSid": "...", "media": {"payload": "..."}}
    ↓
Loop until call ends
    ↓
Twilio sends: {"event": "closed"}
```

---

## 🎯 Recommended Testing Path

### Step 1: Verify Traditional System
```bash
# Point Twilio to: /debug-voice-handler
# Call and verify crystal clear audio
# This validates: TTS generation, BASE_URL, Twilio config
```

### Step 2: Test WebSocket Connection
```bash
# Point Twilio to: /debug-websocket-voice
# Call and listen for initial greeting
# This validates: WebSocket connectivity, Railway config
```

### Step 3: Fix Audio Format
```python
# In /test-websocket-debug, update conversion:
def convert_wav_to_mulaw(wav_data):
    import audioop
    pcm_data = wav_data[44:]  # Skip WAV header
    return audioop.lin2ulaw(pcm_data, 2)

# Use: mulaw = convert_wav_to_mulaw(wav_data)
#      payload = base64.b64encode(mulaw).decode('ascii')
```

### Step 4: Full Conversation Test
```bash
# Call again, should now hear clear responses
# Test back-and-forth conversation
# Validate sub-second latency
```

---

## 🔑 Key Configuration

### Twilio Phone Number
- **Number**: +19174569983
- **Current Webhook**: `/voice` (production)
- **For Testing**: Change to `/debug-websocket-voice`

### Base URL
- **Production**: https://artist-hotline.com
- **WebSocket**: wss://artist-hotline.com

### Audio Format Requirements
| Stage | Format | Sample Rate | Channels | Encoding |
|-------|--------|-------------|----------|----------|
| Simple TTS Output | WAV | 8kHz | Mono | 16-bit PCM |
| Twilio WebSocket | Raw | 8kHz | Mono | µ-law (8-bit) |
| Conversion Needed | Strip header + convert PCM→µ-law + base64 | | | |

---

## 🚨 Troubleshooting Guide

### "No audio heard"
- Check BASE_URL is correct in .env
- Verify Twilio webhook URL is absolute (not relative)
- Check logs: `/logs/streaming`

### "Garbage/static audio"
- **ROOT CAUSE**: Sending WAV instead of µ-law
- **FIX**: Use `audioop.lin2ulaw()` conversion
- See "Step 3: Fix Audio Format" above

### "WebSocket disconnects immediately"
- Check Railway WebSocket support (proven working via `/ws-test`)
- Verify wss:// protocol in Stream URL
- Check for exceptions in WebSocket handler

### "Audio works once then stops"
- Check rate limiting logic (last_response_time)
- Verify buffer clearing after responses
- Check WebSocket connection state before sending

---

**Last Updated**: 2025-10-13
**Next Action**: Test `/debug-websocket-voice` and apply µ-law fix
