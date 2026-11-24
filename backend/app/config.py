from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def database_path() -> Path:
    configured = Path(env("DATABASE_PATH", "./data/appointments.db"))
    if not configured.is_absolute():
        configured = BACKEND_DIR / configured
    configured.parent.mkdir(parents=True, exist_ok=True)
    return configured


GOOGLE_API_KEY = env("GOOGLE_API_KEY")
ELEVENLABS_API_KEY = env("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = env("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-3.5-flash-lite")
API_HOST = env("API_HOST", "0.0.0.0")
API_PORT = int(env("API_PORT", "8000"))
FRONTEND_ORIGIN = env("FRONTEND_ORIGIN", "http://localhost:5173")
