#!/usr/bin/env python3
"""Build condition-specific analysis CSVs from validated LLM outputs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_DIR / "outputs" / "manifests" / "dev_main_manifest.csv"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "outputs" / "analysis"
CONDITIONS = ("full_transcript", "participant_only", "interviewer_only")
ITEM_KEYS = [
    ("no_interest", "pred_no_interest"),
    ("depressed_mood", "pred_depressed_mood"),
    ("sleep", "pred_sleep"),
    ("tired", "pred_tired"),
    ("appetite", "pred_appetite"),
    ("failure", "pred_failure"),
    ("concentration", "pred_concentration"),
    ("psychomotor", "pred_psychomotor"),
]
GROUND_TRUTH_COLUMNS = [
    "PHQ8_Binary",
    "PHQ8_Score",
    "Gender",
    "PHQ8_NoInterest",
    "PHQ8_Depressed",
    "PHQ8_Sleep",
    "PHQ8_Tired",
    "PHQ8_Appetite",
    "PHQ8_Failure",
    "PHQ8_Concentrating",
    "PHQ8_Moving",
]
OUTPUT_COLUMNS = [
    "interview_id",
    "provider",
    "model_name",
    "condition",
    "metadata_condition",
    "metadata_text",
    "repeat_id",
    "pred_no_interest",
    "pred_depressed_mood",
    "pred_sleep",
    "pred_tired",
    "pred_appetite",
    "pred_failure",
    "pred_concentration",
    "pred_psychomotor",
    "pred_evidence_total",
    "thresholded_item_binary",
    "item_rationale",
    "global_binary_judgment",
    "global_binary_confidence",
    "global_rationale",
    *GROUND_TRUTH_COLUMNS,
    "item_output_path",
    "global_output_path",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one LLM analysis CSV per transcript condition."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--model-family", default="gpt")
    parser.add_argument(
        "--output-model-dir",
        default="gpt-4o",
        help="Model output directory to read, e.g. gpt-4o.",
    )
    parser.add_argument(
        "--provider-label",
        default=None,
        help="Provider label to write in the analysis CSV, e.g. OpenAI.",
    )
    parser.add_argument(
        "--model-label",
        default=None,
        help="Exact model label to write in the analysis CSV, e.g. gpt-4o.",
    )
    parser.add_argument(
        "--openai-model",
        default=None,
        help="Deprecated alias for --model-label, kept for old GPT commands.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--prefix",
        default=None,
        help="Output filename prefix. Defaults to dev_<output-model-dir-without-dashes>.",
    )
    return parser.parse_args()


def default_provider_label(model_family: str) -> str:
    return {
        "gpt": "OpenAI",
        "claude": "Anthropic",
        "gemini": "Google",
    }.get(model_family, model_family)


def default_prefix(output_model_dir: str) -> str:
    return f"dev_{output_model_dir.replace('-', '')}"


def resolve_project_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return PROJECT_DIR / path


def project_rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def display_path(path: Path) -> str:
    resolved = path if path.is_absolute() else Path.cwd() / path
    try:
        return str(resolved.relative_to(PROJECT_DIR))
    except ValueError:
        return str(path)


def rewrite_output_path(path_text: str, output_model_dir: str) -> str:
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


def load_output(path_text: str) -> dict[str, Any]:
    path = resolve_project_path(path_text)
    if not path.exists():
        raise FileNotFoundError(path)
    record = json.loads(path.read_text(encoding="utf-8"))
    if record.get("status") != "ok":
        raise ValueError(f"{path_text} has non-ok status: {record.get('status')}")
    output_json = record.get("output_json")
    if not isinstance(output_json, dict):
        raise ValueError(f"{path_text} is missing output_json")
    return output_json


def get_int(value: Any, field_name: str, min_value: int, max_value: int) -> int:
    if not isinstance(value, int) or not min_value <= value <= max_value:
        raise ValueError(f"{field_name} must be an integer in [{min_value}, {max_value}], got {value!r}")
    return value


def build_item_fields(output_json: dict[str, Any]) -> dict[str, str]:
    scores = output_json.get("evidence_scores")
    if not isinstance(scores, dict):
        raise ValueError("item_evidence output missing evidence_scores")

    fields: dict[str, str] = {}
    item_sum = 0
    for source_key, output_key in ITEM_KEYS:
        value = get_int(scores.get(source_key), source_key, 0, 3)
        fields[output_key] = str(value)
        item_sum += value

    evidence_total = get_int(output_json.get("evidence_total"), "evidence_total", 0, 24)
    if evidence_total != item_sum:
        raise ValueError(f"evidence_total mismatch: {evidence_total} != {item_sum}")
    fields["pred_evidence_total"] = str(evidence_total)
    fields["thresholded_item_binary"] = str(int(evidence_total >= 10))
    fields["item_rationale"] = output_json.get("rationale", "")
    return fields


def build_global_fields(output_json: dict[str, Any]) -> dict[str, str]:
    judgment = get_int(output_json.get("global_binary_judgment"), "global_binary_judgment", 0, 1)
    confidence = output_json.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        raise ValueError(f"confidence must be a number in [0, 1], got {confidence!r}")
    return {
        "global_binary_judgment": str(judgment),
        "global_binary_confidence": str(float(confidence)),
        "global_rationale": output_json.get("rationale", ""),
    }


def build_condition_rows(
    manifest_rows: list[dict[str, str]],
    condition: str,
    output_model_dir: str,
    provider_label: str,
    model_label: str,
) -> list[dict[str, str]]:
    item_rows: dict[str, dict[str, str]] = {}
    global_rows: dict[str, dict[str, str]] = {}

    for row in manifest_rows:
        if row["condition"] != condition:
            continue
        if row["prompt_type"] == "item_evidence":
            item_rows[row["interview_id"]] = row
        elif row["prompt_type"] == "global_binary":
            global_rows[row["interview_id"]] = row

    interview_ids = sorted(set(item_rows) | set(global_rows), key=int)
    rows: list[dict[str, str]] = []
    for interview_id in interview_ids:
        if interview_id not in item_rows or interview_id not in global_rows:
            raise ValueError(f"{condition}:{interview_id} missing item or global output")

        item_manifest_row = item_rows[interview_id]
        global_manifest_row = global_rows[interview_id]
        item_output_path = rewrite_output_path(item_manifest_row["output_path"], output_model_dir)
        global_output_path = rewrite_output_path(global_manifest_row["output_path"], output_model_dir)

        item_output = load_output(item_output_path)
        global_output = load_output(global_output_path)

        result = {
            "interview_id": interview_id,
            "provider": provider_label,
            "model_name": model_label,
            "condition": condition,
            "metadata_condition": item_manifest_row["metadata_condition"],
            "metadata_text": item_manifest_row["metadata_text"],
            "repeat_id": item_manifest_row["repeat_id"],
            **build_item_fields(item_output),
            **build_global_fields(global_output),
        }
        for column in GROUND_TRUTH_COLUMNS:
            value = item_manifest_row.get(column, "")
            if value == "":
                raise ValueError(f"{condition}:{interview_id} missing ground-truth column {column}")
            result[column] = value
        result["item_output_path"] = item_output_path
        result["global_output_path"] = global_output_path
        rows.append(result)

    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_condition_rows(rows: list[dict[str, str]], condition: str) -> None:
    if len(rows) != 35:
        raise ValueError(f"{condition} expected 35 rows, found {len(rows)}")
    seen = set()
    for row in rows:
        if row["interview_id"] in seen:
            raise ValueError(f"{condition} duplicate interview_id {row['interview_id']}")
        seen.add(row["interview_id"])
        if row["condition"] != condition:
            raise ValueError(f"Unexpected condition in {condition} output: {row['condition']}")
        item_sum = sum(int(row[output_key]) for _, output_key in ITEM_KEYS)
        evidence_total = int(row["pred_evidence_total"])
        if item_sum != evidence_total:
            raise ValueError(f"{condition}:{row['interview_id']} item total mismatch")
        if int(row["thresholded_item_binary"]) != int(evidence_total >= 10):
            raise ValueError(f"{condition}:{row['interview_id']} threshold mismatch")
        if int(row["global_binary_judgment"]) not in (0, 1):
            raise ValueError(f"{condition}:{row['interview_id']} invalid global judgment")
        for column in GROUND_TRUTH_COLUMNS:
            if row[column] == "":
                raise ValueError(f"{condition}:{row['interview_id']} empty {column}")


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest if args.manifest.is_absolute() else Path.cwd() / args.manifest
    output_dir = args.output_dir if args.output_dir.is_absolute() else PROJECT_DIR / args.output_dir
    manifest_rows = read_manifest(manifest_path, args.model_family)
    provider_label = args.provider_label or default_provider_label(args.model_family)
    model_label = args.model_label or args.openai_model or args.output_model_dir
    output_prefix = args.prefix or default_prefix(args.output_model_dir)

    for condition in CONDITIONS:
        rows = build_condition_rows(
            manifest_rows,
            condition=condition,
            output_model_dir=args.output_model_dir,
            provider_label=provider_label,
            model_label=model_label,
        )
        validate_condition_rows(rows, condition)
        output_path = output_dir / f"{output_prefix}_{condition}_outputs.csv"
        write_csv(output_path, rows)
        print(f"Wrote {display_path(output_path)} with {len(rows)} rows")


if __name__ == "__main__":
    main()
