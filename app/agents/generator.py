"""
Generator Agent

Generates images from plain text prompts (produced by the Chairman).
No DSD dependency — just a prompt string and optional reference images.

Step-by-step:
  1. Floor plan        — no reference images
  2. Front elevation   — floor plan used as reference
  3. Realistic render  — floor plan + front elevation used as references
"""
import asyncio
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

from app.models.project import GeneratedImage
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)

# View type ordering for the step-by-step flow
VIEW_STEPS = ["floor_plan", "front_elevation", "realistic_render"]


class Generator:
    """
    Generates a single image from a prompt with optional reference images.
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import QUALITY_MAX_RETRIES
        self.client = client or OpenRouterClient()
        self.max_retries = QUALITY_MAX_RETRIES

    async def generate_step(
        self,
        prompt: str,
        view_type: str,
        project_id: str,
        reference_images: list[dict] | None = None,
        on_progress: Callable[[str], None] | None = None,
    ) -> GeneratedImage | None:
        """
        Generate a single image step.

        Args:
            prompt:           The chairman's generation prompt for this step.
            view_type:        "floor_plan" | "front_elevation" | "realistic_render"
            project_id:       For file storage.
            reference_images: List of {"data": base64_str, "mime_type": str}.
                              Pass floor plan for front elevation; pass both for
                              realistic render.
            on_progress:      Optional status callback.

        Returns:
            GeneratedImage or None on failure.
        """
        from app.services.project_store import ProjectStore

        store = ProjectStore()

        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        label = view_type.replace("_", " ").title()
        progress(f"[Generation] Generating {label}...")

        # Print full prompt to terminal for developer review
        sep = "=" * 70
        ref_count = len(reference_images) if reference_images else 0
        print(f"\n{sep}")
        print(f"[GENERATION PROMPT] {label}  |  references: {ref_count}")
        print(sep)
        print(prompt)
        print(f"{sep}\n")

        for attempt in range(1, self.max_retries + 1):
            try:
                result = await self.client.generate_image(
                    prompt=prompt,
                    reference_images=reference_images or None,
                )

                images = result.get("images", [])
                if not images:
                    text_resp = result.get("text", "")
                    logger.warning(
                        f"No images in response for {label} "
                        f"(attempt {attempt}). Text: {text_resp[:200]}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(3)
                    continue

                img_data = images[0]
                b64_data = img_data.get("data", "")
                mime_type = img_data.get("mime_type", "image/png")

                if not b64_data:
                    img_url = img_data.get("url", "")
                    if img_url:
                        b64_data = await self._download_b64(img_url)
                    if not b64_data:
                        logger.warning(f"Empty image data for {label}")
                        if attempt < self.max_retries:
                            await asyncio.sleep(3)
                        continue

                ext = {
                    "image/png": ".png",
                    "image/jpeg": ".jpg",
                    "image/webp": ".webp",
                }.get(mime_type, ".png")

                filename = f"{view_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                image_bytes = base64.b64decode(b64_data)
                save_path = store.save_generated_image(project_id, image_bytes, filename)

                generated = GeneratedImage(
                    view_type=view_type,
                    view_label=label,
                    file_path=str(save_path),
                    generation_prompt=prompt[:500],
                    generated_at=datetime.now().isoformat(),
                    approved=False,
                )

                progress(f"[Generation] {label} complete!")
                return generated

            except Exception as e:
                logger.error(f"Error generating {label} (attempt {attempt}): {e}")
                if on_progress:
                    on_progress(f"[Generation] Retry {attempt}/{self.max_retries}: {str(e)[:100]}")
                if attempt < self.max_retries:
                    await asyncio.sleep(3 * attempt)

        progress(f"[Generation] {label} FAILED after {self.max_retries} attempts.")
        return None

    async def _download_b64(self, url: str) -> str:
        """Download an image from URL and return as base64 string."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=60) as http:
                resp = await http.get(url)
                if resp.status_code == 200:
                    return base64.b64encode(resp.content).decode("utf-8")
                logger.error(f"Failed to download image: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
        return ""
