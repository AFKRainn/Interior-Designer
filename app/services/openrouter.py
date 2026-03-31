"""
OpenRouter API Client

Handles all API calls to OpenRouter for:
- Text chat completions (council deliberation)
- Vision / multimodal (image analysis by council)
- Image generation (Nano Banana)

All models are accessed through the same OpenAI-compatible endpoint.
Includes cost tracking, caching, and robust error handling.
"""
import asyncio
import base64
import concurrent.futures
import hashlib
import json
import logging
import random
import re
import time
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cost Tracker (singleton)
# ---------------------------------------------------------------------------
class CostTracker:
    """Tracks API usage costs across all OpenRouter calls."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._calls = []
            cls._instance._total_cost = 0.0
            cls._instance._total_tokens = 0
        return cls._instance

    def record(self, model: str, usage: dict, generation_time: float = 0):
        """Record a single API call's usage."""
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        cost = usage.get("cost", 0.0)

        # OpenRouter sometimes returns cost as string
        if isinstance(cost, str):
            try:
                cost = float(cost)
            except (ValueError, TypeError):
                cost = 0.0

        self._calls.append({
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cost": cost,
            "time": generation_time,
            "timestamp": time.time(),
        })
        self._total_cost += cost
        self._total_tokens += total_tokens

    @property
    def total_cost(self) -> float:
        return self._total_cost

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def call_count(self) -> int:
        return len(self._calls)

    def get_summary(self) -> dict:
        """Get a summary of all API usage."""
        by_model: dict[str, dict] = {}
        for call in self._calls:
            model = call["model"]
            if model not in by_model:
                by_model[model] = {
                    "calls": 0, "tokens": 0, "cost": 0.0, "time": 0.0
                }
            by_model[model]["calls"] += 1
            by_model[model]["tokens"] += call["total_tokens"]
            by_model[model]["cost"] += call["cost"]
            by_model[model]["time"] += call["time"]

        return {
            "total_calls": self.call_count,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 6),
            "by_model": by_model,
        }

    def reset(self):
        """Reset all tracked usage."""
        self._calls.clear()
        self._total_cost = 0.0
        self._total_tokens = 0


# ---------------------------------------------------------------------------
# Simple Response Cache
# ---------------------------------------------------------------------------
class ResponseCache:
    """In-memory LRU cache for API responses to avoid duplicate calls."""

    def __init__(self, max_size: int = 50):
        self._cache: dict[str, tuple[float, dict]] = {}
        self._max_size = max_size
        self._ttl = 3600  # 1 hour TTL

    @staticmethod
    def _make_key(payload: dict) -> str:
        """Create a cache key from the request payload."""
        # Only cache based on model + messages + temperature
        key_parts = {
            "model": payload.get("model", ""),
            "messages": json.dumps(payload.get("messages", []), sort_keys=True),
            "temperature": payload.get("temperature", 0.7),
        }
        key_str = json.dumps(key_parts, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]

    def get(self, payload: dict) -> dict | None:
        """Get cached response if available and not expired."""
        key = self._make_key(payload)
        if key in self._cache:
            ts, response = self._cache[key]
            if time.time() - ts < self._ttl:
                logger.info(f"Cache hit for {payload.get('model', '?')}")
                return response
            else:
                del self._cache[key]
        return None

    def put(self, payload: dict, response: dict):
        """Cache a response."""
        # Don't cache image generation (non-deterministic)
        model = payload.get("model", "")
        if "image" in model.lower():
            return

        # Only cache if temperature is low (deterministic-ish)
        temp = payload.get("temperature", 0.7)
        if temp > 0.5:
            return

        key = self._make_key(payload)

        # Evict oldest if full
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache, key=lambda k: self._cache[k][0])
            del self._cache[oldest_key]

        self._cache[key] = (time.time(), response)

    def clear(self):
        self._cache.clear()


class OpenRouterClient:
    """Async client for the OpenRouter API with cost tracking and caching."""

    def __init__(self, api_key: str | None = None):
        from config import (
            OPENROUTER_API_KEY,
            OPENROUTER_CHAT_URL,
            REQUEST_TIMEOUT,
            MAX_RETRIES,
            RETRY_DELAY,
        )

        self.api_key = api_key or OPENROUTER_API_KEY
        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not set. "
                "Set it in your .env file or pass it directly."
            )

        self.chat_url = OPENROUTER_CHAT_URL
        self.timeout = REQUEST_TIMEOUT
        self.max_retries = MAX_RETRIES
        self.retry_delay = RETRY_DELAY

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "Architecture Agent",
        }

        # Shared singletons
        self.cost_tracker = CostTracker()
        self.cache = ResponseCache()

    # ------------------------------------------------------------------
    # Public Methods
    # ------------------------------------------------------------------

    async def chat_completion(
        self,
        model: str,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: dict | None = None,
    ) -> dict:
        """
        Send a text chat completion request.

        Args:
            model: OpenRouter model ID (e.g. "anthropic/claude-sonnet-4")
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens in response
            response_format: Optional (e.g. {"type": "json_object"})

        Returns:
            Full API response dict
        """
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format

        return await self._make_request(payload)

    async def vision_completion(
        self,
        model: str,
        prompt: str,
        image_data: str | bytes,
        image_mime_type: str = "image/png",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str | None = None,
    ) -> dict:
        """
        Send a vision (image + text) request.

        Args:
            model: OpenRouter model ID (must support vision)
            prompt: Text prompt to accompany the image
            image_data: Base64-encoded image string OR raw bytes
            image_mime_type: MIME type of the image
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            system_prompt: Optional system message

        Returns:
            Full API response dict
        """
        # Ensure base64 string
        if isinstance(image_data, bytes):
            image_b64 = base64.b64encode(image_data).decode("utf-8")
        else:
            image_b64 = image_data

        data_url = f"data:{image_mime_type};base64,{image_b64}"

        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                },
            ],
        })

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        return await self._make_request(payload)

    async def vision_completion_multi(
        self,
        model: str,
        prompt: str,
        images: list[tuple[str | bytes, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        system_prompt: str | None = None,
    ) -> dict:
        """
        Send a vision request with MULTIPLE images.

        Args:
            model: OpenRouter model ID
            prompt: Text prompt
            images: List of (image_data, mime_type) tuples
            temperature: Sampling temperature
            max_tokens: Max tokens
            system_prompt: Optional system message

        Returns:
            Full API response dict
        """
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        content_parts: list[dict] = [{"type": "text", "text": prompt}]

        for img_data, mime_type in images:
            if isinstance(img_data, bytes):
                b64 = base64.b64encode(img_data).decode("utf-8")
            else:
                b64 = img_data
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64}"},
            })

        messages.append({"role": "user", "content": content_parts})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        return await self._make_request(payload)

    async def generate_image(
        self,
        prompt: str,
        model: str | None = None,
        reference_image: str | bytes | None = None,
        reference_mime_type: str = "image/png",
    ) -> dict:
        """
        Generate an image using the configured image model.

        Args:
            prompt: Detailed prompt for image generation
            model: Model ID (defaults to IMAGE_GEN_MODEL from config)
            reference_image: Optional reference image for editing
            reference_mime_type: MIME type of reference image

        Returns:
            Dict with keys:
              'text'   — any text in the response
              'images' — list of dicts with 'data' (base64) and 'mime_type'
              'raw_response' — the full API response
        """
        from config import IMAGE_GEN_MODEL

        model = model or IMAGE_GEN_MODEL["id"]

        content_parts: list[dict] = [{"type": "text", "text": prompt}]

        if reference_image is not None:
            if isinstance(reference_image, bytes):
                ref_b64 = base64.b64encode(reference_image).decode("utf-8")
            else:
                ref_b64 = reference_image
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{reference_mime_type};base64,{ref_b64}"
                },
            })

        _MODALITIES_MODELS = ("black-forest-labs/",)
        is_modalities_model = any(model.startswith(p) for p in _MODALITIES_MODELS)

        if is_modalities_model and len(content_parts) == 1:
            messages = [{"role": "user", "content": content_parts[0]["text"]}]
        else:
            messages = [{"role": "user", "content": content_parts}]

        payload = {
            "model": model,
            "messages": messages,
        }

        if is_modalities_model:
            payload["modalities"] = ["image"]
        else:
            payload["max_tokens"] = 8192

        response = await self._make_request(payload)
        return self._parse_image_response(response)

    # ------------------------------------------------------------------
    # Response Parsing Helpers
    # ------------------------------------------------------------------

    def extract_text(self, response: dict) -> str:
        """Extract text content from a chat completion response."""
        try:
            content = response["choices"][0]["message"]["content"]
            if content is None:
                return ""
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                texts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        texts.append(part.get("text", ""))
                return " ".join(texts)
            return str(content)
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract text: {e}")
            return ""

    def extract_json(self, response: dict) -> dict | list | None:
        """Extract and parse JSON from a chat completion response."""
        text = self.extract_text(response)
        if not text:
            return None

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # JSON inside markdown code blocks
        json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Find first JSON object or array in raw text
        for start_char, end_char in [("{", "}"), ("[", "]")]:
            start_idx = text.find(start_char)
            if start_idx == -1:
                continue
            depth = 0
            for i in range(start_idx, len(text)):
                if text[i] == start_char:
                    depth += 1
                elif text[i] == end_char:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start_idx : i + 1])
                        except json.JSONDecodeError:
                            break

        logger.warning(f"Could not extract JSON from response: {text[:200]}...")
        return None

    def _parse_image_response(self, response: dict) -> dict:
        """
        Parse API response to extract text and image data.
        Handles multiple response formats:
          1. message.images[] — Gemini / Nano Banana returns images as a
             separate list on the message object (each item is a dict with
             ``{"type": "image_url", "image_url": {"url": "data:..."}}``)
          2. Raw base64 string in content
          3. Multipart content list with image_url or inline_data parts
          4. Data URLs in string content
        """
        result: dict = {"text": "", "images": [], "raw_response": response}

        try:
            choices = response.get("choices", [])
            if not choices:
                logger.warning("No choices in image generation response")
                return result

            message = choices[0].get("message", {})
            content = message.get("content", "")

            # ---------------------------------------------------------
            # 1. Check message-level 'images' list (Nano Banana format)
            # ---------------------------------------------------------
            msg_images = message.get("images") or []
            if msg_images:
                for img_item in msg_images:
                    self._extract_image_item(img_item, result)
                if result["images"]:
                    logger.info(
                        f"Extracted {len(result['images'])} image(s) "
                        f"from message.images"
                    )
                    # Also capture any text content
                    if isinstance(content, str) and content:
                        result["text"] = content
                    return result

            # ---------------------------------------------------------
            # 2. String content — could be text OR raw base64 image data
            # ---------------------------------------------------------
            if isinstance(content, str):
                stripped = content.strip()

                # Detect raw base64 image data returned as plain string
                if stripped and self._looks_like_base64_image(stripped):
                    mime_type = self._guess_image_mime(stripped)
                    result["images"].append({
                        "data": stripped,
                        "mime_type": mime_type,
                    })
                    logger.info(
                        f"Detected raw base64 image in content "
                        f"({mime_type}, {len(stripped)} chars)"
                    )
                    return result

                # Check for data URL in string content
                if stripped.startswith("data:image/"):
                    try:
                        header, b64_data = stripped.split(",", 1)
                        mime = header.split(":")[1].split(";")[0]
                        result["images"].append({
                            "data": b64_data,
                            "mime_type": mime,
                        })
                        return result
                    except (ValueError, IndexError):
                        pass

                # Otherwise treat as plain text
                result["text"] = content
                return result

            # ---------------------------------------------------------
            # 3. Multipart content list
            # ---------------------------------------------------------
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue

                    part_type = part.get("type", "")

                    # Text part
                    if part_type == "text":
                        result["text"] += part.get("text", "")

                    # Image URL part (base64 data URL)
                    elif part_type == "image_url":
                        self._extract_image_url_part(part, result)

                    # Inline data part (Gemini native format)
                    elif part_type == "inline_data":
                        result["images"].append({
                            "data": part.get("data", ""),
                            "mime_type": part.get("mime_type", "image/png"),
                        })

        except Exception as e:
            logger.error(f"Error parsing image response: {e}")
            result["error"] = str(e)

        return result

    # ------------------------------------------------------------------
    # Image Extraction Sub-helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_image_url_part(part: dict, result: dict):
        """Extract image data from a ``{"type": "image_url", ...}`` part."""
        image_url = part.get("image_url", {})
        if isinstance(image_url, dict):
            url = image_url.get("url", "")
        else:
            url = str(image_url)

        if url.startswith("data:"):
            try:
                header, b64_data = url.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
                result["images"].append({
                    "data": b64_data,
                    "mime_type": mime,
                })
            except (ValueError, IndexError):
                pass
        elif url:
            result["images"].append({
                "url": url,
                "mime_type": "image/png",
            })

    @classmethod
    def _extract_image_item(cls, img_item, result: dict):
        """
        Extract image from an item in ``message.images[]``.

        Handles several shapes:
        - dict: ``{"type": "image_url", "image_url": {"url": "data:..."}}``
        - dict: ``{"data": "<b64>", "mime_type": "..."}``
        - str:  raw base64 or data-URL
        """
        if isinstance(img_item, dict):
            item_type = img_item.get("type", "")

            if item_type == "image_url" or "image_url" in img_item:
                cls._extract_image_url_part(img_item, result)

            elif "data" in img_item:
                result["images"].append({
                    "data": img_item["data"],
                    "mime_type": img_item.get("mime_type", "image/png"),
                })

            elif "url" in img_item:
                url = img_item["url"]
                if url.startswith("data:"):
                    try:
                        header, b64_data = url.split(",", 1)
                        mime = header.split(":")[1].split(";")[0]
                        result["images"].append({
                            "data": b64_data,
                            "mime_type": mime,
                        })
                    except (ValueError, IndexError):
                        pass
                else:
                    result["images"].append({
                        "url": url,
                        "mime_type": "image/png",
                    })

        elif isinstance(img_item, str):
            if img_item.startswith("data:"):
                try:
                    header, b64_data = img_item.split(",", 1)
                    mime = header.split(":")[1].split(";")[0]
                    result["images"].append({
                        "data": b64_data,
                        "mime_type": mime,
                    })
                except (ValueError, IndexError):
                    pass
            elif len(img_item) > 100:
                result["images"].append({
                    "data": img_item,
                    "mime_type": cls._guess_image_mime(img_item),
                })

    # ------------------------------------------------------------------
    # Image Detection Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _looks_like_base64_image(s: str) -> bool:
        """
        Heuristic: does this string look like base64-encoded image data?

        Checks for known magic-byte prefixes and validates that the string
        contains only base64-safe characters.
        """
        if len(s) < 100:
            return False

        # Known base64 prefixes for common image formats
        IMAGE_PREFIXES = (
            "/9j/",      # JPEG
            "iVBOR",     # PNG
            "UklGR",     # WebP (RIFF)
            "R0lGOD",    # GIF
            "AAAA",      # Sometimes PNG/other
        )

        if not s.startswith(IMAGE_PREFIXES):
            return False

        # Quick validation: check first 200 chars are valid base64
        import re
        sample = s[:200]
        return bool(re.match(r'^[A-Za-z0-9+/=\s]+$', sample))

    @staticmethod
    def _guess_image_mime(b64_data: str) -> str:
        """Guess the MIME type from the first few base64 characters."""
        if b64_data.startswith("/9j/"):
            return "image/jpeg"
        elif b64_data.startswith("iVBOR"):
            return "image/png"
        elif b64_data.startswith("UklGR"):
            return "image/webp"
        elif b64_data.startswith("R0lGOD"):
            return "image/gif"
        return "image/png"  # Default fallback

    # ------------------------------------------------------------------
    # Internal HTTP Logic
    # ------------------------------------------------------------------

    async def _make_request(self, payload: dict) -> dict:
        """
        Make an HTTP POST to OpenRouter with retry logic.

        Handles rate-limiting (429), server errors (5xx), timeouts,
        and connection errors with exponential backoff + jitter.
        Includes cost tracking and response caching.
        """
        # Check cache first
        cached = self.cache.get(payload)
        if cached is not None:
            return cached

        last_error: Exception | None = None
        model = payload.get("model", "unknown")
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.chat_url,
                        headers=self.headers,
                        json=payload,
                    )

                    if response.status_code == 200:
                        result = response.json()
                        elapsed = time.time() - start_time

                        # Track cost
                        usage = result.get("usage", {})
                        self.cost_tracker.record(model, usage, elapsed)

                        # Cache response
                        self.cache.put(payload, result)

                        return result

                    # Rate limit — use Retry-After header with jitter
                    if response.status_code == 429:
                        retry_after = int(
                            response.headers.get(
                                "retry-after",
                                self.retry_delay * (attempt + 1),
                            )
                        )
                        # Add jitter (0-25% extra) to avoid thundering herd
                        jitter = retry_after * random.uniform(0, 0.25)
                        wait = retry_after + jitter
                        logger.warning(
                            f"Rate limited. Waiting {wait:.1f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Server error — exponential backoff with jitter
                    if response.status_code >= 500:
                        backoff = self.retry_delay * (2 ** attempt)
                        jitter = backoff * random.uniform(0, 0.25)
                        wait = backoff + jitter
                        logger.warning(
                            f"Server error {response.status_code}. "
                            f"Retrying in {wait:.1f}s "
                            f"(attempt {attempt + 1}/{self.max_retries})"
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Client error — don't retry
                    error_body = response.text[:500]
                    logger.error(
                        f"API error {response.status_code}: {error_body}"
                    )
                    raise Exception(
                        f"OpenRouter API error {response.status_code}: "
                        f"{error_body}"
                    )

            except httpx.TimeoutException as e:
                last_error = e
                backoff = self.retry_delay * (2 ** attempt)
                logger.warning(
                    f"Request timeout — retrying in {backoff}s "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                await asyncio.sleep(backoff)

            except httpx.ConnectError as e:
                last_error = e
                backoff = self.retry_delay * (2 ** attempt)
                logger.warning(
                    f"Connection error — retrying in {backoff}s "
                    f"(attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                await asyncio.sleep(backoff)

            except Exception as e:
                if "API error" in str(e):
                    raise  # Re-raise client errors
                last_error = e
                logger.error(f"Unexpected error: {e}")
                await asyncio.sleep(self.retry_delay)

        raise Exception(
            f"Failed after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )


# --------------------------------------------------------------------------
# Synchronous wrapper for Streamlit (which doesn't natively support async)
# --------------------------------------------------------------------------

def run_async(coro):
    """
    Run an async coroutine from synchronous Streamlit code.

    Handles the case where an event loop may or may not already exist.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
