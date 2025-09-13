#!/usr/bin/env python3
"""
Static Killer Test Script

Run this in the morning to test the static-free audio system:
1. Tests FFmpeg conversion pipeline
2. Generates .ulaw files for Audacity validation  
3. Provides instructions for A/B testing

Usage: python test_static_killer.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_static_killer():
    """Test the Static Killer audio conversion pipeline."""
    
    print("🔪 STATIC KILLER TEST SYSTEM")
    print("=" * 50)
    
    try:
        # Test imports
        print("📦 Testing imports...")
        from static_killer import convert_wav_static_free, save_test_audio
        from simple_tts import generate_simple_speech
        print("✅ All modules imported successfully")
        
        # Test TTS generation
        print("\n🗣️  Testing TTS generation...")
        test_text = "This is the Static Killer test. The audio should be completely free of static and noise."
        wav_data = await generate_simple_speech(test_text)
        
        if not wav_data:
            print("❌ TTS generation failed")
            return False
            
        print(f"✅ Generated {len(wav_data)} bytes of WAV audio")
        
        # Test Static Killer conversion
        print("\n🔄 Testing FFmpeg μ-law conversion...")
        raw_mulaw = await convert_wav_static_free(wav_data)
        
        if not raw_mulaw:
            print("❌ Static Killer conversion failed")
            print("💡 Make sure FFmpeg is installed: brew install ffmpeg")
            return False
            
        print(f"✅ Converted to {len(raw_mulaw)} bytes of raw μ-law")
        
        # Save test files
        print("\n💾 Saving test files...")
        test_file = "/tmp/static_killer_test.ulaw"
        success = await save_test_audio(wav_data, test_file)
        
        if success:
            print(f"✅ Saved test file: {test_file}")
            print("\n🎧 AUDACITY TEST INSTRUCTIONS:")
            print("1. Open Audacity")
            print("2. File → Import → Raw Data")
            print(f"3. Select: {test_file}")
            print("4. Set: Encoding=μ-law, Sample rate=8000 Hz, Channels=Mono")
            print("5. Click Import and play")
            print("6. Audio should be crystal clear with no static!")
        else:
            print("❌ Failed to save test file")
            return False
        
        # Test endpoints info
        print("\n🌐 ENDPOINT TESTING:")
        print("Test the following endpoints in the morning:")
        print("• GET  /test-static-killer          - Test conversion")
        print("• POST /static-killer-voice         - TwiML for phone testing")
        print("• WS   /static-killer-stream        - WebSocket streaming")
        print("• POST /test-audio-play             - Direct playback test")
        
        print("\n📞 PHONE TESTING:")
        print("1. Update Twilio webhook URL to: /static-killer-voice")
        print("2. Call your number")
        print("3. Compare audio quality with regular /voice endpoint")
        print("4. Static Killer should have ZERO static!")
        
        print("\n✅ Static Killer test system ready!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        logger.exception("Full error details:")
        return False

async def compare_systems():
    """Show comparison between old vs new systems."""
    
    print("\n🔍 SYSTEM COMPARISON")
    print("=" * 50)
    
    print("📊 OLD SYSTEM (current):")
    print("• Uses Python audioop for μ-law conversion")
    print("• May inject headers/padding causing static")
    print("• Endpoint: /voice or /coqui-stream")
    
    print("\n⚡ STATIC KILLER SYSTEM (new):")
    print("• Uses FFmpeg for proven raw μ-law conversion")
    print("• Headerless format as recommended in Static Hell guide")
    print("• Proper 160ms chunking for optimal streaming")
    print("• Endpoint: /static-killer-voice")
    
    print("\n🧪 A/B TESTING PLAN:")
    print("1. Test current system: Call your number (uses /voice)")
    print("2. Note any static or audio issues")
    print("3. Update webhook to /static-killer-voice")  
    print("4. Test Static Killer system: Call again")
    print("5. Compare audio quality - should be night and day!")

if __name__ == "__main__":
    print("🌅 Good morning! Ready to kill some static?")
    
    # Run tests
    success = asyncio.run(test_static_killer())
    
    if success:
        asyncio.run(compare_systems())
        print("\n🎯 Everything is ready for testing!")
        print("Sweet dreams were had, now let's eliminate that static! 😴➡️🔪")
    else:
        print("\n💥 Setup issues found - check the errors above")
        sys.exit(1)