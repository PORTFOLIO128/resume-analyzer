"""
LLM Service — Groq API Client
Uses Groq's OpenAI-compatible API with httpx + HTTP/2.
Model: llama-3.3-70b-versatile (free tier, fast, high quality)
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class LLMServiceError(Exception):
    """Raised when the LLM API call fails."""


class GrokLLMService:
    """
    Groq API client (OpenAI-compatible).
    Renamed kept as GrokLLMService for import compatibility.
    """

    def __init__(self) -> None:
        self._api_url = settings.GROQ_API_URL
        self._api_key = settings.GROQ_API_KEY
        self._model = settings.GROQ_MODEL
        self._timeout = settings.REQUEST_TIMEOUT_SECONDS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a system + user prompt to Groq and return the raw text response.

        Args:
            system_prompt: Instructions / persona for the model.
            user_prompt:   The actual content to evaluate.

        Returns:
            Raw text from the model (expected to be JSON by the caller).

        Raises:
            LLMServiceError: On network, HTTP, or unexpected API errors.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 2048,
            "stream": False,
            "response_format": {"type": "json_object"},  # Groq supports JSON mode
        }

        logger.info("Calling Groq API [model=%s] …", self._model)

        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(
                    self._api_url,
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException:
            raise LLMServiceError(
                f"Groq API request timed out after {self._timeout}s. Please retry."
            )
        except httpx.ConnectError as exc:
            raise LLMServiceError(
                f"Cannot reach Groq API at {self._api_url}. "
                f"Check your internet connection. Detail: {exc}"
            )
        except httpx.RequestError as exc:
            raise LLMServiceError(f"Unexpected request error: {exc}") from exc

        self._raise_for_status(response)
        return self._extract_content(response.json())

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 200:
            return

        try:
            body = response.json()
            api_msg = (
                body.get("error", {}).get("message", "")
                or body.get("message", "")
            )
        except Exception:
            api_msg = response.text[:300]

        error_map = {
            401: "Invalid GROQ_API_KEY. Check your .env file.",
            403: "Access forbidden. Your Groq API key may lack permissions.",
            429: "Groq rate limit exceeded. Please wait and retry.",
            500: "Groq API internal server error. Retry later.",
            503: "Groq API is currently unavailable. Retry later.",
        }

        base = error_map.get(
            response.status_code,
            f"Groq API returned HTTP {response.status_code}",
        )
        message = f"{base} — {api_msg}" if api_msg else base
        logger.error("Groq API error [%d]: %s", response.status_code, message)
        raise LLMServiceError(message)

    @staticmethod
    def _extract_content(response_json: Dict[str, Any]) -> str:
        try:
            content = response_json["choices"][0]["message"]["content"]
            logger.info("Groq API response received — %d characters.", len(content))
            return content.strip()
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected Groq API response structure: %s", response_json)
            raise LLMServiceError(
                f"Could not parse Groq API response: {exc}"
            ) from exc
