# Replicant Jason Voice Hotline

A real-time AI voice hotline that lets callers speak with a synthetic version of Jason using Twilio, ElevenLabs, OpenAI, and the Vocode framework.

## Features

- **Real-time voice conversations** via Twilio phone calls
- **AI-powered responses** using GPT-4
- **Synthetic voice** using ElevenLabs voice cloning
- **Phone call transcription** with Deepgram
- **Warm, curious personality** as "Replicant Jason"
- **FastAPI backend** for easy deployment

## Prerequisites

Before setting up the project, you'll need accounts and API keys for:

1. **OpenAI** - For GPT-4 conversations
2. **ElevenLabs** - For voice synthesis (with your voice cloned)
3. **Twilio** - For phone number and call handling
4. **Deepgram** - For speech-to-text transcription

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

Edit the `AGENT_PROMPT` in `vocode_config.py` to change Replicant Jason's personality, conversation style, and behavior.

### Voice Settings

Adjust ElevenLabs voice parameters in `vocode_config.py`:
- `stability`: Lower = more expressive, Higher = more consistent
- `similarity_boost`: How much to match the original voice
- `model_id`: Use `eleven_turbo_v2` for speed or `eleven_multilingual_v2` for quality

### Transcription Settings

Configure Deepgram settings in `vocode_config.py` for better transcription accuracy based on your use case.

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
Caller → Twilio → FastAPI App → Vocode Framework
                                     ↓
                              ┌─────────────┐
                              │   Vocode    │
                              │ Orchestrator│
                              └─────────────┘
                                     ↓
                 ┌─────────────────────────────────────┐
                 ↓                ↓                    ↓
          ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
          │  Deepgram    │ │    OpenAI    │ │ ElevenLabs   │
          │(Transcribe)  │ │   (GPT-4)    │ │ (Synthesize) │
          └──────────────┘ └──────────────┘ └──────────────┘
```

## License

MIT License - feel free to use this for your own voice hotline projects!