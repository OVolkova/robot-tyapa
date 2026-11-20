# Tyapa 🐕

An AI-powered robot dog that can see, talk, listen, learn to walk, and navigate your home.

## Why "Tyapa"?
Tyapa is named after the paper robot dog from Encyclopedia of Professor Fortran (Энциклопедия профессора Фортрана, 1991) — a beloved post-Soviet-era children's book that taught kids computer science through comics. In the book, a cat named X builds a robot dog called Tyapa and writes programs for it. One of the book's interactive exercises lets you follow Tyapa's program step by step to navigate through a neighbourhood and find X's friend's house — basically embodied AI, years before the term existed.

Thirty years later, I'm building the real Tyapa. A robot dog that listens, speaks, sees through a camera, and learns to walk and find its way around the house — not on paper, but on four actual legs. The technology changed. The joy of watching a small dog figure out where to go didn't.

---

## What it does

Raspberry Pi 5 orchestrator for the [Petoi Bittle](https://www.petoi.com/products/petoi-robot-dog-bittle) robot dog.

Four small services talk over ZeroMQ (localhost by default):

```
hearing (mic → VAD → Whisper) ──heard──▶ brain (LLM) ──say──▶ speech (Kokoro → speaker)
                                           │
                                           └──act──▶ body (Petoi serial)
```

Shared message format, ports and the skill catalogue live in `protocol/`.

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

`just` lists all commands: `sync`, `run <svc>`, `cli`, `test`, `lint`, `format`, `check`, `ci`, `status`, `restart`, `stop`, `logs`.

### Environment variables

Per-service, in `services/<svc>/.env` (gitignored). The brain needs:
```bash
OPENAI_API_KEY=sk-...       # required
LLM_PROVIDER=openai         # optional, default: openai
LLM_MODEL=gpt-4o-mini       # optional, default: gpt-5.4-nano
```
Other knobs: `LOG_LEVEL`, `TYAPA_HOST` (clients connect here), `TYAPA_BIND` (services bind here, default `127.0.0.1` — the sockets are unauthenticated, don't expose them), `BODY_DRY_RUN=1`, `GAIT_MAX_S`.

---

## Configuration

Settings live in each service's `config.py` (`services/hearing`, `speech`, `body`, `brain`). Ports are in `protocol/tyapa_protocol/endpoints.py`.

| Setting | Default | Notes |
|---------|---------|-------|
| `SAMPLE_RATE` | `16000` | INMP441 native rate |
| `RECORD_DEVICE` | `"mic_mono"` | ALSA alias for left-channel mic |
| `PLAYBACK_DEVICE` | `"default"` | Routes through softvol → dmixer → amp |
| `VAD_THRESHOLD` | `0.5` | Silero speech probability; raise if servo noise triggers false starts |
| `VAD_SILENCE_MS` | `300` | Silence after speech ends recording |
| `VAD_MAX_RECORD_S` | `15` | Hard ceiling per utterance |
| `STT_MODEL` | `"openai/whisper-tiny.en"` | Swap for `whisper-base.en` for better accuracy |
| `TTS_VOICE` | `"af_heart"` | Kokoro voice |
| `TTS_LANG_CODE` | `"b"` | British English; must match voice |
| `TTS_SPEED` | `1.0` | Speech rate |
| `GAIT_MAX_S` | `10` | Any gait stops after this; `0` = never |
| `ROBOT_BAUD` | `115200` | BiBoard baud rate |

---

## Running

**On the Pi (systemd):**
```bash
sudo cp systemd/tyapa@.service systemd/tyapa.target /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now tyapa.target
just status    # or: just logs brain
```
The units assume the repo is at `/home/pi/robot-tyapa` and user `pi`; edit them otherwise.

**In the foreground (stop the systemd unit first):** `just run hearing`, `just run brain`, etc.

**Laptop testing without hardware:** `BODY_DRY_RUN=1 just run body`, `just run brain`, `just cli fake-voice` (type instead of talk).

Models take ~30 seconds to load. Once the brain logs `Tyapa online. Listening...`, speak to the dog. `just cli ping` shows which services are up.

---

## Development

```bash
just sync     # create/refresh all venvs
just lint     # ruff check
just format   # ruff format
just test     # pytest in every project
just ci       # full lint + test
```
