# Artist Hotline Documentation

This directory contains documentation for the Artist Hotline project, organized by purpose.

## Quick Reference

### Session Documentation
- **SESSION_FINAL_WRAPUP.md** - Complete overview of October 17, 2025 session
- **README_SESSION_SUMMARY.md** - Quick start guide for what was accomplished

### Code Cleanup Guides
- **CODE_CLEANUP_RECOMMENDATIONS.md** - Detailed analysis of code to clean up
- **CLEANUP_QUICK_START.md** - Step-by-step cleanup instructions (1-2 hours)
- **NEXT_STEPS.md** - Future improvements and technical debt tracking

### Feature Planning
- **CONVERSATION_IMPROVEMENTS.md** - Plans for caller memory and conversation variety
- **IMPLEMENT_CALLER_MEMORY.md** - Quick implementation guide for caller memory system
- **REALTIME_API_SETUP.md** - OpenAI Realtime API integration notes

## Project Structure

```
artist-hotline/
├── main.py                    # FastAPI server + WebSocket handler (production)
├── caller_memory.py          # Caller memory system (future feature)
├── realtime_api_handler.py   # OpenAI Realtime API handler (future feature)
├── requirements.txt          # Python dependencies
├── README.md                 # Main project README
│
├── docs/                     # Documentation (you are here)
│   ├── README.md            # This file
│   ├── Session docs/        # What was accomplished
│   ├── Cleanup guides/      # How to clean up the code
│   └── Feature plans/       # Future improvements
│
└── archive/                  # Archived experimental code
    ├── simple_tts.py        # Simple TTS implementation (reference)
    ├── coqui_tts.py         # Coqui TTS implementation (reference)
    ├── static_killer.py     # FFmpeg audio processing (reference)
    ├── audio_utils.py       # Audio utilities (reference)
    ├── test_*.py            # Old test scripts
    └── vocode_config.py     # Old Vocode configuration
```

## Current System Status

**Status:** PRODUCTION READY
**Deployed:** Railway (https://artist-hotline-production.up.railway.app)
**Phone Number:** Twilio (configured)

### What Works
- Real-time voice conversations via Twilio WebSocket
- Speech-to-text with OpenAI Whisper
- AI responses with GPT-4o-mini
- Text-to-speech with ElevenLabs
- Conversation memory within a call
- Natural 2-second pause detection
- Junk transcription filtering

### What's Next
1. **Code Cleanup** (1-2 hours) - Remove ~1,200 lines of test code
2. **Testing** (ongoing) - 50+ real conversations
3. **Monitoring** (1 hour) - Add Sentry for error tracking
4. **Caller Memory** (30 minutes) - Remember returning callers
5. **Improvements** (ongoing) - See NEXT_STEPS.md

## Performance Metrics

- **Response Time:** 4-5 seconds (excellent)
- **Cost per Call:** $0.10-0.15 (5-minute call)
- **Monthly Cost:** $10-40/month (low-moderate usage)
- **Uptime:** 100% since deployment

## Quick Commands

```bash
# Check health
curl https://artist-hotline-production.up.railway.app/health

# View Railway logs
railway logs

# Run locally
uvicorn main:app --reload

# Deploy to Railway
git push origin main  # Auto-deploys
```

## Need Help?

1. Check **SESSION_FINAL_WRAPUP.md** for complete system overview
2. Check **CODE_CLEANUP_RECOMMENDATIONS.md** for cleanup guidance
3. Check **NEXT_STEPS.md** for future improvements
4. Review main **README.md** for setup instructions

## Archive

The `/archive` directory contains experimental code from development:
- Old TTS implementations (simple_tts, coqui_tts, static_killer)
- Test scripts (test_audio_pipeline, test_streaming, etc.)
- Legacy configurations (vocode_config)

These are kept for reference but not used in production.
