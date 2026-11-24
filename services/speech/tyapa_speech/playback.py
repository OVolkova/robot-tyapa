import io
import logging
import subprocess
import wave

from tyapa_protocol import suppress_stderr

logger = logging.getLogger(__name__)

_CHUNK_FRAMES = 1024


def play_wav_bytes(wav_bytes: bytes) -> None:
    """Play on the ALSA default device (see /etc/asound.conf: softvol -> dmixer -> amp)."""
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

        with suppress_stderr():
            pa = pyaudio.PyAudio()
        fmt = pa.get_format_from_width(sampwidth)

        # output_device_index=None -> system default -> respects /etc/asound.conf pcm.!default
        stream = pa.open(
            format=fmt,
            channels=nchannels,
            rate=framerate,
            output=True,
            output_device_index=None,
            frames_per_buffer=_CHUNK_FRAMES,
        )
        try:
            logger.debug(
                "Playback: %d ch, %d Hz, %d-bit, %d frames",
                nchannels,
                framerate,
                sampwidth * 8,
                nframes,
            )
            data = wf.readframes(_CHUNK_FRAMES)
            while data:
                stream.write(data)
                data = wf.readframes(_CHUNK_FRAMES)
        finally:
            stream.stop_stream()
            stream.close()
            pa.terminate()


def _play_via_aplay(wav_bytes: bytes) -> None:
    # aplay reads WAV header from stdin when given '-'
    subprocess.run(["aplay", "-"], input=wav_bytes, check=False)
