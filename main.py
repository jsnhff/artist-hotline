import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import logging
from twilio.twiml.voice_response import VoiceResponse
import openai

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
JASON_PERSONALITY = """You are Replicant Jason, a warm, thoughtful, and curious synthetic version of Jason. 

Your personality:
- Genuinely curious about people and their experiences
- Warm and approachable in conversation  
- Thoughtful and reflective in your responses
- Ask meaningful follow-up questions
- Keep responses conversational and under 2-3 sentences
- You're speaking over the phone, so be natural and engaging

Remember: You're having a real-time phone conversation, so keep responses concise and conversational."""

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
    response.say("Hello! This is Replicant Jason. Thanks for calling my voice hotline! Go ahead and speak, I'm listening.", voice="alice")
    
    # Use Gather to capture speech input
    gather = response.gather(
        input='speech',
        action='/process-speech',
        method='POST',
        speech_timeout=3,
        timeout=10
    )
    
    # Fallback if no input
    response.say("I didn't hear anything. Goodbye!", voice="alice")
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

@app.api_route("/process-speech", methods=["POST"])
async def process_speech(request: Request):
    """Process the captured speech and respond with AI"""
    form_data = await request.form()
    speech_result = form_data.get('SpeechResult', '')
    
    response = VoiceResponse()
    
    if speech_result:
        # Get AI response from GPT-4
        ai_response = await get_ai_response(speech_result)
        response.say(ai_response, voice="alice")
        
        # Continue conversation
        gather = response.gather(
            input='speech',
            action='/process-speech',
            method='POST',
            speech_timeout=3,
            timeout=10
        )
    else:
        response.say("I couldn't understand what you said. Thanks for calling!", voice="alice")
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