"""
Council Reviewer Agent

A single expert model (GPT) that reviews the consultant's Final Design
Summary against the original image(s). It either approves the summary or
returns a list of specific issues for the consultant to resolve with the client.
"""
import logging

from app.prompts.council_prompts import (
    COUNCIL_REVIEWER_SYSTEM_PROMPT,
    COUNCIL_REVIEWER_PROMPT,
)
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class CouncilReviewer:
    """
    Checks the consultant's Final Design Summary for completeness and accuracy.

    Returns:
      {"approved": True}
      {"approved": False, "issues": ["issue 1", "issue 2", ...]}
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import COUNCIL_REVIEWER_MODEL
        self.client = client or OpenRouterClient()
        self.model = COUNCIL_REVIEWER_MODEL["id"]
        self.reasoning_effort = COUNCIL_REVIEWER_MODEL.get("reasoning_effort", "none")

    async def review(
        self,
        messages: list[dict],
        final_summary: str,
        images: list[dict] | None = None,
    ) -> dict:
        """
        Review the design summary.

        Args:
            messages:      Full consultant–client conversation history.
            final_summary: The consultant's Final Design Summary text.
            images:        List of {"data": base64_str, "mime_type": str}.

        Returns:
            {"approved": bool, "issues": list[str]}
        """
        conversation_text = self._format_conversation(messages)

        prompt = COUNCIL_REVIEWER_PROMPT.format(
            conversation=conversation_text,
            final_summary=final_summary,
        )

        if images:
            content_parts: list[dict] = [{"type": "text", "text": prompt}]
            for img in images:
                data = img.get("data", "")
                mime = img.get("mime_type", "image/png")
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}"},
                })

            api_messages = [
                {"role": "system", "content": COUNCIL_REVIEWER_SYSTEM_PROMPT},
                {"role": "user", "content": content_parts},
            ]
        else:
            api_messages = [
                {"role": "system", "content": COUNCIL_REVIEWER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

        response = await self.client.chat_completion(
            model=self.model,
            messages=api_messages,
            temperature=1.0,
            reasoning_effort=self.reasoning_effort,
        )

        parsed = self.client.extract_json(response) or {}
        if not isinstance(parsed, dict):
            parsed = {}

        approved = bool(parsed.get("approved", False))
        issues = parsed.get("issues", [])
        if not isinstance(issues, list):
            issues = [str(issues)]

        logger.info(
            f"Council review: approved={approved}, "
            f"issues={len(issues)}: {issues[:2]}"
        )

        return {"approved": approved, "issues": issues}

    @staticmethod
    def _format_conversation(messages: list[dict]) -> str:
        """Format the conversation history as readable text for the reviewer."""
        lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")

            if role == "system":
                continue

            if isinstance(content, list):
                # Extract text parts only (images are sent separately)
                text_parts = [
                    p.get("text", "") for p in content
                    if isinstance(p, dict) and p.get("type") == "text"
                ]
                content = " ".join(text_parts)

            label = "Client" if role == "user" else "Consultant"
            lines.append(f"{label}: {content}")

        return "\n\n".join(lines)
