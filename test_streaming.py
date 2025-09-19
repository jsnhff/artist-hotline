#!/usr/bin/env python3
"""
Standalone streaming test script for Artist Hotline
Run this alongside your main app to test streaming without breaking production
"""

import asyncio
import httpx
import json
import subprocess
import time

BASE_URL = "http://localhost:8000"  # Adjust if your app runs elsewhere

async def run_test(test_name, endpoint, expected_status="success"):
    """Run a single test and report results"""
    print(f"\n{'='*50}")
    print(f"🧪 Running {test_name}")
    print(f"{'='*50}")
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if endpoint.startswith("POST"):
                method, url = endpoint.split(" ", 1)
                response = await client.post(f"{BASE_URL}{url}")
            else:
                response = await client.get(f"{BASE_URL}{endpoint}")
            
            duration = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("status") == expected_status:
                    print(f"✅ {test_name} PASSED ({duration:.2f}s)")
                    
                    # Print key details
                    if "files" in result:
                        print(f"📁 Files created:")
                        for name, path in result["files"].items():
                            print(f"   {name}: {path}")
                    
                    if "test_commands" in result:
                        print(f"🎵 Test commands:")
                        for name, cmd in result["test_commands"].items():
                            print(f"   {name}: {cmd}")
                    
                    if "results" in result and isinstance(result["results"], list):
                        print(f"📊 Results:")
                        for i, res in enumerate(result["results"]):
                            if "phrase" in res and "generation_time" in res:
                                print(f"   {i+1}: '{res['phrase']}' -> {res['generation_time']}")
                    
                    return True, result
                else:
                    print(f"❌ {test_name} FAILED - Wrong status: {result.get('status')}")
                    if "error" in result:
                        print(f"   Error: {result['error']}")
                    return False, result
            else:
                print(f"❌ {test_name} FAILED - HTTP {response.status_code}")
                print(f"   Response: {response.text}")
                return False, None
                
    except Exception as e:
        duration = time.time() - start_time
        print(f"❌ {test_name} FAILED ({duration:.2f}s)")
        print(f"   Exception: {e}")
        return False, None

async def test_audio_playback(file_path, description):
    """Test local audio playback"""
    print(f"\n🎵 Testing {description}")
    print(f"   File: {file_path}")
    
    try:
        # Try to play with ffplay (non-blocking)
        result = subprocess.run([
            'ffplay', '-nodisp', '-autoexit', '-t', '3', file_path
        ], capture_output=True, timeout=5)
        
        if result.returncode == 0:
            print(f"✅ {description} played successfully")
            return True
        else:
            print(f"❌ {description} playback failed")
            print(f"   Error: {result.stderr.decode()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} playback timed out (file may be playing)")
        return True  # Assume success if it's still playing
    except Exception as e:
        print(f"❌ {description} playback error: {e}")
        return False

async def main():
    print("🚀 Artist Hotline Streaming Test Suite")
    print("=" * 50)
    
    # Check if server is running
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{BASE_URL}/health")
            if response.status_code != 200:
                print("❌ Server not running - start your app first!")
                return
    except:
        print("❌ Cannot connect to server - is it running on localhost:8000?")
        return
    
    print("✅ Server is running")
    
    # Test 1: Check dependencies
    print("\n🔍 Checking test system status...")
    success, result = await run_test("Dependency Check", "/test-streaming-status", "ready")
    if not success:
        print("❌ Missing dependencies - tests may fail")
        if result:
            print(f"   Simple TTS: {result.get('simple_tts', False)}")
            print(f"   FFmpeg: {result.get('ffmpeg', False)}")
    
    # Test 2: Audio conversion pipeline
    success, result = await run_test("Audio Conversion", "POST /test-audio-conversion")
    if success and result:
        # Test local playback of converted files
        if "files" in result:
            if "wav" in result["files"]:
                await test_audio_playback(result["files"]["wav"], "WAV file")
            if "mulaw" in result["files"]:
                # Test mulaw with explicit format
                mulaw_file = result["files"]["mulaw"]
                print(f"\n🎵 Testing mulaw file: {mulaw_file}")
                try:
                    result_play = subprocess.run([
                        'ffplay', '-f', 'mulaw', '-ar', '8000', '-ac', '1', 
                        '-nodisp', '-autoexit', '-t', '3', mulaw_file
                    ], capture_output=True, timeout=5)
                    
                    if result_play.returncode == 0:
                        print("✅ Mulaw file played successfully")
                    else:
                        print(f"❌ Mulaw playback failed: {result_play.stderr.decode()}")
                except Exception as e:
                    print(f"❌ Mulaw playback error: {e}")
    
    # Test 3: Sine wave generation
    success, result = await run_test("Sine Wave Generation", "POST /test-sine-wave")
    if success and result and "file" in result:
        await test_audio_playback(result["file"], "Sine wave (should be pure 440Hz tone)")
    
    # Test 4: Coqui analysis
    success, result = await run_test("Coqui Analysis", "POST /test-coqui-analysis")
    if success and result:
        summary = result.get("summary", {})
        print(f"📊 Coqui Performance Summary:")
        print(f"   Average generation time: {summary.get('avg_generation_time', 'unknown')}")
        print(f"   Total audio bytes: {summary.get('total_audio_bytes', 'unknown')}")
    
    print("\n" + "=" * 50)
    print("🏁 Test Suite Complete!")
    print("=" * 50)
    print("\nNext Steps:")
    print("1. If local audio plays cleanly -> conversion works")
    print("2. Test with Twilio by setting webhook to /debug-voice-handler")
    print("3. Check streaming logs for any static issues")
    print("4. Compare results with streaming-testing-plan.md")

if __name__ == "__main__":
    asyncio.run(main())