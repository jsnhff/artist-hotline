#!/usr/bin/env python3
"""
Test script for the complete audio conversion pipeline:
MP3 (from ElevenLabs) → PCM → 8kHz Mono WAV → µ-law (for Twilio)

This validates that pydub + ffmpeg + audioop work correctly together.
"""

import asyncio
import base64
import io
import os
import sys
import wave
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test 1: Verify all dependencies are available"""
    print("=" * 60)
    print("TEST 1: Checking dependencies")
    print("=" * 60)

    try:
        import audioop
        print("✅ audioop available (stdlib)")
    except ImportError:
        print("❌ audioop not available")
        return False

    try:
        from pydub import AudioSegment
        print("✅ pydub available")
    except ImportError:
        print("❌ pydub not available - install: pip install pydub")
        return False

    try:
        # Test if ffmpeg is accessible
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, timeout=2)
        if result.returncode == 0:
            print("✅ ffmpeg available")
        else:
            print("❌ ffmpeg returned error")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        print("❌ ffmpeg not found - install: brew install ffmpeg (Mac) or apt-get install ffmpeg (Linux)")
        return False

    print()
    return True


def test_create_sample_mp3():
    """Test 2: Create a sample MP3 file for testing"""
    print("=" * 60)
    print("TEST 2: Creating sample MP3")
    print("=" * 60)

    try:
        from pydub import AudioSegment
        from pydub.generators import Sine

        # Generate 1 second of 440Hz sine wave (A note)
        tone = Sine(440).to_audio_segment(duration=1000)

        # Export as MP3
        mp3_buffer = io.BytesIO()
        tone.export(mp3_buffer, format="mp3", bitrate="128k")
        mp3_bytes = mp3_buffer.getvalue()

        print(f"✅ Generated {len(mp3_bytes)} bytes of MP3 audio")
        print()
        return mp3_bytes

    except Exception as e:
        print(f"❌ Failed to create sample MP3: {e}")
        print()
        return None


def test_mp3_to_wav(mp3_bytes):
    """Test 3: Convert MP3 to 8kHz mono WAV"""
    print("=" * 60)
    print("TEST 3: Converting MP3 → 8kHz Mono WAV")
    print("=" * 60)

    try:
        from pydub import AudioSegment

        # Decode MP3
        audio_segment = AudioSegment.from_mp3(io.BytesIO(mp3_bytes))
        print(f"✅ Decoded MP3: {audio_segment.frame_rate}Hz, {audio_segment.channels} channels")

        # Resample to 8kHz mono (Twilio requirement)
        audio_segment = audio_segment.set_frame_rate(8000).set_channels(1)
        print(f"✅ Resampled to: {audio_segment.frame_rate}Hz, {audio_segment.channels} channel")

        # Export as WAV
        wav_buffer = io.BytesIO()
        audio_segment.export(wav_buffer, format="wav")
        wav_bytes = wav_buffer.getvalue()

        print(f"✅ Generated {len(wav_bytes)} bytes of WAV audio")
        print()
        return wav_bytes

    except Exception as e:
        print(f"❌ Failed to convert MP3 to WAV: {e}")
        import traceback
        traceback.print_exc()
        print()
        return None


def test_wav_to_mulaw(wav_bytes):
    """Test 4: Convert WAV to µ-law using the production function"""
    print("=" * 60)
    print("TEST 4: Converting WAV → µ-law")
    print("=" * 60)

    try:
        import audioop

        # Use wave module to properly parse WAV header
        wav_buffer = io.BytesIO(wav_bytes)
        with wave.open(wav_buffer, 'rb') as wav_file:
            # Get WAV properties
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            framerate = wav_file.getframerate()
            n_frames = wav_file.getnframes()

            print(f"   WAV properties:")
            print(f"   - Channels: {channels}")
            print(f"   - Sample width: {sample_width} bytes")
            print(f"   - Frame rate: {framerate} Hz")
            print(f"   - Frames: {n_frames}")

            # Extract pure PCM data (no matter what header size)
            pcm_data = wav_file.readframes(n_frames)

        print(f"✅ Extracted {len(pcm_data)} bytes of PCM data")

        # Convert 16-bit linear PCM to µ-law (8-bit)
        mulaw_data = audioop.lin2ulaw(pcm_data, 2)

        print(f"✅ Converted to {len(mulaw_data)} bytes of µ-law")
        print(f"   Compression ratio: {len(pcm_data) / len(mulaw_data):.2f}x")
        print()
        return mulaw_data

    except Exception as e:
        print(f"❌ Failed to convert WAV to µ-law: {e}")
        import traceback
        traceback.print_exc()
        print()
        return None


def test_base64_encoding(mulaw_data):
    """Test 5: Encode µ-law for Twilio WebSocket"""
    print("=" * 60)
    print("TEST 5: Encoding µ-law → base64")
    print("=" * 60)

    try:
        mulaw_b64 = base64.b64encode(mulaw_data).decode('ascii')

        print(f"✅ Encoded to {len(mulaw_b64)} base64 characters")
        print(f"   Preview: {mulaw_b64[:50]}...")
        print()
        return mulaw_b64

    except Exception as e:
        print(f"❌ Failed to encode base64: {e}")
        print()
        return None


def test_full_pipeline():
    """Test the complete pipeline end-to-end"""
    print("\n" + "=" * 60)
    print("COMPLETE AUDIO CONVERSION PIPELINE TEST")
    print("=" * 60 + "\n")

    # Test 1: Dependencies
    if not test_imports():
        print("\n❌ PIPELINE TEST FAILED: Missing dependencies")
        return False

    # Test 2: Create sample MP3
    mp3_bytes = test_create_sample_mp3()
    if not mp3_bytes:
        print("\n❌ PIPELINE TEST FAILED: Cannot create sample MP3")
        return False

    # Test 3: MP3 → WAV
    wav_bytes = test_mp3_to_wav(mp3_bytes)
    if not wav_bytes:
        print("\n❌ PIPELINE TEST FAILED: Cannot convert MP3 to WAV")
        return False

    # Test 4: WAV → µ-law
    mulaw_data = test_wav_to_mulaw(wav_bytes)
    if not mulaw_data:
        print("\n❌ PIPELINE TEST FAILED: Cannot convert WAV to µ-law")
        return False

    # Test 5: µ-law → base64
    mulaw_b64 = test_base64_encoding(mulaw_data)
    if not mulaw_b64:
        print("\n❌ PIPELINE TEST FAILED: Cannot encode base64")
        return False

    # Success!
    print("=" * 60)
    print("✅✅✅ COMPLETE PIPELINE TEST PASSED! ✅✅✅")
    print("=" * 60)
    print()
    print("Pipeline Summary:")
    print(f"  MP3 input:       {len(mp3_bytes):,} bytes")
    print(f"  WAV intermediate: {len(wav_bytes):,} bytes")
    print(f"  µ-law output:    {len(mulaw_data):,} bytes")
    print(f"  Base64 encoded:  {len(mulaw_b64):,} chars")
    print()
    print("✅ Ready for Railway deployment!")
    print()

    return True


if __name__ == "__main__":
    success = test_full_pipeline()
    sys.exit(0 if success else 1)
