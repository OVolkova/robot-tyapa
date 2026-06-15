import io
import logging
import subprocess
import wave

from robot_tyapa.config import PLAYBACK_DEVICE

logger = logging.getLogger(__name__)


def play_wav_bytes(wav_bytes: bytes, device_name: str = PLAYBACK_DEVICE) -> None:
    """Play WAV bytes through the ALSA default device (MAX98357A amp)."""
    try:
        _play_via_pyaudio(wav_bytes)
    except Exception as e:
        logger.warning("PyAudio playback failed (%s); falling back to aplay", e)
        _play_via_aplay(wav_bytes)


def _play_via_pyaudio(wav_bytes: bytes) -> None:
    import pyaudio

    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, "rb") as wf:
        nchannels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        nframes = wf.getnframes()

        pa = pyaudio.PyAudio()
        fmt = pa.get_format_from_width(sampwidth)

        # output_device_index=None -> system default -> respects /etc/asound.conf pcm.!default
        stream = pa.open(
            format=fmt,
            channels=nchannels,
            rate=framerate,
            output=True,
            output_device_index=None,
            frames_per_buffer=1024,
        )
        try:
            logger.debug(
                "Playback: %d ch, %d Hz, %d-bit, %d frames",
                nchannels,
                framerate,
                sampwidth * 8,
                nframes,
            )
            chunk_frames = 1024
            data = wf.readframes(chunk_frames)
            while data:
                stream.write(data)
                data = wf.readframes(chunk_frames)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()


def _play_via_aplay(wav_bytes: bytes) -> None:
    # aplay reads WAV header from stdin when given '-'
    subprocess.run(["aplay", "-"], input=wav_bytes, check=False)
