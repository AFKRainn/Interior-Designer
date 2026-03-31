"""
Council Orchestration — Layer 1

Manages the 3-round deliberation process:
  Round 1: Independent analysis (parallel)
  Round 2: Cross-review (parallel)
  Round 3: Convergence (parallel)
  + Consensus check and Chairman synthesis

This is the entry point for all council sessions.
"""
import asyncio
import json
import logging
from typing import Optional
from uuid import uuid4

from app.models.council_state import (
    CouncilState,
    ConsensusStatus,
    DeliberationRound,
    MemberResponse,
)
from app.models.dsd import DesignSpecificationDocument
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


class Council:
    """
    Orchestrates the multi-model deliberation process.

    Three LLMs independently analyze, cross-review, and converge
    on a unified interpretation of a design input.
    """

    def __init__(self, client: OpenRouterClient | None = None):
        from config import COUNCIL_MODELS, COUNCIL_MAX_ROUNDS

        self.client = client or OpenRouterClient()
        self.models = COUNCIL_MODELS
        self.max_rounds = COUNCIL_MAX_ROUNDS
        self.member_ids = list(self.models.keys())  # ["claude", "gpt", "gemini"]

    async def deliberate(
        self,
        project_id: str,
        user_text: str | None = None,
        image_data: str | None = None,
        image_mime_type: str = "image/png",
        purpose: str = "interpretation",
        on_progress: callable = None,
        all_images: list[dict] | None = None,
    ) -> tuple[CouncilState, DesignSpecificationDocument | None]:
        """
        Run a full council deliberation session.

        Args:
            project_id: The project this deliberation belongs to
            user_text: Text description from the user (optional)
            image_data: Base64-encoded image from the user (optional)
            image_mime_type: MIME type of the image
            purpose: What this deliberation is for
            on_progress: Callback for progress updates (message: str)
            all_images: List of {"data": b64, "mime_type": str} dicts
                        for multi-image support

        Returns:
            Tuple of (CouncilState, DSD or None)
        """
        state = CouncilState(
            session_id=str(uuid4()),
            project_id=project_id,
            purpose=purpose,
        )

        def progress(msg: str):
            if on_progress:
                on_progress(msg)
            logger.info(msg)

        try:
            # ---- Round 1: Independent Analysis ----
            progress("[Round 1] Each council member is independently analyzing the input...")
            await self._run_round1(
                state, user_text, image_data, image_mime_type,
                all_images=all_images,
            )
            progress("[Round 1] Complete - all three interpretations received.")

            # ---- Round 2: Cross-Review ----
            progress("[Round 2] Council members are reviewing each other's interpretations...")
            await self._run_round2(state)
            progress("[Round 2] Complete - cross-reviews received.")

            # ---- Round 3: Convergence ----
            progress("[Round 3] Council members are converging on a unified interpretation...")
            await self._run_round3(state)
            progress("[Round 3] Complete - final interpretations received.")

            # ---- Consensus Check ----
            progress("[Consensus] Checking for consensus...")
            consensus = self._check_consensus(state)

            if consensus:
                state.mark_complete(ConsensusStatus.REACHED, "Council reached consensus.")
                progress("[Consensus] Reached!")
            else:
                state.mark_complete(ConsensusStatus.FORCED, "Chairman made final decision.")
                progress("[Consensus] No full consensus - Chairman will synthesize.")

            # ---- Chairman Synthesis ----
            progress("[Chairman] Synthesizing the final Design Specification...")
            dsd = await self._chairman_synthesis(state, project_id)
            progress("[Chairman] Design Specification Document created!")

            return state, dsd

        except Exception as e:
            logger.error(f"Council deliberation failed: {e}")
            state.mark_complete(ConsensusStatus.FAILED, str(e))
            raise

    # ------------------------------------------------------------------
    # Round Implementations
    # ------------------------------------------------------------------

    async def _run_round1(
        self,
        state: CouncilState,
        user_text: str | None,
        image_data: str | None,
        image_mime_type: str,
        all_images: list[dict] | None = None,
    ):
        """Round 1: Each member independently analyzes the input."""
        from app.prompts.council_prompts import (
            COUNCIL_SYSTEM_PROMPT,
            ROUND1_TEXT_PROMPT,
            ROUND1_IMAGE_PROMPT,
            ROUND1_MIXED_PROMPT,
        )
        from app.prompts.domain_knowledge import get_domain_knowledge

        rnd = state.add_round("independent_analysis")

        # Determine input type and build prompt
        has_text = bool(user_text and user_text.strip())
        has_image = bool(image_data) or bool(all_images)

        # Infer design type from text for domain knowledge injection
        design_type = "furniture"  # default
        if user_text:
            text_lower = user_text.lower()
            if any(w in text_lower for w in ("kitchen", "countertop", "stove", "sink")):
                design_type = "kitchen"
            elif any(w in text_lower for w in ("room", "living", "bedroom", "bathroom", "interior")):
                design_type = "room"
            elif any(w in text_lower for w in ("building", "house", "floor plan", "apartment")):
                design_type = "building"

        domain_knowledge = get_domain_knowledge(design_type)

        tasks = []
        for member_id in self.member_ids:
            model_info = self.models[member_id]
            system_prompt = COUNCIL_SYSTEM_PROMPT.format(
                role_description=model_info["role"],
                domain_knowledge=domain_knowledge,
            )

            if has_text and has_image:
                prompt = ROUND1_MIXED_PROMPT.format(user_text=user_text)
            elif has_image:
                additional = f"User's text: {user_text}" if user_text else ""
                prompt = ROUND1_IMAGE_PROMPT.format(additional_context=additional)
            else:
                prompt = ROUND1_TEXT_PROMPT.format(user_input=user_text or "")

            task = self._query_member(
                member_id=member_id,
                model_id=model_info["id"],
                prompt=prompt,
                system_prompt=system_prompt,
                round_number=1,
                image_data=image_data if (has_image and not all_images) else None,
                image_mime_type=image_mime_type,
                all_images=all_images if all_images else None,
            )
            tasks.append(task)

        # Run all three in parallel
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for resp in responses:
            if isinstance(resp, Exception):
                logger.error(f"Round 1 member error: {resp}")
                rnd.responses.append(MemberResponse(
                    member_id="unknown",
                    model_id="unknown",
                    round_number=1,
                    error=str(resp),
                ))
            else:
                rnd.responses.append(resp)

        rnd.mark_complete()

    async def _run_round2(self, state: CouncilState):
        """Round 2: Each member reviews the other two members' Round 1 responses."""
        from app.prompts.council_prompts import ROUND2_REVIEW_PROMPT

        rnd = state.add_round("cross_review")
        round1_responses = state.rounds[0].responses

        # Build a lookup of Round 1 responses by member
        r1_by_member = {}
        for resp in round1_responses:
            if not resp.error:
                r1_by_member[resp.member_id] = resp.response_text

        tasks = []
        for member_id in self.member_ids:
            if member_id not in r1_by_member:
                continue

            model_info = self.models[member_id]
            others = [m for m in self.member_ids if m != member_id and m in r1_by_member]
            if len(others) == 0:
                continue

            # If only 1 other member responded, adapt the prompt
            if len(others) == 1:
                prompt = ROUND2_REVIEW_PROMPT.format(
                    own_interpretation=r1_by_member[member_id],
                    other_member_1_name=self.models[others[0]]["name"],
                    other_interpretation_1=r1_by_member[others[0]],
                    other_member_2_name="(no response)",
                    other_interpretation_2="This member did not provide a response.",
                )
            else:
                prompt = ROUND2_REVIEW_PROMPT.format(
                    own_interpretation=r1_by_member[member_id],
                    other_member_1_name=self.models[others[0]]["name"],
                    other_interpretation_1=r1_by_member[others[0]],
                    other_member_2_name=self.models[others[1]]["name"],
                    other_interpretation_2=r1_by_member[others[1]],
                )

            task = self._query_member(
                member_id=member_id,
                model_id=model_info["id"],
                prompt=prompt,
                round_number=2,
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for resp in responses:
            if isinstance(resp, Exception):
                logger.error(f"Round 2 member error: {resp}")
            else:
                rnd.responses.append(resp)

        rnd.mark_complete()

    async def _run_round3(self, state: CouncilState):
        """Round 3: Each member produces their final converged interpretation."""
        from app.prompts.council_prompts import ROUND3_CONVERGENCE_PROMPT

        rnd = state.add_round("convergence")

        # Collect responses by member from rounds 1 and 2
        r1_by_member = {}
        for resp in state.rounds[0].responses:
            if not resp.error:
                r1_by_member[resp.member_id] = resp.response_text

        r2_by_member = {}
        for resp in state.rounds[1].responses:
            if not resp.error:
                r2_by_member[resp.member_id] = resp.response_text

        tasks = []
        for member_id in self.member_ids:
            if member_id not in r1_by_member:
                continue

            model_info = self.models[member_id]
            others = [m for m in self.member_ids if m != member_id]

            prompt = ROUND3_CONVERGENCE_PROMPT.format(
                own_round1=r1_by_member.get(member_id, "N/A"),
                own_round2=r2_by_member.get(member_id, "N/A"),
                other_member_1_name=self.models[others[0]]["name"],
                other_round2_1=r2_by_member.get(others[0], "N/A"),
                other_member_2_name=self.models[others[1]]["name"],
                other_round2_2=r2_by_member.get(others[1], "N/A"),
            )

            task = self._query_member(
                member_id=member_id,
                model_id=model_info["id"],
                prompt=prompt,
                round_number=3,
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for resp in responses:
            if isinstance(resp, Exception):
                logger.error(f"Round 3 member error: {resp}")
            else:
                rnd.responses.append(resp)

        rnd.mark_complete()

    def _check_consensus(self, state: CouncilState) -> bool:
        """
        Check if the council members reached consensus in Round 3.

        Simple heuristic: if all three produced valid JSON responses,
        we consider it a consensus (the Chairman will reconcile differences).
        More sophisticated checks can be added later.
        """
        from config import COUNCIL_CONSENSUS_THRESHOLD

        round3_responses = state.rounds[2].responses if len(state.rounds) >= 3 else []
        valid_count = sum(1 for r in round3_responses if not r.error and r.response_text)
        return valid_count >= COUNCIL_CONSENSUS_THRESHOLD

    async def _chairman_synthesis(
        self, state: CouncilState, project_id: str
    ) -> DesignSpecificationDocument:
        """Chairman synthesizes all final interpretations into a DSD."""
        from app.agents.chairman import Chairman

        chairman = Chairman(client=self.client)
        return await chairman.synthesize(state, project_id)

    # ------------------------------------------------------------------
    # Helper: Query a single council member
    # ------------------------------------------------------------------

    async def _query_member(
        self,
        member_id: str,
        model_id: str,
        prompt: str,
        round_number: int,
        system_prompt: str | None = None,
        image_data: str | None = None,
        image_mime_type: str = "image/png",
        all_images: list[dict] | None = None,
    ) -> MemberResponse:
        """
        Send a prompt to a single council member and return their response.
        Uses vision endpoint if image data is provided.
        Supports multiple images via all_images parameter.
        """
        try:
            if all_images and len(all_images) > 1:
                # Multiple images — use multi-image vision endpoint
                images_tuples = [
                    (img["data"], img["mime_type"]) for img in all_images
                ]
                response = await self.client.vision_completion_multi(
                    model=model_id,
                    prompt=prompt,
                    images=images_tuples,
                    system_prompt=system_prompt,
                    temperature=0.4,
                    max_tokens=4096,
                )
            elif all_images and len(all_images) == 1:
                response = await self.client.vision_completion(
                    model=model_id,
                    prompt=prompt,
                    image_data=all_images[0]["data"],
                    image_mime_type=all_images[0]["mime_type"],
                    system_prompt=system_prompt,
                    temperature=0.4,
                    max_tokens=4096,
                )
            elif image_data:
                response = await self.client.vision_completion(
                    model=model_id,
                    prompt=prompt,
                    image_data=image_data,
                    image_mime_type=image_mime_type,
                    system_prompt=system_prompt,
                    temperature=0.4,
                    max_tokens=4096,
                )
            else:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = await self.client.chat_completion(
                    model=model_id,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=4096,
                )

            text = self.client.extract_text(response)
            structured = self.client.extract_json(response)

            # Ensure structured_data is a dict (wrap lists)
            if isinstance(structured, list):
                structured = {"data": structured}

            return MemberResponse(
                member_id=member_id,
                model_id=model_id,
                round_number=round_number,
                response_text=text,
                structured_data=structured,
            )

        except Exception as e:
            logger.error(f"Error querying {member_id} ({model_id}): {e}")
            return MemberResponse(
                member_id=member_id,
                model_id=model_id,
                round_number=round_number,
                error=str(e),
            )
