"""
Generator Agent — Phase 3

Handles image generation using Nano Banana (Gemini 3 Pro Image Preview)
via OpenRouter.  Generates architectural views (floor plans, elevations,
3D renders) based on the Design Specification Document.
"""
import asyncio
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app.models.dsd import DesignSpecificationDocument, ViewSpec, ViewType
from app.models.project import GeneratedImage
from app.prompts.generation_prompts import (
    build_prompt_from_council,
    get_generation_prompt,
)
from app.services.image_service import ImageService
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class Generator:
    """
    Generates architectural images from a DSD.

    Uses Nano Banana (Gemini 3 Pro Image Preview) to generate
    each view type with tailored prompts.
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import QUALITY_MAX_RETRIES
        self.client = client or OpenRouterClient()
        self.max_retries = QUALITY_MAX_RETRIES

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_all_views(
        self,
        dsd: DesignSpecificationDocument,
        project_id: str,
        on_progress: Callable[[str], None] | None = None,
        view_filter: list[ViewSpec] | None = None,
    ) -> list[GeneratedImage]:
        """
        Generate views from the DSD.

        Each view is generated sequentially to avoid rate-limiting
        and to provide clear progress updates.

        Args:
            dsd: The approved Design Specification Document
            project_id: Project ID for file storage
            on_progress: Optional callback for status messages
            view_filter: If provided, only generate these specific ViewSpecs.
                         If None, generate all views in the DSD.

        Returns:
            List of GeneratedImage objects (one per view)
        """
        from app.services.project_store import ProjectStore

        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        store = ProjectStore()

        if view_filter is not None:
            views = view_filter
        else:
            views = dsd.views_to_generate
            if not views:
                views = dsd.get_applicable_views()

        total = len(views)
        progress(f"[Generation] Starting image generation for {total} view(s)...")

        results: list[GeneratedImage] = []

        for idx, view_spec in enumerate(views, 1):
            progress(f"[Generation] ({idx}/{total}) Generating {view_spec.label}...")

            generated = await self._generate_single_with_retry(
                dsd=dsd,
                view_spec=view_spec,
                project_id=project_id,
                store=store,
                on_progress=on_progress,
            )

            if generated:
                results.append(generated)
                progress(f"[Generation] ({idx}/{total}) {view_spec.label} complete!")
            else:
                progress(
                    f"[Generation] ({idx}/{total}) {view_spec.label} FAILED "
                    f"after {self.max_retries} attempts."
                )

            # Brief delay between views to be kind to the API
            if idx < total:
                await asyncio.sleep(2)

        success_count = len(results)
        progress(
            f"[Generation] Done! {success_count}/{total} images generated successfully."
        )
        return results

    async def generate_single_view(
        self,
        dsd: DesignSpecificationDocument,
        view_spec: ViewSpec,
        project_id: str,
    ) -> GeneratedImage | None:
        """
        Generate a single view from the DSD.

        Returns:
            A GeneratedImage if successful, None otherwise.
        """
        from app.services.project_store import ProjectStore

        store = ProjectStore()
        return await self._generate_single_with_retry(
            dsd=dsd,
            view_spec=view_spec,
            project_id=project_id,
            store=store,
        )

    async def regenerate_view(
        self,
        dsd: DesignSpecificationDocument,
        view_spec: ViewSpec,
        project_id: str,
        feedback: str = "",
    ) -> GeneratedImage | None:
        """
        Regenerate a view incorporating quality review feedback.

        The feedback is appended to the generation prompt so the model
        can correct specific issues identified during review.
        """
        from app.services.project_store import ProjectStore

        store = ProjectStore()
        return await self._generate_single_with_retry(
            dsd=dsd,
            view_spec=view_spec,
            project_id=project_id,
            store=store,
            extra_instructions=feedback,
        )

    # ------------------------------------------------------------------
    # Internal: Single generation with retry
    # ------------------------------------------------------------------

    async def _generate_single_with_retry(
        self,
        dsd: DesignSpecificationDocument,
        view_spec: ViewSpec,
        project_id: str,
        store,
        on_progress: Callable[[str], None] | None = None,
        extra_instructions: str = "",
    ) -> GeneratedImage | None:
        """
        Attempt to generate a single view, retrying on failure.

        Returns:
            A GeneratedImage on success, None if all retries fail.
        """
        view_name = view_spec.type  # e.g. "front_elevation"
        view_label = view_spec.label  # e.g. "Front Elevation — Wall A"
        view_description = view_spec.description
        council_content = view_spec.generation_prompt  # council-authored content
        dsd_description = dsd.to_prompt_description()

        # Build the prompt — prefer council-authored content over fixed template
        if council_content and len(council_content.strip()) > 40:
            # PRIMARY PATH: Council wrote a specific content prompt.
            # Inject it into the appropriate style wrapper.
            try:
                prompt = build_prompt_from_council(view_name, council_content)
                logger.info(
                    f"Using council-authored prompt for {view_label} "
                    f"({len(council_content)} chars)"
                )
            except ValueError:
                logger.warning(
                    f"No style wrapper for view type '{view_name}', "
                    f"falling back to fixed template."
                )
                prompt = get_generation_prompt(view_name, dsd_description)
        else:
            # FALLBACK PATH: No council content — use fixed template with DSD.
            logger.info(
                f"No council prompt for {view_label} — using fixed template fallback."
            )
            try:
                prompt = get_generation_prompt(view_name, dsd_description)
            except ValueError:
                logger.error(f"No prompt template for view: {view_name}")
                return None

        # Append view label/description context so the model knows WHICH view
        # to draw (important when there are multiple front_elevation views)
        if view_label or view_description:
            view_context = (
                f"\n\nSPECIFIC VIEW CONTEXT:\n"
                f"View Label: {view_label}\n"
            )
            if view_description and view_description not in (council_content or ""):
                view_context += f"View Description: {view_description}\n"
            view_context += (
                "\nGenerate ONLY this specific view — not all elevations combined."
            )
            prompt += view_context

        if extra_instructions:
            prompt += (
                f"\n\nADDITIONAL INSTRUCTIONS (from quality review):\n"
                f"{extra_instructions}"
            )

        # ── Developer review: print full prompt to terminal ──────────────
        separator = "=" * 80
        print(f"\n{separator}")
        print(f"[GENERATION PROMPT] View: {view_label}  |  Type: {view_name}")
        print(f"  Source: {'council-authored' if (council_content and len(council_content.strip()) > 40) else 'fallback template'}")
        print(separator)
        print(prompt)
        print(f"{separator}\n")
        # ─────────────────────────────────────────────────────────────────

        # Use view_spec.id for unique filenames (avoids overwriting
        # when there are multiple front_elevation views)
        safe_label = view_spec.id

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Generating {view_label} ({view_name}) — "
                    f"attempt {attempt}/{self.max_retries}"
                )

                result = await self.client.generate_image(
                    prompt=prompt,
                )

                images = result.get("images", [])
                if not images:
                    text_resp = result.get("text", "")
                    logger.warning(
                        f"No images in response for {view_label} "
                        f"(attempt {attempt}). Text: {text_resp[:200]}"
                    )
                    if attempt < self.max_retries:
                        await asyncio.sleep(3)
                    continue

                # Take the first image
                img_data = images[0]
                b64_data = img_data.get("data", "")
                mime_type = img_data.get("mime_type", "image/png")

                if not b64_data:
                    # Maybe it's a URL instead of base64
                    img_url = img_data.get("url", "")
                    if img_url:
                        logger.info(f"Image returned as URL: {img_url[:100]}...")
                        b64_data = await self._download_image_as_b64(img_url)
                        if not b64_data:
                            logger.warning(f"Failed to download image from URL")
                            if attempt < self.max_retries:
                                await asyncio.sleep(3)
                            continue

                # Determine file extension from mime
                ext = {
                    "image/png": ".png",
                    "image/jpeg": ".jpg",
                    "image/webp": ".webp",
                }.get(mime_type, ".png")

                filename = f"{view_name}_{safe_label}_v{dsd.version}{ext}"

                # Decode and save
                image_bytes = base64.b64decode(b64_data)
                save_path = store.save_generated_image(
                    project_id, image_bytes, filename
                )

                # Create GeneratedImage record
                generated_image = GeneratedImage(
                    view_type=view_name,
                    file_path=str(save_path),
                    dsd_version=dsd.version,
                    generation_prompt=prompt[:500],  # Store truncated prompt
                    generated_at=datetime.now().isoformat(),
                    view_label=view_label,
                    view_spec_id=view_spec.id,
                )

                logger.info(
                    f"Successfully generated {view_label} -> {save_path}"
                )
                return generated_image

            except Exception as e:
                logger.error(
                    f"Error generating {view_label} "
                    f"(attempt {attempt}/{self.max_retries}): {e}"
                )
                if on_progress:
                    on_progress(
                        f"[Generation] Retry {attempt}/{self.max_retries} "
                        f"for {view_label}: {str(e)[:100]}"
                    )
                if attempt < self.max_retries:
                    await asyncio.sleep(3 * attempt)

        return None

    # ------------------------------------------------------------------
    # Helper: Download image from URL
    # ------------------------------------------------------------------

    async def _download_image_as_b64(self, url: str) -> str:
        """Download an image from a URL and return as base64 string."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return base64.b64encode(resp.content).decode("utf-8")
                else:
                    logger.error(
                        f"Failed to download image: HTTP {resp.status_code}"
                    )
                    return ""
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return ""
