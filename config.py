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

# --- build 2 ---------------------------------------------------------------
# Two language jobs, two models, no council (plan 10).
#
# INTAKE talks: fast, cheap, multimodal, reads sketches.
# STRUCTURE thinks: brief -> spec, and utterance -> edit ops. This is where
# the reasoning actually matters now the council is gone, so it runs at max
# effort. Verified on OpenRouter: 1.05M context, text+image+file, supports
# reasoning_effort and structured_outputs.
INTAKE_MODEL = {
    "id": "google/gemini-3.7-flash",
    "name": "Gemini 3.7 Flash",
    "supports_vision": True,
    "reasoning_effort": "high",
}

STRUCTURE_MODEL = {
    "id": "openai/gpt-5.6-terra",
    "name": "GPT-5.6 Terra",
    "supports_vision": True,
    "reasoning_effort": "max",
}

# Below the clarify threshold the edit agent must ask instead of act
# (plan 10.3). Structured uncertainty raises coverage while REDUCING the
# number of questions -- see plan.txt section 15.
CLARIFY_THRESHOLD = 0.75

# --- build 1 (deleted at cutover) -------------------------------------------
BRIEF_MODEL = {
    "id": "google/gemini-3.7-flash",
    "name": "Gemini 3.7 Flash",
    "supports_vision": True,
    "reasoning_effort": "high",
}

# Spec JSON is transcription, not intake. Gemini 3 maps effort to thinkingLevel
# (minimal/low/medium/high) — "none" is not a Gemini 3 level.
SPEC_AUTHOR = {
    "reasoning_effort": "low",
}

IMAGE_GEN_MODEL = {
    "id": "google/gemini-3.1-flash-image-preview",
    "name": "Gemini 3.1 Flash Image Preview (Google)",
    "max_resolution": "2048x2048",
}
