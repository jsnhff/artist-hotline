# WebSocket Streaming Implementation Plan

## Overview
Upgrade Replicant Jason hotline from request/response audio to real-time WebSocket streaming for sub-second response times and natural conversational flow.

## Current vs Target Architecture

### Current (Request/Response)
- Twilio → FastAPI → ElevenLabs REST API → Audio file → TwiML
- 3-5 second response delays
- No interruption handling

### Target (Real-time Streaming) 
- Twilio Media Streams ↔ WebSocket Server ↔ ElevenLabs WebSocket API
- Sub-second response times
- True conversational AI with interruptions

## Phase 1: ElevenLabs WebSocket Streaming

### 1. Replace REST API with WebSocket Connection
```python
# Current approach (main.py:69-105)
async def generate_speech_with_elevenlabs(text: str) -> str:
    # HTTP POST request - slow, file-based
    
# New approach
async def stream_speech_elevenlabs(text: str, websocket):
    uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}/stream-input?model_id=eleven_flash_v2_5"
    async with websockets.connect(uri) as ws:
        # Initialize connection
        await ws.send(json.dumps({
            "voice_settings": {"stability": 0.3, "similarity_boost": 0.75},
            "xi_api_key": ELEVEN_LABS_API_KEY
        }))
        
        # Stream text word-by-word for fastest TTFB
        await ws.send(json.dumps({"text": text}))
        
        # Listen for audio chunks
        async for audio_chunk in listen_for_audio(ws):
            yield audio_chunk
```

### 2. Key Implementation Changes
- **Model**: Switch to `eleven_flash_v2_5` (lowest latency)
- **Streaming**: Word-by-word text streaming 
- **Audio**: Base64 decoded chunks, no file caching
- **Connection**: Persistent WebSocket connections

## Phase 2: Twilio Media Streams Integration

### 3. Add Bidirectional Media Streams

#### TwiML Changes
```xml
<!-- Current -->
<Play>https://artist-hotline.com/audio/{hash}</Play>

<!-- New -->
<Connect>
    <Stream url="wss://artist-hotline.com/media-stream" />
</Connect>
```

#### WebSocket Endpoint
```python
@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    await websocket.accept()
    
    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            if data['event'] == 'media':
                # Receive μ-law audio from Twilio (8kHz, base64)
                audio_payload = data['media']['payload']
                audio_chunk = base64.b64decode(audio_payload)
                
                # Process with speech-to-text
                text = await transcribe_audio(audio_chunk)
                
                # Generate AI response
                ai_response = await get_ai_response(text)
                
                # Stream back via ElevenLabs WebSocket
                async for audio_chunk in stream_speech_elevenlabs(ai_response):
                    # Send back to Twilio
                    media_message = {
                        "event": "media",
                        "streamSid": data['streamSid'],
                        "media": {
                            "payload": base64.b64encode(audio_chunk).decode()
                        }
                    }
                    await websocket.send_text(json.dumps(media_message))
                    
    except WebSocketDisconnect:
        pass
```

### 4. Real-time Audio Pipeline
1. **Receive**: Twilio streams caller audio via WebSocket
2. **Transcribe**: Real-time speech-to-text (Deepgram WebSocket?)
3. **Generate**: AI response with streaming context
4. **Synthesize**: ElevenLabs WebSocket streaming TTS
5. **Stream**: Audio chunks back to Twilio WebSocket

## Phase 3: Architecture Changes

### 5. Dependencies & Server Setup
```bash
pip install websockets gevent-websocket
```

```python
# New imports
import websockets
import asyncio
from fastapi import WebSocket, WebSocketDisconnect

# WebSocket server alongside FastAPI
app = FastAPI()

# Handle concurrent connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.elevenlabs_connections = {}
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
```

### 6. Latency Optimizations
- **Remove audio caching**: Direct streaming, no file storage
- **Connection pooling**: Reuse ElevenLabs WebSocket connections
- **Buffering**: Smart audio buffering for smooth playback
- **Concurrent processing**: Handle multiple streams simultaneously

## Technical Specifications

### ElevenLabs WebSocket API
- **Endpoint**: `wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input`
- **Model**: `eleven_flash_v2_5` (fastest)
- **Audio Format**: Base64 encoded audio chunks
- **Timeout**: 20 seconds default (configurable to 180s)
- **Best Practice**: Stream word-by-word, use `flush: true` for turn endings

### Twilio Media Streams
- **Bidirectional**: `<Connect><Stream url="wss://..." />`
- **Audio Format**: μ-law, 8kHz sample rate, base64 encoded
- **Protocol**: WebSocket Secure (wss://) only
- **Message Types**: connected, start, media, closed

### Performance Expectations
- **Current latency**: 3-5 seconds (REST API + file generation)
- **Target latency**: <1 second (WebSocket streaming)
- **First audio**: <500ms (TTFB optimization)
- **Interruption handling**: Real-time (bidirectional streams)

## Implementation Priority

### Week 1: Foundation
1. Add WebSocket dependencies
2. Create basic ElevenLabs WebSocket connection
3. Test streaming audio generation

### Week 2: Integration  
4. Implement Twilio Media Streams endpoint
5. Connect audio pipeline (Twilio ↔ ElevenLabs)
6. Add real-time transcription

### Week 3: Optimization
7. Fine-tune buffering and latency
8. Handle edge cases and errors
9. Load testing and performance optimization

## Benefits
- **Sub-second response times** vs current 3-5 second delays
- **Natural conversation flow** with interruption handling
- **Real-time transcription** for better context understanding
- **Scalable architecture** for multiple concurrent calls
- **Enhanced user experience** with immediate audio feedback

## Research Sources
- ElevenLabs WebSocket API Documentation (2024)
- ElevenLabs Multi-Context WebSocket API
- Twilio Media Streams Documentation
- Python WebSocket implementation examples
- Real-time voice AI best practices

---
*Research compiled: September 2025*
*Next steps: Begin Phase 1 implementation with ElevenLabs WebSocket streaming*