import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import logging
from twilio.twiml.voice_response import VoiceResponse

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

@app.api_route("/process-speech", methods=["POST"])
async def process_speech(request: Request):
    """Process the captured speech and respond"""
    form_data = await request.form()
    speech_result = form_data.get('SpeechResult', '')
    
    response = VoiceResponse()
    
    if speech_result:
        # For now, just echo back what they said
        response.say(f"I heard you say: {speech_result}. That's interesting! Tell me more.", voice="alice")
        
        # Gather more input for continuous conversation
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