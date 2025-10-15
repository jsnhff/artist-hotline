# Standard library imports
import asyncio
import base64
import hashlib
import json
import logging
import os
import random
import time
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional

# Third-party imports
import httpx
import openai
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="Artist Hotline Voice Agent", version="1.0.0")

# Configuration from environment
class Config:
    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ELEVEN_LABS_API_KEY: str = os.getenv("ELEVEN_LABS_API_KEY", "")
    ELEVEN_LABS_VOICE_ID: str = os.getenv("ELEVEN_LABS_VOICE_ID", "")
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    YOUR_PHONE_NUMBER: str = os.getenv("YOUR_PHONE_NUMBER", "")
    
    # App Configuration
    RAILWAY_PUBLIC_DOMAIN: str = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
    BASE_URL: str = os.getenv("BASE_URL", f"https://{RAILWAY_PUBLIC_DOMAIN}" if RAILWAY_PUBLIC_DOMAIN else "https://artist-hotline-production.up.railway.app")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # Feature Flags
    USE_STREAMING: bool = os.getenv("USE_STREAMING", "false").lower() == "true"
    USE_COQUI_TEST: bool = os.getenv("USE_COQUI_TEST", "false").lower() == "true"

config = Config()

# Configure OpenAI
openai.api_key = config.OPENAI_API_KEY

# Initialize Twilio client
twilio_client = Client(config.TWILIO_ACCOUNT_SID, config.TWILIO_AUTH_TOKEN)

# Global state management
audio_cache: Dict[str, bytes] = {}
call_transcripts: Dict[str, List[str]] = {}
caller_history: Dict[str, Dict] = {}

# Connection manager for WebSocket streams
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.elevenlabs_connections = {}
    
    async def connect(self, websocket: WebSocket, stream_sid: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected for stream {stream_sid}")
    
    def disconnect(self, websocket: WebSocket, stream_sid: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if stream_sid in self.elevenlabs_connections:
            del self.elevenlabs_connections[stream_sid]
        logger.info(f"WebSocket disconnected for stream {stream_sid}")

manager = ConnectionManager()

# Initialize Simple TTS globally at startup
import asyncio
_tts_initialized = False

async def ensure_tts_initialized():
    """Ensure Simple TTS is initialized globally"""
    global _tts_initialized
    if not _tts_initialized:
        try:
            from simple_tts import initialize_simple_tts
            logger.error("🔧 GLOBAL TTS INITIALIZATION STARTING...")
            success = await initialize_simple_tts()
            if success:
                _tts_initialized = True
                logger.error("✅ GLOBAL TTS INITIALIZED SUCCESSFULLY!")
            else:
                logger.error("❌ GLOBAL TTS INITIALIZATION FAILED!")
        except Exception as e:
            logger.error(f"❌ GLOBAL TTS INIT ERROR: {e}")
    return _tts_initialized

# Inspiring quotes
# Quick acknowledgment responses (instant, while thinking)
QUICK_RESPONSES = [
    "Hmm, let me think about that.",
    "Interesting, okay.",
    "Alright, hold on.",
    "Yeah, let me process that.",
    "Hmm, good question.",
    "Right, I hear you.",
    "Okay, give me a sec.",
    "Mm-hmm, thinking.",
]

INSPIRING_QUOTES = [
    "This is the true joy in life, being used for a purpose recognized by yourself as a mighty one. Being a force of nature instead of a feverish, selfish little clod of ailments and grievances, complaining that the world will not devote itself to making you happy. I want to be thoroughly used up when I die, for the harder I work, the more I live. I rejoice in life for its own sake. Life is no brief candle to me. It is a sort of splendid torch which I have got hold of for the moment and I want to make it burn as brightly as possible before handing it on to future generations. - George Bernard Shaw",
    
    "We don't read and write poetry because it's cute. We read and write poetry because we are members of the human race. And the human race is filled with passion. Poetry, beauty, romance, love, these are what we stay alive for. To quote from Whitman, O me! O life! Answer. That you are here, that life exists, and identity, that the powerful play goes on and you may contribute a verse. What will your verse be? - Dead Poets Society",
    
    "The most important thing about art is to work. Nothing else matters except sitting down every day and trying. If you don't show up, the work never gets made. - John Baldessari",
    
    "The goal of art isn't to attain perfection. The goal is to share who we are and how we see the world. One of the greatest rewards of making art is our ability to share it. Even if there is no audience to receive it, we build the muscle of making something and putting it out into the world. - Rick Rubin"
]

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Replicant Jason hotline is running"}

@app.get("/health/streaming")
async def streaming_health_check():
    """Check if streaming configuration is valid"""
    health_status = {
        "streaming_enabled": config.USE_STREAMING,
        "base_url": config.BASE_URL,
        "elevenlabs_configured": bool(config.ELEVEN_LABS_API_KEY and config.ELEVEN_LABS_VOICE_ID),
        "websocket_url": None,
        "status": "unknown"
    }
    
    if config.USE_STREAMING:
        ws_url = config.BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        health_status["websocket_url"] = f"{ws_url}/media-stream"
        
        if health_status["elevenlabs_configured"]:
            health_status["status"] = "ready"
        else:
            health_status["status"] = "missing_elevenlabs_config"
    else:
        health_status["status"] = "streaming_disabled"
    
    return health_status

@app.get("/logs")
async def get_recent_logs():
    """Get recent application logs for debugging"""
    return {
        "total_logs": len(log_capture.logs),
        "logs": list(log_capture.logs)[-100:]  # Last 100 logs
    }

@app.get("/logs/streaming")
async def get_streaming_logs():
    """Get logs related to streaming specifically"""
    streaming_logs = [
        log for log in log_capture.logs 
        if any(keyword in log['message'].lower() for keyword in 
               ['streaming', 'elevenlabs', 'websocket', 'audio', 'chunk', 'twilio'])
    ]
    return {
        "total_streaming_logs": len(streaming_logs),
        "logs": streaming_logs[-50:]  # Last 50 streaming-related logs
    }

@app.get("/")
async def root():
    return {"message": "Welcome to Replicant Jason's Voice Hotline", "status": "ready"}

@app.websocket("/ws-test")
async def websocket_test(websocket: WebSocket):
    """Minimal WebSocket test for Railway debugging"""
    try:
        await websocket.accept()
        logger.info("✅ Minimal WebSocket connected successfully")
        
        await websocket.send_text(json.dumps({
            "event": "connected",
            "message": "Minimal WebSocket working on Railway!",
            "timestamp": time.time()
        }))
        
        while True:
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
                
                # Echo back what we received
                response = {
                    "event": "echo",
                    "received": data,
                    "timestamp": time.time()
                }
                await websocket.send_text(json.dumps(response))
                logger.info(f"✅ WebSocket echoed: {data}")
                
            except Exception as e:
                logger.error(f"WebSocket message error: {e}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        logger.info("WebSocket connection closed")

@app.get("/ws-test-client")
async def websocket_test_client():
    """Simple WebSocket client for testing"""
    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
</head>
<body>
    <h1>Railway WebSocket Test</h1>
    <div id="messages"></div>
    <input type="text" id="messageInput" placeholder="Type a message">
    <button onclick="sendMessage()">Send</button>
    
    <script>
        const ws = new WebSocket('wss://artist-hotline-production.up.railway.app/ws-test');
        const messages = document.getElementById('messages');
        
        ws.onopen = function(event) {
            addMessage('✅ Connected to WebSocket');
        };
        
        ws.onmessage = function(event) {
            addMessage('📨 Received: ' + event.data);
        };
        
        ws.onerror = function(error) {
            addMessage('❌ Error: ' + error);
        };
        
        ws.onclose = function(event) {
            addMessage('🔌 Connection closed');
        };
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = {
                type: 'test',
                content: input.value,
                timestamp: Date.now()
            };
            ws.send(JSON.stringify(message));
            addMessage('📤 Sent: ' + input.value);
            input.value = '';
        }
        
        function addMessage(message) {
            const div = document.createElement('div');
            div.textContent = new Date().toLocaleTimeString() + ' - ' + message;
            messages.appendChild(div);
        }
    </script>
</body>
</html>
    """
    return HTMLResponse(content=html_content)

async def generate_speech_with_elevenlabs(text: str) -> str:
    try:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVEN_LABS_VOICE_ID}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": config.ELEVEN_LABS_API_KEY
        }
        
        data = {
            "text": text,
            "model_id": "eleven_flash_v2_5",  # Fastest model
            "voice_settings": {
                "stability": 0.3,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            },
            "optimize_streaming_latency": 4  # Maximum speed optimization
        }
        
        async with httpx.AsyncClient(timeout=5.0) as client:  # Allow time for flash model
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                audio_data = response.content
                audio_cache[text_hash] = audio_data
                return f"{config.BASE_URL}/audio/{text_hash}"
            else:
                logger.error(f"ElevenLabs API error: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"ElevenLabs error: {e}")
        return None

async def generate_speech_with_elevenlabs_streaming(text: str) -> str:
    try:
        if not text.strip():
            return None
            
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        # Check cache first
        if text_hash in audio_cache:
            return f"{config.BASE_URL}/audio/{text_hash}"
        
        # WebSocket streaming connection
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{config.ELEVEN_LABS_VOICE_ID}/stream-input"
        
        try:
            async with websockets.connect(uri) as websocket:
                # Send initial message with auth and voice settings
                init_message = {
                    "text": " ",  # Small initial text
                    "voice_settings": {
                        "stability": 0.3,
                        "similarity_boost": 0.75,
                        "style": 0.0,
                        "use_speaker_boost": True
                    },
                    "xi_api_key": config.ELEVEN_LABS_API_KEY
                }
                await websocket.send(json.dumps(init_message))
                
                # Send the actual text
                await websocket.send(json.dumps({"text": text}))
                
                # Send EOS (end of stream)
                await websocket.send(json.dumps({"text": ""}))
                
                # Collect audio chunks
                audio_chunks = []
                async for message in websocket:
                    data = json.loads(message)
                    
                    if data.get("audio"):
                        audio_chunk = base64.b64decode(data["audio"])
                        audio_chunks.append(audio_chunk)
                    
                    if data.get("isFinal"):
                        break
                
                if audio_chunks:
                    # Combine all chunks
                    full_audio = b''.join(audio_chunks)
                    audio_cache[text_hash] = full_audio
                    logger.info(f"Streaming TTS generated {len(full_audio)} bytes for text: {text[:50]}...")
                    return f"{config.BASE_URL}/audio/{text_hash}"
                else:
                    logger.error("No audio chunks received from streaming")
                    return None
                    
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket connection failed: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Streaming TTS error: {e}")
        return None

async def generate_speech(text: str) -> str:
    """Hybrid approach: Use streaming TTS for speed, fallback to REST for reliability"""
    if config.USE_STREAMING:
        logger.info("Using hybrid streaming TTS (streaming generation, cached playback)")
        result = await generate_speech_with_elevenlabs_streaming(text)
        if result:
            return result
        else:
            # Fallback to REST API if streaming fails
            logger.warning("Streaming failed, falling back to REST API")
            return await generate_speech_with_elevenlabs(text)
    else:
        logger.info("Using optimized REST API for TTS")
        return await generate_speech_with_elevenlabs(text)

async def stream_speech_to_twilio(text: str, twilio_websocket: WebSocket, stream_sid: str):
    """Stream TTS audio directly to Twilio WebSocket with proper MP3 to µ-law conversion"""
    try:
        if not text.strip():
            logger.warning("Empty text provided to stream_speech_to_twilio")
            return

        logger.info(f"Starting ElevenLabs streaming for: '{text[:50]}...'")

        # Import audio conversion dependencies
        from pydub import AudioSegment
        import io

        # WebSocket streaming connection to ElevenLabs
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{config.ELEVEN_LABS_VOICE_ID}/stream-input"
        logger.debug(f"Connecting to ElevenLabs: {uri}")

        async with websockets.connect(uri) as elevenlabs_ws:
            # Send initial message with auth and voice settings
            # Request MP3 output format (ElevenLabs default)
            init_message = {
                "text": " ",  # Small initial text
                "voice_settings": {
                    "stability": 0.3,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                },
                "generation_config": {
                    "chunk_length_schedule": [120, 160, 250, 290]
                },
                "xi_api_key": config.ELEVEN_LABS_API_KEY
            }
            logger.debug("Sending ElevenLabs init message")
            await elevenlabs_ws.send(json.dumps(init_message))

            # Send the actual text
            logger.debug(f"Sending text to ElevenLabs: {text}")
            await elevenlabs_ws.send(json.dumps({"text": text}))

            # Send EOS (end of stream)
            logger.debug("Sending EOS to ElevenLabs")
            await elevenlabs_ws.send(json.dumps({"text": ""}))

            # Stream audio chunks with proper conversion
            chunk_count = 0
            total_mp3_bytes = 0
            total_mulaw_bytes = 0

            async for message in elevenlabs_ws:
                try:
                    data = json.loads(message)
                    logger.debug(f"ElevenLabs response: {list(data.keys())}")

                    # Check for errors first
                    if data.get("error"):
                        logger.error(f"ElevenLabs error: {data['error']}")
                        break

                    if data.get("audio"):
                        chunk_count += 1
                        audio_b64 = data["audio"]

                        try:
                            # Step 1: Decode base64 to get MP3 bytes
                            mp3_bytes = base64.b64decode(audio_b64)
                            total_mp3_bytes += len(mp3_bytes)
                            logger.debug(f"Chunk {chunk_count}: Decoded {len(mp3_bytes)} MP3 bytes")

                            # Step 2: Decode MP3 to PCM audio using pydub
                            audio_segment = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))

                            # Step 3: Resample to 8kHz mono (Twilio requirement)
                            audio_segment = audio_segment.set_frame_rate(8000).set_channels(1)

                            # Step 4: Export as WAV
                            wav_buffer = io.BytesIO()
                            audio_segment.export(wav_buffer, format="wav")
                            wav_bytes = wav_buffer.getvalue()
                            logger.debug(f"Chunk {chunk_count}: Converted to {len(wav_bytes)} WAV bytes")

                            # Step 5: Convert WAV to µ-law using existing function
                            mulaw_bytes = convert_wav_to_mulaw(wav_bytes)
                            total_mulaw_bytes += len(mulaw_bytes)

                            # Step 6: Encode as base64 for Twilio
                            mulaw_b64 = base64.b64encode(mulaw_bytes).decode('ascii')
                            logger.debug(f"Chunk {chunk_count}: Converted to {len(mulaw_bytes)} µ-law bytes")

                        except Exception as conversion_error:
                            logger.error(f"Failed to convert audio chunk {chunk_count}: {conversion_error}")
                            continue

                        # Step 7: Send properly formatted audio to Twilio
                        media_message = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": mulaw_b64  # Proper µ-law format for Twilio
                            }
                        }

                        try:
                            # Check if WebSocket is still connected before sending
                            if twilio_websocket.client_state.name == "CONNECTED":
                                await twilio_websocket.send_text(json.dumps(media_message))
                                logger.debug(f"✅ Sent converted audio chunk {chunk_count} to Twilio")
                            else:
                                logger.error(f"Twilio WebSocket not connected (state: {twilio_websocket.client_state.name})")
                                break
                        except Exception as send_error:
                            logger.error(f"Failed to send audio to Twilio: {send_error}")
                            break  # Stop trying to send if connection is broken

                    if data.get("isFinal"):
                        logger.info(f"✅ Finished streaming: {chunk_count} chunks")
                        logger.info(f"   MP3 input: {total_mp3_bytes} bytes")
                        logger.info(f"   µ-law output: {total_mulaw_bytes} bytes")
                        logger.info(f"   Text: '{text[:50]}...'")
                        break

                except json.JSONDecodeError as json_error:
                    logger.error(f"Invalid JSON from ElevenLabs: {json_error}")
                except Exception as chunk_error:
                    logger.error(f"Error processing ElevenLabs chunk: {chunk_error}")
                    import traceback
                    logger.error(f"Chunk error traceback: {traceback.format_exc()}")

    except websockets.exceptions.WebSocketException as ws_error:
        logger.error(f"ElevenLabs WebSocket error: {ws_error}")
    except Exception as e:
        logger.error(f"Error in stream_speech_to_twilio: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

class AudioBuffer:
    def __init__(self, max_chunks=50):
        self.chunks = []
        self.max_chunks = max_chunks
        self.silence_threshold = 3  # seconds of silence before processing
        self.last_chunk_time = None
    
    def add_chunk(self, audio_data: bytes):
        self.chunks.append(audio_data)
        self.last_chunk_time = time.time()
        
        # Keep buffer size manageable
        if len(self.chunks) > self.max_chunks:
            self.chunks = self.chunks[-self.max_chunks:]
    
    def should_process(self) -> bool:
        if not self.chunks:
            return False
        
        # Process if we have enough audio or if there's been silence
        if len(self.chunks) >= 10:  # ~0.5 seconds of audio
            return True
        
        if self.last_chunk_time and (time.time() - self.last_chunk_time) > self.silence_threshold:
            return True
            
        return False
    
    def get_audio_data(self) -> bytes:
        if self.chunks:
            return b''.join(self.chunks)
        return b''
    
    def clear(self):
        self.chunks = []

def convert_wav_to_mulaw(wav_data: bytes) -> bytes:
    """
    Convert WAV audio to raw µ-law format for Twilio WebSocket.

    Uses wave module to properly parse headers (handles any header size).
    """
    import audioop
    import wave
    import io

    # Use wave module to properly parse WAV (handles 44, 78, or any byte headers)
    wav_buffer = io.BytesIO(wav_data)
    with wave.open(wav_buffer, 'rb') as wav_file:
        # Extract pure PCM data (no matter what header size)
        pcm_data = wav_file.readframes(wav_file.getnframes())

    # Convert 16-bit linear PCM to µ-law (8-bit)
    mulaw_data = audioop.lin2ulaw(pcm_data, 2)

    return mulaw_data

async def transcribe_audio_buffer(audio_data: bytes) -> str:
    """Enhanced transcription with audio buffer handling"""
    # TODO: Integrate with Deepgram WebSocket API for real-time transcription
    # For now, simulate transcription by detecting audio presence

    if len(audio_data) > 1000:  # If we have substantial audio data
        # Placeholder - in real implementation, this would:
        # 1. Convert μ-law to linear PCM
        # 2. Send to Deepgram WebSocket
        # 3. Return real-time transcription results
        return "[User spoke - real-time transcription would go here]"

    return ""

# Store audio buffers per stream
audio_buffers = {}

# Store recent logs for debugging
class LogCapture(logging.Handler):
    def __init__(self, maxlen=500):
        super().__init__()
        self.logs = deque(maxlen=maxlen)
    
    def emit(self, record):
        log_entry = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'message': self.format(record)
        }
        self.logs.append(log_entry)

# Add log capture handler
log_capture = LogCapture()
log_capture.setLevel(logging.DEBUG)
logger.addHandler(log_capture)

@app.get("/audio/{audio_id}")
async def serve_audio(audio_id: str):
    if audio_id in audio_cache:
        return Response(
            content=audio_cache[audio_id],
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    else:
        return Response(status_code=404)

async def generate_call_summary(conversation: list) -> str:
    try:
        if not conversation:
            return "No conversation recorded"
        
        conversation_text = ""
        for exchange in conversation:
            conversation_text += f"Caller: {exchange['caller']}\nAI: {exchange['ai']}\n\n"
        
        summary_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Summarize this phone conversation between a caller and Replicant Jason (an AI version of artist Jason Huff) in 1-2 sentences. Focus on the main topics discussed and any interesting ideas or projects mentioned."},
                {"role": "user", "content": conversation_text}
            ],
            max_tokens=100,
            temperature=0.3
        )
        
        return summary_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Failed to generate call summary: {e}")
        return "Summary unavailable"

async def send_sms_notification(caller_number: str, is_returning: bool = False, topics: list = []) -> bool:
    try:
        if not YOUR_PHONE_NUMBER:
            logger.warning("YOUR_PHONE_NUMBER not configured - skipping SMS notification")
            return False
            
        timestamp = datetime.now().strftime("%I:%M %p")
        
        if is_returning and topics:
            recent_topics = ", ".join(topics[-2:])
            message = f"📞 Replicant Jason call at {timestamp}\nReturning caller: {caller_number}\nPrevious topics: {recent_topics}"
        elif is_returning:
            message = f"📞 Replicant Jason call at {timestamp}\nReturning caller: {caller_number}"
        else:
            message = f"📞 Replicant Jason call at {timestamp}\nNew caller: {caller_number}"
        
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=YOUR_PHONE_NUMBER
        )
        
        logger.info(f"SMS notification sent for call from {caller_number}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send SMS notification: {e}")
        return False

async def send_call_summary_sms(caller_number: str, call_sid: str) -> bool:
    try:
        if not YOUR_PHONE_NUMBER or call_sid not in call_transcripts:
            return False
        
        conversation = call_transcripts[call_sid]['conversation']
        if not conversation:
            return False
        
        summary = await generate_call_summary(conversation)
        timestamp = datetime.now().strftime("%I:%M %p")
        
        message = f"📋 Call Summary ({timestamp})\nCaller: {caller_number}\n\n{summary}"
        
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=YOUR_PHONE_NUMBER
        )
        
        logger.info(f"Call summary SMS sent for {caller_number}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send call summary SMS: {e}")
        return False

async def get_ai_response(user_input: str, caller_context: str = "") -> str:
    try:
        # 15% chance to offer a quote
        if random.random() < 0.15:
            quote = random.choice(INSPIRING_QUOTES)
            return f"Want to hear an inspiring quote? {quote}"
        
        system_prompt = "You are Replicant Jason, a synthetic version of artist Jason Huff. You're obsessed with making things, not talking about making things. You hate tech buzzwords and Silicon Valley bullshit. You're direct, honest, and a bit sarcastic. You get excited about clever ideas that take real thinking to execute. You like art that helps people see technology's impact in new ways without being cheesy. Keep responses SHORT and conversational - like you're chatting with a friend, not giving a lecture. Avoid numbered lists or structured formats. Give ONE idea or thought at a time. Be practical and focused on ideas that actually make people think. Don't ask multiple questions in one response."
        
        if caller_context:
            system_prompt += f" CALLER CONTEXT: {caller_context}"
        
        chat_response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # Faster than gpt-3.5-turbo-1106
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=80,  # Much shorter, more conversational
            temperature=0.7
        )
        return chat_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "Sorry, I'm having trouble thinking right now. Can you say that again?"

@app.api_route("/voice", methods=["GET", "POST"])
async def handle_call(request: Request):
    # Route to Coqui test system if enabled
    if config.USE_COQUI_TEST:
        logger.info("🧪 Using Coqui TTS test system")
        return await handle_coqui_call(request)
    else:
        logger.info("🎵 Using ElevenLabs production system")
        return await handle_elevenlabs_call(request)

async def handle_elevenlabs_call(request: Request):
    """Original ElevenLabs-based call handling (production system)"""
    form_data = await request.form()
    from_number = form_data.get('From', 'unknown')
    call_sid = form_data.get('CallSid', 'unknown')
    
    response = VoiceResponse()
    
    # Check if this is a returning caller
    is_returning = from_number in caller_history
    topics = caller_history.get(from_number, {}).get('last_topics', []) if is_returning else []
    
    # Send SMS notification
    await send_sms_notification(from_number, is_returning, topics)
    
    # Initialize call transcript
    timestamp = datetime.now().isoformat()
    if call_sid not in call_transcripts:
        call_transcripts[call_sid] = {
            'from_number': from_number,
            'start_time': timestamp,
            'conversation': []
        }
    
    # Update caller history
    if from_number not in caller_history:
        caller_history[from_number] = {
            'first_call': timestamp,
            'call_count': 1,
            'last_topics': []
        }
    else:
        caller_history[from_number]['call_count'] += 1
    
    # Traditional approach for ElevenLabs calls
    if from_number in caller_history:
        caller_info = caller_history[from_number]
        call_count = caller_info['call_count']
        recent_topics = caller_info['last_topics'][-2:] if caller_info['last_topics'] else []
        
        if recent_topics:
            topics_text = " and ".join(recent_topics)
            greeting_text = f"Hey, welcome back! This is Synthetic Jason... I remember we talked about {topics_text}. Want to pick up where we left off?"
        else:
            greeting_text = f"Hey, welcome back! This is Synthetic Jason... I remember you called before. What's on your mind today?"
    else:
        greeting_text = "Hey! This is Synthetic Jason... I'm basically Jason Huff but weirder and more obsessed with art. What wild idea should we dream up together?"
    
    greeting_audio_url = await generate_speech(greeting_text)
    
    if greeting_audio_url:
        response.play(greeting_audio_url)
    else:
        response.say(greeting_text, voice="man")
    
    gather = response.gather(
        input='speech',
        action='/process-speech-elevenlabs',  # Route to ElevenLabs processor
        method='POST',
        speech_timeout=2,  # Slightly longer to reduce interruptions  
        timeout=10  # Give more time for responses
    )
    
    timeout_audio_url = await generate_speech("I didn't catch that. Talk to you later!")
    if timeout_audio_url:
        response.play(timeout_audio_url)
    else:
        response.say("I didn't catch that. Talk to you later!", voice="man")
    response.hangup()
    
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.api_route("/process-speech", methods=["POST"])
async def process_speech(request: Request):
    """Route speech processing based on system type"""
    if config.USE_COQUI_TEST:
        return await process_speech_coqui(request)
    else:
        return await process_speech_elevenlabs(request)

@app.api_route("/process-speech-elevenlabs", methods=["POST"])
async def process_speech_elevenlabs(request: Request):
    form_data = await request.form()
    speech_result = form_data.get('SpeechResult', '')
    call_sid = form_data.get('CallSid', 'unknown')
    from_number = form_data.get('From', 'unknown')
    
    response = VoiceResponse()
    
    if speech_result:
        timestamp = datetime.now().isoformat()
        
        if call_sid not in call_transcripts:
            call_transcripts[call_sid] = {
                'from_number': from_number,
                'start_time': timestamp,
                'conversation': []
            }
        
        # Update caller history
        if from_number not in caller_history:
            caller_history[from_number] = {
                'first_call': timestamp,
                'call_count': 1,
                'last_topics': []
            }
        else:
            caller_history[from_number]['call_count'] += 1
        
        # Build caller context
        caller_info = caller_history[from_number]
        caller_context = f"This caller has called {caller_info['call_count']} time{'s' if caller_info['call_count'] != 1 else ''} before."
        if caller_info['last_topics']:
            caller_context += f" Previous topics: {', '.join(caller_info['last_topics'][-3:])}"
        
        # Generate AI response with built-in acknowledgment
        ai_response = await get_ai_response(speech_result, caller_context if caller_info['call_count'] > 1 else "")
        
        # Prepend a quick acknowledgment to make it feel more responsive
        quick_response = random.choice(QUICK_RESPONSES)
        full_response = f"{quick_response} {ai_response}"
        
        call_transcripts[call_sid]['conversation'].append({
            'timestamp': timestamp,
            'caller': speech_result,
            'ai': full_response
        })
        
        # Track topics for this caller (keep only last 10 topics)
        caller_history[from_number]['last_topics'].append(speech_result[:50])
        if len(caller_history[from_number]['last_topics']) > 10:
            caller_history[from_number]['last_topics'] = caller_history[from_number]['last_topics'][-10:]
        
        logger.info(f"Call {call_sid}: Caller said '{speech_result}' | AI replied '{full_response}'")
        
        audio_url = await generate_speech(full_response)
        
        if audio_url:
            response.play(audio_url)
        else:
            response.say(ai_response, voice="man")
        
        gather = response.gather(
            input='speech',
            action='/process-speech-elevenlabs',  # Route to ElevenLabs processor
            method='POST',
            speech_timeout=2,  # Slightly longer to reduce interruptions  
            timeout=10  # Give more time for responses
        )
    else:
        # Send call summary before hanging up if we have a conversation
        if call_sid in call_transcripts and call_transcripts[call_sid]['conversation']:
            await send_call_summary_sms(from_number, call_sid)
        
        timeout_audio_url = await generate_speech("I couldn't catch what you said. Talk to you later!")
        if timeout_audio_url:
            response.play(timeout_audio_url)
        else:
            response.say("I couldn't catch what you said. Talk to you later!", voice="man")
        response.hangup()
    
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.get("/transcripts")
async def get_transcripts():
    return {
        "total_calls": len(call_transcripts),
        "transcripts": call_transcripts
    }

@app.get("/transcripts/{call_sid}")
async def get_call_transcript(call_sid: str):
    if call_sid in call_transcripts:
        return call_transcripts[call_sid]
    else:
        return {"error": "Call not found"}

@app.api_route("/call-status", methods=["POST"])
async def handle_call_status(request: Request):
    form_data = await request.form()
    call_status = form_data.get('CallStatus', '')
    call_sid = form_data.get('CallSid', '')
    from_number = form_data.get('From', 'unknown')
    
    logger.info(f"Call status update: {call_sid} - {call_status}")
    
    # Send summary when call ends
    if call_status == 'completed' and call_sid in call_transcripts:
        conversation = call_transcripts[call_sid]['conversation']
        if conversation:  # Only send summary if there was actual conversation
            await send_call_summary_sms(from_number, call_sid)
    
    return {"status": "received"}

# ================================
# COQUI TTS TEST SYSTEM 
# ================================

async def handle_coqui_call(request: Request):
    """Coqui TTS-based call handling (test system)"""
    form_data = await request.form()
    from_number = form_data.get('From', 'unknown')
    call_sid = form_data.get('CallSid', 'unknown')
    
    logger.info(f"🧪 Starting Coqui test call from {from_number}")
    
    response = VoiceResponse()
    
    # For now, use Media Streams for bidirectional real-time audio
    connect = response.connect()
    ws_url = config.BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/coqui-stream"
    logger.info(f"Connecting to Coqui Media Stream: {stream_url}")
    connect.stream(url=stream_url)
    
    return HTMLResponse(content=str(response), media_type="application/xml")

async def process_speech_coqui(request: Request):
    """Coqui-based speech processing (placeholder)"""
    # This will be used if we fallback to traditional TwiML approach
    # For now, redirect to Media Streams
    return await handle_coqui_call(request)

@app.websocket("/media-stream")
async def handle_media_stream(websocket: WebSocket):
    """Handle Twilio Media Streams for real-time bidirectional audio"""
    stream_sid = None
    call_sid = None
    
    try:
        await websocket.accept()
        logger.info("✅ Media stream WebSocket accepted")
        
        # Add fallback mechanism - if streaming fails, we can fallback to traditional approach
        fallback_triggered = False
        
        # Track if we've sent the initial greeting
        greeting_sent = False
        
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            logger.debug(f"Received Twilio message: {data.get('event', 'unknown')} - {list(data.keys())}")
            
            if data['event'] == 'connected':
                logger.info("✅ Media stream connected")
                
            elif data['event'] == 'start':
                stream_sid = data['start']['streamSid']
                call_sid = data['start']['callSid']
                logger.info(f"Media stream started: {stream_sid} for call {call_sid}")
                
                # Now properly connect to the manager with the real stream_sid
                manager.active_connections.append(websocket)
                
                # Send initial greeting via streaming  
                greeting_text = "Hey! This is Synthetic Jason speaking in real-time! I can hear you clearly and respond instantly. What's on your mind?"
                
                try:
                    # Add small delay to ensure WebSocket is fully established
                    await asyncio.sleep(0.1)
                    await stream_speech_to_twilio(greeting_text, websocket, stream_sid)
                    logger.info("✅ Initial greeting streamed successfully")
                except Exception as greeting_error:
                    logger.error(f"❌ Failed to stream initial greeting: {greeting_error}")
                    fallback_triggered = True
                
            elif data['event'] == 'media':
                # Extract stream_sid from media event if we don't have it
                if not stream_sid:
                    stream_sid = data.get('streamSid')
                    logger.info(f"🔍 Extracted stream_sid from media event: {stream_sid}")
                
                # If we haven't sent greeting yet and we're receiving media, send it now
                if not greeting_sent and stream_sid:
                    logger.info("📨 Sending initial greeting on first media event")
                    greeting_text = "Hey! This is Synthetic Jason speaking in real-time! I can hear you clearly and respond instantly. What's on your mind?"
                    try:
                        await stream_speech_to_twilio(greeting_text, websocket, stream_sid)
                        greeting_sent = True
                        logger.info("✅ Initial greeting sent successfully")
                    except Exception as greeting_error:
                        logger.error(f"❌ Failed to send initial greeting: {greeting_error}")
                
                # Receive μ-law audio from Twilio (8kHz, base64)
                audio_payload = data['media']['payload']
                audio_chunk = base64.b64decode(audio_payload)
                
                # Initialize audio buffer for this stream if needed
                if stream_sid and stream_sid not in audio_buffers:
                    audio_buffers[stream_sid] = AudioBuffer()
                
                # Add chunk to buffer
                buffer = audio_buffers[stream_sid]
                buffer.add_chunk(audio_chunk)
                
                # Check if we should process accumulated audio
                if buffer.should_process():
                    audio_data = buffer.get_audio_data()
                    logger.info(f"Processing audio buffer: {len(audio_data)} bytes")
                    
                    # Simple test response to verify pipeline
                    if len(audio_data) > 1000 and not hasattr(buffer, 'last_response_time'):
                        logger.info("Audio detected - sending test response")
                        
                        # Generate simple test response
                        test_response = "I heard you! This may sound distorted due to audio format issues."
                        
                        # Stream test response back with error handling
                        try:
                            await stream_speech_to_twilio(test_response, websocket, stream_sid)
                            logger.info("✅ Test response streamed successfully")
                            buffer.last_response_time = time.time()  # Rate limiting
                        except Exception as response_error:
                            logger.error(f"❌ Failed to stream test response: {response_error}")
                            fallback_triggered = True
                        
                        # Clear buffer after processing
                        buffer.clear()
                    elif hasattr(buffer, 'last_response_time') and (time.time() - buffer.last_response_time) < 10:
                        # Rate limit responses to every 10 seconds for testing
                        logger.debug("Skipping response due to rate limiting")
                        buffer.clear()
                    else:
                        logger.info(f"🚨 AUDIO DETECTED: {len(audio_data)} bytes (not responding due to threshold)")
                        buffer.clear()
                    
                    # # For now, respond to any audio activity to test the pipeline
                    # # But limit responses to prevent overwhelming the WebSocket
                    # if len(audio_data) > 2000 and not hasattr(buffer, 'last_response_time'):  # More substantial audio + rate limiting
                    #     logger.info("Audio detected - sending test response")
                    #     
                    #     # Generate simple test response
                    #     test_response = "I heard you! This is a test of real-time audio streaming."
                    #     
                    #     # Stream test response back with error handling
                    #     try:
                    #         await stream_speech_to_twilio(test_response, websocket, stream_sid)
                    #         logger.info("✅ Test response streamed successfully")
                    #         buffer.last_response_time = time.time()  # Rate limiting
                    #     except Exception as response_error:
                    #         logger.error(f"❌ Failed to stream test response: {response_error}")
                    #         fallback_triggered = True
                    #     
                    #     # Clear buffer after processing
                    #     buffer.clear()
                    # elif hasattr(buffer, 'last_response_time') and (time.time() - buffer.last_response_time) < 5:
                    #     # Rate limit responses to every 5 seconds
                    #     logger.debug("Skipping response due to rate limiting")
                    #     buffer.clear()
                
                logger.debug(f"Processed audio chunk: {len(audio_chunk)} bytes, buffer size: {len(buffer.chunks)}")
                
            elif data['event'] == 'closed':
                logger.info(f"Media stream closed: {stream_sid}")
                break
                
    except WebSocketDisconnect:
        logger.info("Media stream WebSocket disconnected")
    except Exception as e:
        logger.error(f"Media stream error: {e}")
    finally:
        if stream_sid:
            manager.disconnect(websocket, stream_sid)
            # Clean up audio buffer
            if stream_sid in audio_buffers:
                del audio_buffers[stream_sid]

@app.websocket("/coqui-stream")
async def handle_coqui_stream(websocket: WebSocket):
    """Handle Twilio Media Streams for Coqui TTS system"""
    stream_sid = None
    call_sid = None
    
    # Import Coqui components (lazy loading)
    try:
        from simple_tts import generate_simple_speech, initialize_simple_tts
        logger.info("✅ Simple TTS fallback loaded successfully")
        TTS_TYPE = "simple"
        generate_speech = generate_simple_speech
        initialize_tts = initialize_simple_tts
    except Exception as e:
        logger.error(f"❌ Failed to load Simple TTS fallback: {e}")
        await websocket.close()
        return
    
    # Keep original Coqui import for future use
    try:
        from coqui_tts import generate_coqui_speech, initialize_coqui_tts
        from whisper_transcription import (
            add_audio_for_transcription, 
            get_transcription, 
            cleanup_transcription_stream,
            initialize_whisper
        )
        from audio_utils import convert_wav_for_twilio, convert_twilio_to_wav, AudioConverter
        
        # Initialize systems on first connection
        logger.info(f"🔧 Initializing {TTS_TYPE.upper()} TTS system...")
        tts_ready = await initialize_tts()
        try:
            whisper_ready = await initialize_whisper("base")
        except:
            logger.warning("⚠️ Whisper initialization failed, continuing without transcription")
            whisper_ready = True
        
        if not tts_ready or not whisper_ready:
            logger.error("❌ Failed to initialize Coqui systems - falling back to ElevenLabs")
            # Could redirect to ElevenLabs system here
            return
            
    except ImportError as e:
        logger.error(f"❌ Coqui dependencies not available: {e}")
        logger.error("Install with: pip install TTS faster-whisper torch numpy")
        return
    
    try:
        await websocket.accept()
        logger.info("🧪 Coqui Media stream WebSocket accepted")
        
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            logger.debug(f"Coqui stream received: {data.get('event', 'unknown')}")
            
            if data['event'] == 'connected':
                logger.info("✅ Coqui Media stream connected")
                
            elif data['event'] == 'start':
                stream_sid = data['start']['streamSid']
                call_sid = data['start']['callSid']
                logger.info(f"🚀 Coqui Media stream started: {stream_sid} for call {call_sid}")
                
                # Send initial greeting via Coqui TTS
                greeting_text = f"Hey! This is Synthetic Jason using {TTS_TYPE} TTS. Testing the new voice streaming system... How does this sound?"
                
                try:
                    # Generate speech with Coqui TTS
                    audio_wav = await generate_speech(greeting_text)
                    if audio_wav:
                        # Convert to Twilio format and send
                        audio_b64 = convert_wav_for_twilio(audio_wav)
                        if audio_b64:
                            media_message = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {"payload": audio_b64}
                            }
                            await websocket.send_text(json.dumps(media_message))
                            logger.info("✅ Coqui greeting sent successfully")
                        else:
                            logger.error("❌ Failed to convert Coqui audio for Twilio")
                    else:
                        logger.error("❌ Coqui TTS failed to generate greeting")
                except Exception as tts_error:
                    logger.error(f"❌ Coqui TTS error: {tts_error}")
                
            elif data['event'] == 'media':
                # Extract stream_sid from media event if we don't have it
                if not stream_sid:
                    stream_sid = data.get('streamSid')
                    logger.info(f"🔍 Extracted stream_sid: {stream_sid}")
                
                # Receive μ-law audio from Twilio (8kHz, base64)
                audio_payload = data['media']['payload']
                mulaw_data = base64.b64decode(audio_payload)
                
                # Convert to PCM for Whisper
                pcm_data = AudioConverter.mulaw_to_pcm(mulaw_data)
                if pcm_data:
                    # Add to transcription buffer
                    add_audio_for_transcription(stream_sid, pcm_data, 8000)
                    
                    # Check for transcription
                    transcription = await get_transcription(stream_sid, 8000)
                    if transcription:
                        logger.info(f"🎤 Transcribed: '{transcription}'")
                        
                        # Generate AI response (reuse existing logic)
                        ai_response = await get_ai_response(transcription)
                        
                        # Generate speech with Coqui TTS
                        try:
                            audio_wav = await generate_speech(ai_response)
                            if audio_wav:
                                audio_b64 = convert_wav_for_twilio(audio_wav)
                                if audio_b64:
                                    media_message = {
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {"payload": audio_b64}
                                    }
                                    await websocket.send_text(json.dumps(media_message))
                                    logger.info(f"✅ Coqui response sent: '{ai_response[:50]}...'")
                        except Exception as response_error:
                            logger.error(f"❌ Failed to generate Coqui response: {response_error}")
                
                logger.debug(f"Processed Coqui audio chunk: {len(mulaw_data)} μ-law bytes")
                
            elif data['event'] == 'closed':
                logger.info(f"Coqui Media stream closed: {stream_sid}")
                break
                
    except WebSocketDisconnect:
        logger.info("Coqui Media stream WebSocket disconnected")
    except Exception as e:
        logger.error(f"Coqui Media stream error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
    finally:
        if stream_sid:
            cleanup_transcription_stream(stream_sid)
            logger.info(f"Coqui stream cleanup completed for {stream_sid}")


# ===== STREAMING DEBUG TEST SYSTEM =====
# Non-destructive testing system for debugging streaming audio
# Runs alongside production system without affecting it

@app.get("/test-streaming-status")
async def test_streaming_status():
    """Check if streaming test dependencies are available"""
    try:
        from simple_tts import generate_simple_speech
        simple_tts_available = True
    except ImportError:
        simple_tts_available = False
    
    import subprocess
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        ffmpeg_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        ffmpeg_available = False
    
    return {
        "status": "ready" if simple_tts_available and ffmpeg_available else "missing_deps",
        "simple_tts": simple_tts_available,
        "ffmpeg": ffmpeg_available,
        "test_endpoints": [
            "/test-streaming-status",
            "/test-audio-conversion",
            "/test-sine-wave", 
            "/test-coqui-analysis",
            "/test-websocket-debug",
            "/debug-voice-handler"
        ]
    }

@app.post("/test-audio-conversion")
async def test_audio_conversion():
    """Test 1: Coqui → WAV → Mulaw conversion pipeline"""
    try:
        from simple_tts import initialize_simple_tts, generate_simple_speech
        import subprocess
        import os
        
        test_text = "Testing streaming voice Jason - this should be crystal clear"
        logger.info(f"🧪 Test 1: Converting text '{test_text}'")
        
        # Initialize TTS first
        tts_ready = await initialize_simple_tts()
        if not tts_ready:
            return {"error": "Failed to initialize Simple TTS"}
        
        # 1. Generate with Simple TTS
        wav_data = await generate_simple_speech(test_text)
        if not wav_data:
            return {"error": "Simple TTS failed to generate audio"}
        
        # Save WAV
        wav_path = "/tmp/streaming_test_coqui.wav"
        with open(wav_path, 'wb') as f:
            f.write(wav_data)
        
        # 2. Try to convert to Twilio mulaw format (skip if FFmpeg not available)
        mulaw_path = "/tmp/streaming_test.ulaw"
        mulaw_size = 0
        format_info = "ffmpeg_not_available"
        
        # Check if ffmpeg exists
        ffmpeg_available = False
        for ffmpeg_path in ['/usr/local/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg', 'ffmpeg']:
            try:
                result = subprocess.run([ffmpeg_path, '-version'], capture_output=True, timeout=2)
                if result.returncode == 0:
                    ffmpeg_available = True
                    # Try conversion
                    result = subprocess.run([
                        ffmpeg_path, '-y', '-i', wav_path,
                        '-ar', '8000', '-ac', '1', '-f', 'mulaw', mulaw_path
                    ], capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        mulaw_size = os.path.getsize(mulaw_path)
                        # Probe final format
                        probe_result = subprocess.run([
                            'ffprobe', '-v', 'quiet', '-show_entries', 
                            'stream=codec_name,sample_rate,channels',
                            '-of', 'csv=p=0', mulaw_path
                        ], capture_output=True, text=True)
                        format_info = probe_result.stdout.strip() if probe_result.returncode == 0 else "unknown"
                    else:
                        format_info = f"conversion_failed: {result.stderr}"
                    break
            except:
                continue
        
        # 3. Analyze results
        wav_size = len(wav_data)
        
        result = {
            "status": "success",
            "test": "audio_conversion",
            "input_wav_bytes": wav_size,
            "output_mulaw_bytes": mulaw_size,
            "final_format": format_info,
            "ffmpeg_available": ffmpeg_available,
            "files": {
                "wav": wav_path
            },
            "test_commands": {
                "play_wav": f"afplay {wav_path}"
            }
        }
        
        if ffmpeg_available and mulaw_size > 0:
            result["compression_ratio"] = f"{mulaw_size/wav_size:.2f}" if wav_size > 0 else "N/A"
            result["files"]["mulaw"] = mulaw_path
            result["test_commands"]["play_mulaw"] = f"ffplay -f mulaw -ar 8000 -ac 1 {mulaw_path}"
        else:
            result["compression_ratio"] = "N/A (no conversion)"
            result["note"] = "Install ffmpeg to test mulaw conversion: brew install ffmpeg"
        
        return result
        
    except Exception as e:
        logger.error(f"Audio conversion test failed: {e}")
        return {"error": str(e)}

@app.post("/test-sine-wave")
async def test_sine_wave():
    """Test 3: Generate known-good mulaw audio for WebSocket testing"""
    try:
        import subprocess
        import base64
        import os
        
        # Generate sine wave directly in mulaw format
        sine_path = "/tmp/test_sine.ulaw"
        result = subprocess.run([
            'ffmpeg', '-y',
            '-f', 'lavfi', 
            '-i', 'sine=frequency=440:duration=2:sample_rate=8000',
            '-f', 'mulaw', sine_path
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            return {"error": f"Sine wave generation failed: {result.stderr}"}
        
        # Read and encode for WebSocket
        with open(sine_path, 'rb') as f:
            mulaw_data = f.read()
        
        payload = base64.b64encode(mulaw_data).decode('ascii')
        file_size = len(mulaw_data)
        
        return {
            "status": "success", 
            "test": "sine_wave",
            "mulaw_bytes": file_size,
            "base64_chars": len(payload),
            "file": sine_path,
            "payload_preview": payload[:100] + "...",
            "test_commands": {
                "play": f"ffplay -f mulaw -ar 8000 -ac 1 {sine_path}",
                "analyze": f"ffprobe -v quiet -show_streams {sine_path}"
            },
            "websocket_payload": {
                "event": "media",
                "streamSid": "TEST_STREAM_ID",
                "media": {"payload": payload}
            }
        }
        
    except Exception as e:
        logger.error(f"Sine wave test failed: {e}")
        return {"error": str(e)}

@app.post("/test-coqui-analysis") 
async def test_coqui_analysis():
    """Test 4: Analyze Simple TTS output format in detail"""
    try:
        from simple_tts import initialize_simple_tts, generate_simple_speech
        import subprocess
        import time
        
        # Initialize TTS first
        tts_ready = await initialize_simple_tts()
        if not tts_ready:
            return {"error": "Failed to initialize Simple TTS"}
        
        test_phrases = [
            "Hello",
            "This is a medium length test",
            "This is a much longer test phrase to analyze how Coqui handles extended speech generation"
        ]
        
        results = []
        
        for i, phrase in enumerate(test_phrases):
            start_time = time.time()
            
            # Generate audio
            wav_data = await generate_simple_speech(phrase)
            generation_time = time.time() - start_time
            
            if not wav_data:
                results.append({"phrase": phrase, "error": "Generation failed"})
                continue
            
            # Save and analyze
            wav_path = f"/tmp/coqui_analysis_{i}.wav"
            with open(wav_path, 'wb') as f:
                f.write(wav_data)
            
            # Detailed analysis with ffprobe
            probe_result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_streams', '-show_format', wav_path
            ], capture_output=True, text=True)
            
            analysis = {
                "phrase": phrase,
                "phrase_length": len(phrase),
                "generation_time": f"{generation_time:.3f}s",
                "wav_bytes": len(wav_data),
                "bytes_per_second": int(len(wav_data) / generation_time) if generation_time > 0 else 0,
                "file": wav_path
            }
            
            if probe_result.returncode == 0:
                import json
                probe_data = json.loads(probe_result.stdout)
                if 'streams' in probe_data and probe_data['streams']:
                    stream = probe_data['streams'][0]
                    analysis.update({
                        "sample_rate": stream.get('sample_rate', 'unknown'),
                        "channels": stream.get('channels', 'unknown'),
                        "codec": stream.get('codec_name', 'unknown'),
                        "bit_rate": stream.get('bit_rate', 'unknown'),
                        "duration": stream.get('duration', 'unknown')
                    })
            
            results.append(analysis)
        
        return {
            "status": "success",
            "test": "coqui_analysis", 
            "results": results,
            "summary": {
                "avg_generation_time": f"{sum(float(r['generation_time'][:-1]) for r in results if 'generation_time' in r) / len(results):.3f}s",
                "total_audio_bytes": sum(r.get('wav_bytes', 0) for r in results)
            }
        }
        
    except Exception as e:
        logger.error(f"Coqui analysis test failed: {e}")
        return {"error": str(e)}

@app.websocket("/test-websocket-debug")
async def test_websocket_debug(websocket: WebSocket):
    """Debug WebSocket for Twilio Media Streams - Fixed for Railway"""
    import os
    try:
        await websocket.accept()
        logger.error("🚀🚀🚀 TWILIO WEBSOCKET CONNECTED!!! 🚀🚀🚀")
        
        # Don't send initial message - wait for Twilio events
        # Twilio will send: connected, start, media, closed
        
        chunk_count = 0
        
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            
            event = data.get('event', 'unknown')
            logger.error(f"🔍🔍🔍 WEBSOCKET EVENT: {event} - Data: {list(data.keys())}")
            
            if event == 'test_sine_wave':
                # Send back the sine wave we generated earlier
                try:
                    sine_path = "/tmp/test_sine.ulaw"
                    if os.path.exists(sine_path):
                        with open(sine_path, 'rb') as f:
                            mulaw_data = f.read()
                        
                        # Send in chunks like Twilio would
                        chunk_size = 160  # 20ms of audio at 8kHz
                        chunks = [mulaw_data[i:i+chunk_size] for i in range(0, len(mulaw_data), chunk_size)]
                        
                        for chunk in chunks:
                            payload = base64.b64encode(chunk).decode('ascii')
                            response = {
                                "event": "debug_audio_chunk",
                                "chunk_number": chunk_count,
                                "payload_size": len(payload),
                                "audio_bytes": len(chunk),
                                "payload": payload
                            }
                            await websocket.send_text(json.dumps(response))
                            chunk_count += 1
                            await asyncio.sleep(0.02)  # 20ms delay
                        
                        await websocket.send_text(json.dumps({
                            "event": "debug_audio_complete",
                            "total_chunks": chunk_count,
                            "total_bytes": len(mulaw_data)
                        }))
                    else:
                        await websocket.send_text(json.dumps({
                            "event": "debug_error",
                            "message": "No sine wave file found - run /test-sine-wave first"
                        }))
                        
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "event": "debug_error", 
                        "message": f"Failed to send sine wave: {e}"
                    }))
            
            elif event == 'test_coqui_audio':
                # Test with Coqui generated audio
                text = data.get('text', 'Debug test message')
                try:
                    from simple_tts import generate_simple_speech
                    import subprocess
                    
                    # Generate and convert
                    wav_data = await generate_simple_speech(text)
                    if wav_data:
                        wav_path = "/tmp/debug_coqui.wav"
                        mulaw_path = "/tmp/debug_coqui.ulaw"
                        
                        with open(wav_path, 'wb') as f:
                            f.write(wav_data)
                        
                        result = subprocess.run([
                            'ffmpeg', '-y', '-i', wav_path,
                            '-ar', '8000', '-ac', '1', '-f', 'mulaw', mulaw_path
                        ], capture_output=True)
                        
                        if result.returncode == 0:
                            with open(mulaw_path, 'rb') as f:
                                mulaw_data = f.read()
                            
                            payload = base64.b64encode(mulaw_data).decode('ascii')
                            await websocket.send_text(json.dumps({
                                "event": "debug_coqui_audio",
                                "text": text,
                                "wav_bytes": len(wav_data),
                                "mulaw_bytes": len(mulaw_data),
                                "payload": payload
                            }))
                        else:
                            await websocket.send_text(json.dumps({
                                "event": "debug_error",
                                "message": f"Conversion failed: {result.stderr.decode()}"
                            }))
                    else:
                        await websocket.send_text(json.dumps({
                            "event": "debug_error",
                            "message": "Coqui generation failed"
                        }))
                        
                except Exception as e:
                    await websocket.send_text(json.dumps({
                        "event": "debug_error",
                        "message": f"Coqui test failed: {e}"
                    }))
            
            elif event == 'connected':
                logger.info("✅ Debug: Twilio Media Stream connected")
                
            elif event == 'start':
                stream_sid = data['start']['streamSid']
                call_sid = data['start']['callSid']
                logger.error(f"🚀🚀🚀 WEBSOCKET START EVENT - Stream: {stream_sid}, Call: {call_sid}")

                # Store stream info for later use
                websocket.stream_sid = stream_sid
                websocket.call_sid = call_sid
                websocket.audio_chunk_count = 0
                websocket.last_response_time = 0

                # Send greeting using ElevenLabs streaming with proper audio conversion
                logger.error("🔊 SENDING GREETING VIA ELEVENLABS STREAMING")
                test_message = "WebSocket is working! You should hear this message clearly with proper audio conversion."

                try:
                    # Use the production-ready stream_speech_to_twilio function
                    # This handles ElevenLabs WebSocket + MP3 to µ-law conversion
                    await stream_speech_to_twilio(test_message, websocket, stream_sid)
                    logger.error("✅✅✅ SENT AUDIO TO TWILIO VIA ELEVENLABS - YOU SHOULD HEAR THIS!")

                except Exception as e:
                    logger.error(f"❌❌❌ ELEVENLABS STREAMING ERROR: {e}")
                    import traceback
                    logger.error(f"FULL TRACEBACK: {traceback.format_exc()}")
            
            elif event == 'media':
                # Handle incoming audio from caller
                stream_sid = data.get('streamSid', getattr(websocket, 'stream_sid', 'unknown'))
                audio_payload = data['media']['payload']
                audio_chunk = base64.b64decode(audio_payload)
                
                # Initialize counters if not present
                if not hasattr(websocket, 'audio_chunk_count'):
                    websocket.audio_chunk_count = 0
                    websocket.last_response_time = 0
                
                websocket.audio_chunk_count += 1
                
                # Log every 10 chunks so we know audio is coming in
                if websocket.audio_chunk_count % 10 == 0:
                    logger.error(f"📥📥📥 RECEIVED {websocket.audio_chunk_count} AUDIO CHUNKS - {len(audio_chunk)} bytes")
                
                # Respond after receiving substantial audio - every 10 chunks (roughly every 0.2 seconds)
                current_time = time.time()
                if (websocket.audio_chunk_count % 10 == 0 and
                    current_time - websocket.last_response_time > 1):

                    logger.error(f"🎤🎤🎤 TRIGGERING RESPONSE AFTER {websocket.audio_chunk_count} CHUNKS")

                    try:
                        responses = [
                            "I hear you loud and clear!",
                            "Yes, I can hear you talking!",
                            "This is working perfectly!",
                            "Great audio quality!",
                            "Keep talking, I'm listening!"
                        ]
                        response_text = responses[websocket.audio_chunk_count // 10 % len(responses)]

                        logger.error(f"🔊🔊🔊 GENERATING RESPONSE: '{response_text}'")

                        # Use ElevenLabs streaming with proper audio conversion
                        await stream_speech_to_twilio(response_text, websocket, stream_sid)
                        websocket.last_response_time = current_time
                        logger.error(f"✅ Debug: Sent response '{response_text}' after {websocket.audio_chunk_count} chunks")

                    except Exception as e:
                        logger.error(f"❌ Debug: Response generation failed - {e}")
                        import traceback
                        logger.error(f"Full response error: {traceback.format_exc()}")
            
            elif event == 'closed':
                logger.info("🔍 Debug: Media stream closed")
                break
                
            elif event == 'ping':
                await websocket.send_text(json.dumps({
                    "event": "pong",
                    "timestamp": time.time()
                }))
            
    except WebSocketDisconnect:
        logger.info("🔍 Debug WebSocket disconnected")
    except Exception as e:
        logger.error(f"Debug WebSocket error: {e}")

@app.api_route("/debug-voice-handler", methods=["GET", "POST"])
async def debug_voice_handler(request: Request):
    """Debug TwiML handler - now using working WebSocket streaming!"""
    try:
        form_data = await request.form()
        speech_result = form_data.get('SpeechResult', '')
        from_number = form_data.get('From', 'unknown')
        call_sid = form_data.get('CallSid', 'unknown')
        
        response = VoiceResponse()
        
        if not speech_result:
            # Initial call - no speech yet
            greeting_text = "Hello! This is the debug voice system. I can generate crystal clear audio. Please say something and I will respond."
            
            # Try to generate with Simple TTS for clear audio
            try:
                from simple_tts import initialize_simple_tts, generate_simple_speech
                
                tts_ready = await initialize_simple_tts()
                if tts_ready:
                    wav_data = await generate_simple_speech(greeting_text)
                    if wav_data:
                        # Save audio for serving
                        import hashlib
                        text_hash = hashlib.md5(greeting_text.encode()).hexdigest()
                        audio_cache[text_hash] = wav_data
                        audio_url = f"{config.BASE_URL}/audio/{text_hash}"
                        response.play(audio_url)
                        logger.info("✅ Debug: Generated greeting with Simple TTS")
                    else:
                        response.say(greeting_text, voice="Polly.Joanna")
                else:
                    response.say(greeting_text, voice="Polly.Joanna")
                    
            except Exception as e:
                logger.error(f"Debug TTS failed: {e}")
                response.say(greeting_text, voice="Polly.Joanna")
            
            # Listen for speech
            gather = response.gather(
                input='speech',
                action='/debug-voice-handler',
                method='POST',
                speech_timeout=3,
                timeout=15,
                enhanced=True
            )
            
        else:
            # User said something - respond!
            logger.info(f"🎤 Debug: User said '{speech_result}'")
            
            response_text = f"I heard you say: {speech_result}. That was crystal clear! Say something else and I'll respond again."
            
            # Generate response with Simple TTS
            try:
                from simple_tts import generate_simple_speech
                wav_data = await generate_simple_speech(response_text)
                if wav_data:
                    import hashlib
                    text_hash = hashlib.md5(response_text.encode()).hexdigest()
                    audio_cache[text_hash] = wav_data
                    audio_url = f"{config.BASE_URL}/audio/{text_hash}"
                    response.play(audio_url)
                    logger.info("✅ Debug: Generated response with Simple TTS")
                else:
                    response.say(response_text, voice="Polly.Joanna")
                    
            except Exception as e:
                logger.error(f"Debug response TTS failed: {e}")
                response.say(response_text, voice="Polly.Joanna")
            
            # Continue listening
            gather = response.gather(
                input='speech',
                action='/debug-voice-handler',
                method='POST', 
                speech_timeout=3,
                timeout=15,
                enhanced=True
            )
        
        # Timeout fallback
        response.say("Thanks for testing the debug system! The audio quality should be crystal clear.")
        response.hangup()
        
        logger.info("📞 Debug voice handler - using traditional TwiML approach")
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Debug voice handler error: {e}")
        response = VoiceResponse()
        response.say("Debug system error occurred")
        return Response(content=str(response), media_type="application/xml")

@app.api_route("/debug-websocket-voice", methods=["GET", "POST"])  
async def debug_websocket_voice_handler(request: Request):
    """WebSocket-only debug voice handler - now that we know WebSockets work!"""
    try:
        response = VoiceResponse()
        response.say("Connecting to working WebSocket streaming system...")
        
        # Connect to our fixed WebSocket
        connect = response.connect()
        ws_url = config.BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        debug_url = f"{ws_url}/test-websocket-debug"
        connect.stream(url=debug_url)
        
        logger.info("📞 WebSocket Debug voice handler - connecting to WORKING WebSocket")
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"WebSocket debug voice handler error: {e}")
        response = VoiceResponse()
        response.say("WebSocket system error occurred")
        return Response(content=str(response), media_type="application/xml")

@app.post("/test-static-killer")
async def test_static_killer_endpoint(request: Request):
    """
    Test endpoint for Static Killer audio conversion.
    Generate a sample audio file using proven FFmpeg pipeline.
    """
    try:
        from static_killer import convert_wav_static_free, save_test_audio
        from simple_tts import generate_simple_speech
        
        # Generate test audio using Simple TTS
        test_text = "Testing the Static Killer system. This should be crystal clear audio without any static or noise."
        wav_data = await generate_simple_speech(test_text)
        
        if not wav_data:
            return {"error": "Failed to generate test audio"}
        
        # Convert using Static Killer FFmpeg pipeline
        raw_mulaw = await convert_wav_static_free(wav_data)
        
        if not raw_mulaw:
            return {"error": "Static Killer conversion failed - check FFmpeg installation"}
        
        # Save test file for Audacity validation
        test_file = "/tmp/static_killer_test.ulaw"
        success = await save_test_audio(wav_data, test_file)
        
        return {
            "status": "success",
            "message": "Static Killer conversion completed",
            "original_wav_bytes": len(wav_data),
            "converted_mulaw_bytes": len(raw_mulaw),
            "test_file": test_file if success else None,
            "audacity_instructions": {
                "1": "Open Audacity",
                "2": "File → Import → Raw Data",
                "3": f"Select: {test_file}",
                "4": "Set: Encoding=μ-law, Sample rate=8000, Channels=Mono", 
                "5": "Click Import and play - should be crystal clear!"
            }
        }
        
    except ImportError as e:
        return {"error": f"Static Killer not available: {e}"}
    except Exception as e:
        logger.error(f"Static Killer test failed: {e}")
        return {"error": str(e)}

@app.websocket("/static-killer-stream")
async def static_killer_stream(websocket: WebSocket):
    """
    WebSocket endpoint for testing static-free Twilio streaming.
    Uses FFmpeg pipeline instead of Python audioop conversion.
    """
    stream_sid = None
    call_sid = None
    
    try:
        from static_killer import convert_wav_static_free, chunk_for_streaming, create_media_payload
        from simple_tts import generate_simple_speech
        
        await websocket.accept()
        logger.info("🔪 Static Killer WebSocket accepted")
        
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            logger.debug(f"Static Killer received: {data['event']}")
            
            if data['event'] == 'connected':
                logger.info("✅ Static Killer Media stream connected")
                
            elif data['event'] == 'start':
                stream_sid = data['start']['streamSid']
                call_sid = data['start']['callSid']
                logger.info(f"🚀 Static Killer stream started: {stream_sid} for call {call_sid}")
                
                # Send greeting using Static Killer conversion
                greeting_text = "Hello! This is the Static Killer system. The audio should be crystal clear without any static or noise."
                
                try:
                    # Generate speech
                    wav_data = await generate_simple_speech(greeting_text)
                    if not wav_data:
                        logger.error("❌ Failed to generate greeting audio")
                        continue
                    
                    # Convert using Static Killer FFmpeg pipeline  
                    raw_mulaw = await convert_wav_static_free(wav_data)
                    if not raw_mulaw:
                        logger.error("❌ Static Killer conversion failed")
                        continue
                    
                    # Chunk for optimal streaming
                    chunks = chunk_for_streaming(raw_mulaw)
                    
                    # Stream each chunk with proper timing
                    for i, chunk in enumerate(chunks):
                        payload = create_media_payload(chunk, stream_sid)
                        await websocket.send_text(json.dumps(payload))
                        
                        # Delay for proper streaming (160ms per chunk)
                        await asyncio.sleep(0.16)
                    
                    logger.info(f"✅ Static Killer: Streamed {len(chunks)} chunks ({len(raw_mulaw)} total bytes)")
                    
                except Exception as e:
                    logger.error(f"❌ Static Killer greeting failed: {e}")
                
            elif data['event'] == 'media':
                # Could process incoming audio here for bidirectional testing
                logger.debug("📥 Static Killer received audio (not processed in test)")
                
            elif data['event'] == 'closed':
                logger.info(f"🔪 Static Killer stream closed: {stream_sid}")
                break
                
    except WebSocketDisconnect:
        logger.info("Static Killer WebSocket disconnected")
    except ImportError:
        logger.error("❌ Static Killer dependencies not available")
        await websocket.close()
    except Exception as e:
        logger.error(f"Static Killer stream error: {e}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")

@app.post("/test-audio-play") 
async def test_audio_play_endpoint():
    """
    Test endpoint that generates audio file for <Play> testing.
    Use this to verify audio quality before streaming tests.
    """
    try:
        from simple_tts import generate_simple_speech
        import tempfile
        
        # Generate test audio
        test_text = "This is a direct audio playback test. If you hear static here, the issue is in audio generation, not streaming."
        wav_data = await generate_simple_speech(test_text)
        
        if not wav_data:
            return {"error": "Failed to generate audio"}
        
        # Save as temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            f.write(wav_data)
            temp_path = f.name
        
        return {
            "status": "success",
            "message": "Test audio generated",
            "file_size": len(wav_data),
            "temp_file": temp_path,
            "twiml_test": f'<Response><Play>{config.BASE_URL}/audio/test</Play></Response>',
            "instructions": "Use this in TwiML to test direct playback (bypass streaming)"
        }
        
    except Exception as e:
        logger.error(f"Audio play test failed: {e}")
        return {"error": str(e)}

@app.api_route("/static-killer-voice", methods=["GET", "POST"])  
async def static_killer_voice_handler(request: Request):
    """
    TwiML handler for Static Killer testing.
    Use this as your Twilio webhook URL to test the static-free system.
    """
    try:
        response = VoiceResponse()
        
        # Add a simple greeting and connect to Static Killer stream
        response.say("Connecting to Static Killer test system...")
        
        # Connect to Static Killer WebSocket
        connect = response.connect()
        ws_url = config.BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        stream_url = f"{ws_url}/static-killer-stream"
        connect.stream(url=stream_url)
        
        logger.info("📞 Static Killer call initiated")
        return Response(content=str(response), media_type="application/xml")
        
    except Exception as e:
        logger.error(f"Static Killer voice handler error: {e}")
        response = VoiceResponse()
        response.say("Sorry, the Static Killer test system is not available.")
        return Response(content=str(response), media_type="application/xml")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))