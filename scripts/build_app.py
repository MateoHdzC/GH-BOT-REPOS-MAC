"""Build script generating a native macOS application bundle: GH-BOT-REPOS-MAC.app."""

import os
import plistlib
import shutil
import stat
import sys
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = WORKSPACE_ROOT / "dist"
APP_BUNDLE_NAME = "GH-BOT-REPOS-MAC.app"
APP_DIR = DIST_DIR / APP_BUNDLE_NAME


def build_app() -> bool:
    """Constructs the macOS .app directory structure and executable launcher."""
    print(f"==> Building {APP_BUNDLE_NAME} in {DIST_DIR}...")

    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)

    contents_dir = APP_DIR / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    info_plist_data = {
        "CFBundleName": "GH-BOT-REPOS-MAC",
        "CFBundleDisplayName": "GH-BOT-REPOS-MAC",
        "CFBundleIdentifier": "com.mateohdz.ghbotmac",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundlePackageType": "APPL",
        "CFBundleSignature": "????",
        "CFBundleExecutable": "GH-BOT-REPOS-MAC",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        "LSUIElement": False,
    }

    with open(contents_dir / "Info.plist", "wb") as f:
        plistlib.dump(info_plist_data, f)

    with open(contents_dir / "PkgInfo", "w", encoding="utf-8") as f:
        f.write("APPL????")

    launcher_path = macos_dir / "GH-BOT-REPOS-MAC"
    python_binary = sys.executable

    launcher_content = f"""#!/bin/bash
APP_ROOT="{WORKSPACE_ROOT}"
PYTHON_BIN="{python_binary}"

export PYTHONPATH="$APP_ROOT:$PYTHONPATH"
cd "$APP_ROOT" || exit 1

exec "$PYTHON_BIN" -m src.ui.app "$@"
"""

    launcher_path.write_text(launcher_content, encoding="utf-8")

    current_stat = os.stat(launcher_path)
    os.chmod(launcher_path, current_stat.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"==> Successfully built {APP_DIR}")
    print(f"==> You can now run the app by opening {APP_DIR} or typing 'open {APP_DIR}'")
    return True


if __name__ == "__main__":
    success = build_app()
    sys.exit(0 if success else 1)
