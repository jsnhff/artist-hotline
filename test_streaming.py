#!/usr/bin/env python3
"""
Simple test script for ElevenLabs WebSocket streaming
"""
import asyncio
import os
import json
import base64
import websockets
from dotenv import load_dotenv

load_dotenv()

ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")

async def test_streaming():
    if not ELEVEN_LABS_API_KEY or not ELEVEN_LABS_VOICE_ID:
        print("❌ Missing ElevenLabs API key or Voice ID")
        return False
    
    print("🔗 Testing ElevenLabs WebSocket streaming...")
    
    uri = f"wss://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}/stream-input"
    test_text = "Hello! This is a test of WebSocket streaming."
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket connection established")
            
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
            print("✅ Initial message with auth sent")
            
            # Send the actual text
            await websocket.send(json.dumps({"text": test_text}))
            print(f"✅ Text sent: {test_text}")
            
            # Send EOS (end of stream)  
            await websocket.send(json.dumps({"text": ""}))
            print("✅ End of stream sent")
            
            # Collect audio chunks
            audio_chunks = []
            chunk_count = 0
            
            async for message in websocket:
                data = json.loads(message)
                print(f"📨 Received message: {data}")
                
                # Check for errors
                if "error" in data:
                    print(f"❌ API Error: {data['error']}")
                    return False
                
                if data.get("audio"):
                    audio_chunk = base64.b64decode(data["audio"])
                    audio_chunks.append(audio_chunk)
                    chunk_count += 1
                    print(f"📦 Received audio chunk {chunk_count}: {len(audio_chunk)} bytes")
                
                if data.get("isFinal"):
                    print("✅ Final message received")
                    break
            
            if audio_chunks:
                total_audio = b''.join(audio_chunks)
                print(f"🎵 Total audio generated: {len(total_audio)} bytes in {chunk_count} chunks")
                return True
            else:
                print("❌ No audio chunks received")
                return False
                
    except websockets.exceptions.WebSocketException as e:
        print(f"❌ WebSocket connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_streaming())
    if success:
        print("\n🎉 WebSocket streaming test passed!")
    else:
        print("\n💥 WebSocket streaming test failed!")