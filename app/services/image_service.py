"""
Image Service — handles image encoding, decoding, resizing, and storage.
"""
import base64
import io
import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


class ImageService:
    """Handles all image operations for the Architecture Agent."""

    # Maximum dimensions for images sent to API (keeps costs reasonable)
    MAX_INPUT_SIZE = (2048, 2048)

    # Supported upload formats
    SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

    MIME_MAP = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }

    FORMAT_MAP = {
        "image/png": "PNG",
        "image/jpeg": "JPEG",
        "image/webp": "WEBP",
    }

    @staticmethod
    def load_and_encode(image_path: str | Path) -> tuple[str, str]:
        """
        Load an image from disk and return (base64_data, mime_type).
        Resizes if too large for the API.
        """
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        suffix = path.suffix.lower()
        if suffix not in ImageService.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported image format: {suffix}")

        mime_type = ImageService.MIME_MAP.get(suffix, "image/png")

        img = Image.open(path)
        img = ImageService._resize_if_needed(img)

        buffer = io.BytesIO()
        save_format = {
            ".png": "PNG",
            ".webp": "WEBP",
        }.get(suffix, "JPEG")
        img.save(buffer, format=save_format)
        b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return b64_data, mime_type

    @staticmethod
    def encode_uploaded_bytes(
        image_bytes: bytes, filename: str = "image.png"
    ) -> tuple[str, str]:
        """
        Encode raw uploaded bytes to base64.
        Also validates and resizes the image.

        Returns (base64_data, mime_type).
        """
        suffix = Path(filename).suffix.lower() if filename else ".png"
        mime_type = ImageService.MIME_MAP.get(suffix, "image/png")

        img = Image.open(io.BytesIO(image_bytes))
        img = ImageService._resize_if_needed(img)

        buffer = io.BytesIO()
        save_format = {
            ".png": "PNG",
            ".webp": "WEBP",
        }.get(suffix, "JPEG")
        img.save(buffer, format=save_format)
        b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")

        return b64_data, mime_type

    @staticmethod
    def decode_and_save(
        b64_data: str,
        save_path: str | Path,
        mime_type: str = "image/png",
    ) -> Path:
        """
        Decode base64 image data and save to disk.

        Returns:
            Path to the saved file.
        """
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        image_bytes = base64.b64decode(b64_data)
        img = Image.open(io.BytesIO(image_bytes))

        # Determine save format
        save_format = ImageService.FORMAT_MAP.get(mime_type, "PNG")

        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            save_format = "JPEG"
        elif suffix == ".webp":
            save_format = "WEBP"
        elif suffix == ".png":
            save_format = "PNG"

        img.save(path, format=save_format)
        logger.info(f"Saved image to {path}")
        return path

    @staticmethod
    def bytes_to_base64(image_bytes: bytes) -> str:
        """Convert raw image bytes to base64 string."""
        return base64.b64encode(image_bytes).decode("utf-8")

    @staticmethod
    def base64_to_bytes(b64_data: str) -> bytes:
        """Convert base64 string to raw bytes."""
        return base64.b64decode(b64_data)

    @staticmethod
    def get_image_info(image_path: str | Path) -> dict:
        """Get basic image information (dimensions, format, size)."""
        path = Path(image_path)
        img = Image.open(path)
        return {
            "width": img.width,
            "height": img.height,
            "format": img.format,
            "mode": img.mode,
            "file_size_kb": round(path.stat().st_size / 1024, 1),
        }

    @staticmethod
    def _resize_if_needed(img: Image.Image) -> Image.Image:
        """Resize image if it exceeds maximum input dimensions."""
        max_w, max_h = ImageService.MAX_INPUT_SIZE
        if img.width > max_w or img.height > max_h:
            img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
            logger.info(f"Resized image to {img.width}x{img.height}")
        return img

    @staticmethod
    def create_thumbnail(
        image_path: str | Path,
        max_size: tuple[int, int] = (300, 300),
    ) -> bytes:
        """
        Create a thumbnail of an image.
        Returns PNG bytes of the thumbnail.
        """
        img = Image.open(image_path)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
