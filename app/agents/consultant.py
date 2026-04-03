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

from app.prompts.consultant_prompts import (
    CONSULTANT_SYSTEM_PROMPT,
    CONSULTANT_COUNCIL_FEEDBACK_PROMPT,
)
from app.json_parse import parse_json_from_text
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


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
        return await self._call(messages)

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _call(self, messages: list[dict]) -> dict:
        """Send messages to the model and parse the response."""
        has_images = any(
            isinstance(m.get("content"), list)
            for m in messages
            if m.get("role") == "user"
        )

        if has_images:
            # Build vision call from the message list manually
            # (openrouter client vision methods are single-turn; for multi-turn
            #  with vision we use chat_completion with inline image content parts)
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

        reply_text = parsed.get("response") or raw_text
        status = parsed.get("status", "chat")
        if status not in ("chat", "confirmed"):
            status = "chat"
        final_summary = parsed.get("final_summary") if status == "confirmed" else None

        # Store clean JSON only (no markdown fences) so UI and downstream agents read reliably
        canonical: dict = {"response": reply_text, "status": status}
        if final_summary:
            canonical["final_summary"] = final_summary
        assistant_content = json.dumps(canonical, ensure_ascii=False)

        updated_messages = messages + [
            {"role": "assistant", "content": assistant_content}
        ]

        return {
            "response": reply_text,
            "status": status,
            "final_summary": final_summary,
            "messages": updated_messages,
        }

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
