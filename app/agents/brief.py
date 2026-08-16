"""
Brief agent — exhaustive intake chat.

Output is facts (a locked brief), not an image prompt and not a Furniture Spec.
When status is confirmed, SpecAuthor.from_brief writes the spec.
"""
from __future__ import annotations

import json
import re

from app.agents.llm_json import complete_json, user_content_with_images
from app.prompts.brief_prompts import BRIEF_SYNTHESIS_PROMPT, BRIEF_SYSTEM_PROMPT
from app.services.openrouter import OpenRouterClient

_USER_DEMANDS_FINALIZE = re.compile(
    r"(?i)(\bmove on\b|\bstop asking\b|\bno more questions\b|"
    r"\bthat'?s enough\b|\benough already\b|\bjust proceed\b|"
    r"\bskip (the )?questions\b|\bi'?m done\b|\bdone answering\b)"
)


class Brief:
    def __init__(self, client: OpenRouterClient | None = None):
        from config import BRIEF_MODEL

        self.client = client or OpenRouterClient()
        self.model = BRIEF_MODEL["id"]
        self.reasoning_effort = BRIEF_MODEL.get("reasoning_effort", "high")

    async def start(
        self,
        user_text: str | None,
        images: list[dict] | None = None,
    ) -> dict:
        messages = [{"role": "system", "content": BRIEF_SYSTEM_PROMPT}]
        messages.append({
            "role": "user",
            "content": user_content_with_images(user_text, images),
        })
        return await self._turn(messages)

    async def reply(
        self,
        messages: list[dict],
        user_text: str,
        images: list[dict] | None = None,
    ) -> dict:
        messages = messages + [{
            "role": "user",
            "content": user_content_with_images(user_text, images),
        }]
        result = await self._turn(messages)
        if result["status"] != "confirmed" and _USER_DEMANDS_FINALIZE.search(
            user_text
        ):
            synth = await self._synthesize(result["messages"])
            if synth is not None:
                return synth
        return result

    async def _synthesize(self, full_messages: list[dict]) -> dict | None:
        synth = [{"role": "system", "content": BRIEF_SYNTHESIS_PROMPT}]
        if full_messages and full_messages[0].get("role") == "system":
            synth.extend(full_messages[1:])
        else:
            synth.extend(full_messages)
        synth.append({
            "role": "user",
            "content": "End Q&A. Output confirmed JSON with the full brief now.",
        })
        out = await self._turn(synth, record_on=full_messages)
        if out["status"] != "confirmed" or not out.get("brief"):
            return None
        return out

    async def _turn(
        self,
        messages: list[dict],
        record_on: list[dict] | None = None,
    ) -> dict:
        result = await complete_json(
            self.client, self.model, messages, self.reasoning_effort
        )
        parsed = result["parsed"]
        response = parsed.get("response") or result["text"]
        status = parsed.get("status", "chat")
        if status not in ("chat", "confirmed"):
            status = "chat"
        brief = parsed.get("brief") if status == "confirmed" else None
        if isinstance(brief, str):
            brief = brief.strip() or None
        else:
            brief = None
        if status == "confirmed" and not brief:
            status = "chat"

        notice = parsed.get("notice")
        if not isinstance(notice, list):
            notice = None

        canonical = {"response": response, "status": status}
        if notice:
            canonical["notice"] = notice
        if brief:
            canonical["brief"] = brief
        history = record_on if record_on is not None else messages
        updated = history + [
            {"role": "assistant", "content": json.dumps(canonical, ensure_ascii=False)}
        ]
        return {
            "response": response,
            "status": status,
            "brief": brief,
            "messages": updated,
        }
