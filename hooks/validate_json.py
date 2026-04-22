#!/usr/bin/env python3
"""Knowledge entry JSON validation script.

Validates knowledge entry JSON files against the schema defined in AGENTS.md.
Supports single file and glob (*.json) input modes.

Usage:
    python hooks/validate_json.py <json_file> [json_file2 ...]
    python hooks/validate_json.py knowledge/articles/pending/*.json

Exit code:
    0 — all files pass validation
    1 — one or more files have errors
"""

import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Schema definition
# ---------------------------------------------------------------------------

# Top-level required fields (direct access)
REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source_url": str,
    "status": str,
}

# Nested required fields under content.*
NESTED_REQUIRED_FIELDS: dict[str, tuple[str, type]] = {
    "content.summary": ("content", str),
    "analysis.tags": ("analysis", list),
}

VALID_STATUSES = {"draft", "review", "published", "archived", "analyzed", "processing"}
VALID_AUDIENCES = {"beginner", "intermediate", "advanced"}

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"^https?://")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _path_label(path: Path) -> str:
    """Return a short human-readable label for a file path."""
    return str(path)


def _get_nested(data: dict, dotted_key: str):
    """Resolve a dotted key like 'content.summary' against a nested dict."""
    parts = dotted_key.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _validate_required_fields(data: dict, path: Path) -> list[str]:
    """Check presence and type of every required field (top-level + nested)."""
    errors: list[str] = []
    label = _path_label(path)

    # Top-level fields
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"[{label}] Missing required field: {field!r}")
            continue

        value = data[field]
        if not isinstance(value, expected_type):
            errors.append(
                f"[{label}] Field {field!r} has wrong type: "
                f"expected {expected_type.__name__}, got {type(value).__name__}"
            )
    # Nested fields
    for dotted_key, (parent_key, expected_type) in NESTED_REQUIRED_FIELDS.items():
        if parent_key not in data or not isinstance(data[parent_key], dict):
            errors.append(f"[{label}] Missing parent object: {parent_key!r}")
            continue
        value = _get_nested(data, dotted_key)
        if value is None:
            errors.append(f"[{label}] Missing required nested field: {dotted_key!r}")
            continue
        if not isinstance(value, expected_type):
            errors.append(
                f"[{label}] Field {dotted_key!r} has wrong type: "
                f"expected {expected_type.__name__}, got {type(value).__name__}"
            )
    return errors


def _validate_id(data: dict, path: Path) -> list[str]:
    """Validate id format: UUID v4."""
    errors: list[str] = []
    raw_id = data.get("id")
    if not isinstance(raw_id, str):
        return errors  # type error already reported by required-fields check

    if not UUID_PATTERN.match(raw_id):
        errors.append(
            f"[{_path_label(path)}] Invalid id format: {raw_id!r} — "
            f"expected UUID v4 (e.g. 4bb86a14-608a-4a0b-a7d1-2404224cd7b6)"
        )
    return errors


def _validate_status(data: dict, path: Path) -> list[str]:
    """Validate status field against allowed values."""
    errors: list[str] = []
    status = data.get("status")
    if not isinstance(status, str):
        return errors

    if status not in VALID_STATUSES:
        valid = ", ".join(sorted(VALID_STATUSES))
        errors.append(
            f"[{_path_label(path)}] Invalid status: {status!r} — "
            f"must be one of {{{valid}}}"
        )
    return errors


def _validate_url(data: dict, path: Path) -> list[str]:
    """Validate source_url starts with http:// or https://."""
    errors: list[str] = []
    url = data.get("source_url")
    if not isinstance(url, str):
        return errors

    if not URL_PATTERN.match(url):
        errors.append(
            f"[{_path_label(path)}] Invalid source_url: {url!r} — "
            f"must start with http:// or https://"
        )
    return errors


def _validate_summary(data: dict, path: Path) -> list[str]:
    """Validate content.summary meets minimum length (20 characters)."""
    errors: list[str] = []
    summary = _get_nested(data, "content.summary")
    if not isinstance(summary, str):
        return errors

    if len(summary.strip()) < 20:
        errors.append(
            f"[{_path_label(path)}] Summary too short ({len(summary.strip())} chars) "
            f"— minimum 20 characters required"
        )
    return errors


def _validate_tags(data: dict, path: Path) -> list[str]:
    """Validate analysis.tags is a non-empty list of strings."""
    errors: list[str] = []
    tags = _get_nested(data, "analysis.tags")
    if not isinstance(tags, list):
        return errors

    if len(tags) == 0:
        errors.append(
            f"[{_path_label(path)}] Tags list is empty — "
            f"at least 1 tag is required"
        )
    else:
        non_strings = [i for i, t in enumerate(tags) if not isinstance(t, str)]
        if non_strings:
            errors.append(
                f"[{_path_label(path)}] Tags contains non-string entries "
                f"at index(es): {non_strings}"
            )
    return errors


def _validate_optional_score(data: dict, path: Path) -> list[str]:
    """Validate analysis.relevance_score (if present) is a number between 0 and 1."""
    errors: list[str] = []
    score = _get_nested(data, "analysis.relevance_score")
    if score is None:
        return errors

    if not isinstance(score, (int, float)):
        errors.append(
            f"[{_path_label(path)}] analysis.relevance_score must be a number, "
            f"got {type(score).__name__}"
        )
    elif score < 0 or score > 1:
        errors.append(
            f"[{_path_label(path)}] analysis.relevance_score {score} is out of range — "
            f"must be between 0 and 1 (inclusive)"
        )
    return errors


def _validate_optional_audience(data: dict, path: Path) -> list[str]:
    """Validate technical_details.complexity (if present) is one of allowed values.

    Maps the field 'content.technical_details.complexity' to audience validation
    since the actual schema uses 'complexity' for audience-like classification.
    """
    errors: list[str] = []
    complexity = _get_nested(data, "content.technical_details.complexity")
    if complexity is None:
        return errors

    if not isinstance(complexity, str):
        errors.append(
            f"[{_path_label(path)}] content.technical_details.complexity must be a string, "
            f"got {type(complexity).__name__}"
        )
    elif complexity not in VALID_AUDIENCES:
        valid = ", ".join(sorted(VALID_AUDIENCES))
        errors.append(
            f"[{_path_label(path)}] Invalid complexity: {complexity!r} — "
            f"must be one of {{{valid}}}"
        )
    return errors


# ---------------------------------------------------------------------------
# Single-file validation
# ---------------------------------------------------------------------------


def validate_file(file_path: Path) -> list[str]:
    """Run all validation rules against a single JSON file.

    Args:
        file_path: Path to the JSON file to validate.

    Returns:
        A list of error messages (empty if the file is valid).
    """
    errors: list[str] = []

    # --- Parse JSON ---
    try:
        raw = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"[{_path_label(file_path)}] Cannot read file: {exc}"]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return [f"[{_path_label(file_path)}] Invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return [
            f"[{_path_label(file_path)}] Root value must be a JSON object (dict), "
            f"got {type(data).__name__}"
        ]

    # --- Run validators ---
    errors.extend(_validate_required_fields(data, file_path))
    errors.extend(_validate_id(data, file_path))
    errors.extend(_validate_status(data, file_path))
    errors.extend(_validate_url(data, file_path))
    errors.extend(_validate_summary(data, file_path))
    errors.extend(_validate_tags(data, file_path))
    errors.extend(_validate_optional_score(data, file_path))
    errors.extend(_validate_optional_audience(data, file_path))

    return errors


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
    """Entry point. Returns 0 on success, 1 on failure."""
    if len(sys.argv) < 2:
        print("Usage: python hooks/validate_json.py <json_file> [json_file2 ...]", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print("  python hooks/validate_json.py knowledge/articles/processed/*.json", file=sys.stderr)
        print("  python hooks/validate_json.py path/to/article.json", file=sys.stderr)
        print("\nNote: This script validates knowledge entry JSON files against the schema", file=sys.stderr)
        print("      defined in AGENTS.md section 5.", file=sys.stderr)
        return 1

    files = _expand_paths(sys.argv[1:])

    if not files:
        print("No JSON files found to validate.", file=sys.stderr)
        return 1

    # --- Validate ---
    all_errors: dict[str, list[str]] = {}
    total_files = len(files)

    for f in files:
        if f.suffix != ".json":
            all_errors[str(f)] = [f"Skipped: not a .json file"]
            continue
        errs = validate_file(f)
        if errs:
            all_errors[str(f)] = errs

    # --- Report ---
    error_count = len(all_errors)
    success_count = total_files - error_count

    print(f"\n{'=' * 60}")
    print(f"Knowledge Entry JSON Validation")
    print(f"{'=' * 60}")
    print(f"Files scanned : {total_files}")
    print(f"Passed       : {success_count}")
    print(f"Failed       : {error_count}")
    print()

    if error_count > 0:
        print(f"{'─' * 60}")
        for file_path, errs in sorted(all_errors.items()):
            print(f"\n  ✗ {file_path}  ({len(errs)} error{'s' if len(errs) > 1 else ''})")
            for err in errs:
                print(f"    • {err}")
        print(f"\n{'─' * 60}")
        return 1

    print("All files passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
