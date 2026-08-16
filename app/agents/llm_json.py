"""Shared OpenRouter JSON completion for the new pipeline agents."""
from __future__ import annotations

from app.json_parse import parse_json_from_text
from app.services.openrouter import OpenRouterClient


async def complete_json(
    client: OpenRouterClient,
    model: str,
    messages: list[dict],
    reasoning_effort: str = "high",
) -> dict:
    """
    One chat completion. Returns {parsed: dict, text: str}.
    parsed is {} if the model did not return JSON.
    """
    response = await client.chat_completion(
        model=model,
        messages=messages,
        temperature=1.0,
        reasoning_effort=reasoning_effort,
    )
    text = client.extract_text(response) or ""
    parsed = client.extract_json(response)
    if not isinstance(parsed, dict):
        fallback = parse_json_from_text(text)
        parsed = fallback if isinstance(fallback, dict) else {}
    return {"parsed": parsed, "text": text}


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
