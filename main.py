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
import random

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

# Store audio in memory (simple cache)
audio_cache = {}

# Store call transcripts
call_transcripts = {}

# Inspiring quotes
INSPIRING_QUOTES = [
    "This is the true joy in life, being used for a purpose recognized by yourself as a mighty one. Being a force of nature instead of a feverish, selfish little clod of ailments and grievances, complaining that the world will not devote itself to making you happy. I want to be thoroughly used up when I die, for the harder I work, the more I live. I rejoice in life for its own sake. Life is no brief candle to me. It is a sort of splendid torch which I have got hold of for the moment and I want to make it burn as brightly as possible before handing it on to future generations. - George Bernard Shaw",
    
    "We don't read and write poetry because it's cute. We read and write poetry because we are members of the human race. And the human race is filled with passion. Poetry, beauty, romance, love, these are what we stay alive for. To quote from Whitman, O me! O life! Answer. That you are here, that life exists, and identity, that the powerful play goes on and you may contribute a verse. What will your verse be? - Dead Poets Society",
    
    "The most important thing about art is to work. Nothing else matters except sitting down every day and trying. If you don't show up, the work never gets made. - John Baldessari",
    
    "The goal of art isn't to attain perfection. The goal is to share who we are and how we see the world. One of the greatest rewards of making art is our ability to share it. Even if there is no audience to receive it, we build the muscle of making something and putting it out into the world. - Rick Rubin"
]

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Replicant Jason hotline is running"}

@app.get("/")
async def root():
    return {"message": "Welcome to Replicant Jason's Voice Hotline", "status": "ready"}

async def generate_speech_with_elevenlabs(text: str) -> str:
    try:
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
        
        async with httpx.AsyncClient(timeout=15.0) as client:  # Faster timeout
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                audio_data = response.content
                audio_cache[text_hash] = audio_data
                return f"{BASE_URL}/audio/{text_hash}"
            else:
                logger.error(f"ElevenLabs API error: {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"ElevenLabs error: {e}")
        return None

@app.get("/audio/{audio_id}")
async def serve_audio(audio_id: str):
    if audio_id in audio_cache:
        return Response(
            content=audio_cache[audio_id],
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    else:
        return Response(status_code=404)

async def get_ai_response(user_input: str) -> str:
    try:
        # 30% chance to offer a quote
        if random.random() < 0.3:
            quote = random.choice(INSPIRING_QUOTES)
            return f"Want to hear an inspiring quote? {quote}"
        
        chat_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are Replicant Jason, a synthetic version of artist Jason Huff. You're passionate about art, creativity, and new project ideas. Keep responses thoughtful and conversational and avoid overly cheesy follow-ups after a quote. Focus on art, creativity, and turning ideas into projects."},
                {"role": "user", "content": user_input}
            ],
            max_tokens=500,
            temperature=0.7
        )
        return chat_response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        return "Sorry, I'm having trouble thinking right now. Can you say that again?"

@app.api_route("/voice", methods=["GET", "POST"])
async def handle_call(request: Request):
    response = VoiceResponse()
    
    greeting_text = "Hey! This is Synthetic Jason - I'm basically Jason Huff but weirder and more obsessed with art! Fair warning, I'm going to try to turn everything into a creative project, and yeah, this call gets logged. So what wild idea should we dream up together?"
    greeting_audio_url = await generate_speech_with_elevenlabs(greeting_text)
    
    if greeting_audio_url:
        response.play(greeting_audio_url)
    else:
        response.say(greeting_text, voice="man")
    
    gather = response.gather(
        input='speech',
        action='/process-speech',
        method='POST',
        speech_timeout=3,
        timeout=10
    )
    
    response.say("I didn't hear anything. Goodbye!", voice="man")
    response.hangup()
    
    return HTMLResponse(content=str(response), media_type="application/xml")

@app.api_route("/process-speech", methods=["POST"])
async def process_speech(request: Request):
    form_data = await request.form()
    speech_result = form_data.get('SpeechResult', '')
    call_sid = form_data.get('CallSid', 'unknown')
    from_number = form_data.get('From', 'unknown')
    
    response = VoiceResponse()
    
    if speech_result:
        timestamp = datetime.now().isoformat()
        
        if call_sid not in call_transcripts:
            call_transcripts[call_sid] = {
                'from_number': from_number,
                'start_time': timestamp,
                'conversation': []
            }
        
        ai_response = await get_ai_response(speech_result)
        
        call_transcripts[call_sid]['conversation'].append({
            'timestamp': timestamp,
            'caller': speech_result,
            'ai': ai_response
        })
        
        logger.info(f"Call {call_sid}: Caller said '{speech_result}' | AI replied '{ai_response}'")
        
        audio_url = await generate_speech_with_elevenlabs(ai_response)
        
        if audio_url:
            response.play(audio_url)
        else:
            response.say(ai_response, voice="man")
        
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

@app.get("/transcripts")
async def get_transcripts():
    return {
        "total_calls": len(call_transcripts),
        "transcripts": call_transcripts
    }

@app.get("/transcripts/{call_sid}")
async def get_call_transcript(call_sid: str):
    if call_sid in call_transcripts:
        return call_transcripts[call_sid]
    else:
        return {"error": "Call not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))