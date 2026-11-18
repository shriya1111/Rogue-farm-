"""Tiny LLM client layer.

Providers:
  anthropic  - official `anthropic` SDK; credentials resolved by the SDK
               (ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN or an `ant auth login` profile).
  gemini     - Google AI Studio OpenAI-compatible endpoint (GEMINI_API_KEY).
  openrouter - OpenRouter (OPENROUTER_API_KEY).

Nothing here is required: every caller has a non-LLM fallback, so the project runs with no key.
"""
from __future__ import annotations

import os
import time

ANTHROPIC_DEFAULT = "claude-opus-5-5"
GEMINI_DEFAULT = "gemini-3.8-flash"
OPENROUTER_DEFAULT = "anthropic/claude-haiku-5.5"
# Models that accept output_config.effort (Haiku 4.5 does not).
_EFFORT_MODELS = ("claude-opus-5", "claude-sonnet-5", "claude-haiku-5", "claude-fable", "claude-opus-4-8",
                  "claude-opus-4-7", "claude-opus-4-6", "claude-sonnet-4-6")
# Models that support the server-side refusal fallback ("default" routing).
_FALLBACK_MODELS = ("claude-fable-5-2", "claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    provider = "none"
    model = "none"

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:  # pragma: no cover
        raise NotImplementedError


class AnthropicClient(LLMClient):
    provider = "anthropic"

    def __init__(self, model: str | None = None):
        try:
            import anthropic
        except ImportError as e:
            raise LLMUnavailable("pip install anthropic") from e
        self._anthropic = anthropic
        self.client = anthropic.Anthropic(max_retries=3, timeout=120.0)
        self.model = model or ANTHROPIC_DEFAULT

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        kwargs = dict(model=self.model, max_tokens=max(max_tokens, 2048), system=system,
                      messages=[{"role": "user", "content": prompt}])
        if self.model.startswith(_EFFORT_MODELS):
            kwargs["output_config"] = {"effort": "low"}  # short, simple tasks
        if self.model in _FALLBACK_MODELS:
            resp = self.client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                    fallbacks="default", **kwargs)
        else:
            resp = self.client.messages.create(**kwargs)
        if resp.stop_reason == "refusal":
            raise LLMUnavailable(f"{self.model} declined the request")
        return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


class OpenAICompatClient(LLMClient):
    """Gemini / OpenRouter via their OpenAI-compatible chat endpoints (plain HTTP)."""

    def __init__(self, provider: str, model: str | None = None):
        import requests
        self.requests, self.provider = requests, provider
        if provider == "gemini":
            self.url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            self.key = os.environ.get("GEMINI_API_KEY", "proxy-injected")
            self.model = model or GEMINI_DEFAULT
        else:
            self.url = "https://openrouter.ai/api/v1/chat/completions"
            self.key = os.environ.get("OPENROUTER_API_KEY", "proxy-injected")
            self.model = model or OPENROUTER_DEFAULT

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        body = {"model": self.model, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}
        last = None
        for attempt in range(4):
            r = self.requests.post(self.url, json=body, timeout=120,
                                   headers={"Authorization": f"Bearer {self.key}"})
            if r.status_code in (429, 500, 502, 503):
                last = r.text[:200]
                time.sleep(2 * (attempt + 1))
                continue
            if r.status_code != 200:
                raise LLMUnavailable(f"{self.provider} HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
            if isinstance(data, list):
                data = data[0]
            return data["choices"][0]["message"]["content"] or ""
        raise LLMUnavailable(f"{self.provider} unavailable: {last}")


def get_client(provider: str, model: str | None = None) -> LLMClient:
    if provider == "anthropic":
        return AnthropicClient(model)
    if provider in ("gemini", "openrouter"):
        if model and model.startswith("claude-") and provider == "openrouter":
            model = "anthropic/" + model.replace("-5-5", "-5.5").replace("-4-5", "-4.5").replace("-4-6", "-4.6")
        elif model and model.startswith("claude-"):
            model = None  # Claude ids mean nothing to Gemini: use its default
        return OpenAICompatClient(provider, model)
    raise LLMUnavailable(f"unknown provider {provider!r}")


def detect_provider() -> str | None:
    """Best-effort guess of an available provider from environment variables."""
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "anthropic"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if os.environ.get("OPENROUTER_API_KEY"):
        return "openrouter"
    return None
