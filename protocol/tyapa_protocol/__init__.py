import contextlib
import logging
import os
import threading


def setup_logging() -> None:
    """Same log format in every service (journald adds the timestamp)."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(name)s: %(message)s",
    )


# fd 2 is process-wide: two overlapping redirects would make the second one "restore" /dev/null
# and leave stderr silenced for good, so redirects are serialised.
_stderr_lock = threading.Lock()


@contextlib.contextmanager
def suppress_stderr():
    """Redirect fd 2 to /dev/null to silence ALSA/JACK probe spam on ARM64.

    Keep the block short (device probing only): everything written to fd 2 by any thread while
    it is open, including log lines, is discarded.
    """
    with _stderr_lock:
        devnull = os.open(os.devnull, os.O_WRONLY)
        try:
            old = os.dup(2)
        except OSError:
            os.close(devnull)
            raise
        os.dup2(devnull, 2)
        try:
            yield
        finally:
            os.dup2(old, 2)
            os.close(old)
            os.close(devnull)
