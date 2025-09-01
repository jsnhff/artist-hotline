import os
from fastapi import FastAPI, Request, Response
from dotenv import load_dotenv
import logging

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

@app.post("/voice")
async def handle_call(request: Request):
    """Handle incoming Twilio calls - will be implemented with proper Vocode integration"""
    from twilio.twiml import VoiceResponse
    
    twiml = VoiceResponse()
    twiml.say("Hello! This is a test version of Replicant Jason. Full voice functionality coming soon!")
    
    return Response(content=str(twiml), media_type="application/xml")

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