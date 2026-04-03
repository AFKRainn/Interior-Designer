"""
Shared JSON parsing helpers (no dependency on OpenRouter client).
"""
import json
import re


def parse_json_from_text(text: str) -> dict | list | None:
    """
    Parse JSON from model output that may include markdown fences or extra prose.

    Handles: bare JSON, ```json ... ``` (with or without newline after the tag),
    and ``` ... ```. Falls back to first balanced { } / [ ] slice.
    """
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    if text.startswith("```"):
        inner = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        inner = re.sub(r"\s*```\s*$", "", inner).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    json_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        depth = 0
        for i in range(start_idx, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start_idx : i + 1])
                    except json.JSONDecodeError:
                        break

    return None
