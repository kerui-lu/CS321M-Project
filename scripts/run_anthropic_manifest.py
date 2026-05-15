#!/usr/bin/env python3
"""Run Anthropic Claude LLM calls from a manifest."""

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


DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Anthropic Messages API calls for claude rows in a manifest."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Manifest CSV to run.",
    )
    parser.add_argument(
        "--anthropic-model",
        default=DEFAULT_MODEL,
        help="Anthropic model ID. Defaults to ANTHROPIC_MODEL or claude-haiku-4-5-20251001.",
    )
    parser.add_argument(
        "--model-family",
        default="claude",
        help="Manifest model_family to run. This script only supports claude.",
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
        help="Nucleus sampling top_p. Defaults to 1.0 to match the GPT-4o run.",
    )
    parser.add_argument(
        "--omit-top-p",
        action="store_true",
        help=(
            "Omit top_p from the Anthropic payload. Use this for Claude models "
            "that reject setting both temperature and top_p."
        ),
    )
    return parser.parse_args()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build_payload(
    row: dict[str, str],
    anthropic_model: str,
    max_output_tokens: int,
    temperature: float,
    top_p: float | None,
) -> dict[str, Any]:
    system_text, user_text = render_prompt(row)
    _, schema = response_schema(row["prompt_type"])
    payload = {
        "model": anthropic_model,
        "max_tokens": max_output_tokens,
        "temperature": temperature,
        "system": system_text,
        "messages": [
            {
                "role": "user",
                "content": [{"type": "text", "text": user_text}],
            }
        ],
        "output_config": {
            "format": {
                "type": "json_schema",
                "schema": schema,
            }
        },
    }
    if top_p is not None:
        payload["top_p"] = top_p
    return payload


def call_anthropic(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        ANTHROPIC_MESSAGES_URL,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Anthropic API error {exc.code}: {error_body}") from exc


def call_anthropic_with_retries(
    payload: dict[str, Any],
    api_key: str,
    max_retries: int,
    retry_sleep_seconds: float,
) -> dict[str, Any]:
    for attempt in range(max_retries + 1):
        try:
            return call_anthropic(payload, api_key)
        except Exception as exc:
            if attempt >= max_retries or not is_retryable_error(exc):
                raise
            sleep_seconds = retry_sleep_seconds * (attempt + 1)
            print(f"Retryable API error: {exc}. Sleeping {sleep_seconds:.1f}s before retry.")
            time.sleep(sleep_seconds)
    raise RuntimeError("Unreachable retry state")


def extract_output_text(response: dict[str, Any]) -> str | None:
    for item in response.get("content", []):
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            return item["text"]
    return None


def main() -> None:
    load_env_file()
    args = parse_args()
    if args.model_family != "claude":
        raise SystemExit("run_anthropic_manifest.py only supports --model-family claude")
    effective_top_p = None if args.omit_top_p else args.top_p

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
    print(f"Anthropic model: {args.anthropic_model}")
    print(f"Temperature: {args.temperature}")
    print(f"Top-p: {'omitted' if effective_top_p is None else effective_top_p}")
    print(f"Max output tokens: {args.max_output_tokens}")

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

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise SystemExit("ANTHROPIC_API_KEY is not set. Export it before running API calls.")

    log_path = PROJECT_DIR / "outputs" / "run_logs" / "anthropic_manifest_runs.jsonl"
    for index, row in enumerate(pending, start=1):
        output_path = resolve_project_path(row["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)

        started_at = datetime.now(timezone.utc).isoformat()
        print(
            f"[{index}/{len(pending)}] {row['interview_id']} "
            f"{row['condition']} {row['prompt_type']}"
        )
        try:
            payload = build_payload(
                row,
                args.anthropic_model,
                args.max_output_tokens,
                args.temperature,
                effective_top_p,
            )
            response = call_anthropic_with_retries(
                payload,
                api_key,
                max_retries=args.max_retries,
                retry_sleep_seconds=args.retry_sleep_seconds,
            )
            output_text = extract_output_text(response)
            if output_text is None:
                raise ValueError("Anthropic response did not include a text content block")
            output_json = json.loads(output_text)
            record = {
                "status": "ok",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "provider": "Anthropic",
                "model_name": args.anthropic_model,
                "anthropic_model": args.anthropic_model,
                "temperature": args.temperature,
                "top_p": effective_top_p,
                "top_p_omitted_reason": (
                    "Anthropic model rejects setting both temperature and top_p"
                    if effective_top_p is None
                    else None
                ),
                "max_output_tokens": args.max_output_tokens,
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
                    "provider": "Anthropic",
                    "model_name": args.anthropic_model,
                    "temperature": args.temperature,
                    "top_p": effective_top_p,
                    "max_output_tokens": args.max_output_tokens,
                    "output_path": row["output_path"],
                    "row": row,
                },
            )
        except Exception as exc:  # noqa: BLE001 - preserve failed row context in run log.
            error_record = {
                "status": "error",
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "provider": "Anthropic",
                "model_name": args.anthropic_model,
                "anthropic_model": args.anthropic_model,
                "temperature": args.temperature,
                "top_p": effective_top_p,
                "top_p_omitted_reason": (
                    "Anthropic model rejects setting both temperature and top_p"
                    if effective_top_p is None
                    else None
                ),
                "max_output_tokens": args.max_output_tokens,
                "effective_output_path": row["output_path"],
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
                    "provider": "Anthropic",
                    "model_name": args.anthropic_model,
                    "temperature": args.temperature,
                    "top_p": effective_top_p,
                    "max_output_tokens": args.max_output_tokens,
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
