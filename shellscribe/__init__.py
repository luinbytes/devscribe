"""ShellScribe - AI-powered terminal session logger."""

__version__ = "0.1.0"
__author__ = "ShellScribe"

import os
from pathlib import Path

# Default paths
SHELLSCRIBE_DIR = Path.home() / ".shellscribe"
DB_PATH = SHELLSCRIBE_DIR / "shellscribe.db"
CONFIG_PATH = SHELLSCRIBE_DIR / "config.json"

# Ensure directory exists
SHELLSCRIBE_DIR.mkdir(parents=True, exist_ok=True)
