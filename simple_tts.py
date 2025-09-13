#!/usr/bin/env python3
"""
Simple TTS fallback using pyttsx3 for testing the streaming pipeline
"""
import asyncio
import logging
import io
import wave
import tempfile
import os
from pathlib import Path
from typing import Optional, AsyncGenerator

# Simple TTS imports
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False
    logging.warning("pyttsx3 not available - install with: pip install pyttsx3")

logger = logging.getLogger(__name__)

class SimpleTTSHandler:
    def __init__(self):
        self.engine = None
        logger.info(f"🗣️ Initializing Simple TTS handler")
        
    async def initialize(self, speaker_wav_path: Optional[str] = None):
        """Initialize the TTS engine asynchronously"""
        if not PYTTSX3_AVAILABLE:
            logger.error("pyttsx3 not available - install with: pip install pyttsx3")
            return False
            
        try:
            # Initialize engine in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.engine = await loop.run_in_executor(None, pyttsx3.init)
            
            # Set voice properties
            voices = self.engine.getProperty('voices')
            if voices:
                # Try to use a female voice if available
                female_voice = None
                for voice in voices:
                    if 'female' in voice.name.lower() or 'samantha' in voice.name.lower():
                        female_voice = voice.id
                        break
                
                if female_voice:
                    self.engine.setProperty('voice', female_voice)
                    logger.info(f"🎤 Using female voice")
                else:
                    logger.info(f"🎤 Using default voice")
            
            # Set speech rate and volume
            self.engine.setProperty('rate', 180)  # Slightly faster
            self.engine.setProperty('volume', 0.9)
            
            logger.info("✅ Simple TTS initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Simple TTS: {e}")
            return False
    
    async def synthesize_speech(self, text: str, language: str = "en") -> Optional[bytes]:
        """
        Generate speech audio from text
        Returns WAV audio as bytes
        """
        if not self.engine:
            logger.error("TTS engine not initialized")
            return None
            
        try:
            # Create temporary file for audio output
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_path = temp_file.name
            
            # Run TTS synchronously (pyttsx3 doesn't work well in thread pools)
            self._synthesize_to_file(text, temp_path)
            
            # Read the generated audio file
            if os.path.exists(temp_path):
                with open(temp_path, 'rb') as f:
                    audio_data = f.read()
                
                # Clean up temp file
                os.unlink(temp_path)
                
                # Convert AIFF to WAV if needed (macOS pyttsx3 generates AIFF)
                if audio_data.startswith(b'FORM'):
                    logger.debug("Converting AIFF to WAV format")
                    wav_bytes = self._convert_aiff_to_wav_simple(audio_data)
                elif audio_data.startswith(b'RIFF'):
                    wav_bytes = audio_data  # Already WAV
                else:
                    logger.error(f"Unknown audio format: {audio_data[:20]}")
                    return None
                
                if wav_bytes:
                    logger.info(f"🔊 Generated {len(wav_bytes)} bytes of WAV audio for: '{text[:50]}...'")
                    return wav_bytes
                else:
                    logger.error("Failed to convert audio to WAV format")
                    return None
            else:
                logger.error("Failed to generate audio file")
                return None
                
        except Exception as e:
            logger.error(f"❌ TTS synthesis failed: {e}")
            return None
    
    def _synthesize_to_file(self, text: str, file_path: str):
        """Synchronous TTS synthesis to file"""
        try:
            # Make sure we have a good text length
            if len(text.strip()) < 3:
                text = f"Hello. {text}. Testing speech synthesis."
            
            self.engine.save_to_file(text, file_path)
            self.engine.runAndWait()
            
            # Verify file was created with content
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                if size <= 44:  # Just header, no audio
                    logger.warning(f"Generated file too small: {size} bytes, retrying...")
                    # Try again with longer text
                    longer_text = f"This is a test. {text}. Please generate proper audio data."
                    self.engine.save_to_file(longer_text, file_path)
                    self.engine.runAndWait()
                    
        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
    
    def _convert_aiff_to_wav(self, aiff_data: bytes) -> bytes:
        """Convert AIFF audio to WAV format using tempfiles"""
        try:
            # Write AIFF to temp file
            with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as aiff_file:
                aiff_file.write(aiff_data)
                aiff_path = aiff_file.name
            
            # Create temp WAV file path
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_path = wav_file.name
            
            # Use FFmpeg or SoX to convert (try ffmpeg first)
            import subprocess
            try:
                # Try ffmpeg first
                result = subprocess.run([
                    'ffmpeg', '-y', '-i', aiff_path, '-acodec', 'pcm_s16le', 
                    '-ar', '8000', '-ac', '1', wav_path
                ], capture_output=True, timeout=10)
                
                if result.returncode == 0:
                    # Read converted WAV file
                    with open(wav_path, 'rb') as f:
                        wav_bytes = f.read()
                    
                    # Clean up temp files
                    os.unlink(aiff_path)
                    os.unlink(wav_path)
                    
                    return wav_bytes
                else:
                    raise Exception(f"ffmpeg failed: {result.stderr.decode()}")
                    
            except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
                logger.warning(f"ffmpeg conversion failed: {e}")
                # Try basic PCM extraction (fallback)
                return self._extract_pcm_from_aiff(aiff_data)
                
        except Exception as e:
            logger.error(f"AIFF to WAV conversion failed: {e}")
            return b''
        finally:
            # Clean up any remaining temp files
            for path in [aiff_path, wav_path]:
                try:
                    if 'path' in locals() and os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
    
    def _convert_aiff_to_wav_simple(self, aiff_data: bytes) -> bytes:
        """Convert AIFF to WAV using pydub or direct conversion"""
        try:
            # Try using subprocess with ffmpeg for reliable conversion
            import subprocess
            
            # Write AIFF to temp file
            with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as aiff_file:
                aiff_file.write(aiff_data)
                aiff_path = aiff_file.name
            
            # Create temp WAV file path  
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_file:
                wav_path = wav_file.name
            
            # Convert using ffmpeg with forced parameters for Twilio compatibility
            try:
                result = subprocess.run([
                    'ffmpeg', '-y', '-i', aiff_path, 
                    '-ar', '8000',  # 8kHz sample rate for Twilio
                    '-ac', '1',     # Mono
                    '-acodec', 'pcm_s16le',  # 16-bit PCM
                    wav_path
                ], capture_output=True, timeout=15, check=True)
                
                # Read converted WAV file
                with open(wav_path, 'rb') as f:
                    wav_bytes = f.read()
                
                logger.info(f"✅ Converted AIFF to WAV: {len(aiff_data)} -> {len(wav_bytes)} bytes")
                return wav_bytes
                    
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.warning(f"ffmpeg conversion failed: {e}, trying fallback")
                return self._extract_pcm_from_aiff(aiff_data)
                
        except Exception as e:
            logger.error(f"AIFF to WAV conversion failed: {e}")
            return b''
        finally:
            # Clean up temp files
            try:
                if 'aiff_path' in locals() and os.path.exists(aiff_path):
                    os.unlink(aiff_path)
                if 'wav_path' in locals() and os.path.exists(wav_path):
                    os.unlink(wav_path)
            except:
                pass
    
    def _extract_pcm_from_aiff(self, aiff_data: bytes) -> bytes:
        """Extract PCM audio from AIFF and create simple WAV"""
        try:
            # Very basic AIFF parsing to extract PCM data
            # This is a simplified approach for the test
            
            # Find SSND chunk (sound data)
            ssnd_pos = aiff_data.find(b'SSND')
            if ssnd_pos == -1:
                raise Exception("No SSND chunk found in AIFF")
            
            # Skip SSND header (8 bytes: chunk ID + size, then 8 bytes offset/blocksize)
            pcm_start = ssnd_pos + 16
            pcm_data = aiff_data[pcm_start:]
            
            # Create minimal WAV header for 16-bit mono 8kHz
            wav_header = self._create_wav_header(len(pcm_data), 8000, 1, 16)
            
            return wav_header + pcm_data
            
        except Exception as e:
            logger.error(f"PCM extraction failed: {e}")
            return b''
    
    def _create_wav_header(self, data_size: int, sample_rate: int = 8000, channels: int = 1, bits_per_sample: int = 16) -> bytes:
        """Create a WAV file header"""
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        
        header = b'RIFF'
        header += (36 + data_size).to_bytes(4, 'little')
        header += b'WAVE'
        header += b'fmt '
        header += (16).to_bytes(4, 'little')  # fmt chunk size
        header += (1).to_bytes(2, 'little')   # audio format (PCM)
        header += channels.to_bytes(2, 'little')
        header += sample_rate.to_bytes(4, 'little')
        header += byte_rate.to_bytes(4, 'little')
        header += block_align.to_bytes(2, 'little')
        header += bits_per_sample.to_bytes(2, 'little')
        header += b'data'
        header += data_size.to_bytes(4, 'little')
        
        return header
    
    async def stream_speech(self, text: str, language: str = "en") -> AsyncGenerator[bytes, None]:
        """
        Stream speech generation
        Currently generates full audio and yields in chunks
        """
        wav_bytes = await self.synthesize_speech(text, language)
        if wav_bytes:
            # Yield in 1KB chunks for streaming effect
            chunk_size = 1024
            for i in range(0, len(wav_bytes), chunk_size):
                yield wav_bytes[i:i + chunk_size]
                # Small delay to simulate streaming
                await asyncio.sleep(0.01)

# Global TTS handler instance
tts_handler = SimpleTTSHandler()

async def initialize_simple_tts() -> bool:
    """Initialize the global Simple TTS handler"""
    return await tts_handler.initialize()

async def generate_simple_speech(text: str, language: str = "en") -> Optional[bytes]:
    """Generate speech using Simple TTS"""
    return await tts_handler.synthesize_speech(text, language)

async def stream_simple_speech(text: str, language: str = "en") -> AsyncGenerator[bytes, None]:
    """Stream speech using Simple TTS"""
    async for chunk in tts_handler.stream_speech(text, language):
        yield chunk

if __name__ == "__main__":
    # Test the TTS handler
    import asyncio
    
    async def test_tts():
        success = await initialize_simple_tts()
        if success:
            audio = await generate_simple_speech("Hello! This is a test of Simple TTS.")
            if audio:
                print(f"Generated {len(audio)} bytes of audio")
            else:
                print("Failed to generate audio")
        else:
            print("Failed to initialize TTS")
    
    asyncio.run(test_tts())