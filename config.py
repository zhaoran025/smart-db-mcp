import sys
import os
from pathlib import Path


def _resolve_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _resolve_resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent


BASE_DIR = _resolve_base_dir()
RESOURCE_DIR = _resolve_resource_dir()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SQLITE_DB_PATH = DATA_DIR / "smart_db_mcp.db"
KEY_FILE = DATA_DIR / "key.bin"

SQLITE_URL = f"sqlite:///{SQLITE_DB_PATH}"
