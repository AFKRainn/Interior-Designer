"""A scripted stand-in for OpenRouterClient.

Queue the JSON you want the model to "return" and assert on what it was
asked. No network, no key, no cost.
"""
from __future__ import annotations

import json
from typing import Any


class FakeClient:
    def __init__(self, replies: list[Any] | None = None):
        # each reply is a dict (serialised to JSON) or a raw string
        self.replies: list[Any] = list(replies or [])
        self.calls: list[dict] = []
        self.images: list[dict] = []
        self.image_replies: list[dict] = []

    # -- chat -------------------------------------------------------------

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 1.0,
        reasoning_effort: str | None = None,
        response_format: dict | None = None,
        **kwargs: Any,
    ) -> dict:
        self.calls.append(
            {
                "model": model,
                "messages": [dict(m) for m in messages],
                "reasoning_effort": reasoning_effort,
                "response_format": response_format,
            }
        )
        if not self.replies:
            raise AssertionError(
                f"FakeClient ran out of replies after {len(self.calls)} call(s)"
            )
        reply = self.replies.pop(0)
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return {"choices": [{"message": {"content": text}, "finish_reason": "stop"}]}

    def extract_text(self, response: dict) -> str:
        return response["choices"][0]["message"]["content"]

    def extract_json(self, response: dict) -> Any:
        try:
            return json.loads(self.extract_text(response))
        except (ValueError, TypeError):
            return None

    # -- images -----------------------------------------------------------

    async def generate_image(
        self,
        prompt: str,
        reference_images: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict:
        self.images.append({"prompt": prompt, "references": reference_images or []})
        if self.image_replies:
            return self.image_replies.pop(0)
        return {"images": [{"data": "ZmFrZQ==", "mime_type": "image/png"}]}

    # -- assertions -------------------------------------------------------

    @property
    def last_prompt(self) -> str:
        parts = []
        for message in self.calls[-1]["messages"]:
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                parts.extend(p.get("text", "") for p in content if isinstance(p, dict))
        return "\n".join(parts)
