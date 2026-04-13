"""Tests for core.llm_client — Ollama wrapper with retry logic.

The ollama package may not be installed in the test environment, so we
inject a mock module into sys.modules before importing the module under test.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ── Ensure the `ollama` module is available for import ──────────────
# If the real ollama package is not installed, inject a stub into
# sys.modules so that `core.llm_client` can be imported.
if "ollama" not in sys.modules:
    _mock_ollama = ModuleType("ollama")
    _mock_ollama.Client = MagicMock  # type: ignore[attr-defined]
    sys.modules["ollama"] = _mock_ollama

from core.llm_client import BASE_DELAY, BACKOFF_FACTOR, MAX_RETRIES, LLMClient, LLMError, LLMResponse


@pytest.fixture
def mock_ollama_client():
    """Patch ollama.Client so no real server is required."""
    with patch("core.llm_client.ollama.Client") as MockClientClass:
        mock_instance = MagicMock()
        MockClientClass.return_value = mock_instance
        yield mock_instance


def _chat_response(content: str = "Hello!", model: str = "llama3", duration_ns: int = 500_000_000):
    """Build a dict matching the shape of ollama's chat() return value."""
    return {
        "message": {"content": content},
        "model": model,
        "total_duration": duration_ns,
    }


# ── LLMResponse dataclass ──────────────────────────────────────────


class TestLLMResponse:
    """Tests for the LLMResponse dataclass."""

    def test_fields(self):
        r = LLMResponse(content="hi", model="llama3", total_duration_ms=42.0)
        assert r.content == "hi"
        assert r.model == "llama3"
        assert r.total_duration_ms == 42.0


# ── LLMClient.generate() ───────────────────────────────────────────


class TestGenerate:
    """Tests for LLMClient.generate()."""

    def test_successful_generation(self, mock_ollama_client):
        """A successful call returns an LLMResponse with correct fields."""
        mock_ollama_client.chat.return_value = _chat_response(
            content="The answer is 42.",
            model="llama3",
            duration_ns=1_000_000_000,
        )
        client = LLMClient()
        result = client.generate("What is the answer?")

        assert isinstance(result, LLMResponse)
        assert result.content == "The answer is 42."
        assert result.model == "llama3"
        assert result.total_duration_ms == 1000.0  # 1e9 ns / 1e6 = 1000 ms

    def test_messages_without_system(self, mock_ollama_client):
        """When no system message is given, only the user message is sent."""
        mock_ollama_client.chat.return_value = _chat_response()
        client = LLMClient()
        client.generate("Hello")

        _, kwargs = mock_ollama_client.chat.call_args
        messages = kwargs["messages"]

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_messages_with_system(self, mock_ollama_client):
        """When a system message is provided, it is prepended to messages."""
        mock_ollama_client.chat.return_value = _chat_response()
        client = LLMClient()
        client.generate("Hello", system="You are a helpful assistant.")

        _, kwargs = mock_ollama_client.chat.call_args
        messages = kwargs["messages"]

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a helpful assistant."
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Hello"

    def test_model_passed_to_chat(self, mock_ollama_client):
        """The configured model name is sent to ollama."""
        mock_ollama_client.chat.return_value = _chat_response()
        client = LLMClient(model="mistral")
        client.generate("Hi")

        _, kwargs = mock_ollama_client.chat.call_args
        assert kwargs["model"] == "mistral"

    @patch("core.llm_client.time.sleep")
    def test_retries_on_failure_then_succeeds(self, mock_sleep, mock_ollama_client):
        """Two failures followed by success returns the successful response."""
        mock_ollama_client.chat.side_effect = [
            ConnectionError("Connection refused"),
            TimeoutError("Timed out"),
            _chat_response(content="Got it!"),
        ]
        client = LLMClient()
        result = client.generate("Retry test")

        assert result.content == "Got it!"
        assert mock_ollama_client.chat.call_count == 3
        # Should have slept twice (after attempt 0 and attempt 1)
        assert mock_sleep.call_count == 2

    @patch("core.llm_client.time.sleep")
    def test_backoff_delays(self, mock_sleep, mock_ollama_client):
        """Retry delays follow exponential backoff."""
        mock_ollama_client.chat.side_effect = [
            ConnectionError("fail"),
            ConnectionError("fail"),
            _chat_response(),
        ]
        client = LLMClient()
        client.generate("test")

        expected_delays = [
            BASE_DELAY * (BACKOFF_FACTOR ** 0),  # 1.0
            BASE_DELAY * (BACKOFF_FACTOR ** 1),  # 2.0
        ]
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == expected_delays

    @patch("core.llm_client.time.sleep")
    def test_raises_llm_error_after_max_retries(self, mock_sleep, mock_ollama_client):
        """After MAX_RETRIES failures, LLMError is raised."""
        mock_ollama_client.chat.side_effect = ConnectionError("Connection refused")
        client = LLMClient()

        with pytest.raises(LLMError, match=f"after {MAX_RETRIES} retries"):
            client.generate("This will fail")

        assert mock_ollama_client.chat.call_count == MAX_RETRIES
        assert mock_sleep.call_count == MAX_RETRIES

    @patch("core.llm_client.time.sleep")
    def test_llm_error_contains_last_exception(self, mock_sleep, mock_ollama_client):
        """The LLMError message includes the last underlying exception."""
        mock_ollama_client.chat.side_effect = ValueError("bad model")
        client = LLMClient()

        with pytest.raises(LLMError, match="bad model"):
            client.generate("fail")

    def test_missing_optional_response_fields(self, mock_ollama_client):
        """Handles missing model and total_duration in the response gracefully."""
        mock_ollama_client.chat.return_value = {
            "message": {"content": "hi"},
            # no "model" or "total_duration"
        }
        client = LLMClient(model="llama3")
        result = client.generate("test")
        assert result.content == "hi"
        assert result.model == "llama3"  # falls back to configured model
        assert result.total_duration_ms == 0.0


# ── LLMClient.is_available() ───────────────────────────────────────


class TestIsAvailable:
    """Tests for LLMClient.is_available()."""

    def test_returns_true_when_reachable(self, mock_ollama_client):
        """is_available() returns True when ollama.list() succeeds."""
        mock_ollama_client.list.return_value = {"models": []}
        client = LLMClient()
        assert client.is_available() is True

    def test_returns_false_when_unreachable(self, mock_ollama_client):
        """is_available() returns False when ollama.list() raises."""
        mock_ollama_client.list.side_effect = ConnectionError("unreachable")
        client = LLMClient()
        assert client.is_available() is False

    def test_returns_false_on_any_exception(self, mock_ollama_client):
        """is_available() returns False on any exception type."""
        mock_ollama_client.list.side_effect = RuntimeError("unexpected")
        client = LLMClient()
        assert client.is_available() is False


# ── Constants ───────────────────────────────────────────────────────


class TestConstants:
    """Verify retry-related constants are set to expected values."""

    def test_max_retries(self):
        assert MAX_RETRIES == 3

    def test_base_delay(self):
        assert BASE_DELAY == 1.0

    def test_backoff_factor(self):
        assert BACKOFF_FACTOR == 2.0
