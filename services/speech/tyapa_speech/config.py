PLAYBACK_DEVICE = "default"  # routes: softvol -> dmixer -> tyapaaudio device 1

# TTS -- Kokoro voice settings
TTS_VOICE = "af_heart"  # see kokoro docs for available voices
TTS_LANG_CODE = "b"  # "b" = British English; must match voice
TTS_SPEED = 1.0

PLAYBACK_FREQUENCY = 16000  # keep at 16kHz, matches the ALSA playback chain
