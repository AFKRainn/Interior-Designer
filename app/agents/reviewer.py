"""
Reviewer Agent — Phase 4

Handles quality review of generated images against the DSD.
Uses council vision models to score each image on multiple criteria
and provide structured feedback for regeneration.
"""
import asyncio
import logging
from pathlib import Path
from typing import Callable, Optional

from app.models.dsd import DesignSpecificationDocument
from app.models.project import (
    GeneratedImage,
    ReviewFeedback,
    ReviewResult,
    ReviewScores,
)
from app.prompts.review_prompts import QUALITY_REVIEW_PROMPT, CHANGE_VERIFICATION_PROMPT
from app.services.image_service import ImageService
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class Reviewer:
    """
    Reviews generated images for quality and accuracy.

    Uses a council vision model to score images against the DSD
    on five criteria:
      - Dimensional accuracy
      - Material & color accuracy
      - Style adherence
      - View correctness
      - Overall quality

    If an image scores below the threshold it is flagged for
    regeneration with specific feedback.
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import (
            QUALITY_MIN_SCORE,
            QUALITY_MAX_RETRIES,
            COUNCIL_MODELS,
            VIEWS_CONFIG,
        )

        self.client = client or OpenRouterClient()
        self.min_score = QUALITY_MIN_SCORE
        self.max_retries = QUALITY_MAX_RETRIES
        self.council_models = COUNCIL_MODELS
        self.views_config = VIEWS_CONFIG

        # Use Claude for reviews by default (best at structured analysis)
        self._review_model = self.council_models["claude"]["id"]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def review_image(
        self,
        image: GeneratedImage,
        dsd: DesignSpecificationDocument,
    ) -> ReviewResult:
        """
        Review a single generated image against the DSD.

        Sends the image + DSD description to a vision model and
        parses the structured JSON response into a ReviewResult.

        Args:
            image: The generated image to review
            dsd: The Design Specification Document it should match

        Returns:
            ReviewResult with scores, feedback, and approval status
        """
        view_type = image.view_type
        view_desc = self.views_config.get(view_type, {}).get(
            "description", view_type.replace("_", " ").title()
        )
        dsd_description = dsd.to_prompt_description()

        # Build the review prompt
        prompt = QUALITY_REVIEW_PROMPT.format(
            dsd_description=dsd_description,
            view_type=view_type.replace("_", " ").title(),
            view_description=view_desc,
            min_score=self.min_score,
        )

        # Load the generated image
        img_path = Path(image.file_path)
        if not img_path.exists():
            return ReviewResult(
                image_id=image.id,
                reviewer_model=self._review_model,
                error=f"Image file not found: {image.file_path}",
            )

        try:
            b64_data, mime_type = ImageService.load_and_encode(img_path)
        except Exception as e:
            return ReviewResult(
                image_id=image.id,
                reviewer_model=self._review_model,
                error=f"Failed to load image: {e}",
            )

        # Call the vision model
        try:
            response = await self.client.vision_completion(
                model=self._review_model,
                prompt=prompt,
                image_data=b64_data,
                image_mime_type=mime_type,
                temperature=0.3,   # Low temperature for consistent scoring
                max_tokens=2048,
            )

            return self._parse_review_response(response, image.id)

        except Exception as e:
            logger.error(f"Review API call failed for {image.id}: {e}")
            return ReviewResult(
                image_id=image.id,
                reviewer_model=self._review_model,
                error=f"API call failed: {e}",
            )

    async def review_all_images(
        self,
        images: list[GeneratedImage],
        dsd: DesignSpecificationDocument,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[ReviewResult]:
        """
        Review all generated images sequentially.

        Args:
            images: List of generated images to review
            dsd: The DSD to review against
            on_progress: Optional callback for status messages

        Returns:
            List of ReviewResult objects (one per image)
        """
        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        total = len(images)
        progress(f"[Review] Starting quality review for {total} image(s)...")

        results: list[ReviewResult] = []

        for idx, image in enumerate(images, 1):
            view_name = image.display_label
            progress(f"[Review] ({idx}/{total}) Reviewing {view_name}...")

            result = await self.review_image(image, dsd)
            results.append(result)

            if result.error:
                progress(
                    f"[Review] ({idx}/{total}) {view_name}: "
                    f"ERROR - {result.error[:80]}"
                )
            elif result.approved:
                progress(
                    f"[Review] ({idx}/{total}) {view_name}: "
                    f"APPROVED (score: {result.average_score:.1f}/10)"
                )
            else:
                issues_summary = "; ".join(result.feedback.issues[:2]) if result.feedback.issues else "Below threshold"
                progress(
                    f"[Review] ({idx}/{total}) {view_name}: "
                    f"NEEDS WORK (score: {result.average_score:.1f}/10) - {issues_summary}"
                )

            # Brief delay between reviews
            if idx < total:
                await asyncio.sleep(1)

        # Summary
        approved = sum(1 for r in results if r.approved)
        failed = sum(1 for r in results if r.error)
        needs_work = total - approved - failed
        progress(
            f"[Review] Done! {approved} approved, "
            f"{needs_work} need work, {failed} errors."
        )

        return results

    async def review_and_regenerate(
        self,
        images: list[GeneratedImage],
        dsd: DesignSpecificationDocument,
        project_id: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[list[GeneratedImage], list[ReviewResult]]:
        """
        Review all images and automatically regenerate those that fail.

        This is the main quality loop:
        1. Review all images
        2. For images below threshold, regenerate with feedback
        3. Re-review regenerated images
        4. Repeat up to max_retries times

        Args:
            images: Generated images to review
            dsd: The DSD to review against
            project_id: Project ID for saving regenerated images
            on_progress: Progress callback

        Returns:
            Tuple of (final_images, all_review_results)
        """
        from app.agents.generator import Generator

        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        generator = Generator(client=self.client)
        current_images = list(images)
        all_reviews: list[ReviewResult] = []

        for attempt in range(1, self.max_retries + 1):
            progress(
                f"[Review] === Quality review round {attempt}/{self.max_retries} ==="
            )

            # Review current set
            reviews = await self.review_all_images(
                current_images, dsd, on_progress=on_progress
            )
            all_reviews.extend(reviews)

            # Apply review results to images
            for img, review in zip(current_images, reviews):
                img.quality_score = review.average_score
                img.quality_feedback = self._format_feedback_text(review)
                img.review_result = review
                img.review_attempts = attempt
                if review.approved:
                    img.approved = True

            # Check which images need regeneration
            to_regen: list[tuple[GeneratedImage, ReviewResult]] = []
            for img, review in zip(current_images, reviews):
                if not review.approved and not review.error:
                    to_regen.append((img, review))

            if not to_regen:
                progress("[Review] All images approved! Quality review complete.")
                break

            if attempt >= self.max_retries:
                progress(
                    f"[Review] Max review rounds reached. "
                    f"{len(to_regen)} image(s) still below threshold."
                )
                break

            # Regenerate failed images
            progress(
                f"[Review] Regenerating {len(to_regen)} image(s) "
                f"with quality feedback..."
            )

            from app.models.dsd import ViewSpec, ViewType

            for img, review in to_regen:
                view_name = img.display_label
                progress(f"[Review] Regenerating {view_name}...")

                # Find the matching ViewSpec from the DSD
                view_spec = None
                if img.spec_id:
                    for vs in (dsd.views_to_generate or []):
                        if vs.id == img.spec_id:
                            view_spec = vs
                            break
                if view_spec is None:
                    try:
                        ViewType(img.view_type)  # validate
                    except ValueError:
                        progress(f"[Review] Unknown view type: {img.view_type}, skipping")
                        continue
                    view_spec = ViewSpec(
                        type=img.view_type,
                        label=view_name,
                    )

                feedback = review.regeneration_instructions
                if not feedback:
                    # Build feedback from issues
                    feedback = self._build_regeneration_feedback(review)

                new_image = await generator.regenerate_view(
                    dsd=dsd,
                    view_spec=view_spec,
                    project_id=project_id,
                    feedback=feedback,
                )

                if new_image:
                    # Replace old image in current set
                    idx = current_images.index(img)
                    current_images[idx] = new_image
                    progress(f"[Review] {view_name} regenerated successfully.")
                else:
                    progress(f"[Review] {view_name} regeneration failed.")

                await asyncio.sleep(2)

        return current_images, all_reviews

    async def verify_change(
        self,
        original_image_path: str,
        modified_image_path: str,
        change_description: str,
        change_type: str = "unknown",
        sections_affected: list[str] | None = None,
    ) -> dict:
        """
        Verify that a design change was applied correctly.

        Compares original and modified images using the vision model.

        Args:
            original_image_path: Path to the original image
            modified_image_path: Path to the modified image
            change_description: What was supposed to change
            change_type: Type of change (cosmetic, structural, etc.)
            sections_affected: Which parts of the design were affected

        Returns:
            Dict with verification results
        """
        prompt = CHANGE_VERIFICATION_PROMPT.format(
            change_description=change_description,
            change_type=change_type,
            sections_affected=", ".join(sections_affected or ["unspecified"]),
        )

        # Load both images
        try:
            orig_b64, orig_mime = ImageService.load_and_encode(original_image_path)
            mod_b64, mod_mime = ImageService.load_and_encode(modified_image_path)
        except Exception as e:
            return {"error": f"Failed to load images: {e}"}

        try:
            response = await self.client.vision_completion_multi(
                model=self._review_model,
                prompt=prompt,
                images=[
                    (orig_b64, orig_mime),
                    (mod_b64, mod_mime),
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            parsed = self.client.extract_json(response)
            if parsed and isinstance(parsed, dict):
                return parsed

            text = self.client.extract_text(response)
            return {"raw_response": text, "error": "Could not parse JSON"}

        except Exception as e:
            return {"error": f"Verification failed: {e}"}

    # ------------------------------------------------------------------
    # Internal: Parse review response
    # ------------------------------------------------------------------

    def _parse_review_response(
        self, response: dict, image_id: str
    ) -> ReviewResult:
        """Parse the vision model's JSON response into a ReviewResult."""
        parsed = self.client.extract_json(response)

        if not parsed or not isinstance(parsed, dict):
            # Fallback: try to extract useful info from text
            text = self.client.extract_text(response)
            logger.warning(
                f"Could not parse review JSON for {image_id}. "
                f"Text: {text[:200]}"
            )
            return ReviewResult(
                image_id=image_id,
                reviewer_model=self._review_model,
                error=f"Could not parse review response: {text[:200]}",
            )

        try:
            # Extract scores
            scores_raw = parsed.get("scores", {})
            scores = ReviewScores(
                dimensional_accuracy=float(scores_raw.get("dimensional_accuracy", 0)),
                material_color_accuracy=float(scores_raw.get("material_color_accuracy", 0)),
                style_adherence=float(scores_raw.get("style_adherence", 0)),
                view_correctness=float(scores_raw.get("view_correctness", 0)),
                overall_quality=float(scores_raw.get("overall_quality", 0)),
            )

            # Calculate average
            score_values = [
                scores.dimensional_accuracy,
                scores.material_color_accuracy,
                scores.style_adherence,
                scores.view_correctness,
                scores.overall_quality,
            ]
            avg_score = sum(score_values) / len(score_values) if score_values else 0

            # Use model's average if provided
            model_avg = parsed.get("average_score")
            if model_avg is not None:
                try:
                    avg_score = float(model_avg)
                except (ValueError, TypeError):
                    pass

            # Extract feedback
            fb_raw = parsed.get("feedback", {})
            feedback = ReviewFeedback(
                strengths=fb_raw.get("strengths", []) if isinstance(fb_raw, dict) else [],
                issues=fb_raw.get("issues", []) if isinstance(fb_raw, dict) else [],
                suggestions=fb_raw.get("suggestions", []) if isinstance(fb_raw, dict) else [],
            )

            # Approval
            approved = parsed.get("approved", avg_score >= self.min_score)
            if isinstance(approved, str):
                approved = approved.lower() in ("true", "yes", "1")

            # Regeneration instructions
            regen = parsed.get("regeneration_prompt_additions", "")

            return ReviewResult(
                image_id=image_id,
                reviewer_model=self._review_model,
                scores=scores,
                average_score=round(avg_score, 2),
                approved=bool(approved),
                feedback=feedback,
                regeneration_instructions=str(regen),
            )

        except Exception as e:
            logger.error(f"Error parsing review result: {e}")
            return ReviewResult(
                image_id=image_id,
                reviewer_model=self._review_model,
                error=f"Parse error: {e}",
            )

    # ------------------------------------------------------------------
    # Internal: Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_feedback_text(review: ReviewResult) -> str:
        """Format a ReviewResult into a human-readable text summary."""
        parts = []

        if review.error:
            return f"Review error: {review.error}"

        parts.append(f"Score: {review.average_score:.1f}/10")

        if review.feedback.strengths:
            parts.append("Strengths: " + "; ".join(review.feedback.strengths))

        if review.feedback.issues:
            parts.append("Issues: " + "; ".join(review.feedback.issues))

        if review.feedback.suggestions:
            parts.append("Suggestions: " + "; ".join(review.feedback.suggestions))

        return " | ".join(parts)

    @staticmethod
    def _build_regeneration_feedback(review: ReviewResult) -> str:
        """Build regeneration instructions from review feedback."""
        parts = []
        threshold = 7  # Below this, add specific guidance

        if review.feedback.issues:
            parts.append("Fix these issues:")
            for issue in review.feedback.issues:
                parts.append(f"- {issue}")

        if review.feedback.suggestions:
            parts.append("\nFollow these suggestions:")
            for sug in review.feedback.suggestions:
                parts.append(f"- {sug}")

        # Add specific score-based guidance
        if review.scores.dimensional_accuracy < threshold:
            parts.append("\nPay special attention to proportions and dimensions.")

        if review.scores.material_color_accuracy < threshold:
            parts.append("Ensure materials and colors match the specification exactly.")

        if review.scores.style_adherence < threshold:
            parts.append("Make sure the overall style and aesthetic match the design brief.")

        if review.scores.view_correctness < threshold:
            parts.append("Ensure this is the correct view type (angle, orientation, projection).")

        return "\n".join(parts) if parts else "Improve overall quality and accuracy."
