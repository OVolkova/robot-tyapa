# Tyapa 🐕

An AI-powered robot dog that can see, talk, listen, learn to walk, and navigate your home.

## Why "Tyapa"?
Tyapa is named after the paper robot dog from Encyclopedia of Professor Fortran (Энциклопедия профессора Фортрана, 1991) — a beloved post-Soviet-era children's book that taught kids computer science through comics. In the book, a cat named X builds a robot dog called Tyapa and writes programs for it. One of the book's interactive exercises lets you follow Tyapa's program step by step to navigate through a neighbourhood and find X's friend's house — basically embodied AI, years before the term existed.

Thirty years later, I'm building the real Tyapa. A robot dog that listens, speaks, sees through a camera, and learns to walk and find its way around the house — not on paper, but on four actual legs. The technology changed. The joy of watching a small dog figure out where to go didn't.

---

## What it does

Raspberry Pi 5 orchestrator for the [Petoi Bittle](https://www.petoi.com/products/petoi-robot-dog-bittle) robot dog.

Records voice from an INMP441 microphone, transcribes with Whisper, generates a response and robot action with an LLM, synthesises speech with Kokoro TTS, plays it through a MAX98357A amplifier, and sends the action as a serial command to the Petoi BiBoard.

```
mic → Whisper STT → LLM → Kokoro TTS → speaker
                     ↓
              Petoi serial command
```

---

## Hardware

| Component | Notes |
|-----------|-------|
| Raspberry Pi 5 (4 GB+) | Runs all models locally |
| INMP441 I2S microphone | GPIO 18/19/20, ALSA device `mic_mono` |
| MAX98357A I2S amplifier | GPIO 18/19/21, ALSA device `default` |
| Petoi BiBoard (ESP32) | Connected via Grove G2 → GPIO 14/15 UART |

---

## Setup

### System packages

**Raspberry Pi (Pi OS Bookworm):**

Pi OS Bookworm ships with Python 3.11, which is the required version.
```bash
sudo apt install -y portaudio19-dev
```

**macOS (for local development):**
```bash
brew install portaudio
```

### Install tooling and dependencies

```bash
bash setup.sh
```

`setup.sh` installs [uv](https://docs.astral.sh/uv/) (Python package manager) and [just](https://just.systems/) (task runner) if they are not already present, then runs `uv sync --extra dev` to install all project dependencies.

After that, `just` lists all available commands:

```
$ just
Available recipes:
    install  # uv sync --extra dev
    test     # pytest + coverage
    lint     # ruff check
    format   # ruff format
    check    # lint + format check (read-only)
    ci       # check + test
```

### Environment variables
```bash
export OPENAI_API_KEY=sk-...       # required
export LLM_PROVIDER=openai         # optional, default: openai
export LLM_MODEL=gpt-4o-mini       # optional, default: gpt-5.4-nano
```

---

## Configuration

All settings are in [`robot_tyapa/config.py`](robot_tyapa/config.py).

| Setting | Default | Notes |
|---------|---------|-------|
| `SAMPLE_RATE` | `16000` | INMP441 native rate |
| `RECORD_DEVICE` | `"mic_mono"` | ALSA alias for left-channel mic |
| `PLAYBACK_DEVICE` | `"default"` | Routes through softvol → dmixer → amp |
| `VAD_RMS_THRESHOLD` | `800` | Raise if servo noise triggers false starts |
| `VAD_SILENCE_MS` | `500` | Silence after speech ends recording |
| `VAD_MAX_RECORD_S` | `15` | Hard ceiling per utterance |
| `STT_MODEL` | `"openai/whisper-tiny.en"` | Swap for `whisper-base.en` for better accuracy |
| `TTS_VOICE` | `"af_heart"` | Kokoro voice |
| `TTS_LANG_CODE` | `"b"` | British English; must match voice |
| `TTS_SPEED` | `1.0` | Speech rate |
| `ROBOT_PORT` | `"/dev/serial0"` | Symlink → ttyAMA10 on Pi 5 |
| `ROBOT_BAUD` | `115200` | BiBoard baud rate |

---

## Running

```bash
uv run python -m robot_tyapa.main
```

The first run takes ~30 seconds to load Whisper and Kokoro models. Once you see `Tyapa online. Listening...`, speak to the dog.

---

## Development

```bash
uv sync --extra dev   # install dev deps

just lint             # ruff check
just format           # ruff format
just test             # pytest + coverage
just ci               # full lint + test
```
