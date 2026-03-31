"""
Configuration for the Architecture Agent system.
Model definitions, API settings, and file paths.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PROJECTS_DIR = DATA_DIR / "projects"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Ensure directories exist
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# OpenRouter API
# ---------------------------------------------------------------------------
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_CHAT_URL = f"{OPENROUTER_BASE_URL}/chat/completions"

# Request settings
REQUEST_TIMEOUT = 180  # seconds (generous for image generation)
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds between retries

# ---------------------------------------------------------------------------
# Council Models (Multimodal — can analyze images + text)
# ---------------------------------------------------------------------------
COUNCIL_MODELS = {
    "claude": {
        "id": "anthropic/claude-sonnet-4.6",
        "name": "Claude 4.6 (Anthropic)",
        "role": "Structured analysis & detail extraction",
        "supports_vision": True,
    },
    "gpt": {
        "id": "openai/gpt-5.4",
        "name": "GPT-5.4 (OpenAI)",
        "role": "Creative interpretation & spatial reasoning",
        "supports_vision": True,
    },
    "gemini": {
        "id": "google/gemini-3.1-pro-preview",
        "name": "Gemini Pro (Google)",
        "role": "Visual understanding & multimodal analysis",
        "supports_vision": True,
    },
}

# ---------------------------------------------------------------------------
# Image Generation Model
# ---------------------------------------------------------------------------
IMAGE_GEN_MODEL = {
    "id": "google/gemini-3.1-flash-image-preview",
    "name": "Gemini 3.1 Flash Image Preview (Google)",
    "max_resolution": "2048x2048",
}

# ---------------------------------------------------------------------------
# Council Settings
# ---------------------------------------------------------------------------
COUNCIL_MAX_ROUNDS = 3
COUNCIL_CONSENSUS_THRESHOLD = 2  # At least 2 out of 3 must agree
CHAIRMAN_MODEL = "claude"  # Default chairman for synthesis

# ---------------------------------------------------------------------------
# Quality Review Settings
# ---------------------------------------------------------------------------
QUALITY_MIN_SCORE = 7  # Out of 10 — images scoring below are regenerated
QUALITY_MAX_RETRIES = 3  # Max regeneration attempts per image

# ---------------------------------------------------------------------------
# Generation Settings — View Types
# ---------------------------------------------------------------------------
VIEWS_CONFIG = {
    "floor_plan": {
        "name": "Floor Plan",
        "description": "Top-down orthographic view showing layout and dimensions",
        "applicable_to": ["furniture", "room", "building"],
    },
    "front_elevation": {
        "name": "Front Elevation",
        "description": "Front face view showing height and width proportions",
        "applicable_to": ["furniture", "room", "building"],
    },
    "side_elevation": {
        "name": "Side Elevation",
        "description": "Side face view showing depth and height proportions",
        "applicable_to": ["furniture", "room", "building"],
    },
    "rear_elevation": {
        "name": "Rear Elevation",
        "description": "Rear face view",
        "applicable_to": ["room", "building"],
    },
    "perspective_3d_front": {
        "name": "3D Perspective (Front)",
        "description": "Realistic 3D render from front-angle viewpoint",
        "applicable_to": ["furniture", "room", "building"],
    },
    "perspective_3d_angle": {
        "name": "3D Perspective (Angle)",
        "description": "Realistic 3D render from 45-degree angle viewpoint",
        "applicable_to": ["furniture", "room", "building"],
    },
    "realistic_render": {
        "name": "Realistic Lifestyle Render",
        "description": "Photorealistic image in a real-world environment with props and context",
        "applicable_to": ["furniture", "room", "building"],
    },
}

# ---------------------------------------------------------------------------
# Streamlit Settings
# ---------------------------------------------------------------------------
APP_TITLE = "Architecture Agent"
APP_ICON = "🏛️"
APP_LAYOUT = "wide"
