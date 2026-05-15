#!/usr/bin/env python3
"""Run OpenAI-only LLM calls from a manifest."""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = PROJECT_DIR / "outputs" / "manifests" / "dev_pilot_manifest.csv"
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


ITEM_EVIDENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["evidence_scores", "evidence_total", "rationale"],
    "properties": {
        "evidence_scores": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "no_interest",
                "depressed_mood",
                "sleep",
                "tired",
                "appetite",
                "failure",
                "concentration",
                "psychomotor",
            ],
            "properties": {
                "no_interest": {"type": "integer", "enum": [0, 1, 2, 3]},
                "depressed_mood": {"type": "integer", "enum": [0, 1, 2, 3]},
                "sleep": {"type": "integer", "enum": [0, 1, 2, 3]},
                "tired": {"type": "integer", "enum": [0, 1, 2, 3]},
                "appetite": {"type": "integer", "enum": [0, 1, 2, 3]},
                "failure": {"type": "integer", "enum": [0, 1, 2, 3]},
                "concentration": {"type": "integer", "enum": [0, 1, 2, 3]},
                "psychomotor": {"type": "integer", "enum": [0, 1, 2, 3]},
            },
        },
        "evidence_total": {"type": "integer"},
        "rationale": {"type": "string"},
    },
}


GLOBAL_BINARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["global_binary_judgment", "confidence", "rationale"],
    "properties": {
        "global_binary_judgment": {"type": "integer", "enum": [0, 1]},
        "confidence": {"type": "number"},
        "rationale": {"type": "string"},
    },
}


def load_env_file(env_path: Path = PROJECT_DIR / ".env") -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run OpenAI Responses API calls for gpt rows in a manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Manifest CSV to run.",
    )
    parser.add_argument(
        "--openai-model",
        default=DEFAULT_MODEL,
        help="OpenAI model ID. Defaults to OPENAI_MODEL or gpt-4o-mini.",
    )
    parser.add_argument(
        "--model-family",
        default="gpt",
        help="Manifest model_family to run. This script only supports gpt.",
    )
    parser.add_argument(
        "--output-model-dir",
        default=None,
        help=(
            "Optional model-specific output directory name to replace the "
            "manifest's model_family path component, e.g. gpt-4o."
        ),
    )
    parser.add_argument(
        "--interview-id",
        action="append",
        default=None,
        help="Only run rows for this interview ID. May be repeated.",
    )
    parser.add_argument(
        "--condition",
        action="append",
        default=None,
        help="Only run rows for this condition. May be repeated.",
    )
    parser.add_argument(
        "--prompt-type",
        action="append",
        default=None,
        help="Only run rows for this prompt type. May be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of pending calls to run.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run rows even if the output_path already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned calls without making API requests.",
    )
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.0,
        help="Optional pause between API calls.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=5,
        help="Maximum retry attempts for transient API failures such as rate limits.",
    )
    parser.add_argument(
        "--retry-sleep-seconds",
        type=float,
        default=10.0,
        help="Base sleep interval between retries; actual sleep scales by attempt.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=600,
        help="Maximum output tokens per response.",
    )
    return parser.parse_args()


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


def split_prompt_template(prompt_text: str) -> tuple[str, str]:
    system_marker = "SYSTEM:"
    user_marker = "\nUSER:"
    if not prompt_text.startswith(system_marker) or user_marker not in prompt_text:
        raise ValueError("Prompt template must contain SYSTEM: and USER: sections")
    system_part, user_part = prompt_text.split(user_marker, 1)
    return system_part[len(system_marker) :].strip(), user_part.strip()


def render_prompt(row: dict[str, str]) -> tuple[str, str]:
    prompt_path = resolve_project_path(row["prompt_path"])
    transcript_path = resolve_project_path(row["transcript_path"])
    prompt_text = prompt_path.read_text(encoding="utf-8")
    transcript_text = transcript_path.read_text(encoding="utf-8")
    prompt_text = prompt_text.replace("{METADATA}", row["metadata_text"])
    prompt_text = prompt_text.replace("{TRANSCRIPT}", transcript_text)
    if "{METADATA}" in prompt_text or "{TRANSCRIPT}" in prompt_text:
        raise ValueError(f"Unrendered placeholder remains for row {row}")
    return split_prompt_template(prompt_text)


def response_schema(prompt_type: str) -> tuple[str, dict[str, Any]]:
    if prompt_type == "item_evidence":
        return "item_evidence_response", ITEM_EVIDENCE_SCHEMA
    if prompt_type == "global_binary":
        return "global_binary_response", GLOBAL_BINARY_SCHEMA
    raise ValueError(f"Unsupported prompt_type: {prompt_type}")


def build_payload(row: dict[str, str], openai_model: str, max_output_tokens: int) -> dict[str, Any]:
    system_text, user_text = render_prompt(row)
    schema_name, schema = response_schema(row["prompt_type"])
    return {
        "model": openai_model,
        "instructions": system_text,
        "input": [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_text}],
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            }
        },
        "max_output_tokens": max_output_tokens,
        "store": False,
        "metadata": {
            "interview_id": row["interview_id"],
            "condition": row["condition"],
            "prompt_type": row["prompt_type"],
            "metadata_condition": row["metadata_condition"],
        },
    }


def extract_output_text(response: dict[str, Any]) -> str | None:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return content["text"]
    return None


def call_openai(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        OPENAI_RESPONSES_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {error_body}") from exc


def is_retryable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "429" in message
        or "503" in message
        or "rate_limit" in message
        or "unavailable" in message
        or "temporarily unavailable" in message
        or "timeout" in message
        or "timed out" in message
    )


def call_openai_with_retries(
    payload: dict[str, Any],
    api_key: str,
    max_retries: int,
    retry_sleep_seconds: float,
) -> dict[str, Any]:
    for attempt in range(max_retries + 1):
        try:
            return call_openai(payload, api_key)
        except Exception as exc:
            if attempt >= max_retries or not is_retryable_error(exc):
                raise
            sleep_seconds = retry_sleep_seconds * (attempt + 1)
            print(f"Retryable API error: {exc}. Sleeping {sleep_seconds:.1f}s before retry.")
            time.sleep(sleep_seconds)
    raise RuntimeError("Unreachable retry state")


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def output_is_ok(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return record.get("status") == "ok"


def row_matches_filters(row: dict[str, str], args: argparse.Namespace) -> bool:
    if args.interview_id is not None and row.get("interview_id") not in args.interview_id:
        return False
    if args.condition is not None and row.get("condition") not in args.condition:
        return False
    if args.prompt_type is not None and row.get("prompt_type") not in args.prompt_type:
        return False
    return True


def append_run_log(log_path: Path, record: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    load_env_file()
    args = parse_args()
    if args.model_family != "gpt":
        raise SystemExit("run_openai_manifest.py only supports --model-family gpt")

    manifest_path = args.manifest if args.manifest.is_absolute() else Path.cwd() / args.manifest
    rows = [
        row
        for row in read_manifest(manifest_path)
        if row.get("model_family") == args.model_family
        and row_matches_filters(row, args)
    ]
    pending = [
        row
        for row in rows
        if args.force
        or not output_is_ok(resolve_project_path(rewrite_output_path(row["output_path"], args.output_model_dir)))
    ]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"Manifest rows for {args.model_family}: {len(rows)}")
    print(f"Pending rows selected: {len(pending)}")
    print(f"OpenAI model: {args.openai_model}")

    if args.dry_run:
        for row in pending[:10]:
            print(
                "DRY RUN",
                row["interview_id"],
                row["condition"],
                row["prompt_type"],
                rewrite_output_path(row["output_path"], args.output_model_dir),
            )
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is not set. Export it before running API calls.")

    log_path = PROJECT_DIR / "outputs" / "run_logs" / "openai_manifest_runs.jsonl"
    for index, row in enumerate(pending, start=1):
        effective_output_path_text = rewrite_output_path(row["output_path"], args.output_model_dir)
        output_path = resolve_project_path(effective_output_path_text)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(timezone.utc).isoformat()
        print(
            f"[{index}/{len(pending)}] {row['interview_id']} "
            f"{row['condition']} {row['prompt_type']}"
        )
        try:
            payload = build_payload(row, args.openai_model, args.max_output_tokens)
            response = call_openai_with_retries(
                payload,
                api_key,
                max_retries=args.max_retries,
                retry_sleep_seconds=args.retry_sleep_seconds,
            )
            output_text = extract_output_text(response)
            output_json = json.loads(output_text) if output_text is not None else None
            record = {
                "status": "ok",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "openai_model": args.openai_model,
                "effective_output_path": effective_output_path_text,
                "manifest_row": row,
                "output_json": output_json,
                "raw_response": response,
            }
            output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            append_run_log(
                log_path,
                {
                    "status": "ok",
                    "openai_model": args.openai_model,
                    "output_path": effective_output_path_text,
                    "manifest_output_path": row["output_path"],
                    "row": row,
                },
            )
        except Exception as exc:  # noqa: BLE001 - preserve failed row context in run log.
            error_record = {
                "status": "error",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "openai_model": args.openai_model,
                "effective_output_path": effective_output_path_text,
                "manifest_row": row,
                "error": str(exc),
            }
            output_path.write_text(
                json.dumps(error_record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            append_run_log(
                log_path,
                {
                    "status": "error",
                    "openai_model": args.openai_model,
                    "output_path": effective_output_path_text,
                    "manifest_output_path": row["output_path"],
                    "row": row,
                    "error": str(exc),
                },
            )
            raise

        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
