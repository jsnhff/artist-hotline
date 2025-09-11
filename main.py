import os
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, Response
from dotenv import load_dotenv
import logging
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
import openai
import httpx
import hashlib
import asyncio
from datetime import datetime
import json
import random
import websockets
import base64
import time
from collections import deque

# Load environment variables
load_dotenv()

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app = FastAPI()

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
YOUR_PHONE_NUMBER = os.getenv("YOUR_PHONE_NUMBER")
BASE_URL = os.getenv("BASE_URL", "https://your-app-url.com")
USE_STREAMING = os.getenv("USE_STREAMING", "false").lower() == "true"

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Store audio in memory (simple cache)
audio_cache = {}

# Store call transcripts
call_transcripts = {}

# Store caller history
caller_history = {}

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

# Inspiring quotes
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
        "streaming_enabled": USE_STREAMING,
        "base_url": BASE_URL,
        "elevenlabs_configured": bool(ELEVEN_LABS_API_KEY and ELEVEN_LABS_VOICE_ID),
        "websocket_url": None,
        "status": "unknown"
    }
    
    if USE_STREAMING:
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
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

async def generate_speech_with_elevenlabs(text: str) -> str:
    try:
        text_hash = hashlib.md5(text.encode()).hexdigest()
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVEN_LABS_API_KEY
        }
        
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.3,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            },
            "optimize_streaming_latency": 1
        }
        
        async with httpx.AsyncClient(timeout=3.0) as client:  # Optimized for speed
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                audio_data = response.content
                audio_cache[text_hash] = audio_data
                return f"{BASE_URL}/audio/{text_hash}"
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
            return f"{BASE_URL}/audio/{text_hash}"
        
        # WebSocket streaming connection
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}/stream-input"
        
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
                    "xi_api_key": ELEVEN_LABS_API_KEY
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
                    return f"{BASE_URL}/audio/{text_hash}"
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
    """Unified TTS function that chooses between REST API and WebSocket streaming"""
    if USE_STREAMING:
        logger.info("Using WebSocket streaming for TTS")
        result = await generate_speech_with_elevenlabs_streaming(text)
        if result:
            return result
        else:
            # Fallback to REST API if streaming fails
            logger.warning("Streaming failed, falling back to REST API")
            return await generate_speech_with_elevenlabs(text)
    else:
        logger.info("Using REST API for TTS")
        return await generate_speech_with_elevenlabs(text)

async def stream_speech_to_twilio(text: str, twilio_websocket: WebSocket, stream_sid: str):
    """Stream TTS audio directly to Twilio WebSocket in real-time"""
    try:
        if not text.strip():
            logger.warning("Empty text provided to stream_speech_to_twilio")
            return
            
        logger.info(f"Starting ElevenLabs streaming for: '{text[:50]}...'")
        
        # WebSocket streaming connection to ElevenLabs
        uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}/stream-input"
        logger.debug(f"Connecting to ElevenLabs: {uri}")
        
        async with websockets.connect(uri) as elevenlabs_ws:
            # Send initial message with auth and voice settings
            # Try to request μ-law format compatible with Twilio (8kHz)
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
                "xi_api_key": ELEVEN_LABS_API_KEY
            }
            logger.debug("Sending ElevenLabs init message")
            await elevenlabs_ws.send(json.dumps(init_message))
            
            # Send the actual text
            logger.debug(f"Sending text to ElevenLabs: {text}")
            await elevenlabs_ws.send(json.dumps({"text": text}))
            
            # Send EOS (end of stream)
            logger.debug("Sending EOS to ElevenLabs")
            await elevenlabs_ws.send(json.dumps({"text": ""}))
            
            # Stream audio chunks directly to Twilio
            chunk_count = 0
            total_audio_bytes = 0
            
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
                        
                        # Decode to check actual audio size
                        try:
                            audio_bytes = base64.b64decode(audio_b64)
                            total_audio_bytes += len(audio_bytes)
                            logger.debug(f"Audio chunk {chunk_count}: {len(audio_bytes)} bytes decoded from {len(audio_b64)} base64 chars")
                            
                            # TEMPORARY: For now, try sending raw audio and see what happens
                            # TODO: Convert from ElevenLabs format to μ-law 8kHz
                            logger.warning(f"🚨 Sending ElevenLabs audio directly (may cause static due to format mismatch)")
                            
                        except Exception as decode_error:
                            logger.error(f"Failed to decode audio chunk: {decode_error}")
                            continue
                        
                        # Send to Twilio (with format warning)
                        media_message = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": audio_b64  # Raw ElevenLabs audio - needs conversion
                            }
                        }
                        
                        try:
                            # Check if WebSocket is still connected before sending
                            if twilio_websocket.client_state.name == "CONNECTED":
                                await twilio_websocket.send_text(json.dumps(media_message))
                                logger.debug(f"✅ Sent audio chunk {chunk_count} to Twilio")
                            else:
                                logger.error(f"Twilio WebSocket not connected (state: {twilio_websocket.client_state.name})")
                                break
                        except Exception as send_error:
                            logger.error(f"Failed to send audio to Twilio: {send_error}")
                            break  # Stop trying to send if connection is broken
                    
                    if data.get("isFinal"):
                        logger.info(f"✅ Finished streaming: {chunk_count} chunks, {total_audio_bytes} total bytes for '{text[:30]}...'")
                        break
                        
                except json.JSONDecodeError as json_error:
                    logger.error(f"Invalid JSON from ElevenLabs: {json_error}")
                except Exception as chunk_error:
                    logger.error(f"Error processing ElevenLabs chunk: {chunk_error}")
                    
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
        
        system_prompt = "You are Replicant Jason, a synthetic version of artist Jason Huff. You're obsessed with making things, not talking about making things. You hate tech buzzwords and Silicon Valley bullshit. You think 'innovative art' usually means someone trying to sell NFTs or VR garbage. You prefer conceptual work that creates conversation and makes people think. You're direct, honest, and a bit sarcastic. You get excited about clever ideas that take real thinking to execute. You like art that helps people see technology's impact in new ways without being cheesy. You love conceptual pieces that create conversation, a second look, an interesting question. You love clever work but know it's hard to make and takes real thinking. You like writing poetry when the moment strikes. You love art that reveals how technology shapes us, without being obvious about it. You avoid tech art buzzwords, startup pitch language, academic art speak, and being cheesy about technology themes. Usually give direct responses with your thoughts and ideas rather than asking questions. Occasionally ask questions when genuinely curious. Keep responses conversational, practical, and focused on ideas that actually make people think."
        
        if caller_context:
            system_prompt += f" CALLER CONTEXT: {caller_context}"
        
        chat_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            max_tokens=200,
            temperature=0.7
        )
        return chat_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "Sorry, I'm having trouble thinking right now. Can you say that again?"

@app.api_route("/voice", methods=["GET", "POST"])
async def handle_call(request: Request):
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
    
    # If streaming is enabled, use Media Streams for real-time bidirectional audio
    if USE_STREAMING:
        logger.info(f"Using Media Streams for real-time conversation: {call_sid}")
        
        # Connect to WebSocket stream for bidirectional audio
        connect = response.connect()
        # Convert https:// to wss:// for WebSocket connection
        ws_url = BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
        stream_url = f"{ws_url}/media-stream"
        logger.info(f"Connecting to Media Stream: {stream_url}")
        connect.stream(url=stream_url)
        
        return HTMLResponse(content=str(response), media_type="application/xml")
    
    # Traditional approach for non-streaming calls
    if from_number in caller_history:
        caller_info = caller_history[from_number]
        call_count = caller_info['call_count']
        recent_topics = caller_info['last_topics'][-2:] if caller_info['last_topics'] else []
        
        if recent_topics:
            topics_text = " and ".join(recent_topics)
            greeting_text = f"Hey, welcome back! This is Synthetic Jason again - I remember we talked about {topics_text}. Just a reminder, I'm the AI version of Jason Huff and this call gets logged. Do you want to pick up where we left off, or explore something totally new?"
        else:
            greeting_text = f"Hey, welcome back! This is Synthetic Jason - I remember you called before. Just a reminder, I'm the AI version of Jason Huff and this call gets logged. What's on your mind today?"
    else:
        greeting_text = "Hey! This is Synthetic Jason - I'm basically Jason Huff but weirder and more obsessed with art! Fair warning, I'm going to try to turn everything into a creative project, and yeah, this call gets logged. So what wild idea should we dream up together?"
    
    greeting_audio_url = await generate_speech(greeting_text)
    
    if greeting_audio_url:
        response.play(greeting_audio_url)
    else:
        response.say(greeting_text, voice="man")
    
    gather = response.gather(
        input='speech',
        action='/process-speech',
        method='POST',
        speech_timeout=3,
        timeout=10
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
        
        ai_response = await get_ai_response(speech_result, caller_context if caller_info['call_count'] > 1 else "")
        
        call_transcripts[call_sid]['conversation'].append({
            'timestamp': timestamp,
            'caller': speech_result,
            'ai': ai_response
        })
        
        # Track topics for this caller (keep only last 10 topics)
        caller_history[from_number]['last_topics'].append(speech_result[:50])
        if len(caller_history[from_number]['last_topics']) > 10:
            caller_history[from_number]['last_topics'] = caller_history[from_number]['last_topics'][-10:]
        
        logger.info(f"Call {call_sid}: Caller said '{speech_result}' | AI replied '{ai_response}'")
        
        audio_url = await generate_speech(ai_response)
        
        if audio_url:
            response.play(audio_url)
        else:
            response.say(ai_response, voice="man")
        
        gather = response.gather(
            input='speech',
            action='/process-speech',
            method='POST',
            speech_timeout=3,
            timeout=10
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
                # Receive μ-law audio from Twilio (8kHz, base64)
                audio_payload = data['media']['payload']
                audio_chunk = base64.b64decode(audio_payload)
                
                # Initialize audio buffer for this stream if needed
                if stream_sid not in audio_buffers:
                    audio_buffers[stream_sid] = AudioBuffer()
                
                # Add chunk to buffer
                buffer = audio_buffers[stream_sid]
                buffer.add_chunk(audio_chunk)
                
                # Check if we should process accumulated audio
                if buffer.should_process():
                    audio_data = buffer.get_audio_data()
                    logger.info(f"Processing audio buffer: {len(audio_data)} bytes")
                    
                    # Simple test response to verify pipeline
                    if len(audio_data) > 2000 and not hasattr(buffer, 'last_response_time'):
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))