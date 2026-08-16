"""Fake OpenRouter client for tests. No network."""
from __future__ import annotations

import json

from app.json_parse import parse_json_from_text

# 1x1 PNG. Tests never call a live image API.
TINY_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


class FakeOpenRouter:
    def __init__(self, payloads: list | None = None, images: list | None = None):
        self.payloads = list(payloads or [])
        self.images = list(images or [])
        self.calls: list[dict] = []
        self.image_calls: list[dict] = []

    async def chat_completion(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        item = self.payloads.pop(0)
        text = item if isinstance(item, str) else json.dumps(item)
        return {"choices": [{"message": {"content": text}}]}

    async def generate_image(self, prompt: str, reference_images=None, **kwargs) -> dict:
        refs = list(reference_images or [])
        record = {"prompt": prompt, "reference_images": refs}
        self.image_calls.append(record)
        self.calls.append({"kind": "image", **record})
        if self.images:
            item = self.images.pop(0)
            if isinstance(item, dict):
                return item
            return {"images": [{"data": item, "mime_type": "image/png"}]}
        return {"images": [{"data": TINY_PNG, "mime_type": "image/png"}]}

    def extract_text(self, response: dict) -> str:
        return response["choices"][0]["message"]["content"]

    def extract_json(self, response: dict):
        return parse_json_from_text(self.extract_text(response))
