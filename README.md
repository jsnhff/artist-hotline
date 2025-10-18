# Artist Hotline - AI Voice Assistant

A real-time AI voice hotline that lets callers have natural conversations with Synthetic Jason, an AI assistant powered by OpenAI and ElevenLabs.

## Features

- **Real-time voice conversations** via Twilio WebSocket streaming
- **AI-powered responses** using GPT-4o-mini
- **Natural text-to-speech** using ElevenLabs voice cloning
- **Speech-to-text** with OpenAI Whisper
- **Conversation memory** within each call
- **Natural timing** with 2-second silence detection
- **FastAPI backend** deployed on Railway

## Prerequisites

Before setting up the project, you'll need accounts and API keys for:

1. **OpenAI** - For GPT-4o-mini conversations and Whisper transcription
2. **ElevenLabs** - For voice synthesis (with your voice cloned)
3. **Twilio** - For phone number and WebSocket call handling

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
git clone <your-repo-url>
cd artist-hotline
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your actual API keys:

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-your-actual-openai-key

# ElevenLabs Configuration  
ELEVEN_LABS_API_KEY=your-actual-elevenlabs-key
ELEVEN_LABS_VOICE_ID=your-actual-voice-id

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-actual-twilio-sid
TWILIO_AUTH_TOKEN=your-actual-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Application Configuration
BASE_URL=https://your-deployed-app-url.com
PORT=8000
```

### 3. Get Your ElevenLabs Voice ID

1. Log into your ElevenLabs account
2. Go to Voice Lab
3. Select your cloned voice
4. Copy the Voice ID from the settings

### 4. Local Development

Run the application locally:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The app will be available at `http://localhost:8000`

### 5. Test the Health Endpoint

```bash
curl http://localhost:8000/health
```

Should return: `{"status": "healthy", "message": "Replicant Jason hotline is running"}`

## Deployment

### Deploy to Render

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Set the build command: `pip install -r requirements.txt`
4. Set the start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add all environment variables from your `.env` file
6. Deploy!

### Deploy to Railway

1. Connect your GitHub repository to Railway
2. Set environment variables in the Railway dashboard
3. Railway will auto-detect the Python app and deploy

### Twilio Webhook Configuration

Once deployed, configure your Twilio phone number:

1. Go to Twilio Console → Phone Numbers → Manage → Active numbers
2. Click on your phone number
3. Set the webhook URL to: `https://your-app-url.com/voice`
4. Set HTTP method to `POST`
5. Set the status callback URL to: `https://your-app-url.com/call-status` (for call summaries)
6. Save the configuration

## Usage

1. Call your Twilio phone number
2. You'll hear Replicant Jason's greeting
3. Start speaking - your voice will be transcribed
4. GPT-4 generates a response in Jason's personality
5. ElevenLabs synthesizes the response in Jason's voice
6. The conversation continues in real-time!

## Customization

### Personality Customization

Edit the system prompt in the `get_ai_response()` function in `main.py` to change Synthetic Jason's personality, conversation style, and behavior.

### Voice Settings

Adjust ElevenLabs voice parameters in `main.py`:
- `voice_id`: Your cloned voice ID from ElevenLabs
- `model_id`: Currently using `eleven_flash_v2_5` for speed
- Adjust in the `generate_speech_with_elevenlabs()` function

## Troubleshooting

### Common Issues

1. **No response from calls**: Check that your Twilio webhook URL is correct and publicly accessible
2. **Poor voice quality**: Adjust ElevenLabs stability and similarity_boost settings
3. **Transcription errors**: Verify Deepgram API key and model settings
4. **OpenAI errors**: Ensure your API key has sufficient credits and access to GPT-4

### Logs

Check application logs for debugging:

```bash
# Local development
uvicorn main:app --log-level debug

# On Render/Railway
Check the deployment logs in your dashboard
```

### Testing Locally with ngrok

For local testing with Twilio webhooks:

```bash
# Install ngrok
npm install -g ngrok

# Expose local server
ngrok http 8000

# Use the ngrok URL as your Twilio webhook: https://abc123.ngrok.io/voice
```

## Architecture

```
Caller → Twilio WebSocket → FastAPI App (main.py)
              (µ-law audio)       ↓
                          ┌─────────────────┐
                          │ Silence Detect  │
                          │  (2s pause)     │
                          └────────┬────────┘
                                   ↓
                 ┌─────────────────────────────────────┐
                 ↓                ↓                    ↓
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │   Whisper    │ │ GPT-4o-mini  │ │ ElevenLabs   │
          │(Transcribe)  │ │  (Respond)   │ │ (Synthesize) │
          └──────────────┘ └──────────────┘ └──────────────┘
                                   ↓
                          ┌─────────────────┐
                          │ Audio Convert   │
                          │ MP3 → µ-law     │
                          └────────┬────────┘
                                   ↓
                          Back to caller via
                          Twilio WebSocket
```

## Documentation

See the `docs/` directory for detailed documentation:
- **docs/SESSION_FINAL_WRAPUP.md** - Complete system overview
- **docs/CODE_CLEANUP_RECOMMENDATIONS.md** - Code cleanup guide
- **docs/NEXT_STEPS.md** - Future improvements and roadmap

## License

MIT License - feel free to use this for your own voice hotline projects!