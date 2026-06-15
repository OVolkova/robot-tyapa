import io
import logging

import scipy.signal
import soundfile as sf
import torch
import torchaudio
from kokoro import KPipeline
from transformers import WhisperForConditionalGeneration, WhisperProcessor

from robot_tyapa.brain.llm_client import PERFORM_ACTION_TOOL, SYSTEM_PROMPT, create_llm_client

logger = logging.getLogger(__name__)

WHISPER_FREQUENCY = 16000
KOKORO_VOICE_FREQ = 24000  # Kokoro's TTS model runs at 24kHz
PLAYBACK_FREQUENCY = 16000  # Keep at 16kHz

_MAX_HISTORY = 10
_KEEP_RECENT = 4


def get_device() -> str:
    device = "cpu"
    if torch.cuda.is_available():
        device = "cuda"
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        device = "mps"
    logger.info("device is %s", device)
    return device


def resample(waveform, target_freq: int, original_freq: int):
    if target_freq == original_freq:
        return waveform
    return scipy.signal.resample(waveform, int(waveform.shape[0] * target_freq / original_freq))


class TextToText:
    def __init__(self, provider: str | None = None, model: str | None = None):
        self.llm = create_llm_client(provider=provider, model=model)
        self.history: list[dict] = []

    def _maybe_summarize(self) -> None:
        if len(self.history) < _MAX_HISTORY:
            return
        to_summarize = self.history[:-_KEEP_RECENT]
        recent = self.history[-_KEEP_RECENT:]
        summary_text, _ = self.llm.complete(
            [
                {
                    "role": "system",
                    "content": (
                        "Summarise the following robot-dog conversation in 2-3 sentences. "
                        "Note topics discussed and any physical actions the robot performed."
                    ),
                },
                *to_summarize,
                {"role": "user", "content": "Summarise the conversation above briefly."},
            ]
        )
        self.history = [
            {
                "role": "system",
                "content": f"Summary of earlier conversation: {summary_text or 'Previous exchanges occurred.'}",
            },
            *recent,
        ]
        logger.info("[TextToText] History summarised → %d messages kept", len(self.history))

    def generate(self, user_text: str, current_action: str = "balance") -> tuple[str, str | None]:
        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.history)
        messages.append(
            {"role": "user", "content": f"[Current robot action: {current_action}]\n{user_text}"}
        )
        logger.info(
            "[TextToText] Sending to LLM: %d messages, user_text=%r", len(messages), user_text
        )
        response_text, action_key = self.llm.complete(messages, tools=[PERFORM_ACTION_TOOL])
        logger.info("[TextToText] LLM: text=%r, action=%r", response_text, action_key)
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": response_text or ""})
        self._maybe_summarize()
        return response_text, action_key


class TextToSpeech:
    def __init__(
        self,
        voice: str = "af_heart",
        lang_code: str = "b",
        speed: float = 1.0,
        model_freq: int = KOKORO_VOICE_FREQ,
    ):
        self.voice = voice
        self.speed = speed
        self.model_freq = model_freq
        self.pipeline = KPipeline(lang_code=lang_code)

    def generate(self, text):
        logger.info("Generating speech for text: %s", text)
        generator = self.pipeline(
            text,
            voice=self.voice,
            speed=self.speed,
            split_pattern=r"\n+",
        )

        original_waveform = [a for _, _, a in generator][0]
        logger.info(
            "Original waveform shape: %s, freq: %d", original_waveform.shape, self.model_freq
        )
        waveform = resample(
            original_waveform,
            original_freq=self.model_freq,
            target_freq=PLAYBACK_FREQUENCY,
        )
        logger.info("Resampled waveform shape: %s, freq: %d", waveform.shape, PLAYBACK_FREQUENCY)
        return waveform, PLAYBACK_FREQUENCY


class SpeechToText:
    def __init__(
        self,
        model_name: str = "openai/whisper-tiny.en",
        model_freq: int = WHISPER_FREQUENCY,
        device: str | None = None,
    ):
        self.device = device or get_device()
        self.processor = WhisperProcessor.from_pretrained(model_name)
        self.model = WhisperForConditionalGeneration.from_pretrained(model_name)
        self.model.to(self.device)
        self.model.config.forced_decoder_ids = None
        self.model.generation_config.forced_decoder_ids = None
        self.model_freq = model_freq

    def __call__(self, waveform, freq):
        logger.info(
            "STT input: shape=%s freq=%d model_freq=%d", waveform.shape, freq, self.model_freq
        )
        waveform = resample(waveform, self.model_freq, freq)
        logger.info("STT resampled: shape=%s", waveform.shape)
        processed = self.processor(
            waveform, sampling_rate=self.model_freq, return_tensors="pt", return_attention_mask=True
        )
        input_features = processed.input_features.to(self.device)
        attention_mask = processed.attention_mask.to(self.device)

        predicted_ids = self.model.generate(input_features, attention_mask=attention_mask)
        transcription = self.processor.batch_decode(predicted_ids, skip_special_tokens=True)
        return transcription[0]


class SpeechToSpeechActionProcessor:
    def __init__(
        self,
        # LLM
        provider: str,
        model: str,
        # STT
        stt_model: str,
        # TTS
        tts_voice: str,
        tts_lang_code: str,
        tts_speed: float,
    ):
        logger.info("Loading models...")
        self.speech_to_text = SpeechToText(model_name=stt_model)
        logger.info("  Loaded SpeechToText (Whisper %s)", stt_model)
        self.text_to_speech = TextToSpeech(
            voice=tts_voice, lang_code=tts_lang_code, speed=tts_speed
        )
        logger.info("  Loaded TextToSpeech (Kokoro voice=%s)", tts_voice)
        self.text_to_text = TextToText(provider=provider, model=model)
        logger.info("  Loaded TextToText (LLM)")

    def process(
        self, audio_bytes: bytes, current_action: str = "balance"
    ) -> tuple[io.BytesIO, str, str | None]:
        signal, frequency = torchaudio.load(io.BytesIO(audio_bytes))
        waveform = signal.numpy()[0]
        user_text = self.speech_to_text(waveform, frequency)
        logger.info("STT: %r", user_text)

        response_text, action_key = self.text_to_text.generate(user_text, current_action)

        spoken_text = response_text.strip()
        if spoken_text:
            out_waveform, out_freq = self.text_to_speech.generate(spoken_text)
            buf = io.BytesIO()
            sf.write(buf, out_waveform, out_freq, format="wav", subtype="PCM_16")
            buf.seek(0)
        else:
            buf = io.BytesIO()

        serial_action = f"k{action_key}" if action_key else None
        return buf, response_text or "", serial_action
