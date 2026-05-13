#!/usr/bin/env python3
"""Validate saved LLM output JSON files against prompt-specific expectations."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_DIR / "outputs" / "manifests" / "dev_pilot_manifest.csv"
ITEM_KEYS = [
    "no_interest",
    "depressed_mood",
    "sleep",
    "tired",
    "appetite",
    "failure",
    "concentration",
    "psychomotor",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate saved LLM outputs.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--model-family", default="gpt")
    parser.add_argument(
        "--output-model-dir",
        default=None,
        help=(
            "Optional model-specific output directory name to replace the "
            "manifest's model_family path component, e.g. gpt-4o."
        ),
    )
    parser.add_argument(
        "--write-summary",
        type=Path,
        default=PROJECT_DIR / "outputs" / "validation" / "dev_pilot_gpt_validation.csv",
    )
    return parser.parse_args()


def display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else Path.cwd() / path
    try:
        return str(resolved.relative_to(PROJECT_DIR))
    except ValueError:
        return str(path)


def resolve_project_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


def rewrite_output_path(path_text: str, output_model_dir: str | None) -> str:
    if output_model_dir is None:
        return path_text
    path = Path(path_text)
    parts = list(path.parts)
    try:
        dev_main_index = parts.index("dev_main")
    except ValueError as exc:
        raise ValueError(f"Cannot rewrite output path without dev_main component: {path_text}") from exc
    model_index = dev_main_index + 1
    if model_index >= len(parts):
        raise ValueError(f"Cannot rewrite output path with missing model component: {path_text}")
    parts[model_index] = output_model_dir
    return Path(*parts).as_posix()


def read_manifest(path: Path, model_family: str) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return [
            row
            for row in csv.DictReader(f)
            if row.get("model_family") == model_family
        ]


def load_output(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing_output"
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid_json_file:{exc}"
    if record.get("status") != "ok":
        return None, f"run_status_{record.get('status', 'unknown')}"
    output_json = record.get("output_json")
    if not isinstance(output_json, dict):
        return None, "missing_output_json"
    return output_json, None


def validate_item_evidence(output_json: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scores = output_json.get("evidence_scores")
    if not isinstance(scores, dict):
        return ["missing_evidence_scores"]

    item_sum = 0
    for key in ITEM_KEYS:
        value = scores.get(key)
        if not isinstance(value, int) or not 0 <= value <= 3:
            errors.append(f"invalid_{key}")
        else:
            item_sum += value

    total = output_json.get("evidence_total")
    if not isinstance(total, int) or not 0 <= total <= 24:
        errors.append("invalid_evidence_total")
    elif total != item_sum:
        errors.append(f"evidence_total_mismatch:{total}!={item_sum}")

    if not isinstance(output_json.get("rationale"), str):
        errors.append("invalid_rationale")
    extra_keys = sorted(set(output_json) - {"evidence_scores", "evidence_total", "rationale"})
    if extra_keys:
        errors.append(f"extra_keys:{'|'.join(extra_keys)}")
    return errors


def validate_global_binary(output_json: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    judgment = output_json.get("global_binary_judgment")
    if judgment not in (0, 1):
        errors.append("invalid_global_binary_judgment")

    confidence = output_json.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        errors.append("invalid_confidence")

    if not isinstance(output_json.get("rationale"), str):
        errors.append("invalid_rationale")
    extra_keys = sorted(set(output_json) - {"global_binary_judgment", "confidence", "rationale"})
    if extra_keys:
        errors.append(f"extra_keys:{'|'.join(extra_keys)}")
    return errors


def validate_row(row: dict[str, str], output_model_dir: str | None) -> dict[str, str]:
    effective_output_path = rewrite_output_path(row["output_path"], output_model_dir)
    output_path = resolve_project_path(effective_output_path)
    output_json, load_error = load_output(output_path)
    errors = [load_error] if load_error else []

    if output_json is not None:
        if row["prompt_type"] == "item_evidence":
            errors.extend(validate_item_evidence(output_json))
        elif row["prompt_type"] == "global_binary":
            errors.extend(validate_global_binary(output_json))
        else:
            errors.append(f"unsupported_prompt_type:{row['prompt_type']}")

    return {
        "interview_id": row["interview_id"],
        "condition": row["condition"],
        "prompt_type": row["prompt_type"],
        "model_family": row["model_family"],
        "output_path": effective_output_path,
        "is_valid": str(not errors),
        "errors": ";".join(error for error in errors if error),
    }


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else Path.cwd() / args.manifest
    rows = read_manifest(manifest_path, args.model_family)
    summary_rows = [validate_row(row, args.output_model_dir) for row in rows]

    args.write_summary.parent.mkdir(parents=True, exist_ok=True)
    with args.write_summary.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    valid_count = sum(row["is_valid"] == "True" for row in summary_rows)
    print(f"Validated rows: {len(summary_rows)}")
    print(f"Valid rows: {valid_count}")
    print(f"Invalid rows: {len(summary_rows) - valid_count}")
    print(f"Wrote summary: {display_path(args.write_summary)}")


if __name__ == "__main__":
    main()
