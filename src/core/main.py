"""Main entrypoint for running the GH-BOT-REPOS-MAC daemon engine."""

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from src.core.engine import BotEngine
from src.utils.constants import DEFAULT_CONFIG_PATH
from src.utils.logger import get_logger, setup_logger


def parse_args() -> argparse.Namespace:
    """Parses command line arguments."""
    parser = argparse.ArgumentParser(
        description="GH-BOT-REPOS-MAC: Automated Git Watcher and Synchronizer for macOS."
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to JSON configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug-level logging output",
    )
    return parser.parse_args()


def main() -> int:
    """Launches the bot engine and maintains execution loop until signal interruption."""
    args = parse_args()
    log_level = logging.DEBUG if args.debug else logging.INFO
    setup_logger(level=log_level)
    logger = get_logger("main")

    logger.info("=== GH-BOT-REPOS-MAC Daemon Engine Starting ===")

    engine = BotEngine(config_path=args.config)

    def handle_shutdown_signal(sig: int, frame: object) -> None:
        signame = signal.Signals(sig).name
        logger.info(f"Received shutdown signal {signame}. Terminating gracefully...")
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown_signal)
    signal.signal(signal.SIGTERM, handle_shutdown_signal)

    if not engine.start():
        logger.error("Failed to initialize engine. Exiting.")
        return 1

    try:
        while engine.is_running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received.")
    finally:
        engine.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
