"""
Refiner Agent — Phase 6

Handles change management: classifying changes, updating the DSD,
and orchestrating targeted regeneration so only affected views
are re-generated.
"""
import asyncio
import json
import logging
from typing import Callable, Optional

from app.models.dsd import (
    ChangeType,
    DesignSpecificationDocument,
    ViewSpec,
    ViewType,
)
from app.models.project import GeneratedImage
from app.prompts.refinement_prompts import (
    CHANGE_CLASSIFICATION_PROMPT,
    COUNCIL_QUICK_REVIEW_PROMPT,
    DSD_UPDATE_PROMPT,
)
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class Refiner:
    """
    Manages design changes and targeted regeneration.

    Flow:
    1. classify_change()  — determine what kind of change + impact
    2. apply_change()     — produce updated DSD (new version)
    3. targeted_regeneration() — regenerate only affected views
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import COUNCIL_MODELS

        self.client = client or OpenRouterClient()
        # Use Claude for classification and DSD editing (best structured output)
        self._model = COUNCIL_MODELS["claude"]["id"]

    # ------------------------------------------------------------------
    # 1. Classify a change request
    # ------------------------------------------------------------------

    async def classify_change(
        self,
        change_request: str,
        dsd: DesignSpecificationDocument,
    ) -> dict:
        """
        Classify a user's change request.

        Returns a dict with:
            change_type: cosmetic | structural | additive | subtractive
            description: clear description of the change
            dsd_sections_affected: list of DSD section names
            views_to_regenerate: list of view type strings
            views_unaffected: list of view type strings
            reasoning: why this classification
            risk_level: low | medium | high
        """
        prompt = CHANGE_CLASSIFICATION_PROMPT.format(
            dsd_description=dsd.to_prompt_description(),
            change_request=change_request,
        )

        response = await self.client.chat_completion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )

        parsed = self.client.extract_json(response)
        if not parsed or not isinstance(parsed, dict):
            text = self.client.extract_text(response)
            logger.warning(f"Could not parse classification: {text[:200]}")
            # Fallback: assume structural change affecting all views
            return {
                "change_type": "structural",
                "description": change_request,
                "dsd_sections_affected": ["description"],
                "views_to_regenerate": [v.value for v in dsd.get_applicable_views()],
                "views_unaffected": [],
                "reasoning": "Fallback classification — could not parse model response",
                "risk_level": "medium",
            }

        return parsed

    # ------------------------------------------------------------------
    # 2. Apply change to DSD
    # ------------------------------------------------------------------

    async def apply_change(
        self,
        change_request: str,
        dsd: DesignSpecificationDocument,
        classification: dict | None = None,
    ) -> DesignSpecificationDocument:
        """
        Apply a change to the DSD, producing a new version.

        If classification is not provided, it will be auto-classified first.

        Args:
            change_request: The user's change request text
            dsd: Current DSD
            classification: Optional pre-classified change info

        Returns:
            New version of the DSD with the change applied
        """
        if classification is None:
            classification = await self.classify_change(change_request, dsd)

        change_type = classification.get("change_type", "structural")
        description = classification.get("description", change_request)
        sections = classification.get("dsd_sections_affected", ["description"])

        baseline_notice = dsd.get_locked_summary() if dsd.baseline_locked else ""
        prompt = DSD_UPDATE_PROMPT.format(
            current_dsd_json=dsd.model_dump_json(indent=2),
            change_type=change_type,
            change_description=description,
            sections_affected=", ".join(sections),
            baseline_lock_notice=baseline_notice,
        )

        response = await self.client.chat_completion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )

        parsed = self.client.extract_json(response)
        if not parsed or not isinstance(parsed, dict):
            logger.error("Could not parse updated DSD from model response")
            # Fallback: create new version with just the change recorded
            try:
                ct = ChangeType(change_type)
            except ValueError:
                ct = ChangeType.STRUCTURAL
            return dsd.create_new_version(
                change_type=ct,
                description=description,
                sections=sections,
            )

        # Validate the updated DSD
        try:
            updated_dsd = DesignSpecificationDocument.model_validate(parsed)
            # Ensure version was incremented
            if updated_dsd.version <= dsd.version:
                updated_dsd.version = dsd.version + 1
            # Ensure project_id is preserved
            updated_dsd.project_id = dsd.project_id
            return updated_dsd
        except Exception as e:
            logger.error(f"Invalid DSD from model: {e}")
            # Fallback: manual version bump
            try:
                ct = ChangeType(change_type)
            except ValueError:
                ct = ChangeType.STRUCTURAL
            return dsd.create_new_version(
                change_type=ct,
                description=description,
                sections=sections,
            )

    # ------------------------------------------------------------------
    # 3. Targeted regeneration
    # ------------------------------------------------------------------

    async def targeted_regeneration(
        self,
        dsd: DesignSpecificationDocument,
        views_to_regenerate: list[str],
        change_description: str,
        project_id: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> list[GeneratedImage]:
        """
        Regenerate only the views affected by a change.

        Uses the updated DSD and change description as additional
        context so the image generation can focus on applying the change.

        Args:
            dsd: The UPDATED DSD (new version)
            views_to_regenerate: List of view type strings to regenerate
            change_description: What changed (for targeted prompt)
            project_id: Project ID for storage
            on_progress: Progress callback

        Returns:
            List of newly generated images
        """
        from app.agents.generator import Generator

        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        generator = Generator(client=self.client)
        results: list[GeneratedImage] = []
        total = len(views_to_regenerate)

        progress(
            f"[Refinement] Regenerating {total} view(s) "
            f"for change: {change_description[:60]}..."
        )

        # Resolve view type strings to ViewSpec objects from the DSD.
        # A view_str like "front_elevation" may match MULTIPLE ViewSpecs
        # (e.g. Wall A and Wall B of an L-shaped kitchen).
        specs_to_regen: list[ViewSpec] = []
        for view_str in views_to_regenerate:
            matched = [vs for vs in (dsd.views_to_generate or []) if vs.type == view_str]
            if matched:
                specs_to_regen.extend(matched)
            else:
                # Fallback: create a basic ViewSpec
                try:
                    ViewType(view_str)  # validate
                except ValueError:
                    progress(f"[Refinement] Unknown view type: {view_str}, skipping")
                    continue
                specs_to_regen.append(ViewSpec(
                    type=view_str,
                    label=view_str.replace("_", " ").title(),
                ))

        total = len(specs_to_regen)
        for idx, view_spec in enumerate(specs_to_regen, 1):
            view_name = view_spec.label
            progress(f"[Refinement] ({idx}/{total}) Regenerating {view_name}...")

            # Use regenerate_view with the change as feedback
            baseline_notice = dsd.get_locked_summary() if dsd.baseline_locked else ""
            feedback = (
                f"DESIGN CHANGE APPLIED: {change_description}\n"
                f"Ensure this change is reflected in the image while "
                f"keeping all other aspects of the design identical.\n"
                f"{baseline_notice}"
            ).strip()

            new_image = await generator.regenerate_view(
                dsd=dsd,
                view_spec=view_spec,
                project_id=project_id,
                feedback=feedback,
            )

            if new_image:
                results.append(new_image)
                progress(f"[Refinement] ({idx}/{total}) {view_name} complete!")
            else:
                progress(f"[Refinement] ({idx}/{total}) {view_name} FAILED")

            if idx < total:
                await asyncio.sleep(2)

        progress(
            f"[Refinement] Done! {len(results)}/{total} views regenerated."
        )
        return results

    # ------------------------------------------------------------------
    # 4. Council quick review of DSD changes
    # ------------------------------------------------------------------

    async def council_quick_review(
        self,
        original_dsd: DesignSpecificationDocument,
        updated_dsd: DesignSpecificationDocument,
        change_request: str,
        change_type: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> dict:
        """
        Have the council review the DSD modification for consistency.

        Returns a dict with:
            change_valid, change_complete, issues, suggestions, approved
        """
        from config import COUNCIL_MODELS

        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        progress("[Council Review] Council is reviewing the modification...")

        prompt = COUNCIL_QUICK_REVIEW_PROMPT.format(
            original_dsd=original_dsd.to_prompt_description(),
            updated_dsd=updated_dsd.to_prompt_description(),
            change_description=change_request,
            change_type=change_type,
        )

        # Query all three council members in parallel
        import asyncio as _asyncio

        council_models = [
            COUNCIL_MODELS["claude"]["id"],
            COUNCIL_MODELS["gpt"]["id"],
            COUNCIL_MODELS["gemini"]["id"],
        ]

        async def _query(model_id: str) -> dict | None:
            try:
                resp = await self.client.chat_completion(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=1024,
                )
                parsed = self.client.extract_json(resp)
                if isinstance(parsed, dict):
                    return parsed
            except Exception as e:
                logger.warning(f"Council review from {model_id} failed: {e}")
            return None

        results = await _asyncio.gather(*[_query(m) for m in council_models])
        valid_results = [r for r in results if r is not None]

        if not valid_results:
            progress("[Council Review] No council responses — proceeding anyway.")
            return {"approved": True, "issues": [], "suggestions": []}

        # Majority vote: approved if majority says approved
        approvals = sum(1 for r in valid_results if r.get("approved", False))
        majority_approved = approvals > len(valid_results) / 2

        all_issues: list[str] = []
        all_suggestions: list[str] = []
        for r in valid_results:
            all_issues.extend(r.get("issues", []))
            all_suggestions.extend(r.get("suggestions", []))

        progress(
            f"[Council Review] {approvals}/{len(valid_results)} members approved. "
            f"{'Approved.' if majority_approved else 'Issues found.'}"
        )

        if all_issues:
            for issue in all_issues[:5]:  # Show top 5 issues
                progress(f"[Council Review] Issue: {issue}")

        return {
            "approved": majority_approved,
            "change_valid": all(r.get("change_valid", True) for r in valid_results),
            "change_complete": all(r.get("change_complete", True) for r in valid_results),
            "issues": all_issues,
            "suggestions": all_suggestions,
        }

    # ------------------------------------------------------------------
    # Full refinement pipeline
    # ------------------------------------------------------------------

    async def refine(
        self,
        change_request: str,
        dsd: DesignSpecificationDocument,
        project_id: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> tuple[DesignSpecificationDocument, dict, list[GeneratedImage]]:
        """
        Full refinement pipeline:
            classify → update DSD → council review → regenerate ALL technical views.

        Args:
            change_request: User's change request text
            dsd: Current DSD
            project_id: Project ID
            on_progress: Progress callback

        Returns:
            Tuple of (updated_dsd, classification, new_images)
        """
        def progress(msg: str):
            logger.info(msg)
            if on_progress:
                on_progress(msg)

        # Step 1: Classify
        progress("[Refinement] Classifying change request...")
        classification = await self.classify_change(change_request, dsd)
        change_type = classification.get("change_type", "structural")
        risk = classification.get("risk_level", "unknown")

        progress(
            f"[Refinement] Classification: {change_type} (risk: {risk})"
        )

        # Step 2: Update DSD
        progress("[Refinement] Updating Design Specification...")
        updated_dsd = await self.apply_change(
            change_request, dsd, classification
        )
        progress(
            f"[Refinement] DSD updated to version {updated_dsd.version}"
        )

        # Step 3: Council quick review
        review = await self.council_quick_review(
            original_dsd=dsd,
            updated_dsd=updated_dsd,
            change_request=change_request,
            change_type=change_type,
            on_progress=on_progress,
        )

        if review.get("issues"):
            progress(
                f"[Refinement] Council found {len(review['issues'])} issue(s). "
                f"Proceeding with regeneration."
            )

        # Step 4: Regenerate ALL technical views (mandatory)
        # Floor plan + ALL front elevations must always be regenerated
        # to maintain consistency across views.
        _TECHNICAL_TYPES = {"floor_plan", "front_elevation", "side_elevation", "rear_elevation"}
        technical_specs = [
            vs for vs in (updated_dsd.views_to_generate or [])
            if vs.type in _TECHNICAL_TYPES
        ]

        # Fallback: if DSD has no technical views, create defaults
        if not technical_specs:
            technical_specs = [
                ViewSpec(type="floor_plan", label="Floor Plan", description="Top-down layout"),
                ViewSpec(type="front_elevation", label="Front Elevation", description="Frontal view"),
            ]

        # Ensure at least 1 floor_plan + 1 front_elevation are present
        has_floor = any(vs.type == "floor_plan" for vs in technical_specs)
        has_elev = any(vs.type == "front_elevation" for vs in technical_specs)
        if not has_floor:
            technical_specs.insert(0, ViewSpec(
                type="floor_plan", label="Floor Plan", description="Top-down layout"
            ))
        if not has_elev:
            technical_specs.append(ViewSpec(
                type="front_elevation", label="Front Elevation", description="Frontal view"
            ))

        progress(
            f"[Refinement] Regenerating ALL {len(technical_specs)} technical view(s) "
            f"for consistency..."
        )

        from app.agents.generator import Generator
        generator = Generator(client=self.client)
        results: list[GeneratedImage] = []
        change_desc = classification.get("description", change_request)

        for idx, view_spec in enumerate(technical_specs, 1):
            progress(
                f"[Refinement] ({idx}/{len(technical_specs)}) "
                f"Regenerating {view_spec.label}..."
            )

            baseline_notice = updated_dsd.get_locked_summary() if updated_dsd.baseline_locked else ""
            feedback = (
                f"DESIGN CHANGE APPLIED: {change_desc}\n"
                f"Ensure this change is reflected in the image while "
                f"keeping all other aspects of the design identical.\n"
                f"{baseline_notice}"
            ).strip()

            new_image = await generator.regenerate_view(
                dsd=updated_dsd,
                view_spec=view_spec,
                project_id=project_id,
                feedback=feedback,
            )

            if new_image:
                results.append(new_image)
                progress(
                    f"[Refinement] ({idx}/{len(technical_specs)}) "
                    f"{view_spec.label} complete!"
                )
            else:
                progress(
                    f"[Refinement] ({idx}/{len(technical_specs)}) "
                    f"{view_spec.label} FAILED"
                )

            if idx < len(technical_specs):
                import asyncio as _aio
                await _aio.sleep(2)

        progress(
            f"[Refinement] Done! {len(results)}/{len(technical_specs)} "
            f"views regenerated."
        )

        return updated_dsd, classification, results
