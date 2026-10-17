"""Tests for the LLM advisory provider.

All external calls are mocked — no real API keys are used.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.app.models.schemas import (
    CheckResult,
    ReportStatus,
    Severity,
    ValidationReport,
)
from backend.app.services.llm import (
    LLMConfig,
    LLMNotConfiguredError,
    LLMProviderError,
    build_advisory_prompt,
    generate_advisory,
)


def _make_report(severity: Severity = Severity.error) -> ValidationReport:
    check = CheckResult(
        check_id="manifest_name_invalid",
        category="manifest",
        severity=severity,
        title="Plugin name does not conform to identifier rules",
        message="Name 'Bad Name' must be lowercase.",
        file_path=".cursor-plugin/plugin.json",
    )
    return ValidationReport(
        report_id="r_test",
        plugin_name="test-plugin",
        plugin_version="1.0.0",
        status=ReportStatus.failed,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        checks=[check],
        summary={"error": 1, "warning": 0, "info": 0},
    )


class TestNotConfigured:
    def test_no_api_key_raises(self):
        config = LLMConfig(api_key="", provider="openai-compatible")
        report = _make_report()
        with pytest.raises(LLMNotConfiguredError):
            generate_advisory(config, report)

    def test_none_api_key_raises(self):
        config = LLMConfig(api_key=None, provider="openai-compatible")  # type: ignore
        report = _make_report()
        with pytest.raises(LLMNotConfiguredError):
            generate_advisory(config, report)


class TestUnknownProvider:
    def test_unknown_provider_raises(self):
        config = LLMConfig(api_key="test-key", provider="unknown-provider")
        report = _make_report()
        with pytest.raises(LLMProviderError) as exc_info:
            generate_advisory(config, report)
        assert "unknown-provider" in str(exc_info.value).lower() \
            or "unknown" in str(exc_info.value).lower()


class TestOpenAI:
    @patch("httpx.Client")
    def test_openai_success(self, mock_client_cls):
        """Mock the OpenAI-compatible adapter and verify the result."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "The plugin has a name issue."}}]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client_cls.return_value.__exit__.return_value = False

        config = LLMConfig(
            api_key="test-key",
            provider="openai-compatible",
            model="gpt-4o-mini",
            base_url="https://api.openai.com/v1",
        )
        report = _make_report()
        result = generate_advisory(config, report)
        assert result == "The plugin has a name issue."
        mock_client.post.assert_called_once()

    @patch("httpx.Client")
    def test_openai_error_propagates(self, mock_client_cls):
        """Provider errors should be wrapped in LLMProviderError."""
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_response.text = "Service unavailable"
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client_cls.return_value.__exit__.return_value = False

        config = LLMConfig(api_key="test-key", provider="openai-compatible")
        report = _make_report()
        with pytest.raises(LLMProviderError):
            generate_advisory(config, report)

    @patch("httpx.Client")
    def test_openai_timeout(self, mock_client_cls):
        """Timeouts should be wrapped in LLMProviderError."""
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("timed out")
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client_cls.return_value.__exit__.return_value = False

        config = LLMConfig(api_key="test-key", provider="openai-compatible", timeout=1)
        report = _make_report()
        with pytest.raises(LLMProviderError) as exc_info:
            generate_advisory(config, report)
        assert "timed out" in str(exc_info.value).lower()


class TestAnthropic:
    @patch("httpx.Client")
    def test_anthropic_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"text": "Claude says: fix the name."}]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client_cls.return_value.__exit__.return_value = False

        config = LLMConfig(api_key="test-key", provider="anthropic")
        report = _make_report()
        result = generate_advisory(config, report)
        assert result == "Claude says: fix the name."


class TestGemini:
    @patch("httpx.Client")
    def test_gemini_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "candidates": [
                {"content": {"parts": [{"text": "Gemini says: check name."}]}}
            ]
        }
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client_cls.return_value.__exit__.return_value = False

        config = LLMConfig(api_key="test-key", provider="gemini")
        report = _make_report()
        result = generate_advisory(config, report)
        assert result == "Gemini says: check name."


class TestOllama:
    @patch("httpx.Client")
    def test_ollama_success(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "Ollama says: ok."}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client_cls.return_value.__exit__.return_value = False

        config = LLMConfig(
            api_key="test-key",
            provider="ollama",
            base_url="http://localhost:11434",
            model="granite3",
        )
        report = _make_report()
        result = generate_advisory(config, report)
        assert result == "Ollama says: ok."


class TestAdvisoryPrompt:
    def test_prompt_includes_check_details(self):
        report = _make_report()
        prompt = build_advisory_prompt(report)
        assert "manifest_name_invalid" in prompt
        assert "test-plugin" in prompt
        assert "failed" in prompt
        assert "Advisory:" in prompt

    def test_prompt_marks_advisory(self):
        report = _make_report()
        prompt = build_advisory_prompt(report)
        # Prompt should instruct the model that output is advisory
        assert "advisory" in prompt.lower() or "advisory" in prompt.lower()

    def test_redacted_errors(self):
        """Test that _redact_key removes key-shaped data."""
        from backend.app.services.llm import _redact_key

        # Generate a clearly synthetic key-like string at runtime
        fake = "sk-test-" + "0" * 40
        redacted = _redact_key(f"error: {fake}")
        assert fake not in redacted
        assert "[REDACTED]" in redacted