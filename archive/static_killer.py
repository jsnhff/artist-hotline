#!/usr/bin/env python3
"""
Static Killer: FFmpeg-based audio conversion for zero-static Twilio streaming.

This module implements the proven audio conversion pipeline from the Static Hell guide,
using FFmpeg to generate headerless raw μ-law data that Twilio Media Streams expects.
"""

import asyncio
import base64
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class StaticKillerConverter:
    """
    FFmpeg-based audio converter that eliminates static in Twilio Media Streams.
    
    Uses the verified conversion pipeline to generate pure raw μ-law data
    without headers or padding that cause static issues.
    """
    
    def __init__(self):
        self.chunk_duration_ms = 160  # 160ms chunks as recommended
        self.sample_rate = 8000  # Twilio requirement
        self.chunk_size_bytes = int((self.sample_rate * self.chunk_duration_ms) / 1000)
        logger.info("🔪 Static Killer initialized - preparing to eliminate audio static")
    
    async def wav_to_raw_mulaw(self, wav_data: bytes) -> Optional[bytes]:
        """
        Convert WAV audio to raw μ-law using the proven FFmpeg pipeline.
        
        This is the exact conversion method from the Static Hell guide:
        - Converts to 8kHz mono
        - Outputs headerless raw μ-law format
        - No Python audio processing (which often adds headers/padding)
        
        Args:
            wav_data: Input WAV audio data
            
        Returns:
            Raw μ-law bytes ready for Twilio, or None if conversion failed
        """
        try:
            # Create temporary files for FFmpeg processing
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as input_file:
                input_file.write(wav_data)
                input_path = input_file.name
            
            with tempfile.NamedTemporaryFile(suffix='.ulaw', delete=False) as output_file:
                output_path = output_file.name
            
            # The proven FFmpeg command from Static Hell guide
            ffmpeg_cmd = [
                'ffmpeg',
                '-hide_banner',
                '-loglevel', 'error',
                '-i', input_path,
                '-ar', '8000',      # 8kHz sample rate
                '-ac', '1',         # Mono
                '-f', 'mulaw',      # Raw μ-law format (no headers!)
                '-y',               # Overwrite output
                output_path
            ]
            
            # Run FFmpeg conversion
            result = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                logger.error(f"❌ FFmpeg conversion failed: {error_msg}")
                return None
            
            # Read the generated raw μ-law data
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                with open(output_path, 'rb') as f:
                    raw_mulaw_data = f.read()
                
                logger.info(f"✅ Static Killer: Converted {len(wav_data)} WAV bytes → {len(raw_mulaw_data)} raw μ-law bytes")
                return raw_mulaw_data
            else:
                logger.error("❌ FFmpeg output file is empty or missing")
                return None
                
        except FileNotFoundError:
            logger.error("❌ FFmpeg not found - install with: brew install ffmpeg (macOS) or apt install ffmpeg (Linux)")
            return None
        except Exception as e:
            logger.error(f"❌ Static Killer conversion failed: {e}")
            return None
        finally:
            # Clean up temporary files
            for path in [input_path, output_path]:
                try:
                    if 'path' in locals() and os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
    
    def chunk_raw_mulaw(self, raw_mulaw_data: bytes) -> list[bytes]:
        """
        Split raw μ-law data into proper chunks for Twilio streaming.
        
        Creates 160ms chunks (~1280 bytes raw) as recommended for optimal
        streaming performance with minimal latency.
        
        Args:
            raw_mulaw_data: Raw μ-law audio bytes
            
        Returns:
            List of audio chunks ready for base64 encoding
        """
        if not raw_mulaw_data:
            return []
        
        chunks = []
        for i in range(0, len(raw_mulaw_data), self.chunk_size_bytes):
            chunk = raw_mulaw_data[i:i + self.chunk_size_bytes]
            chunks.append(chunk)
        
        logger.debug(f"🔪 Chunked {len(raw_mulaw_data)} bytes into {len(chunks)} chunks of ~{self.chunk_size_bytes} bytes each")
        return chunks
    
    def create_twilio_media_payload(self, raw_chunk: bytes, stream_sid: str) -> dict:
        """
        Create properly formatted Twilio Media Stream payload.
        
        Uses the exact format from the Static Hell guide that's verified to work.
        
        Args:
            raw_chunk: Raw μ-law audio chunk
            stream_sid: Twilio stream SID
            
        Returns:
            JSON payload ready for WebSocket transmission
        """
        encoded_audio = base64.b64encode(raw_chunk).decode('utf-8')
        
        payload = {
            "event": "media",
            "streamSid": stream_sid,
            "media": {
                "payload": encoded_audio
            }
        }
        
        return payload
    
    async def validate_audio_file(self, file_path: str) -> Tuple[bool, dict]:
        """
        Validate raw μ-law audio file for manual testing in Audacity.
        
        This allows you to test the audio quality before streaming to Twilio:
        1. Import the .ulaw file in Audacity as "Raw audio"  
        2. Set: Encoding=μ-law, Sample rate=8000 Hz, Mono
        3. Play back to verify no static
        
        Args:
            file_path: Path to .ulaw file to validate
            
        Returns:
            Tuple of (is_valid, info_dict)
        """
        try:
            if not os.path.exists(file_path):
                return False, {"error": "File not found"}
            
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False, {"error": "Empty file"}
            
            # Calculate duration (8000 samples per second, 1 byte per sample for μ-law)
            duration_seconds = file_size / 8000
            
            info = {
                "file_size": file_size,
                "duration_seconds": round(duration_seconds, 2),
                "sample_rate": 8000,
                "channels": 1,
                "format": "μ-law",
                "audacity_import_settings": {
                    "encoding": "μ-law",
                    "sample_rate": "8000 Hz",
                    "channels": "Mono"
                }
            }
            
            logger.info(f"✅ Audio validation: {file_size} bytes, {duration_seconds:.2f}s duration")
            return True, info
            
        except Exception as e:
            return False, {"error": str(e)}

# Global converter instance
static_killer = StaticKillerConverter()

async def convert_wav_static_free(wav_data: bytes) -> Optional[bytes]:
    """Convert WAV to static-free raw μ-law using FFmpeg pipeline."""
    return await static_killer.wav_to_raw_mulaw(wav_data)

def chunk_for_streaming(raw_mulaw_data: bytes) -> list[bytes]:
    """Chunk raw μ-law data for optimal Twilio streaming."""
    return static_killer.chunk_raw_mulaw(raw_mulaw_data)

def create_media_payload(raw_chunk: bytes, stream_sid: str) -> dict:
    """Create Twilio Media Stream payload with verified format."""
    return static_killer.create_twilio_media_payload(raw_chunk, stream_sid)

async def save_test_audio(wav_data: bytes, output_path: str) -> bool:
    """
    Save WAV as .ulaw file for manual testing in Audacity.
    
    Use this to test audio quality before streaming:
    1. Call this function with your WAV data
    2. Open the .ulaw file in Audacity (Import > Raw Audio)  
    3. Set μ-law encoding, 8000 Hz, Mono
    4. Play to verify crystal clear audio
    """
    try:
        raw_mulaw = await static_killer.wav_to_raw_mulaw(wav_data)
        if not raw_mulaw:
            return False
        
        with open(output_path, 'wb') as f:
            f.write(raw_mulaw)
        
        # Validate the saved file
        is_valid, info = await static_killer.validate_audio_file(output_path)
        if is_valid:
            logger.info(f"💾 Saved test audio: {output_path} ({info['file_size']} bytes, {info['duration_seconds']}s)")
            logger.info(f"🎧 Test in Audacity: Import Raw Audio → μ-law, 8000 Hz, Mono")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"❌ Failed to save test audio: {e}")
        return False

if __name__ == "__main__":
    # Test the Static Killer with a simple example
    import asyncio
    
    async def test_static_killer():
        logger.info("🔪 Testing Static Killer conversion pipeline")
        
        # This would normally come from your TTS system
        # For testing, you'd use: wav_data = await generate_simple_speech("Hello world")
        logger.info("💡 To test: call convert_wav_static_free() with your TTS-generated WAV data")
        logger.info("💡 Then use save_test_audio() to create .ulaw files for Audacity testing")
        logger.info("✅ Static Killer ready - should eliminate static in Twilio streams!")
    
    asyncio.run(test_static_killer())