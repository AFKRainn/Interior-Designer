"""
Design Consultant Agent — Pre-Council Chat Layer

A lightweight conversational agent that checks whether the user's input is
clear enough for the council to begin work.  It does NOT rewrite or improve
the user's description — the council receives the raw conversation verbatim.

Flow:
  1. User provides initial input (text + optional images)
  2. Consultant assesses completeness
  3. If clear  → tells the user they are ready; user can add more or proceed
  4. If unclear → asks 1-2 focused questions; repeats until clear
  5. When the user proceeds, the raw conversation is forwarded to the council
"""
import json
import logging

from app.prompts.consultant_prompts import (
    CONSULTANT_SYSTEM_PROMPT,
    CONSULTANT_ASSESS_PROMPT,
    CONSULTANT_FOLLOWUP_PROMPT,
)
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class Consultant:
    """
    Pre-council design consultant that checks input completeness.

    Maintains a conversation history.  Once enough information is present,
    it signals done=True so the UI can offer the "Send to Council" action.
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import COUNCIL_MODELS
        self.client = client or OpenRouterClient()
        self.model = COUNCIL_MODELS["claude"]["id"]
        self.reasoning_effort = COUNCIL_MODELS["claude"].get(
            "reasoning_effort", "none")

    async def assess_input(
        self,
        user_text: str | None,
        image_count: int = 0,
        element_selections: str = "None",
    ) -> dict:
        """
        Assess the completeness of the user's initial input.

        Returns a dict with:
          - has_enough: bool
          - clarifying_questions: list[str]
          - ready_message: str
        """
        image_note = (
            f"The user uploaded {image_count} reference image(s). "
            "The council will analyze them directly."
            if image_count > 0
            else "No images provided."
        )

        prompt = CONSULTANT_ASSESS_PROMPT.format(
            user_text=user_text or "(No text provided)",
            image_count=image_count,
            image_note=image_note,
            element_selections=element_selections or "None",
        )

        messages = [
            {"role": "system", "content": CONSULTANT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        response = await self.client.chat_completion(
            model=self.model,
            messages=messages,
            temperature=0.4,
            reasoning_effort=self.reasoning_effort,
        )

        parsed = self.client.extract_json(response)
        if parsed and isinstance(parsed, dict):
            return parsed

        # Fallback — couldn't parse, assume enough info to proceed
        raw_text = self.client.extract_text(response) or ""
        logger.warning(
            f"Consultant assessment failed to parse JSON. Raw: {raw_text[:300]}"
        )
        return {
            "has_enough": True,
            "clarifying_questions": [],
            "ready_message": (
                "Your request looks good! Add any extra details below, "
                "or send it straight to the council."
            ),
        }

    async def continue_conversation(
        self,
        conversation_history: list[dict],
        user_message: str,
    ) -> dict:
        """
        Continue the consultation conversation.

        Returns:
          - response_text: The consultant's reply to show the user
          - done: Whether the consultation is complete (enough info gathered)
        """
        history_text = ""
        for msg in conversation_history:
            role = "Consultant" if msg["role"] == "assistant" else "Client"
            history_text += f"{role}: {msg['content']}\n\n"

        prompt = CONSULTANT_FOLLOWUP_PROMPT.format(
            conversation_history=history_text,
            user_message=user_message,
        )

        messages = [
            {"role": "system", "content": CONSULTANT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        response = await self.client.chat_completion(
            model=self.model,
            messages=messages,
            temperature=0.4,
            reasoning_effort=self.reasoning_effort,
        )

        parsed = self.client.extract_json(response)
        if parsed and isinstance(parsed, dict):
            return {
                "response_text": parsed.get("response_text", ""),
                "done": bool(parsed.get("done", False)),
            }

        # Fallback — couldn't parse, treat as done
        raw_text = self.client.extract_text(response) or ""
        logger.warning(
            f"Consultant follow-up failed to parse JSON. Raw: {raw_text[:300]}"
        )
        return {
            "response_text": raw_text or "Looks good — you can send this to the council.",
            "done": True,
        }
