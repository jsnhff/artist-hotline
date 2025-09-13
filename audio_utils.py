#!/usr/bin/env python3
"""
Audio Format Conversion Utilities
Handles conversion between different audio formats for Twilio Media Streams
"""
import io
import wave
import logging
import base64
from typing import Optional

# Audio processing imports
try:
    import audioop
    AUDIOOP_AVAILABLE = True
except ImportError:
    AUDIOOP_AVAILABLE = False
    logging.warning("audioop not available - limited audio conversion")

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("numpy not available - some conversions may fail")

logger = logging.getLogger(__name__)

class AudioConverter:
    """Audio format conversion utilities for Twilio integration"""
    
    TWILIO_SAMPLE_RATE = 8000  # Twilio uses 8kHz
    TWILIO_CHANNELS = 1        # Mono
    TWILIO_SAMPWIDTH = 1       # 8-bit for μ-law
    
    @staticmethod
    def mulaw_to_pcm(mulaw_data: bytes) -> bytes:
        """Convert μ-law audio to linear PCM"""
        if not AUDIOOP_AVAILABLE:
            raise RuntimeError("audioop not available for μ-law conversion")
        
        try:
            # Convert μ-law to 16-bit PCM
            pcm_data = audioop.ulaw2lin(mulaw_data, 2)
            logger.debug(f"Converted {len(mulaw_data)} μ-law bytes to {len(pcm_data)} PCM bytes")
            return pcm_data
        except Exception as e:
            logger.error(f"μ-law to PCM conversion failed: {e}")
            return b''
    
    @staticmethod
    def pcm_to_mulaw(pcm_data: bytes) -> bytes:
        """Convert linear PCM to μ-law audio"""
        if not AUDIOOP_AVAILABLE:
            raise RuntimeError("audioop not available for μ-law conversion")
        
        try:
            # Convert 16-bit PCM to μ-law
            mulaw_data = audioop.lin2ulaw(pcm_data, 2)
            logger.debug(f"Converted {len(pcm_data)} PCM bytes to {len(mulaw_data)} μ-law bytes")
            return mulaw_data
        except Exception as e:
            logger.error(f"PCM to μ-law conversion failed: {e}")
            return b''
    
    @staticmethod
    def wav_to_pcm(wav_data: bytes) -> tuple[bytes, int, int]:
        """
        Extract PCM data from WAV file
        Returns: (pcm_data, sample_rate, channels)
        """
        try:
            wav_buffer = io.BytesIO(wav_data)
            with wave.open(wav_buffer, 'rb') as wav_file:
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                sampwidth = wav_file.getsampwidth()
                frames = wav_file.readframes(wav_file.getnframes())
                
                logger.debug(f"WAV file: {sample_rate}Hz, {channels}ch, {sampwidth}bytes/sample, {len(frames)} PCM bytes")
                return frames, sample_rate, channels
                
        except Exception as e:
            logger.error(f"WAV to PCM conversion failed: {e}")
            return b'', 0, 0
    
    @staticmethod
    def resample_audio(pcm_data: bytes, from_rate: int, to_rate: int, sampwidth: int = 2) -> bytes:
        """Resample audio to different sample rate"""
        if not AUDIOOP_AVAILABLE:
            logger.warning("audioop not available - cannot resample audio")
            return pcm_data
            
        if from_rate == to_rate:
            return pcm_data
            
        try:
            # Use audioop for resampling
            resampled_data = audioop.ratecv(pcm_data, sampwidth, 1, from_rate, to_rate, None)[0]
            logger.debug(f"Resampled audio from {from_rate}Hz to {to_rate}Hz")
            return resampled_data
        except Exception as e:
            logger.error(f"Audio resampling failed: {e}")
            return pcm_data
    
    @staticmethod
    def wav_to_twilio_mulaw(wav_data: bytes) -> bytes:
        """
        Convert WAV data to Twilio-compatible μ-law format
        (8kHz, mono, μ-law encoded)
        """
        try:
            # Extract PCM data from WAV
            pcm_data, sample_rate, channels = AudioConverter.wav_to_pcm(wav_data)
            if not pcm_data:
                return b''
            
            # Convert to mono if stereo
            if channels > 1:
                pcm_data = audioop.tomono(pcm_data, 2, 1, 1)
                logger.debug("Converted stereo to mono")
            
            # Resample to 8kHz if needed
            if sample_rate != AudioConverter.TWILIO_SAMPLE_RATE:
                pcm_data = AudioConverter.resample_audio(
                    pcm_data, sample_rate, AudioConverter.TWILIO_SAMPLE_RATE, 2
                )
            
            # Convert to μ-law
            mulaw_data = AudioConverter.pcm_to_mulaw(pcm_data)
            
            logger.info(f"Converted WAV to Twilio μ-law: {len(wav_data)} -> {len(mulaw_data)} bytes")
            return mulaw_data
            
        except Exception as e:
            logger.error(f"WAV to Twilio μ-law conversion failed: {e}")
            return b''
    
    @staticmethod
    def twilio_mulaw_to_wav(mulaw_data: bytes) -> bytes:
        """
        Convert Twilio μ-law data to WAV format
        """
        try:
            # Convert μ-law to PCM
            pcm_data = AudioConverter.mulaw_to_pcm(mulaw_data)
            if not pcm_data:
                return b''
            
            # Create WAV file in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(AudioConverter.TWILIO_CHANNELS)
                wav_file.setsampwidth(2)  # 16-bit PCM
                wav_file.setframerate(AudioConverter.TWILIO_SAMPLE_RATE)
                wav_file.writeframes(pcm_data)
            
            wav_data = wav_buffer.getvalue()
            logger.debug(f"Converted Twilio μ-law to WAV: {len(mulaw_data)} -> {len(wav_data)} bytes")
            return wav_data
            
        except Exception as e:
            logger.error(f"Twilio μ-law to WAV conversion failed: {e}")
            return b''

    @staticmethod
    def base64_to_mulaw(b64_data: str) -> bytes:
        """Convert base64 encoded data to μ-law bytes"""
        try:
            return base64.b64decode(b64_data)
        except Exception as e:
            logger.error(f"Base64 decode failed: {e}")
            return b''
    
    @staticmethod
    def mulaw_to_base64(mulaw_data: bytes) -> str:
        """Convert μ-law bytes to base64 string"""
        try:
            return base64.b64encode(mulaw_data).decode('ascii')
        except Exception as e:
            logger.error(f"Base64 encode failed: {e}")
            return ''

# Convenience functions
def convert_wav_for_twilio(wav_data: bytes) -> str:
    """Convert WAV data to base64 μ-law for Twilio"""
    mulaw_data = AudioConverter.wav_to_twilio_mulaw(wav_data)
    return AudioConverter.mulaw_to_base64(mulaw_data)

def convert_twilio_to_wav(b64_mulaw: str) -> bytes:
    """Convert Twilio base64 μ-law to WAV data"""
    mulaw_data = AudioConverter.base64_to_mulaw(b64_mulaw)
    return AudioConverter.twilio_mulaw_to_wav(mulaw_data)

if __name__ == "__main__":
    # Test audio conversion
    print("Testing audio conversion utilities...")
    
    # Test base64 roundtrip
    test_data = b"Hello World"
    b64_data = AudioConverter.mulaw_to_base64(test_data)
    decoded_data = AudioConverter.base64_to_mulaw(b64_data)
    print(f"Base64 roundtrip: {test_data == decoded_data}")
    
    print("Audio conversion utilities ready!")