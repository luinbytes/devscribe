"""DevScribe - AI-powered terminal session logger."""

__version__ = "0.1.0"
__author__="***"

import os
import sys
from pathlib import Path

# Default paths — use APPDATA on Windows, ~/.devscribe on Unix
if sys.platform == "win32":
    _appdata = os.environ.get("APPDATA", None)
    if _appdata:
        DEVSCRIBE_DIR = Path(_appdata) / "devscribe"
    else:
        DEVSCRIBE_DIR = Path.home() / ".devscribe"
else:
    DEVSCRIBE_DIR = Path.home() / ".devscribe"

DB_PATH = DEVSCRIBE_DIR / "devscribe.db"
CONFIG_PATH = DEVSCRIBE_DIR / "config.json"

# Ensure directory exists
DEVSCRIBE_DIR.mkdir(parents=True, exist_ok=True)
