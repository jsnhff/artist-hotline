"""
OpenAI Realtime API handler for ultra-low latency voice conversations.

This implementation uses OpenAI's Realtime API for ~500ms-1s latency responses,
compared to 4-5s with the Whisper + GPT approach.

Cost: ~$0.06/minute vs $0.02/minute for Whisper+GPT
"""

import asyncio
import json
import base64
import logging
import websockets
from fastapi import WebSocket

logger = logging.getLogger(__name__)

# OpenAI Realtime API WebSocket URL
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"

async def handle_realtime_api_call(twilio_ws: WebSocket, stream_sid: str, openai_api_key: str):
    """
    Handle a call using OpenAI Realtime API with ultra-low latency.

    This creates a bidirectional audio stream:
    Twilio → OpenAI Realtime API → Twilio

    The Realtime API handles:
    - Voice Activity Detection (VAD)
    - Speech-to-Text (streaming)
    - Response generation (GPT-4o)
    - Text-to-Speech (streaming)

    All in one integrated pipeline with ~500ms latency!
    """

    try:
        # Connect to OpenAI Realtime API
        async with websockets.connect(
            OPENAI_REALTIME_URL,
            additional_headers={
                "Authorization": f"Bearer {openai_api_key}",
                "OpenAI-Beta": "realtime=v1"
            }
        ) as openai_ws:
            logger.info("🚀 Connected to OpenAI Realtime API")

            # Send session configuration
            await send_session_update(openai_ws)

            # Send initial greeting using the same voice as your current setup
            greeting_text = "Hey! This is Synthetic Jason... I'm basically Jason Huff but weirder and more obsessed with art. What wild idea should we dream up together?"
            await send_greeting(openai_ws, greeting_text)

            # Create bidirectional audio streaming tasks
            async def stream_twilio_to_openai():
                """Forward audio from Twilio to OpenAI"""
                try:
                    chunk_count = 0
                    async for message in twilio_ws.iter_text():
                        data = json.loads(message)

                        if data.get('event') == 'media':
                            chunk_count += 1
                            if chunk_count % 100 == 0:
                                logger.info(f"📤 Sent {chunk_count} audio chunks to OpenAI")
                            # Convert µ-law to PCM16 for OpenAI
                            import audioop

                            audio_payload = data['media']['payload']

                            # Decode base64 µ-law
                            mulaw_data = base64.b64decode(audio_payload)

                            # Convert µ-law 8kHz to PCM16
                            pcm_data = audioop.ulaw2lin(mulaw_data, 2)  # 2 bytes per sample

                            # Resample from 8kHz to 24kHz (OpenAI expects 24kHz for PCM16)
                            pcm_24k = audioop.ratecv(pcm_data, 2, 1, 8000, 24000, None)[0]

                            # Encode to base64
                            pcm_b64 = base64.b64encode(pcm_24k).decode('utf-8')

                            # Send to OpenAI
                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": pcm_b64
                            }
                            await openai_ws.send(json.dumps(audio_append))

                        elif data.get('event') == 'stop':
                            logger.info("Twilio stream stopped")
                            break

                except Exception as e:
                    logger.error(f"Error streaming Twilio → OpenAI: {e}")

            async def stream_openai_to_twilio():
                """Forward audio responses from OpenAI back to Twilio"""
                try:
                    response_count = 0
                    async for message in openai_ws:
                        response = json.loads(message)

                        # Log all events for debugging
                        event_type = response.get('type', 'unknown')
                        if event_type not in ['response.audio.delta', 'input_audio_buffer.speech_started', 'input_audio_buffer.speech_stopped']:
                            logger.info(f"📥 OpenAI event: {event_type}")

                        # Handle different event types
                        if response.get('type') == 'response.audio.delta':
                            response_count += 1
                            if response_count % 10 == 0:
                                logger.info(f"📥 Received {response_count} audio responses from OpenAI")
                            # OpenAI is sending PCM16 24kHz audio data
                            import audioop

                            audio_payload = response.get('delta', '')
                            if not audio_payload:
                                continue

                            # Decode base64 PCM16
                            pcm_24k = base64.b64decode(audio_payload)

                            # Resample from 24kHz to 8kHz
                            pcm_8k = audioop.ratecv(pcm_24k, 2, 1, 24000, 8000, None)[0]

                            # Convert PCM16 to µ-law
                            mulaw_data = audioop.lin2ulaw(pcm_8k, 2)

                            # Encode to base64
                            mulaw_b64 = base64.b64encode(mulaw_data).decode('utf-8')

                            # Send to Twilio
                            media_message = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": mulaw_b64
                                }
                            }
                            await twilio_ws.send_json(media_message)

                        elif response.get('type') == 'response.audio_transcript.done':
                            # Log what the AI said
                            transcript = response.get('transcript', '')
                            logger.info(f"🤖 AI said: {transcript}")

                        elif response.get('type') == 'conversation.item.input_audio_transcription.completed':
                            # Log what the user said
                            transcript = response.get('transcript', '')
                            logger.info(f"👤 User said: {transcript}")

                        elif response.get('type') == 'error':
                            error = response.get('error', {})
                            logger.error(f"OpenAI Realtime API error: {error}")

                except Exception as e:
                    logger.error(f"Error streaming OpenAI → Twilio: {e}")

            # Run both directions simultaneously
            await asyncio.gather(
                stream_twilio_to_openai(),
                stream_openai_to_twilio()
            )

    except Exception as e:
        logger.error(f"Realtime API error: {e}")
        raise


async def send_greeting(openai_ws, text: str):
    """
    Send an initial greeting message that the AI will speak.

    This triggers an immediate response from the AI with the greeting text.
    """
    greeting_message = {
        "type": "conversation.item.create",
        "item": {
            "type": "message",
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": f"[SYSTEM: Say this greeting to the user] {text}"
                }
            ]
        }
    }
    await openai_ws.send(json.dumps(greeting_message))

    # Trigger response generation
    response_create = {
        "type": "response.create"
    }
    await openai_ws.send(json.dumps(response_create))
    logger.info("🔊 Sent greeting to Realtime API")


async def send_session_update(openai_ws):
    """
    Configure the OpenAI Realtime API session.

    This sets up:
    - Audio format (µ-law for Twilio compatibility)
    - Voice Activity Detection (server-side)
    - System instructions (personality)
    - Voice settings
    """

    session_update = {
        "type": "session.update",
        "session": {
            "modalities": ["text", "audio"],
            "instructions": """You are Synthetic Jason, an AI version of artist Jason Huff.
You're weird, obsessed with art, love discussing creative ideas, and have a quirky personality.
Keep responses conversational and under 30 words.
You already introduced yourself at the start of the call, so don't introduce yourself again.""",

            "voice": "shimmer",  # Options: alloy (neutral), echo (deep), shimmer (energetic)

            "input_audio_format": "pcm16",  # Twilio sends µ-law but we'll convert
            "output_audio_format": "pcm16",  # We'll convert back to µ-law

            "input_audio_transcription": {
                "model": "whisper-1"
            },

            "turn_detection": {
                "type": "server_vad",  # Server-side Voice Activity Detection
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 500  # Respond after 500ms silence
            },

            "temperature": 0.9,
            "max_response_output_tokens": 150
        }
    }

    await openai_ws.send(json.dumps(session_update))
    logger.info("✅ Sent Realtime API session configuration")
