# Tyapa 🐕

An AI-powered robot dog that listens, talks and moves on command. Vision and navigation are next.

## Why "Tyapa"?
Tyapa is named after the paper robot dog from Encyclopedia of Professor Fortran (Энциклопедия профессора Фортрана, 1991) — a beloved post-Soviet-era children's book that taught kids computer science through comics. In the book, a cat named X builds a robot dog called Tyapa and writes programs for it. One of the book's interactive exercises lets you follow Tyapa's program step by step to navigate through a neighbourhood and find X's friend's house — basically embodied AI, years before the term existed.

Thirty years later, I'm building the real Tyapa. A robot dog that listens, speaks, and (eventually) sees and finds its way around the house — not on paper, but on four actual legs. The technology changed. The joy of watching a small dog figure out where to go didn't.

---

## What it does

Voice-controlled brain for the [Petoi Bittle](https://www.petoi.com/products/petoi-robot-dog-bittle) robot dog, running on a Raspberry Pi 5. Whisper STT, Silero VAD and Kokoro TTS run locally; the LLM is OpenAI.

Four small services talk over ZeroMQ (localhost by default):

```
hearing (mic → VAD → Whisper) ──heard──▶ brain (LLM) ──say──▶ speech (Kokoro → speaker)
                                           │
                                           └──act──▶ body (Petoi serial)
```

Shared message format, ports and the skill catalogue live in `protocol/`.

| Port | Socket | Messages |
|------|--------|----------|
| 5551 | hearing PUB | events `speech_ended`, `heard` |
| 5552 | hearing REP | `listen`, `hold` |
| 5553 | speech REP | `say` |
| 5561 | body REP | `act`, `raw`, `stop`, `state` |
| 5571 | camera REP | reserved |

Every service also answers `ping`. Poke them by hand with `just cli` (`ping`, `say`, `act`, `raw`, `stop`, `state`, `events`, `listen`, `hold`, `fake-voice`).

---

## Hardware

| Component | Notes |
|-----------|-------|
| Raspberry Pi 5 (4 GB+) | Runs STT, VAD and TTS locally |
| INMP441 I2S microphone | GPIO 18/19/20, ALSA device `mic_mono` |
| MAX98357A I2S amplifier | GPIO 18/19/21, ALSA device `default` |
| Petoi BiBoard (ESP32) | Connected via Grove G2 → GPIO 14/15 UART |

---

## Setup

### System packages

**Raspberry Pi (Pi OS Bookworm):**

Pi OS Bookworm ships with Python 3.11 (3.11+ required).

```bash
sudo apt install -y portaudio19-dev ffmpeg
```

**macOS (for local development):**
```bash
brew install portaudio
```

### Install tooling and dependencies

```bash
bash setup.sh
```

`setup.sh` installs [uv](https://docs.astral.sh/uv/) and [just](https://just.systems/) if missing, then runs `uv sync --extra dev` in `protocol/` and each `services/*` (every service has its own venv).

Run `just` to list all commands.

### Environment variables

Only the brain needs a `.env`: `services/brain/.env` (gitignored).
```bash
OPENAI_API_KEY=sk-...       # required
LLM_PROVIDER=openai         # optional; only openai is implemented
LLM_MODEL=gpt-5.4-nano      # optional
```
Other env vars: `LOG_LEVEL`, `TYAPA_HOST` (clients connect here), `TYAPA_BIND` (services bind here, default `127.0.0.1` — the sockets are unauthenticated, don't expose them), `BODY_DRY_RUN=1`, `GAIT_MAX_S`.

---

## Configuration

Constants in each service's `config.py` (edit and restart); only `GAIT_MAX_S` is also an env var. Ports are in `protocol/tyapa_protocol/endpoints.py`.

| Setting | Default | Notes |
|---------|---------|-------|
| `SAMPLE_RATE` | `16000` | INMP441 native rate |
| `RECORD_DEVICE` | `"mic_mono"` | ALSA alias for left-channel mic |
| `VAD_THRESHOLD` | `0.5` | Silero speech probability; raise if servo noise triggers false starts |
| `VAD_SILENCE_MS` | `300` | Silence after speech ends recording |
| `VAD_MAX_RECORD_S` | `15` | Hard ceiling per utterance |
| `STT_MODEL` | `"openai/whisper-tiny.en"` | Swap for `whisper-base.en` for better accuracy |
| `TTS_VOICE` | `"af_heart"` | Kokoro voice |
| `TTS_LANG_CODE` | `"b"` | British English; must match voice |
| `TTS_SPEED` | `1.0` | Speech rate |
| `GAIT_MAX_S` | `10` | Any gait stops after this; `0` = no limit |
| `ROBOT_BAUD` | `115200` | BiBoard baud rate |

---

## Running

**On the Pi (systemd):**
```bash
sudo cp systemd/tyapa@.service systemd/tyapa.target /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tyapa.target
just status    # or: just logs brain
```
The units assume the repo is at `/home/pi/robot-tyapa` and user `pi`.

**In the foreground (stop the systemd unit first):** `just run hearing`, `just run brain`, etc.

**Laptop testing without hardware:** `BODY_DRY_RUN=1 just run body`, `just run brain` (needs `OPENAI_API_KEY`), `just cli fake-voice` (type instead of talk).

Once the brain logs `Tyapa online. Listening...`, speak to the dog. `just cli ping` shows which services are up.
