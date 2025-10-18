#!/usr/bin/env python3
"""
Call Simulator - Test voice assistant logic without actual phone calls

This tool simulates the full call flow to test:
- Caller memory and personalized greetings
- Response variety (avoiding repeated questions)
- Conversation history management
- GPT response generation
- Filler words and timing

Usage:
    python call_simulator.py                    # Interactive mode
    python call_simulator.py --test-greetings   # Test greeting variations
    python call_simulator.py --test-conversation "path/to/script.txt"
    python call_simulator.py --phone "+1234567890"  # Simulate specific caller
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional
import openai

# Import your actual logic
from caller_memory import (
    generate_greeting,
    get_caller_info,
    update_caller,
    get_time_since_last_call,
    get_response_style_prompt,
    get_filler_word
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize OpenAI API
openai.api_key = os.environ.get('OPENAI_API_KEY')


class CallSimulator:
    """Simulates a phone call to test voice assistant logic"""

    def __init__(self, phone_number: str = "+15555551234"):
        self.phone_number = phone_number
        self.conversation_history: List[Dict] = []
        self.call_start_time = datetime.now()
        self.exchange_count = 0

    async def start_call(self):
        """Start a simulated call"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📞 SIMULATED CALL STARTED")
        logger.info(f"📱 From: {self.phone_number}")
        logger.info(f"{'='*60}\n")

        # Get caller info
        caller_info = get_caller_info(self.phone_number)
        if caller_info:
            logger.info(f"👤 Caller Info:")
            logger.info(f"   - Call count: {caller_info['call_count']}")
            logger.info(f"   - Last call: {get_time_since_last_call(self.phone_number)}")
            logger.info(f"   - Topics: {caller_info.get('topics_discussed', [])}")
        else:
            logger.info(f"👤 First-time caller!")

        # Generate and display greeting
        greeting = generate_greeting(self.phone_number)
        logger.info(f"\n🎤 AI GREETING:\n   {greeting}\n")

        # Initialize conversation history with response variety
        style_instruction = get_response_style_prompt()
        logger.info(f"🎨 Response Style: {style_instruction[:80]}...")

        base_prompt = "You are Synthetic Jason, an AI version of artist Jason Huff. You're weird, obsessed with art, and love discussing creative ideas. Keep responses under 30 words."
        full_prompt = f"{base_prompt} {style_instruction}"

        self.conversation_history = [
            {"role": "system", "content": full_prompt}
        ]

        logger.info(f"\n{'='*60}")
        logger.info(f"💬 CONVERSATION (type 'quit' to end call)")
        logger.info(f"{'='*60}\n")

    async def send_message(self, user_message: str) -> str:
        """
        Simulate user speaking and get AI response

        This mimics the actual flow:
        1. Silence detected → filler word
        2. Whisper transcription (simulated)
        3. GPT response generation
        4. TTS playback (simulated)
        """
        self.exchange_count += 1

        # Simulate filler word
        filler = get_filler_word()
        logger.info(f"🗣️  Filler word: '{filler}' (played instantly)")

        # Add user message to history
        self.conversation_history.append({"role": "user", "content": user_message})
        logger.info(f"\n👤 USER: {user_message}")

        # Keep only last 10 messages (like production)
        if len(self.conversation_history) > 11:
            self.conversation_history = [self.conversation_history[0]] + self.conversation_history[-10:]

        # Get AI response using actual GPT API
        logger.info(f"🤔 Thinking... (generating response)")
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=self.conversation_history,
                max_tokens=100,
                temperature=0.9
            )

            ai_message = response['choices'][0]['message']['content']

            # Add to history
            self.conversation_history.append({"role": "assistant", "content": ai_message})

            # Check if response ends with question
            has_question = '?' in ai_message

            logger.info(f"\n🎤 AI: {ai_message}")
            if has_question:
                logger.warning(f"⚠️  Response contains question mark (style variety may not be working)")
            else:
                logger.info(f"✅ Response without question (good variety!)")

            return ai_message

        except Exception as e:
            logger.error(f"❌ Error generating response: {e}")
            return "Sorry, I had trouble processing that."

    async def end_call(self):
        """End the simulated call and save memory"""
        logger.info(f"\n{'='*60}")
        logger.info(f"📞 CALL ENDED")
        logger.info(f"{'='*60}")

        call_duration = (datetime.now() - self.call_start_time).total_seconds()
        logger.info(f"⏱️  Duration: {call_duration:.1f} seconds")
        logger.info(f"💬 Exchanges: {self.exchange_count}")

        # Save caller memory
        if self.phone_number != 'unknown':
            try:
                update_caller(self.phone_number)
                logger.info(f"📝 Saved call memory for {self.phone_number}")
            except Exception as e:
                logger.error(f"Failed to save caller memory: {e}")

        logger.info(f"\n{'='*60}\n")


async def interactive_mode(phone_number: str):
    """Run simulator in interactive mode"""
    sim = CallSimulator(phone_number)
    await sim.start_call()

    while True:
        try:
            # Get user input
            user_input = input("\n👤 YOU: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'bye', 'goodbye']:
                await sim.end_call()
                break

            # Get AI response
            await sim.send_message(user_input)

        except KeyboardInterrupt:
            print("\n")
            await sim.end_call()
            break
        except EOFError:
            print("\n")
            await sim.end_call()
            break


async def test_greetings():
    """Test greeting variations for different caller scenarios"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🧪 TESTING GREETING VARIATIONS")
    logger.info(f"{'='*60}\n")

    test_numbers = [
        ("+15555550001", "First-time caller"),
        ("+15555550002", "Returning caller (will simulate)")
    ]

    for phone_number, description in test_numbers:
        logger.info(f"\n📱 Testing: {description} ({phone_number})")

        # Get caller info
        caller_info = get_caller_info(phone_number)
        if caller_info:
            logger.info(f"   Existing caller:")
            logger.info(f"   - Call count: {caller_info['call_count']}")
            logger.info(f"   - Last call: {get_time_since_last_call(phone_number)}")
        else:
            logger.info(f"   New caller (no history)")

        # Generate greeting
        greeting = generate_greeting(phone_number)
        logger.info(f"\n   🎤 Greeting:\n   {greeting}\n")

        # Show multiple style variations
        logger.info(f"   Response style variations (3 samples):")
        for i in range(3):
            style = get_response_style_prompt()
            logger.info(f"   {i+1}. {style[:80]}...")

    logger.info(f"\n{'='*60}\n")


async def test_conversation_script(script_path: str, phone_number: str):
    """Test a pre-written conversation script"""
    logger.info(f"\n{'='*60}")
    logger.info(f"🧪 TESTING CONVERSATION SCRIPT")
    logger.info(f"📄 Script: {script_path}")
    logger.info(f"{'='*60}\n")

    # Read script
    try:
        with open(script_path, 'r') as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        logger.error(f"❌ Script file not found: {script_path}")
        return

    # Run conversation
    sim = CallSimulator(phone_number)
    await sim.start_call()

    for line in lines:
        logger.info(f"\n📝 [Script]: {line}")
        await sim.send_message(line)
        await asyncio.sleep(0.5)  # Small delay for readability

    await sim.end_call()


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Call Simulator - Test voice assistant logic')
    parser.add_argument('--phone', default='+15555551234', help='Phone number to simulate')
    parser.add_argument('--test-greetings', action='store_true', help='Test greeting variations')
    parser.add_argument('--test-conversation', metavar='SCRIPT', help='Test with conversation script file')

    args = parser.parse_args()

    # Check for OpenAI API key
    if not os.environ.get('OPENAI_API_KEY'):
        logger.error("❌ OPENAI_API_KEY environment variable not set!")
        logger.error("   Set it with: export OPENAI_API_KEY='your-key-here'")
        sys.exit(1)

    # Run appropriate mode
    if args.test_greetings:
        await test_greetings()
    elif args.test_conversation:
        await test_conversation_script(args.test_conversation, args.phone)
    else:
        await interactive_mode(args.phone)


if __name__ == '__main__':
    asyncio.run(main())
