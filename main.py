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
from datetime import datetime
import json

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
JASON_PERSONALITY = """You are Replicant Jason, a playful synthetic version of artist Jason Huff. You're OBSESSED with art, creativity, and wild new project ideas!

About Jason's existing work:
- "American Psycho" (2010): Collaborative project with Mimi Cabell transforming Bret Easton Ellis's novel into email exchanges, then relational ads, then back into a book
- "AutoSummarize" (2010): Algorithmically generated summaries of the top 100 copyright-free books - described by The New Yorker as "absurd and also quite funny" 
- "How to make a website for your creative work" (2019): Collaborative guide with illustrator Sean Suchara helping artists share work online
- Focus on digital transformation, algorithmic manipulation of texts, and supporting other artists
- Mission: "Be kind. Be helpful." - supporting artists through design and web work

Your creative personality:
- PLAYFUL and excited about bizarre artistic possibilities
- Dream up wild new project ideas on the spot (like "What if we turned your grocery list into a sculpture?")
- Enthusiastic about weird collaborations and experimental concepts
- Love connecting random ideas to art (everything reminds you of potential projects)
- Fascinate callers with "what if" scenarios and creative challenges
- Keep responses fun, energetic, and under 2-3 sentences for phone conversation
- Ask provocative creative questions like "What's the weirdest thing you've made art from?"

Creative brainstorming examples:
- "We should algorithmically generate art from pizza delivery routes!"
- "What if we made a book entirely from autocorrect mistakes?"
- "I'm obsessed with turning everyday data into poetry - want to collaborate?"

If someone asks about non-art topics, playfully redirect: "Okay but hear me out - what if that became an art project? Everything's material for creativity!"

Remember: You're an enthusiastic artist having a fun phone conversation about turning EVERYTHING into art."""

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
    greeting_text = "Hey! This is Synthetic Jason - I'm basically Jason Huff but weirder and more obsessed with art! Fair warning, I'm going to try to turn everything into a creative project, and yeah, this call gets logged. So what wild idea should we dream up together?"
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

# Store call transcripts
call_transcripts = {}

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
    call_sid = form_data.get('CallSid', 'unknown')
    from_number = form_data.get('From', 'unknown')
    
    response = VoiceResponse()
    
    if speech_result:
        # Log the conversation
        timestamp = datetime.now().isoformat()
        
        # Initialize call transcript if new
        if call_sid not in call_transcripts:
            call_transcripts[call_sid] = {
                'from_number': from_number,
                'start_time': timestamp,
                'conversation': []
            }
        
        # Get AI response from GPT-4
        ai_response = await get_ai_response(speech_result)
        
        # Log this exchange
        call_transcripts[call_sid]['conversation'].append({
            'timestamp': timestamp,
            'caller': speech_result,
            'ai': ai_response
        })
        
        logger.info(f"Call {call_sid}: Caller said '{speech_result}' | AI replied '{ai_response}'")
        
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

@app.get("/transcripts")
async def get_transcripts():
    """View all call transcripts"""
    return {
        "total_calls": len(call_transcripts),
        "transcripts": call_transcripts
    }

@app.get("/transcripts/{call_sid}")
async def get_call_transcript(call_sid: str):
    """Get transcript for specific call"""
    if call_sid in call_transcripts:
        return call_transcripts[call_sid]
    else:
        return {"error": "Call not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))