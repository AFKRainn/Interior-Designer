"""
Project Store — handles saving and loading projects to/from disk.
Uses JSON file storage (lightweight, no database needed).
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class ProjectStore:
    """Manages project persistence using JSON files."""

    def __init__(self, projects_dir: Path | None = None):
        from config import PROJECTS_DIR
        self.projects_dir = projects_dir or PROJECTS_DIR
        self.projects_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    def _project_dir(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    def _project_file(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "project.json"

    def _dsd_file(self, project_id: str, version: int = 0) -> Path:
        if version == 0:
            return self._project_dir(project_id) / "dsd_current.json"
        return self._project_dir(project_id) / f"dsd_v{version}.json"

    def _images_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "images"

    def _uploads_dir(self, project_id: str) -> Path:
        return self._project_dir(project_id) / "uploads"

    # ------------------------------------------------------------------
    # Project CRUD
    # ------------------------------------------------------------------

    def save_project(self, project) -> Path:
        """Save a project to disk."""
        project_dir = self._project_dir(project.id)
        project_dir.mkdir(parents=True, exist_ok=True)
        self._images_dir(project.id).mkdir(exist_ok=True)
        self._uploads_dir(project.id).mkdir(exist_ok=True)

        project.updated_at = datetime.now().isoformat()

        project_file = self._project_file(project.id)
        project_file.write_text(
            project.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info(f"Saved project {project.id} to {project_file}")
        return project_file

    def load_project(self, project_id: str):
        """Load a project from disk. Returns None if not found."""
        from app.models.project import Project

        project_file = self._project_file(project_id)
        if not project_file.exists():
            logger.warning(f"Project file not found: {project_file}")
            return None

        data = json.loads(project_file.read_text(encoding="utf-8"))
        return Project.model_validate(data)

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and all its files."""
        project_dir = self._project_dir(project_id)
        if project_dir.exists():
            shutil.rmtree(project_dir)
            logger.info(f"Deleted project {project_id}")
            return True
        return False

    def list_projects(self) -> list[dict]:
        """List all projects with basic metadata, newest first."""
        projects = []
        if not self.projects_dir.exists():
            return projects

        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue
            project_file = project_dir / "project.json"
            if project_file.exists():
                try:
                    data = json.loads(
                        project_file.read_text(encoding="utf-8")
                    )
                    projects.append({
                        "id": data.get("id", project_dir.name),
                        "name": data.get("name", "Untitled"),
                        "status": data.get("status", "unknown"),
                        "created_at": data.get("created_at", ""),
                        "updated_at": data.get("updated_at", ""),
                    })
                except Exception as e:
                    logger.error(
                        f"Error reading project {project_dir.name}: {e}"
                    )

        projects.sort(key=lambda p: p.get("updated_at", ""), reverse=True)
        return projects

    # ------------------------------------------------------------------
    # DSD CRUD
    # ------------------------------------------------------------------

    def save_dsd(self, project_id: str, dsd) -> Path:
        """Save a DSD to disk (both current and versioned copy)."""
        project_dir = self._project_dir(project_id)
        project_dir.mkdir(parents=True, exist_ok=True)

        dsd_json = dsd.model_dump_json(indent=2)

        # Save current version
        current_file = self._dsd_file(project_id, 0)
        current_file.write_text(dsd_json, encoding="utf-8")

        # Save versioned copy
        versioned_file = self._dsd_file(project_id, dsd.version)
        versioned_file.write_text(dsd_json, encoding="utf-8")

        logger.info(f"Saved DSD v{dsd.version} for project {project_id}")
        return current_file

    def load_dsd(self, project_id: str, version: int = 0):
        """Load a DSD from disk. Version 0 = current."""
        from app.models.dsd import DesignSpecificationDocument

        dsd_file = self._dsd_file(project_id, version)
        if not dsd_file.exists():
            logger.warning(f"DSD file not found: {dsd_file}")
            return None

        data = json.loads(dsd_file.read_text(encoding="utf-8"))
        return DesignSpecificationDocument.model_validate(data)

    def list_dsd_versions(self, project_id: str) -> list[int]:
        """List all saved DSD version numbers for a project."""
        project_dir = self._project_dir(project_id)
        if not project_dir.exists():
            return []
        versions = []
        for f in project_dir.glob("dsd_v*.json"):
            try:
                v = int(f.stem.replace("dsd_v", ""))
                versions.append(v)
            except ValueError:
                pass
        return sorted(versions)

    # ------------------------------------------------------------------
    # Image Storage
    # ------------------------------------------------------------------

    def save_uploaded_image(
        self, project_id: str, image_bytes: bytes, filename: str
    ) -> Path:
        """Save an uploaded image to the project's uploads directory."""
        uploads_dir = self._uploads_dir(project_id)
        uploads_dir.mkdir(parents=True, exist_ok=True)

        save_path = uploads_dir / filename
        save_path.write_bytes(image_bytes)
        logger.info(f"Saved uploaded image to {save_path}")
        return save_path

    def save_generated_image(
        self, project_id: str, image_bytes: bytes, filename: str
    ) -> Path:
        """Save a generated image to the project's images directory."""
        images_dir = self._images_dir(project_id)
        images_dir.mkdir(parents=True, exist_ok=True)

        save_path = images_dir / filename
        save_path.write_bytes(image_bytes)
        logger.info(f"Saved generated image to {save_path}")
        return save_path

    def get_image_path(self, project_id: str, filename: str) -> Path:
        """Get the full path for a generated image."""
        return self._images_dir(project_id) / filename

    def get_upload_path(self, project_id: str, filename: str) -> Path:
        """Get the full path for an uploaded image."""
        return self._uploads_dir(project_id) / filename
