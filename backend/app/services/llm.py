"""Opt-in LLM advisory provider.

Generates natural-language explanations grounded in actual CheckResult
objects.  The deterministic validation engine is never bypassed — LLM
output is advisory only and clearly labeled as such.

Supported providers (selected via LLM_PROVIDER):
  - "openai-compatible" (default) — OpenAI-compatible API via LLM_BASE_URL
  - "anthropic" — Claude messages endpoint
  - "gemini" — Google generateContent
  - "ollama" — local Ollama chat

When LLM_API_KEY is unset or LLM_PROVIDER is omitted, generate_advisory
raises LLMNotConfiguredError.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

import httpx

from backend.app.models.schemas import CheckResult, ValidationReport

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 30


class LLMNotConfiguredError(Exception):
    """Raised when no LLM_API_KEY is configured."""


class LLMProviderError(Exception):
    """Raised when the LLM provider rejects the request or times out."""


@dataclass
class LLMConfig:
    api_key: str
    provider: str = "openai-compatible"
    model: str = "gpt-4o-mini"
    base_url: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT


def _truncate(message: str, limit: int = 500) -> str:
    if len(message) > limit:
        return message[:limit - 3] + "..."
    return message


def build_advisory_prompt(report: ValidationReport) -> str:
    """Build a prompt for the LLM from the validation report.

    Only includes the actual check results — no fabricated context.
    """
    checks_text = "\n".join(
        f"  - [{c.severity.value}] [{c.check_id}] {c.category}: "
        f"{c.title} — {_truncate(c.message)}"
        for c in report.checks
    )

    return (
        "You are a diagnostic assistant for Cursor plugin developers. "
        "Given the validation findings below, explain in 2-3 sentences why "
        "the plugin is likely failing to load or function. Be specific and "
        "cite the check IDs. Do not fabricate issues not listed.\n\n"
        f"Plugin: {report.plugin_name} ({report.plugin_version or 'unknown'})\n"
        f"Overall status: {report.status.value}\n"
        f"Summary: errors={report.summary.get('error', 0)}, "
        f"warnings={report.summary.get('warning', 0)}, "
        f"info={report.summary.get('info', 0)}\n\n"
        "Findings:\n"
        f"{checks_text}\n\n"
        "Advisory:"
    )


def _redact_key(text: str) -> str:
    """Replace API key-like substrings with a placeholder."""
    return re.sub(r"(sk-[A-Za-z0-9_-]{10,}|[A-Za-z0-9_-]{32,})", "[REDACTED]", text)


def _call_openai(config: LLMConfig, prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 512,
        "temperature": 0.3,
    }
    url = config.base_url.rstrip("/") if config.base_url else "https://api.openai.com/v1"
    url = f"{url}/chat/completions"

    with httpx.Client(timeout=config.timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            detail = _redact_key(resp.text[:300])
            raise LLMProviderError(
                f"Provider returned {resp.status_code}: {detail}"
            )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


def _call_anthropic(config: LLMConfig, prompt: str) -> str:
    headers = {
        "x-api-key": config.api_key,
        "content-type": "application/json",
        "anthropic-version": "2023-06-01",
    }
    payload = {
        "model": config.model,
        "max_tokens": 512,
        "messages": [{"role": "user", "content": prompt}],
    }
    url = f"{config.base_url.rstrip('/') if config.base_url else 'https://api.anthropic.com'}/v1/messages"

    with httpx.Client(timeout=config.timeout) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            detail = _redact_key(resp.text[:300])
            raise LLMProviderError(
                f"Provider returned {resp.status_code}: {detail}"
            )
        data = resp.json()
        return data["content"][0]["text"].strip()


def _call_gemini(config: LLMConfig, prompt: str) -> str:
    url = config.base_url.rstrip("/") if config.base_url else "https://generativelanguage.googleapis.com/v1"
    url = f"{url}/models/{config.model}:generateContent?key={config.api_key}"

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 512, "temperature": 0.3},
    }

    with httpx.Client(timeout=config.timeout) as client:
        resp = client.post(url, json=payload)
        if resp.status_code != 200:
            detail = _redact_key(resp.text[:300])
            raise LLMProviderError(
                f"Provider returned {resp.status_code}: {detail}"
            )
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _call_ollama(config: LLMConfig, prompt: str) -> str:
    url = f"{config.base_url.rstrip('/') if config.base_url else 'http://localhost:11434'}/api/generate"
    payload = {
        "model": config.model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 512},
    }

    with httpx.Client(timeout=config.timeout) as client:
        resp = client.post(url, json=payload)
        if resp.status_code != 200:
            detail = _redact_key(resp.text[:300])
            raise LLMProviderError(
                f"Provider returned {resp.status_code}: {detail}"
            )
        data = resp.json()
        return data.get("response", "").strip()


_PROVIDER_DISPATCH = {
    "openai-compatible": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
    "ollama": _call_ollama,
}


def generate_advisory(config: LLMConfig, report: ValidationReport) -> str:
    """Generate an LLM advisory explanation for a validation report.

    Raises LLMNotConfiguredError if no API key is set (caller may treat
    as advisory unavailable).
    Raises LLMProviderError on provider failures.
    """
    if not config.api_key:
        raise LLMNotConfiguredError("LLM_API_KEY is not configured")

    provider_fn = _PROVIDER_DISPATCH.get(config.provider)
    if provider_fn is None:
        raise LLMProviderError(
            f"Unknown LLM provider: '{config.provider}'. "
            f"Supported: {', '.join(_PROVIDER_DISPATCH.keys())}"
        )

    prompt = build_advisory_prompt(report)

    try:
        result = provider_fn(config, prompt)
    except httpx.TimeoutException:
        raise LLMProviderError(
            f"LLM request timed out after {config.timeout}s"
        )
    except LLMProviderError:
        raise
    except Exception as exc:
        raise LLMProviderError(
            f"Unexpected error from {config.provider}: {type(exc).__name__}"
        )

    # Guard against empty responses
    if not result:
        raise LLMProviderError("Provider returned an empty response")

    return result