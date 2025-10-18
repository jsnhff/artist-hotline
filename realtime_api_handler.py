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

            # Create bidirectional audio streaming tasks
            async def stream_twilio_to_openai():
                """Forward audio from Twilio to OpenAI"""
                try:
                    async for message in twilio_ws.iter_text():
                        data = json.loads(message)

                        if data.get('event') == 'media':
                            # Forward µ-law audio to OpenAI
                            audio_payload = data['media']['payload']
                            audio_append = {
                                "type": "input_audio_buffer.append",
                                "audio": audio_payload  # Already base64 encoded µ-law
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
                    async for message in openai_ws:
                        response = json.loads(message)

                        # Handle different event types
                        if response.get('type') == 'response.audio.delta':
                            # OpenAI is sending audio data
                            audio_payload = response.get('delta', '')

                            # Send to Twilio
                            media_message = {
                                "event": "media",
                                "streamSid": stream_sid,
                                "media": {
                                    "payload": audio_payload
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

            "voice": "alloy",  # Options: alloy, echo, shimmer

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
