"""
Council State — tracks the deliberation process.
Records each round, each member's response, and consensus status.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ConsensusStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    REACHED = "reached"
    FORCED = "forced"    # Chairman had to make final call
    FAILED = "failed"


class MemberResponse(BaseModel):
    """A single council member's response in a round."""
    member_id: str      # "claude", "gpt", "gemini"
    model_id: str       # Full OpenRouter model ID
    round_number: int
    response_text: str = ""
    structured_data: Optional[dict | list] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None


class DeliberationRound(BaseModel):
    """One round of council deliberation."""
    round_number: int
    round_type: str     # "independent_analysis", "cross_review", "convergence"
    responses: list[MemberResponse] = Field(default_factory=list)
    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def mark_complete(self):
        """Mark this round as complete."""
        self.completed_at = datetime.now().isoformat()


class CouncilState(BaseModel):
    """
    Full state of a council deliberation session.

    Tracks all rounds, responses, and whether consensus was reached.
    Used for both initial interpretation and quality review sessions.
    """
    session_id: str
    project_id: str
    purpose: str = ""   # "interpretation", "quality_review", "change_review"

    rounds: list[DeliberationRound] = Field(default_factory=list)
    current_round: int = 0
    max_rounds: int = 3

    consensus_status: ConsensusStatus = ConsensusStatus.PENDING
    consensus_summary: str = ""
    chairman_id: Optional[str] = None

    started_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def add_round(self, round_type: str) -> DeliberationRound:
        """Add a new deliberation round."""
        self.current_round += 1
        new_round = DeliberationRound(
            round_number=self.current_round,
            round_type=round_type,
        )
        self.rounds.append(new_round)
        self.consensus_status = ConsensusStatus.IN_PROGRESS
        return new_round

    def get_latest_responses(self) -> list[MemberResponse]:
        """Get responses from the most recent round."""
        if not self.rounds:
            return []
        return self.rounds[-1].responses

    def get_member_responses(self, member_id: str) -> list[MemberResponse]:
        """Get all responses from a specific member across all rounds."""
        responses = []
        for rnd in self.rounds:
            for resp in rnd.responses:
                if resp.member_id == member_id:
                    responses.append(resp)
        return responses

    def mark_complete(self, status: ConsensusStatus, summary: str = ""):
        """Mark the deliberation as complete."""
        self.consensus_status = status
        self.consensus_summary = summary
        self.completed_at = datetime.now().isoformat()
        # Also close the last round if still open
        if self.rounds and self.rounds[-1].completed_at is None:
            self.rounds[-1].mark_complete()
