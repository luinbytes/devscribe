"""DevScribe - AI-powered terminal session logger."""

__version__ = "0.1.0"
__author__ = "DevScribe"

import os
from pathlib import Path

# Default paths
DEVSCRIBE_DIR = Path.home() / ".devscribe"
DB_PATH = DEVSCRIBE_DIR / "devscribe.db"
CONFIG_PATH = DEVSCRIBE_DIR / "config.json"

# Ensure directory exists
DEVSCRIBE_DIR.mkdir(parents=True, exist_ok=True)
