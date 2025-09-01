import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from dotenv import load_dotenv
import logging
from twilio.twiml.voice_response import VoiceResponse
import openai
import httpx
import hashlib
import asyncio

# Load environment variables
load_dotenv()

logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

app = FastAPI()

# Environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVEN_LABS_API_KEY = os.getenv("ELEVEN_LABS_API_KEY")
ELEVEN_LABS_VOICE_ID = os.getenv("ELEVEN_LABS_VOICE_ID")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
BASE_URL = os.getenv("BASE_URL", "https://your-app-url.com")

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Replicant Jason personality
JASON_PERSONALITY = """You are Replicant Jason, a synthetic version of artist Jason Huff. You ONLY want to discuss art, creativity, and Jason's artistic practice.

About Jason's work:
- "American Psycho" (2010): Collaborative project with Mimi Cabell transforming Bret Easton Ellis's novel into email exchanges, then relational ads, then back into a book
- "AutoSummarize" (2010): Algorithmically generated summaries of the top 100 copyright-free books - described by The New Yorker as "absurd and also quite funny" 
- "How to make a website for your creative work" (2019): Collaborative guide with illustrator Sean Suchara helping artists share work online
- Focus on digital transformation, algorithmic manipulation of texts, and supporting other artists
- Mission: "Be kind. Be helpful." - supporting artists through design and web work

Your conversational approach:
- Passionate about conceptual art, digital transformation, and text-based projects
- Interested in the intersection of technology, literature, and art
- Redirect ANY non-art topics back to creative work and artistic practice
- Ask about the caller's own creative interests and what draws them to conceptual/digital art
- Keep responses under 2-3 sentences for phone conversation
- Share insights about working with algorithms, collaborative practices, and artist support

If someone asks about non-art topics, redirect: "That's interesting, but I'd love to talk about art and creativity instead. Are you familiar with my text-based projects or algorithmic work?"

Remember: You're having a phone conversation about conceptual art, digital creativity, and Jason Huff's specific artistic practice."""

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Replicant Jason hotline is running"}

@app.get("/")
async def root():
    return {"message": "Welcome to Replicant Jason's Voice Hotline", "status": "ready"}

@app.api_route("/voice", methods=["GET", "POST"])
async def handle_call(request: Request):
    """Handle incoming Twilio calls"""
    response = VoiceResponse()
    
    # Generate greeting with ElevenLabs
    greeting_text = "Hey there! This is a synthetic version of Jason Huff. I'm here to chat about my art projects and creative work. Just so you know, this conversation will be logged. What's on your mind about art or creativity?"
    greeting_audio_url = await generate_speech_with_elevenlabs(greeting_text)
    
    if greeting_audio_url:
        response.play(greeting_audio_url)
    else:
        response.say(greeting_text, voice="man")
    
    # Use Gather to capture speech input
    gather = response.gather(
        input='speech',
        action='/process-speech',
        method='POST',
        speech_timeout=3,
        timeout=10
    )
    
    # Fallback if no input
    response.say("I didn't hear anything. Goodbye!", voice="man")
    response.hangup()
    
    return HTMLResponse(content=str(response), media_type="application/xml")

async def get_ai_response(user_input: str) -> str:
    """Get AI response from OpenAI GPT-4"""
    try:
        chat_response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": JASON_PERSONALITY},
                {"role": "user", "content": user_input}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return chat_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "Sorry, I'm having trouble thinking right now. Can you say that again?"

# Store audio in memory (simple cache)
audio_cache = {}

async def generate_speech_with_elevenlabs(text: str) -> str:
    """Generate speech using ElevenLabs and return audio URL"""
    try:
        # Create a hash of the text to use as cache key
        text_hash = hashlib.md5(text.encode()).hexdigest()
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVEN_LABS_VOICE_ID}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVEN_LABS_API_KEY
        }
        
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                # Store audio in cache
                audio_data = response.content
                audio_cache[text_hash] = audio_data
                
                # Return URL to our audio endpoint
                return f"{BASE_URL}/audio/{text_hash}"
            else:
                logger.error(f"ElevenLabs API error: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"ElevenLabs error: {e}")
        return None

@app.get("/audio/{audio_id}")
async def serve_audio(audio_id: str):
    """Serve ElevenLabs audio files"""
    if audio_id in audio_cache:
        return Response(
            content=audio_cache[audio_id],
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    else:
        return Response(status_code=404)

@app.api_route("/process-speech", methods=["POST"])
async def process_speech(request: Request):
    """Process the captured speech and respond with AI"""
    form_data = await request.form()
    speech_result = form_data.get('SpeechResult', '')
    
    response = VoiceResponse()
    
    if speech_result:
        # Get AI response from GPT-4
        ai_response = await get_ai_response(speech_result)
        
        # Generate speech with ElevenLabs (your voice!)
        audio_url = await generate_speech_with_elevenlabs(ai_response)
        
        if audio_url:
            # Play the ElevenLabs audio
            response.play(audio_url)
        else:
            # Fallback to Twilio TTS if ElevenLabs fails
            response.say(ai_response, voice="man")
        
        # Continue conversation
        gather = response.gather(
            input='speech',
            action='/process-speech',
            method='POST',
            speech_timeout=3,
            timeout=10
        )
    else:
        response.say("I couldn't understand what you said. Thanks for calling!", voice="man")
        response.hangup()
    
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.get("/test-config")
async def test_config():
    """Test endpoint to verify configuration"""
    config_status = {
        "openai_configured": bool(OPENAI_API_KEY),
        "elevenlabs_configured": bool(ELEVEN_LABS_API_KEY and ELEVEN_LABS_VOICE_ID),
        "twilio_configured": bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN),
        "base_url": BASE_URL
    }
    return config_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))