"""
Consultant Agent

Expert interior designer / architect that chats with the client to fully
understand a design before handing off to the Council Reviewer.

Two modes (auto-detected from context):
  Mode 1 — Image Analysis: user has a sketch/image to realise.
  Mode 2 — Participant Design: designing from scratch or with suggestions.

The consultant maintains a conversation history (messages list) that is
passed back on every call. The full history is forwarded to the council
and chairman verbatim.
"""
import json
import logging
import re

from app.prompts.consultant_prompts import (
    CONSULTANT_SYSTEM_PROMPT,
    CONSULTANT_COUNCIL_FEEDBACK_PROMPT,
    CONSULTANT_SYNTHESIS_SYSTEM_PROMPT,
)
from app.json_parse import parse_json_from_text
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# Client clearly ended Q&A — if the model still returns chat, we run a synthesis pass.
_USER_DEMANDS_FINALIZE = re.compile(
    r"(?i)(\bmove on\b|\bstop asking\b|\bno more questions\b|won'?t be answering|won'?t answer|"
    r"not answering|\bconfirm for all\b|\bconfirm all\b|\bthat'?s enough\b|\benough already\b|"
    r"\bjust proceed\b|\bget (this |it )?done\b|\bprefer not to answer\b|"
    r"\bskip (the )?questions\b|\bi'?m done\b|\bdone answering\b|\bgave enough\b|\bi gave enough\b|"
    r"without answering|not be answering more)",
)


class Consultant:
    """
    Drives the consultant conversation loop.

    Each public method returns a dict:
      {
        "response":      str  — the message to show the client,
        "status":        str  — "chat" | "confirmed",
        "final_summary": str | None  — populated when status == "confirmed",
        "messages":      list — updated conversation history,
      }
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import CONSULTANT_MODEL
        self.client = client or OpenRouterClient()
        self.model = CONSULTANT_MODEL["id"]
        self.reasoning_effort = CONSULTANT_MODEL.get("reasoning_effort", "none")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(
        self,
        user_text: str | None,
        images: list[dict] | None = None,
    ) -> dict:
        """
        Begin a new consultation.

        Args:
            user_text: The client's initial message.
            images:    List of {"data": base64_str, "mime_type": str}.

        Returns:
            Consultant response dict (see class docstring).
        """
        messages = [{"role": "system", "content": CONSULTANT_SYSTEM_PROMPT}]

        user_content = self._build_user_content(user_text, images)
        messages.append({"role": "user", "content": user_content})

        return await self._call(messages)

    async def continue_chat(
        self,
        messages: list[dict],
        user_text: str,
    ) -> dict:
        """
        Continue the consultation with a new client message.

        Args:
            messages:  Full conversation history so far.
            user_text: The client's latest message.

        Returns:
            Consultant response dict with updated messages.
        """
        messages = messages + [{"role": "user", "content": user_text}]
        result = await self._call(messages)
        if result.get("status") != "confirmed" and _USER_DEMANDS_FINALIZE.search(
            user_text
        ):
            synth = await self._synthesize_confirmed(result["messages"])
            if synth is not None:
                return synth
        return result

    async def handle_council_feedback(
        self,
        messages: list[dict],
        issues: list[str],
    ) -> dict:
        """
        Inject council reviewer feedback into the conversation.

        The consultant reformulates the issues as a natural question to the
        client without revealing that an internal reviewer flagged them.

        Args:
            messages: Full conversation history so far.
            issues:   List of issue strings from the council reviewer.

        Returns:
            Consultant response dict with updated messages.
        """
        issues_text = "\n".join(f"- {issue}" for issue in issues)
        feedback_msg = CONSULTANT_COUNCIL_FEEDBACK_PROMPT.format(
            issues=issues_text
        )
        messages = messages + [{"role": "user", "content": feedback_msg}]
        return await self._call(messages)

    async def force_finalize(self, messages: list[dict]) -> dict:
        """
        Client used explicit UI control to end consultation. Synthesize confirmed
        JSON from the full thread (no new user message).
        """
        synth = await self._synthesize_confirmed(messages)
        if synth is not None:
            return synth
        return {
            "response": "Could not finalize automatically. Try one more short reply or start over.",
            "status": "chat",
            "final_summary": None,
            "messages": messages,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _synthesize_confirmed(
        self, full_messages: list[dict]
    ) -> dict | None:
        """
        Replace trailing assistant behavior: one call with a strict system prompt
        so the thread ends with status=confirmed + final_summary.
        Returns None if synthesis did not produce a valid confirmation.
        """
        if not full_messages:
            return None

        synth_messages: list[dict] = [
            {"role": "system", "content": CONSULTANT_SYNTHESIS_SYSTEM_PROMPT},
        ]
        if full_messages[0].get("role") == "system":
            synth_messages.extend(full_messages[1:])
        else:
            synth_messages.extend(full_messages)

        synth_messages.append({
            "role": "user",
            "content": (
                "The client has ended the Q&A phase. Produce the single JSON object "
                "now (status confirmed, full final_summary, short response). "
                "Synthesize only what is already agreed in the thread."
            ),
        })

        out = await self._call_raw(synth_messages)
        if out.get("status") != "confirmed" or not out.get("final_summary"):
            logger.warning(
                "Synthesis pass did not return confirmed with final_summary; "
                "keeping prior assistant message"
            )
            return None

        base = (
            full_messages[:-1]
            if full_messages[-1].get("role") == "assistant"
            else full_messages
        )
        new_content = out["messages"][-1]["content"]
        fixed_messages = base + [{"role": "assistant", "content": new_content}]
        return {
            "response": out["response"],
            "status": out["status"],
            "final_summary": out["final_summary"],
            "messages": fixed_messages,
        }

    async def _call_raw(self, messages: list[dict]) -> dict:
        """API round-trip + parse + normalize; returns dict with messages including assistant."""
        has_images = any(
            isinstance(m.get("content"), list)
            for m in messages
            if m.get("role") == "user"
        )

        if has_images:
            response = await self.client.chat_completion(
                model=self.model,
                messages=messages,
                temperature=1.0,
                reasoning_effort=self.reasoning_effort,
            )
        else:
            response = await self.client.chat_completion(
                model=self.model,
                messages=messages,
                temperature=1.0,
                reasoning_effort=self.reasoning_effort,
            )

        raw_text = self.client.extract_text(response) or ""
        parsed = self.client.extract_json(response)
        if not isinstance(parsed, dict):
            p2 = parse_json_from_text(raw_text)
            parsed = p2 if isinstance(p2, dict) else {}

        reply_text, status, final_summary = self._normalize_parsed(parsed, raw_text)

        canonical: dict = {"response": reply_text, "status": status}
        if final_summary:
            canonical["final_summary"] = final_summary
        assistant_content = json.dumps(canonical, ensure_ascii=False)

        updated_messages = messages + [
            {"role": "assistant", "content": assistant_content},
        ]

        return {
            "response": reply_text,
            "status": status,
            "final_summary": final_summary,
            "messages": updated_messages,
        }

    @staticmethod
    def _normalize_parsed(parsed: dict, raw_text: str) -> tuple[str, str, str | None]:
        """Fix model mistakes: summary with chat status, or confirmed without summary."""
        reply_text = parsed.get("response") or raw_text
        status = parsed.get("status", "chat")
        if status not in ("chat", "confirmed"):
            status = "chat"

        final_summary = parsed.get("final_summary")
        fs = final_summary if isinstance(final_summary, str) else None

        # Model wrote a full summary but forgot to flip status → unblock pipeline
        if status == "chat" and fs and len(fs.strip()) > 250:
            status = "confirmed"
        elif status == "confirmed" and (not fs or len(fs.strip()) < 80):
            status = "chat"
            fs = None

        if status != "confirmed":
            fs = None

        return reply_text, status, fs

    async def _call(self, messages: list[dict]) -> dict:
        """Send messages to the model and parse the response."""
        return await self._call_raw(messages)

    @staticmethod
    def _build_user_content(
        user_text: str | None,
        images: list[dict] | None,
    ) -> list[dict] | str:
        """
        Build the user message content.
        Returns a list (multimodal) if images are provided, else a plain string.
        """
        if not images:
            return user_text or ""

        parts: list[dict] = []
        if user_text:
            parts.append({"type": "text", "text": user_text})

        for img in images:
            data = img.get("data", "")
            mime = img.get("mime_type", "image/png")
            parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{data}"},
            })

        return parts
