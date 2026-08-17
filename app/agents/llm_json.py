"""Shared OpenRouter JSON completion for the new pipeline agents."""
from __future__ import annotations

import logging

from app.json_parse import parse_json_from_text
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


async def complete_json(
    client: OpenRouterClient,
    model: str,
    messages: list[dict],
    reasoning_effort: str = "high",
    response_format: dict | None = None,
) -> dict:
    """
    One chat completion. Returns {parsed: dict, text: str, finish_reason}.
    parsed is {} if the model did not return JSON.
    """
    response = await client.chat_completion(
        model=model,
        messages=messages,
        temperature=1.0,
        reasoning_effort=reasoning_effort,
        response_format=response_format,
    )
    text = client.extract_text(response) or ""
    parsed = client.extract_json(response)
    if not isinstance(parsed, dict):
        fallback = parse_json_from_text(text)
        parsed = fallback if isinstance(fallback, dict) else {}
    finish_reason = None
    usage = None
    try:
        finish_reason = response["choices"][0].get("finish_reason")
        usage = response.get("usage")
    except (KeyError, IndexError, TypeError, AttributeError):
        pass
    if not parsed:
        logger.warning(
            "complete_json empty JSON model=%s finish=%s text_len=%d usage=%s preview=%r",
            model,
            finish_reason,
            len(text),
            usage,
            text[:300],
        )
    return {
        "parsed": parsed,
        "text": text,
        "finish_reason": finish_reason,
    }


def user_content_with_images(
    user_text: str | None,
    images: list[dict] | None,
) -> list[dict] | str:
    if not images:
        return user_text or ""
    parts: list[dict] = []
    text = (user_text or "").strip()
    if text:
        parts.append({"type": "text", "text": text})
    else:
        parts.append({"type": "text", "text": "(image attached)"})
    for img in images:
        data = img.get("data", "")
        mime = img.get("mime_type", "image/png")
        parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{data}"},
        })
    return parts
