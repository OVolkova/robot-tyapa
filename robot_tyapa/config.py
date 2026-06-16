import os

# Audio hardware
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024
RECORD_DEVICE = "mic_mono"  # ALSA alias defined in /etc/asound.conf
PLAYBACK_DEVICE = "default"  # routes: softvol -> dmixer -> tyapaaudio device 1

# VAD (Voice Activity Detection)
VAD_THRESHOLD = 0.5  # silero speech probability cutoff (0–1)
VAD_SILENCE_MS = 300  # trailing silence before end-of-speech event
VAD_MAX_RECORD_S = 15  # hard cap on recording length once speech starts
VAD_MIN_SPEECH_S = 0.3  # discard bursts shorter than this
VAD_NO_SPEECH_TIMEOUT_S = 30  # return None if no speech detected within this window

# STT — Whisper model (any HuggingFace whisper variant)
STT_MODEL = (
    "openai/whisper-tiny.en"  # faster; swap for "openai/whisper-base.en" for better accuracy
)

# TTS — Kokoro voice settings
TTS_VOICE = "af_heart"  # see kokoro docs for available voices
TTS_LANG_CODE = "b"  # "b" = British English; must match voice
TTS_SPEED = 1.0

# LLM — forwarded to SpeechToSpeechActionProcessor -> TextToText -> create_llm_client
# OPENAI_API_KEY (or ANTHROPIC_API_KEY) must also be set in environment
LLM_PROVIDER = os.environ.get("LLM_PROVIDER")  # None -> "openai" default
LLM_MODEL = os.environ.get("LLM_MODEL")  # None -> gpt-5.4-nano default

# Robot serial
ROBOT_BAUD = 115200
ROBOT_WAKE_DELAY_S = 0.5
BRAIN_DEFAULT_ACTION = "balance"
