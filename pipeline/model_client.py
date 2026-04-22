"""Unified LLM client supporting DeepSeek, Qwen, and OpenAI via OpenAI-compatible API.

Provides abstract interface, retry logic, token estimation, and cost calculation.
All model calls go through httpx directly (no openai SDK dependency).

Environment variables:
    LLM_PROVIDER       (default: deepseek)
    DEEPSEEK_API_KEY
    QWEN_API_KEY
    OPENAI_API_KEY
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MODEL_CONFIGS: dict[str, dict] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "input_price": 0.27,  # per 1M tokens, USD
        "output_price": 1.10,
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "input_price": 0.80,
        "output_price": 2.00,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "input_price": 0.15,
        "output_price": 0.60,
    },
}

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_REQUEST_TIMEOUT = 60.0

ProviderName = Literal["deepseek", "qwen", "openai"]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Usage:
    """Token usage statistics from an LLM response."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    """Unified response from any LLM provider."""

    content: str
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    provider: str = ""


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Send a chat completion request and return the response.

        Args:
            messages: List of message dicts with ``role`` and ``content`` keys.
            **kwargs: Additional per-request parameters (e.g. temperature).

        Returns:
            An LLMResponse with the assistant reply and usage stats.
        """

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate the number of tokens in *text*.

        Args:
            text: Input string.

        Returns:
            Estimated token count.
        """

    @abstractmethod
    def calculate_cost(self, usage: Usage) -> float:
        """Calculate the cost in USD for a given *usage* record.

        Args:
            usage: Token usage statistics.

        Returns:
            Cost in USD.
        """


# ---------------------------------------------------------------------------
# OpenAI-compatible provider
# ---------------------------------------------------------------------------


class OpenAICompatibleProvider(LLMProvider):
    """Provider that calls any OpenAI-compatible chat completion endpoint.

    Args:
        provider_name: One of ``"deepseek"``, ``"qwen"``, ``"openai"``.
        api_key: API key. Falls back to the corresponding env variable.
    """

    def __init__(
        self,
        provider_name: ProviderName = "deepseek",
        api_key: str | None = None,
    ) -> None:
        self.provider_name = provider_name
        cfg = _MODEL_CONFIGS[provider_name]
        self.base_url = cfg["base_url"]
        self.model_name = cfg["model"]
        self._input_price = cfg["input_price"]
        self._output_price = cfg["output_price"]

        env_key_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "qwen": "QWEN_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        resolved_key = api_key or os.environ.get(env_key_map[provider_name], "")
        if not resolved_key:
            logger.warning(
                "No API key found for provider '%s'. "
                "Set %s or pass api_key explicitly.",
                provider_name,
                env_key_map[provider_name],
            )
        self._api_key = resolved_key

    # -- LLMProvider interface -----------------------------------------------

    def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        """Send a chat completion request.

        Args:
            messages: Chat messages.
            **kwargs: Overrides for temperature, max_tokens, etc.

        Returns:
            Parsed LLMResponse.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
            httpx.RequestError: On connection / timeout errors.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": kwargs.pop("model", self.model_name),
            "messages": messages,
            **kwargs,
        }

        with httpx.Client(timeout=_REQUEST_TIMEOUT) as client:
            resp = client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        choice = data["choices"][0]
        content = choice["message"]["content"]

        usage_data = data.get("usage", {})
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )

        return LLMResponse(
            content=content,
            usage=usage,
            model=data.get("model", self.model_name),
            provider=self.provider_name,
        )

    def count_tokens(self, text: str) -> int:
        """Estimate token count using a simple heuristic (4 chars per token).

        For production use, consider a proper tokenizer (e.g. tiktoken).
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    def calculate_cost(self, usage: Usage) -> float:
        """Calculate the estimated USD cost.

        Args:
            usage: Token usage statistics.

        Returns:
            Cost in USD, rounded to 6 decimal places.
        """
        input_cost = (usage.prompt_tokens / 1_000_000) * self._input_price
        output_cost = (usage.completion_tokens / 1_000_000) * self._output_price
        return round(input_cost + output_cost, 6)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def _get_default_provider() -> OpenAICompatibleProvider:
    """Build a provider based on the ``LLM_PROVIDER`` env variable."""
    provider_name: str = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    if provider_name not in _MODEL_CONFIGS:
        logger.warning(
            "Unknown LLM_PROVIDER '%s'. Falling back to 'deepseek'.",
            provider_name,
        )
        provider_name = "deepseek"
    return OpenAICompatibleProvider(provider_name=provider_name)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------


def chat_with_retry(
    messages: list[dict],
    provider: LLMProvider | None = None,
    max_retries: int = _MAX_RETRIES,
    **kwargs,
) -> LLMResponse:
    """Call ``provider.chat()`` with exponential-backoff retry logic.

    Args:
        messages: Chat messages to send.
        provider: An LLMProvider instance. Uses the default provider if None.
        max_retries: Maximum number of retry attempts (default 3).
        **kwargs: Additional arguments forwarded to ``provider.chat()``.

    Returns:
        An LLMResponse on success.

    Raises:
        RuntimeError: When all retry attempts are exhausted.
    """
    p = provider or _get_default_provider()
    last_exc: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            return p.chat(messages, **kwargs)
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = _BACKOFF_BASE ** (attempt - 1)
                logger.warning(
                    "Chat attempt %d/%d failed (%s). Retrying in %.1fs ...",
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
            else:
                logger.error(
                    "All %d chat attempts exhausted. Last error: %s",
                    max_retries,
                    exc,
                )

    raise RuntimeError(
        f"Chat failed after {max_retries} retries."
    ) from last_exc


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------


def quick_chat(
    prompt: str,
    system_prompt: str | None = None,
    provider: LLMProvider | None = None,
    **kwargs,
) -> str:
    """One-shot convenience: send a prompt and get the reply text.

    Args:
        prompt: The user message.
        system_prompt: Optional system-level instruction.
        provider: An LLMProvider instance. Uses the default if None.
        **kwargs: Additional arguments forwarded to ``chat_with_retry``.

    Returns:
        The assistant's reply content as a string.
    """
    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    resp = chat_with_retry(messages, provider=provider, **kwargs)
    return resp.content


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _run_self_test() -> None:
    """Quick smoke-test that exercises the public API."""
    provider_name = os.environ.get("LLM_PROVIDER", "deepseek").lower()
    if provider_name not in _MODEL_CONFIGS:
        provider_name = "deepseek"

    api_key_env = f"{provider_name.upper()}_API_KEY"
    if not os.environ.get(api_key_env):
        logger.warning(
            "Skipping self-test: %s is not set. "
            "Set LLM_PROVIDER and the corresponding API key to run.",
            api_key_env,
        )
        return

    provider = OpenAICompatibleProvider(provider_name=provider_name)  # type: ignore[arg-type]
    logger.info("Self-test: provider=%s model=%s", provider_name, provider.model_name)

    # --- chat ---
    messages = [
        {"role": "user", "content": "Say 'Hello from model_client' in 5 words or fewer."}
    ]
    resp = chat_with_retry(messages, provider=provider, temperature=0.0)
    logger.info("Response: %s", resp.content)
    logger.info("Usage: %s", resp.usage)
    assert resp.content, "Response content should not be empty"

    # --- quick_chat ---
    reply = quick_chat(
        "Reply with only the word 'OK'.",
        system_prompt="You are a terse assistant.",
        provider=provider,
        temperature=0.0,
    )
    logger.info("quick_chat: %s", reply)
    assert reply.strip(), "quick_chat reply should not be empty"

    # --- token estimation ---
    sample = "Hello, world! This is a test sentence."
    estimated = provider.count_tokens(sample)
    logger.info("Estimated tokens for %r: %d", sample, estimated)
    assert estimated > 0, "Token count should be positive"

    # --- cost calculation ---
    usage = Usage(prompt_tokens=100, completion_tokens=50, total_tokens=150)
    cost = provider.calculate_cost(usage)
    logger.info("Estimated cost for usage %s: $%.6f", usage, cost)
    assert cost >= 0, "Cost should be non-negative"

    logger.info("All self-tests passed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _run_self_test()
