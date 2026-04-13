"""LLM client wrapper for Ollama with retry logic."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import ollama

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
BACKOFF_FACTOR = 2.0


class LLMError(Exception):
    """Raised when LLM call fails after all retries."""


@dataclass
class LLMResponse:
    """Parsed LLM response."""

    content: str
    model: str
    total_duration_ms: float


class LLMClient:
    """Wrapper around Ollama API with retry + backoff."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3"):
        self._model = model
        self._client = ollama.Client(host=base_url)

    def generate(self, prompt: str, system: str = "") -> LLMResponse:
        """Generate text from prompt with retry logic."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.chat(model=self._model, messages=messages)
                return LLMResponse(
                    content=response["message"]["content"],
                    model=response.get("model", self._model),
                    total_duration_ms=response.get("total_duration", 0) / 1e6,
                )
            except Exception as e:
                last_error = e
                delay = BASE_DELAY * (BACKOFF_FACTOR ** attempt)
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt + 1, MAX_RETRIES, e, delay,
                )
                time.sleep(delay)

        raise LLMError(f"LLM call failed after {MAX_RETRIES} retries: {last_error}")

    def is_available(self) -> bool:
        """Check if Ollama is reachable and model is loaded."""
        try:
            self._client.list()
            return True
        except Exception:
            return False
