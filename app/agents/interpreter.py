"""
Interpreter Agent — stub for Phase 2

Handles the initial interpretation of user input before
it enters the council. Pre-processes text and images.

This module will be expanded in Phase 2 to handle:
- Input validation and normalization
- Sketch quality assessment
- Text description enrichment
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Interpreter:
    """
    Pre-processes user input before council deliberation.

    Currently a pass-through; will be enhanced in Phase 2
    with input validation, quality checks, and normalization.
    """

    def __init__(self):
        pass

    def prepare_input(
        self,
        text: str | None = None,
        image_data: str | None = None,
        image_mime_type: str = "image/png",
    ) -> dict:
        """
        Prepare and validate user input for the council.

        Returns:
            Dict with 'text', 'image_data', 'image_mime_type', 'input_type'
        """
        has_text = bool(text and text.strip())
        has_image = bool(image_data)

        if not has_text and not has_image:
            raise ValueError("At least one of text or image must be provided.")

        input_type = "mixed" if (has_text and has_image) else ("image" if has_image else "text")

        return {
            "text": text.strip() if has_text else None,
            "image_data": image_data,
            "image_mime_type": image_mime_type,
            "input_type": input_type,
        }
