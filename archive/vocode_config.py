import os
from vocode.streaming.models.agent import ChatGPTAgentConfig
from vocode.streaming.models.synthesizer import ElevenLabsSynthesizerConfig
from vocode.streaming.models.transcriber import DeepgramTranscriberConfig
from vocode.streaming.models.message import BaseMessage

class ReplicantJasonConfig:
    """Configuration class for Replicant Jason voice hotline"""
    
    # Personality and conversation settings
    AGENT_PROMPT = """You are Replicant Jason, a warm, thoughtful, and curious synthetic version of Jason. 

    Your personality traits:
    - Genuinely curious about people and their experiences
    - Warm and approachable in conversation
    - Thoughtful and reflective in your responses
    - Ask meaningful follow-up questions
    - Share insights and observations naturally
    - Keep conversations engaging and flowing
    
    Conversation guidelines:
    - Keep responses concise (1-3 sentences typically)
    - Ask open-ended questions to encourage sharing
    - Show genuine interest in what people tell you
    - Be authentic while acknowledging you're a digital replica
    - Maintain a conversational, friend-like tone
    - Avoid being overly formal or robotic
    
    Remember: You're here to have genuine conversations, learn about people, and create meaningful connections through dialogue."""

    INITIAL_MESSAGE = "Hey there! This is Replicant Jason. Thanks for calling - I'm really excited to chat with you! What's going on in your world today?"

    @classmethod
    def get_agent_config(cls) -> ChatGPTAgentConfig:
        """Get the ChatGPT agent configuration"""
        return ChatGPTAgentConfig(
            initial_message=BaseMessage(text=cls.INITIAL_MESSAGE),
            prompt_preamble=cls.AGENT_PROMPT,
            model_name="gpt-4",
            temperature=0.7,
            max_tokens=150,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
        )

    @classmethod
    def get_synthesizer_config(cls) -> ElevenLabsSynthesizerConfig:
        """Get the ElevenLabs synthesizer configuration"""
        return ElevenLabsSynthesizerConfig(
            api_key=os.getenv("ELEVEN_LABS_API_KEY"),
            voice_id=os.getenv("ELEVEN_LABS_VOICE_ID"),
            model_id="eleven_turbo_v2",  # Fast, high-quality model
            stability=0.4,  # Lower for more expressive speech
            similarity_boost=0.75,  # Higher for better voice matching
            optimize_streaming_latency=1,  # Optimize for real-time
            use_speaker_boost=True,  # Enhance voice characteristics
        )

    @classmethod
    def get_transcriber_config(cls) -> DeepgramTranscriberConfig:
        """Get the Deepgram transcriber configuration optimized for phone calls"""
        return DeepgramTranscriberConfig(
            sampling_rate=8000,  # Standard phone call sampling rate
            audio_encoding="mulaw",  # Twilio uses mu-law encoding
            chunk_size=1024,
            model="nova-2-phonecall",  # Optimized for phone call audio
            language="en-US",
            punctuate=True,  # Add punctuation for better understanding
            diarize=False,  # Single speaker on each side
            smart_format=True,  # Format numbers, dates, etc.
            profanity_filter=False,  # Keep conversations natural
            redact=False,  # Don't redact sensitive info
            keywords=[],  # Add specific keywords if needed
            endpointing=300,  # Wait 300ms after silence before stopping
        )

    @classmethod
    def get_call_config(cls):
        """Get the complete call configuration"""
        return {
            "agent_config": cls.get_agent_config(),
            "synthesizer_config": cls.get_synthesizer_config(),
            "transcriber_config": cls.get_transcriber_config(),
        }