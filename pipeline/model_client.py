"""Unified LLM client supporting DeepSeek, Qwen, and OpenAI via OpenAI-compatible API.

Provides abstract interface, retry logic, token estimation, and cost calculation.
All model calls go through httpx directly (no openai SDK dependency).

Features:
- Unified interface for DeepSeek, Qwen, and OpenAI
- Automatic cost tracking with CostTracker
- Retry logic with exponential backoff
- Token estimation and cost calculation
- Support for both USD and CNY pricing

Environment variables:
    LLM_PROVIDER       (default: deepseek)
    DEEPSEEK_API_KEY
    QWEN_API_KEY
    OPENAI_API_KEY

Cost Tracking:
    The module automatically tracks token usage and costs through the global
    CostTracker instance. Use `get_cost_tracker()` to access the tracker and
    call `report()` to generate cost reports.
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
        "input_price_cny": 1.0,   # 元/百万 tokens
        "output_price_cny": 2.0,
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "input_price": 0.80,
        "output_price": 2.00,
        "input_price_cny": 4.0,
        "output_price_cny": 12.0,
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "input_price": 0.15,
        "output_price": 0.60,
        "input_price_cny": 150.0,
        "output_price_cny": 600.0,
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

        # 自动记录成本
        try:
            _tracker.record(usage, self.provider_name)
        except Exception as e:
            logger.warning("Failed to record cost for provider %s: %s", self.provider_name, e)

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
# Cost Tracker
# ---------------------------------------------------------------------------


class CostTracker:
    """追踪 LLM 调用的 token 消耗和成本（人民币）。

    记录每次 API 调用的 token 使用情况，并提供成本估算和报告功能。

    Attributes:
        _usage_stats: 按提供商分类的 token 使用统计
    """

    def __init__(self) -> None:
        """初始化 CostTracker，重置所有统计信息。"""
        self._usage_stats: dict[str, dict[str, int]] = {}
        self._reset_stats()

    def _reset_stats(self) -> None:
        """重置所有提供商的统计信息。"""
        for provider in _MODEL_CONFIGS:
            self._usage_stats[provider] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "call_count": 0
            }

    def record(self, usage: Usage, provider: str) -> None:
        """记录一次 API 调用的 token 使用情况。

        Args:
            usage: Token 使用统计
            provider: 提供商名称 ("deepseek", "qwen", "openai")
        """
        if provider not in self._usage_stats:
            self._usage_stats[provider] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "call_count": 0
            }

        stats = self._usage_stats[provider]
        stats["prompt_tokens"] += usage.prompt_tokens
        stats["completion_tokens"] += usage.completion_tokens
        stats["total_tokens"] += usage.total_tokens
        stats["call_count"] += 1

    def estimated_cost(self, provider: str | None = None) -> float:
        """返回指定提供商或所有提供商的估算成本（人民币）。

        Args:
            provider: 提供商名称。如果为 None，返回所有提供商的总成本。

        Returns:
            估算成本（元），四舍五入到 4 位小数。
        """
        if provider is not None:
            if provider not in self._usage_stats:
                return 0.0
            return self._calculate_provider_cost(provider)

        # 计算所有提供商的总成本
        total_cost = 0.0
        for provider_name in self._usage_stats:
            total_cost += self._calculate_provider_cost(provider_name)
        return round(total_cost, 4)

    def _calculate_provider_cost(self, provider: str) -> float:
        """计算指定提供商的成本。"""
        if provider not in _MODEL_CONFIGS:
            return 0.0

        stats = self._usage_stats[provider]
        config = _MODEL_CONFIGS[provider]

        # 使用人民币价格计算
        input_cost = (stats["prompt_tokens"] / 1_000_000) * config.get("input_price_cny", 0)
        output_cost = (stats["completion_tokens"] / 1_000_000) * config.get("output_price_cny", 0)

        return round(input_cost + output_cost, 4)

    def report(self, provider: str | None = None) -> str:
        """生成成本报告。

        Args:
            provider: 提供商名称。如果为 None，生成所有提供商的报告。

        Returns:
            格式化的成本报告字符串。
        """
        if provider is not None:
            return self._generate_provider_report(provider)

        # 生成所有提供商的报告
        reports = []
        for provider_name in sorted(self._usage_stats.keys()):
            if self._usage_stats[provider_name]["call_count"] > 0:
                reports.append(self._generate_provider_report(provider_name))

        if not reports:
            return "没有 API 调用记录。"

        # 添加总计
        total_calls = sum(stats["call_count"] for stats in self._usage_stats.values())
        total_prompt = sum(stats["prompt_tokens"] for stats in self._usage_stats.values())
        total_completion = sum(stats["completion_tokens"] for stats in self._usage_stats.values())
        total_tokens = sum(stats["total_tokens"] for stats in self._usage_stats.values())
        total_cost = self.estimated_cost()

        reports.append("=" * 60)
        reports.append("总计:")
        reports.append(f"  调用次数: {total_calls}")
        reports.append(f"  Prompt tokens: {total_prompt:,}")
        reports.append(f"  Completion tokens: {total_completion:,}")
        reports.append(f"  总 tokens: {total_tokens:,}")
        reports.append(f"  估算成本: ¥{total_cost:.4f}")

        return "\n".join(reports)

    def _generate_provider_report(self, provider: str) -> str:
        """生成单个提供商的报告。"""
        if provider not in self._usage_stats:
            return f"提供商 '{provider}' 没有调用记录。"

        stats = self._usage_stats[provider]
        if stats["call_count"] == 0:
            return f"提供商 '{provider}' 没有调用记录。"

        cost = self._calculate_provider_cost(provider)

        lines = [
            f"{provider.upper()} 成本报告:",
            f"  调用次数: {stats['call_count']}",
            f"  Prompt tokens: {stats['prompt_tokens']:,}",
            f"  Completion tokens: {stats['completion_tokens']:,}",
            f"  总 tokens: {stats['total_tokens']:,}",
            f"  估算成本: ¥{cost:.4f}"
        ]

        return "\n".join(lines)

    def reset(self) -> None:
        """重置所有统计信息。"""
        self._reset_stats()


# 全局 CostTracker 实例
_tracker = CostTracker()


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


def get_cost_tracker() -> CostTracker:
    """获取全局 CostTracker 实例。

    Returns:
        全局 CostTracker 实例，用于访问成本统计和报告。
    """
    return _tracker


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

    # --- CostTracker test ---
    tracker = get_cost_tracker()

    # 重置 tracker 以确保干净的测试环境
    tracker.reset()

    # 测试记录功能
    test_usage = Usage(prompt_tokens=500, completion_tokens=200, total_tokens=700)
    tracker.record(test_usage, "deepseek")
    tracker.record(test_usage, "qwen")

    # 测试成本估算
    deepseek_cost = tracker.estimated_cost("deepseek")
    qwen_cost = tracker.estimated_cost("qwen")
    total_cost = tracker.estimated_cost()

    logger.info("CostTracker test:")
    logger.info("  DeepSeek estimated cost: ¥%.4f", deepseek_cost)
    logger.info("  Qwen estimated cost: ¥%.4f", qwen_cost)
    logger.info("  Total estimated cost: ¥%.4f", total_cost)

    # 验证成本计算（基于价格表：deepseek 输入1元/百万，输出2元/百万）
    expected_deepseek = (500/1_000_000)*1.0 + (200/1_000_000)*2.0
    assert abs(deepseek_cost - expected_deepseek) < 0.0001, (
        f"DeepSeek cost mismatch: {deepseek_cost} vs {expected_deepseek}"
    )

    # 测试报告功能
    report = tracker.report()
    logger.info("CostTracker report:\n%s", report)
    assert "DEEPSEEK" in report, "Report should contain DEEPSEEK section"
    assert "QWEN" in report, "Report should contain QWEN section"
    assert "总计" in report, "Report should contain total section"

    logger.info("All self-tests passed.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _run_self_test()
