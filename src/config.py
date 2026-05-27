from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = DATA_DIR / "logs"
WEB_DIR = PROJECT_ROOT / "docs"


def load_config() -> dict:
    with open(PROJECT_ROOT / "config.json") as f:
        return json.load(f)
