#!/usr/bin/env python3
"""
Coqui TTS Handler with XTTS-v2 Voice Cloning
Real-time streaming TTS for the artist hotline test system
"""
import os
import asyncio
import logging
import base64
import io
import wave
import tempfile
from pathlib import Path
from typing import Optional, AsyncGenerator

# Coqui TTS imports
try:
    from TTS.api import TTS
    import torch
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False
    logging.warning("Coqui TTS not available - install with: pip install TTS")

logger = logging.getLogger(__name__)

class CoquiTTSHandler:
    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2"):
        self.model_name = model_name
        self.tts = None
        if COQUI_AVAILABLE:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = "cpu"
        self.speaker_wav_path = None
        self.language = "en"  # Default language
        
        if COQUI_AVAILABLE:
            logger.info(f"🐸 Initializing Coqui TTS on device: {self.device}")
        else:
            logger.warning("🐸 Coqui TTS handler created but dependencies not available")
        
    async def initialize(self, speaker_wav_path: Optional[str] = None):
        """Initialize the TTS model asynchronously"""
        if not COQUI_AVAILABLE:
            raise RuntimeError("Coqui TTS not available - install with: pip install TTS")
            
        try:
            # Run initialization in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.tts = await loop.run_in_executor(
                None, 
                lambda: TTS(self.model_name).to(self.device)
            )
            
            if speaker_wav_path and Path(speaker_wav_path).exists():
                self.speaker_wav_path = speaker_wav_path
                logger.info(f"🎤 Voice cloning enabled with: {speaker_wav_path}")
            else:
                logger.info("🎤 Using default Coqui XTTS voice: Claribel Dervla")
                
            logger.info("✅ Coqui TTS initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Coqui TTS: {e}")
            return False
    
    async def synthesize_speech(self, text: str, language: str = "en") -> Optional[bytes]:
        """
        Generate speech audio from text
        Returns WAV audio as bytes
        """
        if not self.tts:
            logger.error("TTS not initialized")
            return None
            
        try:
            # Run TTS in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            if self.speaker_wav_path:
                # Voice cloning mode
                wav_data = await loop.run_in_executor(
                    None,
                    lambda: self.tts.tts(
                        text=text,
                        speaker_wav=self.speaker_wav_path,
                        language=language
                    )
                )
            else:
                # Default voice mode - use built-in speaker
                # XTTS-v2 has several built-in speakers, using a pleasant default
                wav_data = await loop.run_in_executor(
                    None,
                    lambda: self.tts.tts(
                        text=text,
                        language=language,
                        speaker="Claribel Dervla"  # Built-in XTTS speaker
                    )
                )
            
            # Convert numpy array to WAV bytes
            wav_bytes = self._numpy_to_wav_bytes(wav_data)
            logger.info(f"🔊 Generated {len(wav_bytes)} bytes of audio for: '{text[:50]}...'")
            return wav_bytes
            
        except Exception as e:
            logger.error(f"❌ TTS synthesis failed: {e}")
            return None
    
    async def stream_speech(self, text: str, language: str = "en") -> AsyncGenerator[bytes, None]:
        """
        Stream speech generation (placeholder for future streaming implementation)
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
    
    def _numpy_to_wav_bytes(self, audio_data) -> bytes:
        """Convert numpy audio data to WAV bytes"""
        import numpy as np
        
        # Ensure audio is in the right format
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Normalize to 16-bit range
        audio_data = np.clip(audio_data * 32767, -32768, 32767).astype(np.int16)
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(22050)  # XTTS default sample rate
            wav_file.writeframes(audio_data.tobytes())
        
        return wav_buffer.getvalue()

# Global TTS handler instance
tts_handler = CoquiTTSHandler()

async def initialize_coqui_tts(speaker_wav_path: Optional[str] = None) -> bool:
    """Initialize the global Coqui TTS handler"""
    return await tts_handler.initialize(speaker_wav_path)

async def generate_coqui_speech(text: str, language: str = "en") -> Optional[bytes]:
    """Generate speech using Coqui TTS"""
    return await tts_handler.synthesize_speech(text, language)

async def stream_coqui_speech(text: str, language: str = "en") -> AsyncGenerator[bytes, None]:
    """Stream speech using Coqui TTS"""
    async for chunk in tts_handler.stream_speech(text, language):
        yield chunk

if __name__ == "__main__":
    # Test the TTS handler
    import asyncio
    
    async def test_tts():
        success = await initialize_coqui_tts()
        if success:
            audio = await generate_coqui_speech("Hello! This is a test of Coqui TTS.")
            if audio:
                print(f"Generated {len(audio)} bytes of audio")
            else:
                print("Failed to generate audio")
        else:
            print("Failed to initialize TTS")
    
    asyncio.run(test_tts())