"""Desktop application launcher managing BotEngine background lifecycle and GUI."""

import argparse
import logging
import signal
import sys
import threading
from pathlib import Path
from typing import Optional

from src.core.engine import BotEngine
from src.ui.main_window import MainWindow
from src.utils.constants import DEFAULT_CONFIG_PATH
from src.utils.logger import get_logger, setup_logger

logger = get_logger("app")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GH-BOT-REPOS-MAC Desktop Application")
    parser.add_argument(
        "--background",
        "-b",
        action="store_true",
        help="Start the application minimized in background (used for login auto-start)",
    )
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to JSON configuration file",
    )
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def run_app(background: bool = False, config_path: Optional[Path] = None, debug: bool = False) -> int:
    """Initializes the BotEngine backend and runs the macOS graphical interface."""
    log_level = logging.DEBUG if debug else logging.INFO
    setup_logger(level=log_level)

    logger.info("[SYSTEM] Starting GH-BOT-REPOS-MAC Application...")

    engine = BotEngine(config_path=config_path)
    engine.start()

    window: Optional[MainWindow] = None

    def quit_application() -> None:
        logger.info("[SYSTEM] Quitting application cleanly...")
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass
        engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, lambda s, f: quit_application())
    signal.signal(signal.SIGTERM, lambda s, f: quit_application())

    try:
        window = MainWindow(engine=engine, on_quit_app=quit_application)

        if background:
            window.hide_to_background()
            logger.info("[SYSTEM] Application started in background mode.")
        else:
            window.show_window()

        window.mainloop()
    except Exception as err:
        logger.error(f"[SYSTEM] [ERROR] GUI encountered an error: {err}", exc_info=True)
    finally:
        engine.stop()

    return 0


def main() -> int:
    args = parse_arguments()
    return run_app(
        background=args.background,
        config_path=args.config,
        debug=args.debug,
    )


if __name__ == "__main__":
    sys.exit(main())
