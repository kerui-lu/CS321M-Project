#!/usr/bin/env python3
"""Run Google Gemini LLM calls from a manifest."""

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

from run_openai_manifest import (
    DEFAULT_MANIFEST,
    PROJECT_DIR,
    append_run_log,
    is_retryable_error,
    load_env_file,
    output_is_ok,
    render_prompt,
    resolve_project_path,
    response_schema,
    row_matches_filters,
)


DEFAULT_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Gemini generateContent API calls for gemini rows in a manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Manifest CSV to run.",
    )
    parser.add_argument(
        "--gemini-model",
        default=DEFAULT_MODEL,
        help="Gemini model ID. Defaults to GEMINI_MODEL or gemini-2.5-flash.",
    )
    parser.add_argument(
        "--model-family",
        default="gemini",
        help="Manifest model_family to run. This script only supports gemini.",
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
    parser.add_argument(
        "--temperature",
        type=float,
        default=1.0,
        help="Sampling temperature. Defaults to 1.0 to match the GPT-4o run.",
    )
    parser.add_argument(
        "--top-p",
        type=float,
        default=1.0,
        help="Nucleus sampling topP. Defaults to 1.0 to match the GPT-4o run.",
    )
    parser.add_argument(
        "--thinking-budget",
        type=int,
        default=None,
        help=(
            "Optional Gemini thinkingBudget. Leave unset for provider default. "
            "For Gemini Pro, use 128 to cap thinking at the documented minimum."
        ),
    )
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def model_endpoint(gemini_model: str) -> str:
    model_path = gemini_model if gemini_model.startswith("models/") else f"models/{gemini_model}"
    return f"{GEMINI_BASE_URL}/{model_path}:generateContent"


def to_gemini_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Convert the canonical JSON schema into Gemini's REST schema subset."""
    converted: dict[str, Any] = {}
    for key, value in schema.items():
        if key == "additionalProperties":
            continue
        if key == "enum" and not all(isinstance(item, str) for item in value):
            continue
        if key == "properties" and isinstance(value, dict):
            converted[key] = {
                prop_key: to_gemini_schema(prop_schema)
                for prop_key, prop_schema in value.items()
            }
            continue
        if key == "items" and isinstance(value, dict):
            converted[key] = to_gemini_schema(value)
            continue
        converted[key] = value
    return converted


def build_payload(
    row: dict[str, str],
    max_output_tokens: int,
    temperature: float,
    top_p: float,
    thinking_budget: int | None,
) -> dict[str, Any]:
    system_text, user_text = render_prompt(row)
    _, schema = response_schema(row["prompt_type"])
    gemini_schema = to_gemini_schema(schema)
    generation_config: dict[str, Any] = {
        "maxOutputTokens": max_output_tokens,
        "temperature": temperature,
        "topP": top_p,
        "responseMimeType": "application/json",
        "responseSchema": gemini_schema,
    }
    if thinking_budget is not None:
        generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}

    return {
        "systemInstruction": {
            "parts": [{"text": system_text}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_text}],
            }
        ],
        "generationConfig": generation_config,
    }


def call_gemini(payload: dict[str, Any], api_key: str, gemini_model: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        model_endpoint(gemini_model),
        data=body,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini API error {exc.code}: {error_body}") from exc


def call_gemini_with_retries(
    payload: dict[str, Any],
    api_key: str,
    gemini_model: str,
    max_retries: int,
    retry_sleep_seconds: float,
) -> dict[str, Any]:
    for attempt in range(max_retries + 1):
        try:
            return call_gemini(payload, api_key, gemini_model)
        except Exception as exc:
            if attempt >= max_retries or not is_retryable_error(exc):
                raise
            sleep_seconds = retry_sleep_seconds * (attempt + 1)
            print(f"Retryable API error: {exc}. Sleeping {sleep_seconds:.1f}s before retry.")
            time.sleep(sleep_seconds)
    raise RuntimeError("Unreachable retry state")


def extract_output_text(response: dict[str, Any]) -> str | None:
    text_parts: list[str] = []
    for candidate in response.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
        if text_parts:
            return "".join(text_parts)
    return None


def main() -> None:
    load_env_file()
    args = parse_args()
    if args.model_family != "gemini":
        raise SystemExit("run_gemini_manifest.py only supports --model-family gemini")

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
        if args.force or not output_is_ok(resolve_project_path(row["output_path"]))
    ]
    if args.limit is not None:
        pending = pending[: args.limit]

    print(f"Manifest rows for {args.model_family}: {len(rows)}")
    print(f"Pending rows selected: {len(pending)}")
    print(f"Gemini model: {args.gemini_model}")
    print(f"Temperature: {args.temperature}")
    print(f"Top-p: {args.top_p}")
    print(f"Max output tokens: {args.max_output_tokens}")
    print(f"Thinking budget: {args.thinking_budget if args.thinking_budget is not None else 'provider default'}")

    if args.dry_run:
        for row in pending[:10]:
            print(
                "DRY RUN",
                row["interview_id"],
                row["condition"],
                row["prompt_type"],
                row["output_path"],
            )
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY is not set. Export it before running API calls.")

    log_path = PROJECT_DIR / "outputs" / "run_logs" / "gemini_manifest_runs.jsonl"
    for index, row in enumerate(pending, start=1):
        output_path = resolve_project_path(row["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(timezone.utc).isoformat()
        response: dict[str, Any] | None = None
        print(
            f"[{index}/{len(pending)}] {row['interview_id']} "
            f"{row['condition']} {row['prompt_type']}"
        )
        try:
            payload = build_payload(
                row,
                args.max_output_tokens,
                args.temperature,
                args.top_p,
                args.thinking_budget,
            )
            response = call_gemini_with_retries(
                payload,
                api_key,
                args.gemini_model,
                max_retries=args.max_retries,
                retry_sleep_seconds=args.retry_sleep_seconds,
            )
            output_text = extract_output_text(response)
            if output_text is None:
                raise ValueError("Gemini response did not include a text part")
            output_json = json.loads(output_text)
            record = {
                "status": "ok",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "provider": "Google",
                "model_name": args.gemini_model,
                "gemini_model": args.gemini_model,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "max_output_tokens": args.max_output_tokens,
                "thinking_budget": args.thinking_budget,
                "effective_output_path": row["output_path"],
                "manifest_row": row,
                "output_json": output_json,
                "raw_response": response,
            }
            output_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            append_run_log(
                log_path,
                {
                    "status": "ok",
                    "provider": "Google",
                    "model_name": args.gemini_model,
                    "temperature": args.temperature,
                    "top_p": args.top_p,
                    "max_output_tokens": args.max_output_tokens,
                    "thinking_budget": args.thinking_budget,
                    "output_path": row["output_path"],
                    "row": row,
                },
            )
        except Exception as exc:  # noqa: BLE001 - preserve failed row context in run log.
            error_record = {
                "status": "error",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "provider": "Google",
                "model_name": args.gemini_model,
                "gemini_model": args.gemini_model,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "max_output_tokens": args.max_output_tokens,
                "thinking_budget": args.thinking_budget,
                "effective_output_path": row["output_path"],
                "manifest_row": row,
                "error": str(exc),
            }
            if response is not None:
                error_record["raw_response"] = response
            output_path.write_text(
                json.dumps(error_record, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            append_run_log(
                log_path,
                {
                    "status": "error",
                    "provider": "Google",
                    "model_name": args.gemini_model,
                    "temperature": args.temperature,
                    "top_p": args.top_p,
                    "max_output_tokens": args.max_output_tokens,
                    "thinking_budget": args.thinking_budget,
                    "output_path": row["output_path"],
                    "row": row,
                    "error": str(exc),
                },
            )
            raise

        if args.sleep_seconds:
            time.sleep(args.sleep_seconds)


if __name__ == "__main__":
    main()
