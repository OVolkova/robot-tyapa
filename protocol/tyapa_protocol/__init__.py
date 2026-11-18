import logging
import os


def setup_logging() -> None:
    """Same log format in every service (journald adds the timestamp)."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(levelname)s %(name)s: %(message)s",
    )
