# Streaming Testing Plan - 30 Minute Session

> **Goal**: Debug and fix Twilio streaming audio static issues by systematically testing each component

## 🔍 Research Summary

### Key Technical Constraints
- **Twilio Media Streams**: Requires `audio/x-mulaw, 8000 Hz, mono, base64 encoded` with NO file headers
- **Coqui TTS**: Outputs standard PCM/WAV format, needs conversion to µ-law
- **Common Static Causes**: File headers, wrong sample rate, stereo vs mono, base64 padding issues

### Current Status
- ✅ WebSocket connection established with Twilio
- ✅ Coqui TTS generates audio 
- ❌ Audio plays with static/distortion
- ❌ Format conversion likely the culprit

## 🔧 Step-by-Step Testing Protocol

### Test 1: Coqui → WAV → Mulaw Conversion (5 mins)
**Goal**: Verify local audio pipeline works cleanly

```bash
# 1. Generate test audio with Coqui
python3 -c "
from simple_tts import generate_simple_speech
import asyncio
wav_data = asyncio.run(generate_simple_speech('Testing streaming voice Jason'))
with open('/tmp/test_coqui.wav', 'wb') as f:
    f.write(wav_data)
"

# 2. Convert to Twilio format
ffmpeg -i /tmp/test_coqui.wav -ar 8000 -ac 1 -f mulaw -y /tmp/test.ulaw

# 3. Test locally
ffplay /tmp/test.ulaw
```

**Expected**: Clean audio = conversion works, static = conversion issue

### Test 2: Twilio Inbound Inspection (5 mins)
**Goal**: Verify Twilio is sending us good audio

**Code to add to WebSocket handler**:
```python
# In media event handler:
audio_payload = data['media']['payload']
raw_audio = base64.b64decode(audio_payload)

# Log every 50th chunk for inspection
if hasattr(buffer, 'chunk_count'):
    buffer.chunk_count += 1
else:
    buffer.chunk_count = 1
    
if buffer.chunk_count % 50 == 0:
    with open(f'/tmp/twilio_chunk_{buffer.chunk_count}.ulaw', 'wb') as f:
        f.write(raw_audio)
    logger.info(f"Saved chunk {buffer.chunk_count} - {len(raw_audio)} bytes")
```

**Test**: Play saved chunks with `ffplay /tmp/twilio_chunk_*.ulaw`

### Test 3: Known-Good Static Payload Test (10 mins)
**Goal**: Test if WebSocket reply logic works with perfect audio

**Create test script** `test_static_payload.py`:
```python
import asyncio
import json
import base64
import websockets

async def test_known_good():
    # Create a simple sine wave in mulaw format
    import numpy as np
    
    # Generate 1 second of 440Hz sine wave at 8kHz
    sample_rate = 8000
    duration = 1.0
    frequency = 440
    
    t = np.linspace(0, duration, int(sample_rate * duration))
    sine_wave = np.sin(2 * np.pi * frequency * t)
    
    # Convert to 16-bit PCM, then to mulaw
    pcm_data = (sine_wave * 32767).astype(np.int16)
    
    # Use audioop to convert to mulaw
    import audioop
    mulaw_data = audioop.lin2ulaw(pcm_data.tobytes(), 2)
    
    # Base64 encode
    payload = base64.b64encode(mulaw_data).decode('ascii')
    
    print(f"Generated {len(mulaw_data)} mulaw bytes, {len(payload)} base64 chars")
    
    # Save for manual testing
    with open('/tmp/test_sine.ulaw', 'wb') as f:
        f.write(mulaw_data)
    
    print("Test with: ffplay /tmp/test_sine.ulaw")
    print("Payload preview:", payload[:100] + "...")
    
    return payload

if __name__ == "__main__":
    asyncio.run(test_known_good())
```

**Use this payload in your WebSocket stream instead of Coqui output**

### Test 4: Coqui Streaming Inference Analysis (5 mins)
**Goal**: Understand Coqui output format precisely

**Add to your code**:
```python
async def analyze_coqui_output(text):
    wav_data = await generate_simple_speech(text)
    
    # Save and analyze with ffprobe
    with open('/tmp/coqui_analysis.wav', 'wb') as f:
        f.write(wav_data)
    
    import subprocess
    result = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json', 
        '-show_streams', '/tmp/coqui_analysis.wav'
    ], capture_output=True, text=True)
    
    print("Coqui output format:", result.stdout)
    return wav_data
```

### Test 5: Mini Automated Loop (5 mins)
**Goal**: Test end-to-end pipeline variations quickly

**Create** `streaming_test_loop.py`:
```python
import asyncio
import subprocess
import time

async def test_pipeline(text, test_name):
    print(f"\n=== Testing: {test_name} ===")
    start_time = time.time()
    
    # 1. Generate with Coqui
    try:
        from simple_tts import generate_simple_speech
        wav_data = await generate_simple_speech(text)
        gen_time = time.time() - start_time
        print(f"✅ Coqui generation: {gen_time:.2f}s, {len(wav_data)} bytes")
    except Exception as e:
        print(f"❌ Coqui failed: {e}")
        return False
    
    # 2. Convert to mulaw
    wav_path = f'/tmp/{test_name}.wav'
    mulaw_path = f'/tmp/{test_name}.ulaw'
    
    with open(wav_path, 'wb') as f:
        f.write(wav_data)
    
    try:
        subprocess.run([
            'ffmpeg', '-y', '-i', wav_path, 
            '-ar', '8000', '-ac', '1', '-f', 'mulaw', mulaw_path
        ], check=True, capture_output=True)
        conv_time = time.time() - start_time
        print(f"✅ Conversion: {conv_time:.2f}s total")
    except subprocess.CalledProcessError as e:
        print(f"❌ Conversion failed: {e}")
        return False
    
    # 3. Quick quality check
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'quiet', '-show_entries', 'stream=codec_name,sample_rate,channels',
            '-of', 'csv=p=0', mulaw_path
        ], capture_output=True, text=True, check=True)
        print(f"✅ Final format: {result.stdout.strip()}")
    except:
        print("⚠️ Could not probe final format")
    
    return True

async def main():
    tests = [
        ("Hello test", "short"),
        ("This is a medium length test message for streaming", "medium"), 
        ("This is a longer test message to see how the streaming system handles more complex audio generation and conversion", "long")
    ]
    
    for text, name in tests:
        success = await test_pipeline(text, name)
        if not success:
            print(f"❌ {name} test failed - stopping")
            break
        time.sleep(1)  # Brief pause between tests

if __name__ == "__main__":
    asyncio.run(main())
```

## 📊 Debug Logging Checklist

Add these logs to your streaming code:

```python
# In WebSocket media handler:
logger.info(f"📊 METRICS - Chunk: {len(audio_chunk)} bytes, Buffer: {len(buffer.chunks)} chunks")

# In Coqui generation:
logger.info(f"📊 COQUI - Generated: {len(wav_data)} bytes in {generation_time:.2f}s")

# In conversion:
logger.info(f"📊 CONVERT - Input: {input_format}, Output: {len(mulaw_data)} mulaw bytes")

# In Twilio send:
logger.info(f"📊 SEND - Payload: {len(payload)} base64 chars, StreamID: {stream_sid}")
```

## 🎯 Success Criteria

- **Test 1**: Local mulaw file plays cleanly
- **Test 2**: Twilio inbound chunks play cleanly  
- **Test 3**: Sine wave plays through WebSocket without static
- **Test 4**: Understand exact Coqui output format
- **Test 5**: End-to-end pipeline completes under 2 seconds

## 🚨 If Static Persists

**Most Likely Issues** (in order):
1. **Headers in audio data** - Strip all WAV/RIFF headers before sending
2. **Sample rate mismatch** - Verify 8000Hz exactly
3. **Base64 encoding** - Check for padding or URL-safe variants
4. **WebSocket message type** - Ensure sending as text, not binary
5. **Chunking size** - Try smaller chunks (160 bytes = 20ms of audio)

## 📝 Quick Commands Reference

```bash
# Analyze any audio file
ffprobe -v quiet -print_format json -show_streams audiofile.wav

# Convert to Twilio format
ffmpeg -i input.wav -ar 8000 -ac 1 -f mulaw output.ulaw

# Play mulaw directly
ffplay -f mulaw -ar 8000 -ac 1 input.ulaw

# Create test sine wave
ffmpeg -f lavfi -i "sine=frequency=440:duration=1:sample_rate=8000" -f mulaw test_sine.ulaw
```

## ⏰ Time Management

- **5 min**: Test 1 (local conversion)
- **5 min**: Test 2 (inbound inspection) 
- **10 min**: Test 3 (known-good payload)
- **5 min**: Test 4 (Coqui analysis)
- **5 min**: Test 5 (automated loop)

**If you get clean audio in Test 1 but static in Test 3** → Focus on WebSocket/base64 encoding
**If static in Test 1** → Focus on Coqui output format and conversion
**If clean in Test 3** → The core pipeline works, issue is in real-time streaming

Good luck! 🚀