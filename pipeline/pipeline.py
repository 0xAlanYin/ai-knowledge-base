"""AI Knowledge Base — 四步知识库自动化流水线。

使用方式::

    # 完整流水线（GitHub + RSS，最多 20 条，使用 DeepSeek）
    python pipeline/pipeline.py --sources github,rss --limit 20 --provider deepseek

    # 只采集 GitHub（最多 5 条，使用 Qwen）
    python pipeline/pipeline.py --sources github --limit 5 --provider qwen

    # 只采集 RSS（最多 10 条，使用 OpenAI）
    python pipeline/pipeline.py --sources rss --limit 10 --provider openai

    # 干跑模式（不写文件）
    python pipeline/pipeline.py --sources github --limit 5 --dry-run

    # 详细日志
    python pipeline/pipeline.py --verbose
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import httpx

from model_client import chat_with_retry, OpenAICompatibleProvider

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "knowledge" / "raw"
ARTICLES_DIR = PROJECT_ROOT / "knowledge" / "articles"

_GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
_GITHUB_ACCEPT_HEADER = "application/vnd.github.v3+json"

_RSS_TIMEOUT = 30.0
_HTTP_TIMEOUT = 15.0
_RATE_LIMIT_SLEEP = 2.0

logger = logging.getLogger("pipeline")

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ===================================================================
# Step 1: Collect
# ===================================================================


def collect_github(
    limit: int = 10,
    keywords: tuple[str, ...] = ("LLM", "Agent", "RAG", "Fine-tuning", "AI"),
    max_stars: int = 50000,
) -> list[dict[str, Any]]:
    """从 GitHub Search API 采集 AI/LLM/Agent 相关仓库。

    Args:
        limit: 最大返回条数。
        keywords: 搜索关键词列表。
        max_stars: 最大 star 数过滤（排除过大的项目）。

    Returns:
        采集到的原始仓库条目列表。
    """
    results: list[dict[str, Any]] = []
    per_page = min(limit, 100)

    for keyword in keywords:
        if len(results) >= limit:
            break

        query = (
            f"{keyword} in:name,description,topics "
            f"stars:<{max_stars} "
            f"pushed:>2025-01-01 "
            f"sort:stars"
        )

        try:
            resp = httpx.get(
                _GITHUB_SEARCH_URL,
                params={"q": query, "per_page": per_page, "page": 1},
                headers={
                    "Accept": _GITHUB_ACCEPT_HEADER,
                    "User-Agent": "ai-knowledge-base/1.0",
                },
                timeout=_HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("items", []):
                if len(results) >= limit:
                    break

                topics = item.get("topics", []) or []
                results.append(
                    {
                        "name": item["full_name"],
                        "url": item["html_url"],
                        "description": (item.get("description") or "").strip(),
                        "stars": item.get("stargazers_count", 0),
                        "language": item.get("language"),
                        "topics": topics,
                        "author": item.get("owner", {}).get("login", ""),
                        "published_at": item.get("created_at", ""),
                    }
                )

            logger.info(
                "GitHub keyword=%r → %d results, collected %d so far",
                keyword,
                len(data.get("items", [])),
                len(results),
            )

        except httpx.HTTPStatusError as exc:
            logger.warning("GitHub API error for %r: %s", keyword, exc)
        except httpx.RequestError as exc:
            logger.warning("GitHub request failed for %r: %s", keyword, exc)

        time.sleep(_RATE_LIMIT_SLEEP)

    logger.info("GitHub collection done: %d items", len(results))
    return results


def collect_rss(
    limit: int = 10,
    urls: tuple[str, ...] = (
        "https://news.ycombinator.com/rss",
        "https://www.reddit.com/r/MachineLearning/.rss",
    ),
) -> list[dict[str, Any]]:
    """从 RSS 源采集 AI 相关内容（简易正则解析）。

    Args:
        limit: 最大返回条数。
        urls: RSS 源 URL 列表。

    Returns:
        采集到的原始 RSS 条目列表。
    """
    results: list[dict[str, Any]] = []

    for url in urls:
        if len(results) >= limit:
            break

        try:
            resp = httpx.get(url, timeout=_RSS_TIMEOUT, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("RSS fetch failed for %s: %s", url, exc)
            continue

        # 简易正则解析 <item> 块
        items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
        for item_xml in items:
            if len(results) >= limit:
                break

            title = _extract_xml_tag(item_xml, "title")
            link = _extract_xml_tag(item_xml, "link")
            description = _extract_xml_tag(item_xml, "description")
            pub_date = _extract_xml_tag(item_xml, "pubDate")

            if not title or not link:
                continue

            results.append(
                {
                    "title": title.strip(),
                    "url": link.strip(),
                    "description": (description or "").strip(),
                    "source": url,
                    "published_at": pub_date.strip() if pub_date else "",
                }
            )

        logger.info(
            "RSS source=%s → %d items parsed, %d collected so far",
            url,
            len(items),
            len(results),
        )

    logger.info("RSS collection done: %d items", len(results))
    return results


def _extract_xml_tag(xml: str, tag: str) -> str:
    """从 XML 片段中提取指定标签的文本内容。"""
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.DOTALL)
    return m.group(1).strip() if m else ""


# ===================================================================
# Step 2: Analyze
# ===================================================================

_ANALYSIS_SYSTEM_PROMPT = """你是一个 AI 技术内容分析师。请分析以下技术内容，返回严格 JSON 格式（不要 markdown 包裹）：
{
  "summary": "简洁的技术摘要（20-200字）",
  "key_points": ["关键点1", "关键点2", "关键点3"],
  "category": "framework|library|tool|paper|tutorial",
  "relevance_score": 0.0-1.0,
  "novelty_score": 0.0-1.0,
  "practicality_score": 0.0-1.0,
  "tags": ["tag1", "tag2"],
  "recommended_audience": ["researchers", "engineers", "product-managers"],
  "complexity": "beginner|intermediate|advanced"
}"""


def _build_analysis_prompt(item: dict[str, Any], source_type: str) -> str:
    """为分析 LLM 构建提示词。

    Args:
        item: 原始条目字典。
        source_type: 数据源类型（github / rss）。

    Returns:
        构造好的提示词字符串。
    """
    if source_type == "github":
        return (
            f"项目名称：{item.get('name', '')}\n"
            f"描述：{item.get('description', '')}\n"
            f"语言：{item.get('language', 'unknown')}\n"
            f"Stars：{item.get('stars', 0)}\n"
            f"Topics：{', '.join(item.get('topics', []) or [])}\n"
        )
    # RSS
    return (
        f"标题：{item.get('title', '')}\n"
        f"描述：{item.get('description', '')}\n"
        f"来源：{item.get('source', '')}\n"
    )


def analyze_item(item: dict[str, Any], source_type: str, provider: str = "deepseek") -> dict[str, Any]:
    """调用 LLM 对单条内容进行摘要/评分/标签分析。

    Args:
        item: 原始条目字典。
        source_type: 数据源类型（github / rss）。
        provider: LLM 提供商（deepseek, qwen, openai）。

    Returns:
        分析结果字典，包含 summary、key_points、analysis 等字段。
    """
    prompt = _build_analysis_prompt(item, source_type)

    try:
        # 创建指定的 provider 实例
        llm_provider = OpenAICompatibleProvider(provider_name=provider)
        
        resp = chat_with_retry(
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            provider=llm_provider,
            temperature=0.3,
            max_tokens=1024,
        )
        raw = resp.content.strip()
        # 去除可能的 markdown 包裹
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        analysis = json.loads(raw)
    except (json.JSONDecodeError, RuntimeError) as exc:
        logger.warning("LLM analysis failed for %s: %s", item.get("name", item.get("title", "?")), exc)
        analysis = _fallback_analysis(item)

    return analysis


def _fallback_analysis(item: dict[str, Any]) -> dict[str, Any]:
    """LLM 调用失败时的兜底分析。

    Args:
        item: 原始条目字典。

    Returns:
        兜底分析结果。
    """
    description = item.get("description", "") or item.get("summary", "") or ""
    return {
        "summary": description[:200] if description else "暂无摘要",
        "key_points": [description[:100]] if description else ["暂无信息"],
        "category": "tool",
        "relevance_score": 0.5,
        "novelty_score": 0.5,
        "practicality_score": 0.5,
        "tags": ["ai"],
        "recommended_audience": ["engineers"],
        "complexity": "intermediate",
    }


# ===================================================================
# Step 3: Organize
# ===================================================================


def _normalize_url(url: str) -> str:
    """标准化 URL（去除尾部斜杠等）。"""
    return url.rstrip("/")


def organize_items(items: list[dict[str, Any]], source_type: str) -> list[dict[str, Any]]:
    """去重 + 格式标准化 + 校验。

    Args:
        items: 原始条目列表（含分析结果）。
        source_type: 数据源类型。

    Returns:
        标准化后的条目列表（已去重）。
    """
    seen_urls: set[str] = set()
    organized: list[dict[str, Any]] = []

    for item in items:
        url = _normalize_url(item.get("url", item.get("source_url", "")))
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        title = item.get("title") or item.get("name", "")
        description = item.get("description") or item.get("summary", "")

        entry = _build_knowledge_entry(
            title=title,
            source_url=url,
            source_type="github_trending" if source_type == "github" else "hacker_news",
            raw=description,
            analysis=item.get("_analysis", {}),
            source_metadata=_build_source_metadata(item, source_type),
        )

        # 校验必填字段
        if not entry.get("id") or not entry.get("title"):
            logger.warning("Skipping invalid entry: missing id or title")
            continue

        organized.append(entry)

    logger.info("Organize: %d unique items (removed %d duplicates)", len(organized), len(items) - len(organized))
    return organized


def _build_source_metadata(item: dict[str, Any], source_type: str) -> dict[str, Any]:
    """构建 source_metadata 字段。

    Args:
        item: 原始条目。
        source_type: 数据源类型。

    Returns:
        source_metadata 字典。
    """
    if source_type == "github":
        return {
            "stars": item.get("stars", 0),
            "language": item.get("language"),
            "description": item.get("description", ""),
            "author": item.get("author", ""),
            "topics": item.get("topics", []),
            "published_at": item.get("published_at", ""),
        }
    return {
        "description": item.get("description", ""),
        "published_at": item.get("published_at", ""),
        "source_rss": item.get("source", ""),
    }


def _build_knowledge_entry(
    title: str,
    source_url: str,
    source_type: str,
    raw: str,
    analysis: dict[str, Any],
    source_metadata: dict[str, Any],
) -> dict[str, Any]:
    """构建符合 AGENTS.md 规范的知识条目 JSON。

    Args:
        title: 条目标题。
        source_url: 原始来源 URL。
        source_type: 来源类型。
        raw: 原始内容。
        analysis: LLM 分析结果。
        source_metadata: 来源元数据。

    Returns:
        标准知识条目字典。
    """
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()

    summary = analysis.get("summary", raw[:200])
    key_points = analysis.get("key_points", [raw[:100]] if raw else [])
    category = analysis.get("category", "tool")
    tags = analysis.get("tags", ["ai"])

    return {
        "id": str(uuid.uuid4()),
        "title": title,
        "source_url": source_url,
        "source_type": source_type,
        "source_metadata": source_metadata,
        "content": {
            "raw": raw,
            "summary": summary,
            "key_points": key_points,
            "technical_details": {
                "frameworks": [],
                "languages": (
                    [source_metadata.get("language", "")]
                    if source_metadata.get("language")
                    else []
                ),
                "complexity": analysis.get("complexity", "intermediate"),
            },
        },
        "analysis": {
            "category": category,
            "relevance_score": analysis.get("relevance_score", 0.5),
            "novelty_score": analysis.get("novelty_score", 0.5),
            "practicality_score": analysis.get("practicality_score", 0.5),
            "tags": tags,
            "recommended_audience": analysis.get("recommended_audience", ["engineers"]),
        },
        "status": "analyzed",
        "timestamps": {
            "collected_at": now,
            "analyzed_at": now,
        },
        "version": 1,
    }


# ===================================================================
# Step 4: Save
# ===================================================================


def save_articles(articles: list[dict[str, Any]], dry_run: bool = False) -> list[Path]:
    """将文章保存为独立 JSON 文件到 knowledge/articles/processed/。

    Args:
        articles: 标准知识条目列表。
        dry_run: 如果为 True，只打印不写入。

    Returns:
        写入的文件路径列表。
    """
    saved: list[Path] = []
    today = datetime.now().strftime("%Y-%m-%d")

    for article in articles:
        source_type_short = article.get("source_type", "unknown").replace("_", "-")
        safe_name = _safe_filename(article.get("title", "untitled"))
        filename = f"{today}-{source_type_short}-{safe_name}.json"
        filepath = ARTICLES_DIR / "processed" / filename

        if dry_run:
            logger.info("[DRY-RUN] Would write: %s", filepath)
            # dry-run 模式下不添加到 saved 列表，因为实际上没有保存
            continue

        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(article, f, ensure_ascii=False, indent=2)

        logger.info("Saved: %s", filepath)
        saved.append(filepath)

    logger.info("Save complete: %d articles %s", len(saved), "(dry-run)" if dry_run else "")
    return saved


def _safe_filename(title: str) -> str:
    """将标题转为安全的文件名片段。

    Args:
        title: 原始标题。

    Returns:
        安全的文件名（最多 40 字符）。
    """
    # 只保留字母、数字、连字符
    safe = re.sub(r"[^a-zA-Z0-9-]", "-", title.lower())
    safe = re.sub(r"-+", "-", safe).strip("-")
    return safe[:40]


# ===================================================================
# Pipeline orchestration
# ===================================================================


def run_pipeline(
    sources: tuple[str, ...] = ("github", "rss"),
    limit: int = 10,
    provider: str = "deepseek",
    dry_run: bool = False,
) -> int:
    """运行完整的四步知识库流水线。

    Args:
        sources: 数据源列表（支持 "github"、"rss"）。
        limit: 每个数据源的最大采集条数。
        provider: LLM 提供商（deepseek, qwen, openai）。
        dry_run: 是否干跑（不写文件）。

    Returns:
        最终保存的文章数量。
    """
    all_raw_items: list[dict[str, Any]] = []

    # Step 1: Collect
    if "github" in sources:
        logger.info("=== Step 1: Collect from GitHub ===")
        github_items = collect_github(limit=limit)
        for item in github_items:
            item["_source_type"] = "github"
        all_raw_items.extend(github_items)
        logger.info("GitHub collected: %d items", len(github_items))

    if "rss" in sources:
        logger.info("=== Step 1: Collect from RSS ===")
        rss_items = collect_rss(limit=limit)
        for item in rss_items:
            item["_source_type"] = "rss"
        all_raw_items.extend(rss_items)
        logger.info("RSS collected: %d items", len(rss_items))

    if not all_raw_items:
        logger.warning("No items collected from any source.")
        return 0

    # Save raw data
    _save_raw_data(all_raw_items, dry_run=dry_run)

    # Step 2: Analyze
    logger.info("=== Step 2: Analyze (%d items) with provider=%s ===", len(all_raw_items), provider)
    for i, item in enumerate(all_raw_items):
        source_type = item.pop("_source_type", "github")
        logger.debug("Analyzing [%d/%d]: %s", i + 1, len(all_raw_items), item.get("name", item.get("title", "?")))
        analysis = analyze_item(item, source_type, provider=provider)
        item["_analysis"] = analysis

    # Step 3: Organize
    logger.info("=== Step 3: Organize ===")

    # 记录每个条目的原始 source_type，然后按类型分组去重/标准化
    for item in all_raw_items:
        item["_source_type_tag"] = item.get("_source_type", "github")

    organized: list[dict[str, Any]] = []
    github_items = [it for it in all_raw_items if it.get("_source_type_tag") == "github"]
    rss_items_final = [it for it in all_raw_items if it.get("_source_type_tag") == "rss"]

    if github_items:
        organized.extend(organize_items(github_items, "github"))
    if rss_items_final:
        organized.extend(organize_items(rss_items_final, "rss"))

    # Step 4: Save
    logger.info("=== Step 4: Save ===")
    saved_paths = save_articles(organized, dry_run=dry_run)

    logger.info(
        "Pipeline complete: %d collected → %d analyzed → %d organized → %d saved",
        len(all_raw_items),
        len(all_raw_items),
        len(organized),
        len(saved_paths),
    )
    return len(saved_paths)


def _save_raw_data(
    items: list[dict[str, Any]],
    dry_run: bool = False,
) -> Path | None:
    """将原始采集数据保存到 knowledge/raw/。

    Args:
        items: 原始条目列表。
        dry_run: 如果为 True，只打印不写入。

    Returns:
        写入的文件路径，或 None。
    """
    today = datetime.now().strftime("%Y-%m-%d")
    raw_path = RAW_DIR / f"pipeline-raw-{today}.json"

    payload = {
        "source": "pipeline",
        "collected_at": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "total_items": len(items),
        "items": items,
    }

    if dry_run:
        logger.info("[DRY-RUN] Would write raw data: %s (%d items)", raw_path, len(items))
        return raw_path

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    logger.info("Raw data saved: %s (%d items)", raw_path, len(items))
    return raw_path


# ===================================================================
# CLI entry point
# ===================================================================


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """解析命令行参数。

    Args:
        argv: 命令行参数列表，默认从 sys.argv 读取。

    Returns:
        解析后的命名空间。
    """
    parser = argparse.ArgumentParser(
        description="AI Knowledge Base — 四步知识库自动化流水线",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--sources",
        default="github,rss",
        help="数据源，逗号分隔（支持: github, rss），默认: github,rss",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="每个数据源的最大采集条数，默认: 10",
    )
    parser.add_argument(
        "--provider",
        choices=["deepseek", "qwen", "openai"],
        default="deepseek",
        help="LLM 提供商（deepseek, qwen, openai），默认: deepseek",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="干跑模式：只打印不写文件",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细日志输出（DEBUG 级别）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI 入口。

    Args:
        argv: 命令行参数。

    Returns:
        退出码（0 表示成功）。
    """
    args = _parse_args(argv)
    _setup_logging(args.verbose)

    sources = tuple(s.strip() for s in args.sources.split(",") if s.strip())
    logger.info(
        "Pipeline started — sources=%s limit=%d provider=%s dry_run=%s",
        sources,
        args.limit,
        args.provider,
        args.dry_run,
    )

    try:
        count = run_pipeline(
            sources=sources,
            limit=args.limit,
            provider=args.provider,
            dry_run=args.dry_run,
        )
        logger.info("Pipeline finished. Total articles saved: %d", count)
        return 0
    except Exception:
        logger.exception("Pipeline failed with unexpected error")
        return 1


if __name__ == "__main__":
    sys.exit(main())
