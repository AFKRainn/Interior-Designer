"""
Project model — represents a complete design project.
Ties together the DSD, generated images, and metadata.
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
    DRAFT = "draft"                              # Just created, no DSD yet
    CONSULTING = "consulting"                    # Design consultant chatting with user
    COUNCIL_REVIEW = "council_review"            # Council is deliberating
    AWAITING_CONFIRMATION = "awaiting_confirmation"  # DSD ready, user must confirm
    GENERATING = "generating"                    # Technical drawings being generated
    DRAWINGS_REVIEW = "drawings_review"          # User reviewing technical drawings
    GENERATING_RENDER = "generating_render"      # Realistic render being generated
    QUALITY_REVIEW = "quality_review"            # Council reviewing images
    COMPLETE = "complete"                        # All images approved
    REFINING = "refining"                        # User requested changes


class ReviewScores(BaseModel):
    """Individual scoring criteria for a quality review."""
    dimensional_accuracy: float = 0.0
    material_color_accuracy: float = 0.0
    style_adherence: float = 0.0
    view_correctness: float = 0.0
    overall_quality: float = 0.0


class ReviewFeedback(BaseModel):
    """Structured feedback from a quality review."""
    strengths: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ReviewResult(BaseModel):
    """Result of a quality review for a single image."""
    image_id: str = ""
    reviewer_model: str = ""
    scores: ReviewScores = Field(default_factory=ReviewScores)
    average_score: float = 0.0
    approved: bool = False
    feedback: ReviewFeedback = Field(default_factory=ReviewFeedback)
    regeneration_instructions: str = ""
    reviewed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    error: Optional[str] = None


class GeneratedImage(BaseModel):
    """A single generated image with metadata."""
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    view_type: str
    view_label: str = ""  # Human-readable label, e.g. "Front Elevation — Wall A"
    view_spec_id: str = ""  # Links back to the ViewSpec.id
    file_path: str = ""
    dsd_version: int = 1
    quality_score: Optional[float] = None
    quality_feedback: Optional[str] = None
    review_result: Optional[ReviewResult] = None
    generation_prompt: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    approved: bool = False
    review_attempts: int = 0

    @property
    def display_label(self) -> str:
        """Human-friendly label — safe for old objects missing view_label."""
        lbl = getattr(self, "view_label", "") or ""
        return lbl if lbl else self.view_type.replace("_", " ").title()

    @property
    def spec_id(self) -> str:
        """ViewSpec id — safe for old objects missing view_spec_id."""
        return getattr(self, "view_spec_id", "") or ""


class InputData(BaseModel):
    """Raw user input for a project."""
    text_description: Optional[str] = None
    image_paths: list[str] = Field(default_factory=list)
    input_type: str = "text"  # "text", "image", "mixed"


class Project(BaseModel):
    """
    A complete design project.

    Tracks the full lifecycle from initial input through council
    deliberation, image generation, review, and refinement.
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    # Input
    input_data: InputData = Field(default_factory=InputData)

    # DSD (current version ID)
    dsd_id: Optional[str] = None

    # Generated images (current set)
    images: list[GeneratedImage] = Field(default_factory=list)

    # DSD version history (list of version numbers saved)
    dsd_versions: list[int] = Field(default_factory=list)

    def update_status(self, new_status: ProjectStatus):
        """Update project status and timestamp."""
        self.status = new_status
        self.updated_at = datetime.now().isoformat()

    def add_image(self, image: GeneratedImage):
        """Add a generated image to the project."""
        self.images.append(image)
        self.updated_at = datetime.now().isoformat()

    def get_images_by_view(self, view_type: str) -> list[GeneratedImage]:
        """Get all images of a specific view type."""
        return [img for img in self.images if img.view_type == view_type]

    def get_latest_images(self) -> list[GeneratedImage]:
        """Get the most recent image for each view (by view_spec_id or view_type)."""
        latest: dict[str, GeneratedImage] = {}
        for img in self.images:
            # Use view_spec_id as key if available, else fall back to view_type
            key = img.spec_id if img.spec_id else img.view_type
            if key not in latest or img.generated_at > latest[key].generated_at:
                latest[key] = img
        return list(latest.values())
