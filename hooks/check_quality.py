#!/usr/bin/env python3
"""Knowledge entry 5-dimension quality scoring script.

Evaluates knowledge entry JSON files (as defined in AGENTS.md) across five
dimensions and produces a weighted total score (0–100) with A/B/C grading.

Usage:
    python hooks/check_quality.py <json_file> [json_file2 ...]
    python hooks/check_quality.py knowledge/articles/pending/*.json

Scoring dimensions (weighted total = 100):
  - Summary quality       (25 pts): length + technical keywords
  - Technical depth       (25 pts): mapped from item.score (1–10 → 0–25)
  - Format compliance     (20 pts): 4 pts each for id, title, source_url, status, timestamps
  - Tag precision         (15 pts): tag count + allowed-list check
  - Buzzword detection    (15 pts): penalises empty catchphrases (CN + EN)

Grade:  A >= 80, B >= 60, C < 60

Exit code:
    0 — all files grade B or above
    1 — one or more files grade C
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# ---- Dimension max scores (weighted total = 100) ----
MAX_SUMMARY_QUALITY = 25
MAX_TECH_DEPTH = 25
MAX_FORMAT_COMPLIANCE = 20
MAX_TAG_PRECISION = 15
MAX_BUZZWORD_DETECTION = 15

# ---- Grade thresholds ----
GRADE_A_MIN = 80
GRADE_B_MIN = 60

# ---- Summary scoring ----
SUMMARY_FULL_LENGTH = 50  # ≥50 chars → full marks
SUMMARY_BASE_LENGTH = 20  # ≥20 chars → base marks
SUMMARY_BASE_SCORE = 10  # points for meeting base length
TECHNICAL_KEYWORDS: set[str] = {
    "llm", "agent", "rag", "fine-tuning", "finetuning", "langchain",
    "pytorch", "transformer", "embedding", "vector", "retrieval",
    "prompt", "inference", "multi-modal", "multimodal", "neural",
    "deep learning", "machine learning", "nlp", "autonomous",
    "orchestration", "workflow", "mcp", "a2a", "function calling",
    "tool use", "chain-of-thought", "cot", "react", "agentic",
    "知识图谱", "语义搜索", "大模型", "检索增强", "向量数据库",
}

# ---- Tag allowed list ----
VALID_TAGS: set[str] = {
    "framework", "library", "tool", "paper", "tutorial",
    "agent", "llm", "rag", "fine-tuning", "nlp",
    "computer-vision", "multi-modal", "embedding", "vector-db",
    "prompt-engineering", "code-generation", "deployment",
    "security", "platform", "design", "data-processing",
    "browser-automation", "transformer", "api", "devops",
    "testing", "monitoring", "optimization", "open-source",
}

# ---- Buzzword blacklists ----
BUZZWORDS_CN: list[str] = [
    "赋能", "抓手", "闭环", "打通", "全链路",
    "底层逻辑", "颗粒度", "对齐", "拉通", "沉淀",
    "强大的", "革命性的",
]
BUZZWORDS_EN: list[str] = [
    "groundbreaking", "revolutionary", "game-changing",
    "cutting-edge", "state-of-the-art", "bleeding-edge",
    "paradigm-shift", "next-generation", "disruptive",
]

_BUZZWORD_PATTERNS: list[re.Pattern] = [
    re.compile(re.escape(bw), re.IGNORECASE) for bw in BUZZWORDS_CN + BUZZWORDS_EN
]

# ---- Format compliance ----
FORMAT_FIELDS: list[str] = ["id", "title", "source_url", "status", "timestamps"]
FORMAT_POINTS_PER_FIELD = MAX_FORMAT_COMPLIANCE // len(FORMAT_FIELDS)  # 4

TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"^https?://")

# ---- Progress bar ----
BAR_WIDTH = 40
BAR_FILL = "█"
BAR_EMPTY = "░"
BAR_DONE = "✓"
BAR_FAIL = "✗"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class DimensionScore:
    """Score for a single quality dimension."""

    name: str
    score: float
    max_score: float
    detail: str = ""

    @property
    def percentage(self) -> float:
        """Return score as a percentage of max_score."""
        if self.max_score == 0:
            return 0.0
        return round(self.score / self.max_score * 100, 1)


@dataclass
class QualityReport:
    """Aggregated quality report for a single knowledge entry."""

    file: str
    dimensions: list[DimensionScore] = field(default_factory=list)

    @property
    def total(self) -> float:
        return round(sum(d.score for d in self.dimensions), 1)

    @property
    def max_total(self) -> int:
        return sum(d.max_score for d in self.dimensions)

    @property
    def grade(self) -> str:
        t = self.total
        if t >= GRADE_A_MIN:
            return "A"
        if t >= GRADE_B_MIN:
            return "B"
        return "C"

    def summary_line(self) -> str:
        dims = " | ".join(f"{d.name}: {d.score}/{d.max_score}" for d in self.dimensions)
        return f"  Total: {self.total}/{self.max_total}  Grade: {self.grade}  ({dims})"


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def _get_nested(data: dict, dotted_key: str) -> Any:
    """Resolve a dotted key like 'content.summary' against a nested dict."""
    parts = dotted_key.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _get_item_score(data: dict) -> int | None:
    """Extract the numeric score from the data (handles both entry and pending formats).

    For processed entries: analysis.relevance_score (0-1 float)
    For pending items:    each item has a top-level "score" (1-10 int)
    """
    # Try the processed entry format first
    relevance = _get_nested(data, "analysis.relevance_score")
    if relevance is not None and isinstance(relevance, (int, float)):
        return relevance  # 0-1 range

    # Try the pending / tech-summary format — items list
    items = data.get("items")
    if isinstance(items, list) and len(items) > 0:
        # For aggregate files, we return the average score of all items
        scores = [it["score"] for it in items if isinstance(it.get("score"), (int, float))]
        if scores:
            return sum(scores) / len(scores)
    return None


def _get_summary(data: dict) -> str | None:
    """Extract the summary text."""
    summary = _get_nested(data, "content.summary")
    if summary is not None:
        return summary

    # pending format: items[0].summary
    items = data.get("items")
    if isinstance(items, list) and len(items) > 0:
        return str(items[0].get("summary", ""))
    return None


def _get_tags(data: dict) -> list[str] | None:
    """Extract tags list."""
    tags = _get_nested(data, "analysis.tags")
    if tags is not None:
        return tags

    items = data.get("items")
    if isinstance(items, list) and len(items) > 0:
        return items[0].get("tags")
    return None


def _get_raw_text(data: dict) -> str:
    """Collect all text fields for buzzword scanning."""
    texts: list[str] = []

    title = data.get("title", "")
    if title:
        texts.append(str(title))

    source_meta = data.get("source_metadata")
    if isinstance(source_meta, dict):
        desc = source_meta.get("description", "")
        if desc:
            texts.append(str(desc))

    content = data.get("content")
    if isinstance(content, dict):
        for key in ("raw", "summary"):
            val = content.get(key)
            if val:
                texts.append(str(val))
        key_points = content.get("key_points")
        if isinstance(key_points, list):
            texts.extend(str(kp) for kp in key_points if kp)

    analysis = data.get("analysis")
    if isinstance(analysis, dict):
        reason = analysis.get("relevance_reason", "")
        if reason:
            texts.append(str(reason))

    # pending format — items
    items = data.get("items")
    if isinstance(items, list):
        for item in items:
            texts.append(str(item.get("summary", "")))
            texts.append(str(item.get("score_reason", "")))
            highlights = item.get("highlights", [])
            if isinstance(highlights, list):
                texts.extend(str(h) for h in highlights)

    return "\n".join(texts)


def _has_timestamps(data: dict) -> bool:
    """Check that timestamps object exists with at least one valid timestamp."""
    ts = data.get("timestamps")
    if not isinstance(ts, dict):
        return False
    for value in ts.values():
        if isinstance(value, str) and TIMESTAMP_PATTERN.search(value):
            return True
    return False


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------


def _score_summary(data: dict) -> DimensionScore:
    """Score the summary quality dimension (0-25)."""
    detail_parts: list[str] = []
    summary = _get_summary(data)

    if not summary or not summary.strip():
        return DimensionScore(
            name="Summary",
            score=0,
            max_score=MAX_SUMMARY_QUALITY,
            detail="No summary found",
        )

    length = len(summary.strip())
    score = 0.0

    if length >= SUMMARY_FULL_LENGTH:
        score = MAX_SUMMARY_QUALITY
        detail_parts.append(f"{length} chars (full marks)")
    elif length >= SUMMARY_BASE_LENGTH:
        # Linear interpolation: SUMMARY_BASE_LENGTH → SUMMARY_BASE_SCORE,
        # SUMMARY_FULL_LENGTH → MAX_SUMMARY_QUALITY
        ratio = (length - SUMMARY_BASE_LENGTH) / (SUMMARY_FULL_LENGTH - SUMMARY_BASE_LENGTH)
        score = SUMMARY_BASE_SCORE + ratio * (MAX_SUMMARY_QUALITY - SUMMARY_BASE_SCORE)
        detail_parts.append(f"{length} chars (partial: {score:.1f})")
    else:
        score = 0.0
        detail_parts.append(f"{length} chars (below {SUMMARY_BASE_LENGTH} minimum)")

    # Keyword bonus: up to 5 extra points (capped at max_score)
    lower = summary.lower()
    bonus = 0.0
    for kw in TECHNICAL_KEYWORDS:
        if kw.lower() in lower:
            bonus += 2.0
    bonus = min(bonus, 5.0)
    score = min(score + bonus, float(MAX_SUMMARY_QUALITY))
    if bonus > 0:
        detail_parts.append(f"keyword bonus: +{bonus:.0f}")

    return DimensionScore(
        name="Summary",
        score=round(score, 1),
        max_score=MAX_SUMMARY_QUALITY,
        detail="; ".join(detail_parts),
    )


def _score_tech_depth(data: dict) -> DimensionScore:
    """Score the technical depth dimension (0-25)."""
    raw_score = _get_item_score(data)

    if raw_score is None:
        return DimensionScore(
            name="TechDepth",
            score=0,
            max_score=MAX_TECH_DEPTH,
            detail="No score field found",
        )

    # Map relevance score (0.0-1.0) or item score (1-10) to 0-25
    if raw_score <= 1.0:
        # 0.0-1.0 range → linear to 0-25
        mapped = raw_score * MAX_TECH_DEPTH
    else:
        # 1-10 range → linear to 0-25
        clamped = max(1, min(10, raw_score))
        mapped = (clamped - 1) / 9 * MAX_TECH_DEPTH

    detail = f"raw={raw_score} → mapped={mapped:.1f}/{MAX_TECH_DEPTH}"
    return DimensionScore(
        name="TechDepth",
        score=round(mapped, 1),
        max_score=MAX_TECH_DEPTH,
        detail=detail,
    )


def _score_format(data: dict) -> DimensionScore:
    """Score the format compliance dimension (0-20)."""
    earned = 0
    missing: list[str] = []

    for field in FORMAT_FIELDS:
        if field == "timestamps":
            if _has_timestamps(data):
                earned += FORMAT_POINTS_PER_FIELD
            else:
                missing.append("timestamps")
        elif field == "id":
            raw_id = data.get("id")
            if isinstance(raw_id, str) and UUID_PATTERN.match(raw_id):
                earned += FORMAT_POINTS_PER_FIELD
            else:
                missing.append("id")
        elif field == "source_url":
            url = data.get("source_url")
            if isinstance(url, str) and URL_PATTERN.match(url):
                earned += FORMAT_POINTS_PER_FIELD
            else:
                missing.append("source_url")
        else:
            val = data.get(field)
            if isinstance(val, str) and val.strip():
                earned += FORMAT_POINTS_PER_FIELD
            else:
                missing.append(field)

    detail = f"{earned}/{MAX_FORMAT_COMPLIANCE}"
    if missing:
        detail += f"  missing: {', '.join(missing)}"

    return DimensionScore(
        name="Format",
        score=earned,
        max_score=MAX_FORMAT_COMPLIANCE,
        detail=detail,
    )


def _score_tags(data: dict) -> DimensionScore:
    """Score the tag precision dimension (0-15)."""
    tags = _get_tags(data)

    if not tags or not isinstance(tags, list):
        return DimensionScore(
            name="Tags",
            score=0,
            max_score=MAX_TAG_PRECISION,
            detail="No tags found",
        )

    count = len(tags)
    valid_count = sum(1 for t in tags if t in VALID_TAGS)
    invalid = [t for t in tags if t not in VALID_TAGS]

    # Optimal: 1-3 tags with high validity
    if count == 0:
        score = 0.0
    elif count == 1:
        score = MAX_TAG_PRECISION * 0.85 if valid_count == 1 else MAX_TAG_PRECISION * 0.5
    elif count == 2:
        score = MAX_TAG_PRECISION * 0.95 if valid_count >= 2 else MAX_TAG_PRECISION * 0.6
    elif count == 3:
        score = float(MAX_TAG_PRECISION) if valid_count >= 3 else MAX_TAG_PRECISION * 0.7
    elif count <= 5:
        score = MAX_TAG_PRECISION * 0.8 if valid_count >= 3 else MAX_TAG_PRECISION * 0.5
    else:
        score = MAX_TAG_PRECISION * 0.6

    # Penalty for invalid tags
    if invalid:
        penalty = min(len(invalid) * 2.0, score * 0.5)
        score -= penalty

    score = max(0.0, min(score, float(MAX_TAG_PRECISION)))

    detail_parts = [f"{count} tags", f"{valid_count} valid"]
    if invalid:
        detail_parts.append(f"invalid: {invalid}")
    detail_parts.append(f"score: {score:.1f}")

    return DimensionScore(
        name="Tags",
        score=round(score, 1),
        max_score=MAX_TAG_PRECISION,
        detail="; ".join(detail_parts),
    )


def _score_buzzwords(data: dict) -> DimensionScore:
    """Score the buzzword detection dimension (0-15).

    Starts at max, deducts per unique buzzword found. Heavier penalty for
    exact phrase matches.
    """
    text = _get_raw_text(data)
    if not text.strip():
        return DimensionScore(
            name="Buzzword",
            score=MAX_BUZZWORD_DETECTION,
            max_score=MAX_BUZZWORD_DETECTION,
            detail="No text to scan",
        )

    found: list[str] = []
    penalty = 0.0

    for pattern in _BUZZWORD_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            word = matches[0].strip().lower()
            # Avoid duplicate entries (case-insensitive)
            if word not in {f.lower() for f in found}:
                found.append(matches[0].strip())
                penalty += 3.0  # 3 points per unique buzzword

    score = max(0.0, float(MAX_BUZZWORD_DETECTION) - penalty)

    detail_parts = [f"score: {score:.1f}"]
    if found:
        detail_parts.append(f"buzzwords found: {found}")

    return DimensionScore(
        name="Buzzword",
        score=round(score, 1),
        max_score=MAX_BUZZWORD_DETECTION,
        detail="; ".join(detail_parts),
    )


# ---------------------------------------------------------------------------
# Single-file quality check
# ---------------------------------------------------------------------------


def check_file(file_path: Path) -> QualityReport | None:
    """Run all 5 dimension scorers against a single JSON file.

    Args:
        file_path: Path to the JSON file.

    Returns:
        A QualityReport, or None if the file could not be read / parsed.
    """
    try:
        raw = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"  [{BAR_FAIL}] Cannot read: {exc}", file=sys.stderr)
        return None

    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"  [{BAR_FAIL}] Invalid JSON: {exc}", file=sys.stderr)
        return None

    if not isinstance(data, dict):
        print(f"  [{BAR_FAIL}] Root is not a JSON object", file=sys.stderr)
        return None

    dimensions = [
        _score_summary(data),
        _score_tech_depth(data),
        _score_format(data),
        _score_tags(data),
        _score_buzzwords(data),
    ]

    return QualityReport(file=str(file_path), dimensions=dimensions)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------


def _progress_bar(report: QualityReport) -> str:
    """Render a visual progress bar coloured by grade."""
    ratio = report.total / report.max_total
    filled = int(ratio * BAR_WIDTH)
    bar = BAR_FILL * filled + BAR_EMPTY * (BAR_WIDTH - filled)
    return bar


def _grade_color(grade: str) -> str:
    """Return a grade with color-like visual weight (plain-text only)."""
    if grade == "A":
        return f"[{grade}]"
    if grade == "B":
        return f"[{grade}]"
    return f"[{grade}]"


def print_report(report: QualityReport) -> None:
    """Print a single quality report to stdout."""
    bar = _progress_bar(report)
    grade_tag = _grade_color(report.grade)

    print(f"  {bar}  {report.total:5.1f}/{report.max_total}  Grade {grade_tag}")

    for dim in report.dimensions:
        pct = dim.percentage
        marker = BAR_DONE if dim.score >= dim.max_score * 0.6 else BAR_FAIL
        print(f"    {marker} {dim.name:10s}  {dim.score:5.1f}/{dim.max_score:<3d}  ({pct:5.1f}%)  {dim.detail}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _expand_paths(raw_paths: list[str]) -> list[Path]:
    """Expand glob patterns and return a sorted list of unique JSON files."""
    expanded: set[Path] = set()
    for raw in raw_paths:
        p = Path(raw)
        if "*" in raw:
            expanded.update(sorted(p.parent.glob(p.name)))
        else:
            if p.exists():
                expanded.add(p.resolve())
            else:
                print(f"Warning: file not found — {p}", file=sys.stderr)
    return sorted(expanded)


def main() -> int:
    """Entry point. Returns 0 on success, 1 if any file grades C."""
    if len(sys.argv) < 2:
        print("Usage: python hooks/check_quality.py <json_file> [json_file2 ...]", file=sys.stderr)
        return 1

    files = _expand_paths(sys.argv[1:])

    if not files:
        print("No JSON files found to check.", file=sys.stderr)
        return 1

    # --- Score ---
    reports: list[QualityReport] = []
    skipped: int = 0
    total_files = len(files)

    for f in files:
        if f.suffix != ".json":
            print(f"  [{BAR_FAIL}] Skipped (not .json): {f}")
            skipped += 1
            continue

        print(f"\n── {f.name} ──")
        report = check_file(f)
        if report is None:
            skipped += 1
            continue
        reports.append(report)
        print_report(report)

    # --- Summary ---
    grade_counts = {"A": 0, "B": 0, "C": 0}
    for r in reports:
        grade_counts[r.grade] += 1

    has_c = grade_counts["C"] > 0

    print(f"\n{'=' * 60}")
    print(f"Quality Check Summary")
    print(f"{'=' * 60}")
    print(f"Files scanned : {total_files}")
    print(f"Scored        : {len(reports)}")
    print(f"Skipped/failed: {skipped}")
    print(f"Grade A       : {grade_counts['A']}")
    print(f"Grade B       : {grade_counts['B']}")
    print(f"Grade C       : {grade_counts['C']}")
    print()

    if has_c:
        print("Result: FAIL — one or more entries grade C")
        return 1

    print("Result: PASS — all entries grade B or above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
