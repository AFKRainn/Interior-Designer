"""
Configuration for the Interior Designer.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
OUTPUTS_DIR = BASE_DIR / "outputs"

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL}/chat/completions"

REQUEST_TIMEOUT = 180
MAX_RETRIES = 3
RETRY_DELAY = 2

BRIEF_MODEL = {
    "id": "google/gemini-3.7-flash",
    "name": "Gemini 3.7 Flash",
    "supports_vision": True,
    "reasoning_effort": "high",
}

# Spec JSON is transcription, not intake. Gemini 3 maps effort to thinkingLevel
# (minimal/low/medium/high) — "none" is not a Gemini 3 level. OpenRouter "high"
# takes ~80% of max_tokens for thinking, so 8192 left ~1.6k for the spec and
# the model returned no JSON object.
SPEC_AUTHOR = {
    "reasoning_effort": "low",
    "max_tokens": 16384,
}

IMAGE_GEN_MODEL = {
    "id": "google/gemini-3.1-flash-image-preview",
    "name": "Gemini 3.1 Flash Image Preview (Google)",
    "max_resolution": "2048x2048",
}
