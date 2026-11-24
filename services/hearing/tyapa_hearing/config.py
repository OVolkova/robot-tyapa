# Audio hardware
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024
RECORD_DEVICE = "mic_mono"  # ALSA alias defined in /etc/asound.conf

# VAD (Voice Activity Detection)
VAD_THRESHOLD = 0.5  # silero speech probability cutoff (0-1)
VAD_SILENCE_MS = 300  # trailing silence before end-of-speech event
VAD_MAX_RECORD_S = 15  # hard cap on recording length once speech starts
VAD_MIN_SPEECH_S = 0.3  # discard bursts shorter than this
VAD_NO_SPEECH_TIMEOUT_S = 30  # return None if no speech detected within this window

# speech-to-text (STT) — Whisper model (any HuggingFace whisper variant)
STT_MODEL = "openai/whisper-tiny.en"  # or whisper-base.en for accuracy
STT_SAMPLE_RATE = 16000  # Hz expected by Whisper

# brain silent this long after a 'heard' -> re-open the mic anyway
TURN_TIMEOUT_S = 60
