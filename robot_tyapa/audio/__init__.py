import contextlib
import os


@contextlib.contextmanager
def _suppress_stderr():
    """Redirect fd 2 to /dev/null to silence ALSA/JACK probe spam on ARM64."""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old = os.dup(2)
    os.dup2(devnull, 2)
    try:
        yield
    finally:
        os.dup2(old, 2)
        os.close(old)
        os.close(devnull)
