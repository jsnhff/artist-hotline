#!/usr/bin/env python3
"""
Real-time Audio Transcription with faster-whisper
Handles streaming audio transcription for the Coqui TTS system
"""
import asyncio
import logging
import io
import wave
import time
from typing import Optional, List, AsyncGenerator
from collections import deque

# Whisper imports
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    logging.warning("faster-whisper not available - install with: pip install faster-whisper")

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logging.warning("PyTorch not available - CPU inference only")

logger = logging.getLogger(__name__)

class AudioBuffer:
    """Buffer for collecting audio chunks before transcription"""
    
    def __init__(self, max_duration: float = 10.0, sample_rate: int = 8000):
        self.max_duration = max_duration
        self.sample_rate = sample_rate
        self.max_samples = int(max_duration * sample_rate * 2)  # 2 bytes per sample (16-bit)
        
        self.buffer = deque()
        self.total_bytes = 0
        self.last_chunk_time = time.time()
        
    def add_chunk(self, audio_data: bytes):
        """Add audio chunk to buffer"""
        self.buffer.append(audio_data)
        self.total_bytes += len(audio_data)
        self.last_chunk_time = time.time()
        
        # Remove old chunks if buffer is too large
        while self.total_bytes > self.max_samples:
            old_chunk = self.buffer.popleft()
            self.total_bytes -= len(old_chunk)
    
    def should_transcribe(self, silence_threshold: float = 1.0) -> bool:
        """Check if we should transcribe based on silence duration"""
        if not self.buffer:
            return False
            
        # Transcribe if we have enough audio or after silence
        silence_duration = time.time() - self.last_chunk_time
        min_audio_duration = 0.5  # At least 500ms of audio
        
        return (
            self.total_bytes > (min_audio_duration * self.sample_rate * 2) and
            silence_duration > silence_threshold
        ) or self.total_bytes > (self.max_samples * 0.8)  # Buffer almost full
    
    def get_audio_data(self) -> bytes:
        """Get all buffered audio data"""
        return b''.join(self.buffer)
    
    def clear(self):
        """Clear the audio buffer"""
        self.buffer.clear()
        self.total_bytes = 0

class WhisperTranscriber:
    """Real-time transcription with faster-whisper"""
    
    def __init__(self, model_size: str = "base", device: str = "auto", compute_type: str = "auto"):
        self.model_size = model_size
        self.device = self._get_device(device)
        self.compute_type = compute_type
        self.model = None
        
        logger.info(f"🎤 Initializing Whisper transcriber: {model_size} on {self.device}")
        
    def _get_device(self, device: str) -> str:
        """Determine the best device to use"""
        if device != "auto":
            return device
            
        if TORCH_AVAILABLE and torch.cuda.is_available():
            return "cuda"
        else:
            return "cpu"
    
    async def initialize(self) -> bool:
        """Initialize the Whisper model asynchronously"""
        if not FASTER_WHISPER_AVAILABLE:
            logger.error("faster-whisper not available - install with: pip install faster-whisper")
            return False
            
        try:
            # Initialize model in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self.model = await loop.run_in_executor(
                None,
                lambda: WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type
                )
            )
            
            logger.info(f"✅ Whisper model {self.model_size} loaded on {self.device}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Whisper model: {e}")
            return False
    
    async def transcribe_audio(self, audio_data: bytes, sample_rate: int = 8000) -> Optional[str]:
        """
        Transcribe audio data to text
        
        Args:
            audio_data: Raw PCM audio data (16-bit)
            sample_rate: Sample rate of the audio
            
        Returns:
            Transcribed text or None if transcription failed
        """
        if not self.model or not audio_data:
            return None
            
        try:
            # Convert raw PCM to WAV format for Whisper
            wav_data = self._pcm_to_wav(audio_data, sample_rate)
            if not wav_data:
                return None
            
            # Run transcription in thread pool
            loop = asyncio.get_event_loop()
            segments, info = await loop.run_in_executor(
                None,
                lambda: self.model.transcribe(
                    io.BytesIO(wav_data),
                    language="en",  # Can be made configurable
                    vad_filter=True,  # Voice activity detection
                    vad_parameters=dict(min_silence_duration_ms=500)
                )
            )
            
            # Combine all segments
            transcription = ""
            for segment in segments:
                transcription += segment.text
            
            transcription = transcription.strip()
            if transcription:
                logger.info(f"🎤 Transcribed: '{transcription}'")
                return transcription
            else:
                logger.debug("No speech detected in audio")
                return None
                
        except Exception as e:
            logger.error(f"❌ Transcription failed: {e}")
            return None
    
    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int) -> bytes:
        """Convert raw PCM data to WAV format"""
        try:
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(pcm_data)
            
            return wav_buffer.getvalue()
            
        except Exception as e:
            logger.error(f"PCM to WAV conversion failed: {e}")
            return b''

class StreamingTranscriber:
    """Manages streaming transcription with audio buffering"""
    
    def __init__(self, model_size: str = "base"):
        self.transcriber = WhisperTranscriber(model_size)
        self.audio_buffers = {}  # stream_id -> AudioBuffer
        
    async def initialize(self) -> bool:
        """Initialize the transcriber"""
        return await self.transcriber.initialize()
    
    def add_audio_chunk(self, stream_id: str, audio_data: bytes, sample_rate: int = 8000):
        """Add audio chunk for a specific stream"""
        if stream_id not in self.audio_buffers:
            self.audio_buffers[stream_id] = AudioBuffer(sample_rate=sample_rate)
        
        self.audio_buffers[stream_id].add_chunk(audio_data)
    
    async def check_for_transcription(self, stream_id: str, sample_rate: int = 8000) -> Optional[str]:
        """Check if we should transcribe audio for a stream"""
        if stream_id not in self.audio_buffers:
            return None
            
        buffer = self.audio_buffers[stream_id]
        
        if buffer.should_transcribe():
            audio_data = buffer.get_audio_data()
            buffer.clear()
            
            if audio_data:
                return await self.transcriber.transcribe_audio(audio_data, sample_rate)
        
        return None
    
    def cleanup_stream(self, stream_id: str):
        """Clean up audio buffer for a stream"""
        if stream_id in self.audio_buffers:
            del self.audio_buffers[stream_id]
            logger.debug(f"Cleaned up transcription buffer for stream {stream_id}")

# Global transcriber instance
streaming_transcriber = StreamingTranscriber()

async def initialize_whisper(model_size: str = "base") -> bool:
    """Initialize the global Whisper transcriber"""
    global streaming_transcriber
    streaming_transcriber = StreamingTranscriber(model_size)
    return await streaming_transcriber.initialize()

def add_audio_for_transcription(stream_id: str, audio_data: bytes, sample_rate: int = 8000):
    """Add audio chunk for transcription"""
    streaming_transcriber.add_audio_chunk(stream_id, audio_data, sample_rate)

async def get_transcription(stream_id: str, sample_rate: int = 8000) -> Optional[str]:
    """Check for transcription result"""
    return await streaming_transcriber.check_for_transcription(stream_id, sample_rate)

def cleanup_transcription_stream(stream_id: str):
    """Clean up transcription stream"""
    streaming_transcriber.cleanup_stream(stream_id)

if __name__ == "__main__":
    # Test the transcription system
    import asyncio
    
    async def test_transcription():
        success = await initialize_whisper("base")
        if success:
            print("✅ Whisper transcription initialized successfully")
            
            # Test with dummy audio data
            dummy_audio = b'\x00' * 8000  # 1 second of silence
            add_audio_for_transcription("test", dummy_audio)
            
            result = await get_transcription("test")
            print(f"Transcription result: {result}")
            
            cleanup_transcription_stream("test")
        else:
            print("❌ Failed to initialize Whisper transcription")
    
    asyncio.run(test_transcription())