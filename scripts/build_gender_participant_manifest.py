#!/usr/bin/env python3
"""Build Dev actual-gender metadata LLM-call manifests."""

from __future__ import annotations

import argparse
import csv
import zipfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "Data"
DEV_DIR = DATA_DIR / "Data_DEV"
DEV_LABELS = DATA_DIR / "dev_split_Depression_AVEC2017.csv"
PROMPT_DIR = PROJECT_DIR / "prompts"
OUTPUT_DIR = PROJECT_DIR / "outputs"
MANIFEST_DIR = OUTPUT_DIR / "manifests"
FULL_TRANSCRIPT_DIR = OUTPUT_DIR / "transcripts" / "dev_full"

LABEL_ID_COLUMN = "Participant_ID"
METADATA_CONDITION = "actual_gender"
REPEAT_ID = "1"
PROMPTS = {
    "item_evidence": PROMPT_DIR / "prompt_a_item_evidence.txt",
    "global_binary": PROMPT_DIR / "prompt_b_global_binary.txt",
}
CONDITIONS = ("participant_only", "full_transcript")
MODEL_OUTPUT_DIRS = {
    "gpt": "gpt-4o",
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-pro",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a Dev actual-gender metadata manifest for one transcript condition."
    )
    parser.add_argument(
        "--condition",
        choices=CONDITIONS,
        default="participant_only",
        help="Transcript condition to run with actual gender metadata.",
    )
    parser.add_argument(
        "--experiment-name",
        default=None,
        help=(
            "Experiment directory/name for manifest and raw outputs. Defaults to "
            "dev_gender_participant_only or dev_gender_full_transcript."
        ),
    )
    return parser.parse_args()


def project_rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def read_labels() -> tuple[list[dict[str, str]], list[str]]:
    with DEV_LABELS.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if reader.fieldnames is None or LABEL_ID_COLUMN not in reader.fieldnames:
            raise ValueError(f"{DEV_LABELS} must include {LABEL_ID_COLUMN}")
        if "Gender" not in reader.fieldnames:
            raise ValueError(f"{DEV_LABELS} must include Gender")
        return sorted(rows, key=lambda row: int(row[LABEL_ID_COLUMN])), reader.fieldnames


def metadata_text(gender_code: str) -> str:
    if gender_code == "0":
        return "Gender: female."
    if gender_code == "1":
        return "Gender: male."
    raise ValueError(f"Unexpected Gender code: {gender_code!r}")


def participant_transcript_path(interview_id: str) -> Path:
    return DEV_DIR / f"{interview_id}_P" / f"{interview_id}_TRANSCRIPT_PARTICIPANT.csv"


def read_zip_transcript(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        names = [
            name
            for name in zf.namelist()
            if name.endswith("_TRANSCRIPT.csv") and not name.endswith("/")
        ]
        if len(names) != 1:
            raise ValueError(
                f"{zip_path.name} should contain exactly one transcript; found {len(names)}"
            )
        return zf.read(names[0]).decode("utf-8-sig")


def full_transcript_path(interview_id: str) -> Path:
    out_path = FULL_TRANSCRIPT_DIR / f"{interview_id}_TRANSCRIPT_FULL.csv"
    if out_path.exists():
        return out_path

    zip_path = DEV_DIR / f"{interview_id}_P.zip"
    if not zip_path.exists():
        raise FileNotFoundError(zip_path)

    FULL_TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    text = read_zip_transcript(zip_path)
    if not text.endswith("\n"):
        text += "\n"
    out_path.write_text(text, encoding="utf-8")
    return out_path


def transcript_path_for_condition(interview_id: str, condition: str) -> Path:
    if condition == "participant_only":
        return participant_transcript_path(interview_id)
    if condition == "full_transcript":
        return full_transcript_path(interview_id)
    raise ValueError(f"Unsupported condition: {condition}")


def default_experiment_name(condition: str) -> str:
    if condition == "participant_only":
        return "dev_gender_participant_only"
    if condition == "full_transcript":
        return "dev_gender_full_transcript"
    raise ValueError(f"Unsupported condition: {condition}")


def build_rows(
    labels: list[dict[str, str]],
    label_columns: list[str],
    condition: str,
    experiment_name: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for label_row in labels:
        interview_id = label_row[LABEL_ID_COLUMN]
        transcript_path = transcript_path_for_condition(interview_id, condition)
        if not transcript_path.exists():
            raise FileNotFoundError(transcript_path)

        row_metadata_text = metadata_text(label_row["Gender"])
        for prompt_type, prompt_path in PROMPTS.items():
            if not prompt_path.exists():
                raise FileNotFoundError(prompt_path)

            for model_family, output_model_dir in MODEL_OUTPUT_DIRS.items():
                output_path = (
                    OUTPUT_DIR
                    / "llm_raw"
                    / experiment_name
                    / output_model_dir
                    / condition
                    / prompt_type
                    / f"{interview_id}.json"
                )
                row = {
                    "interview_id": interview_id,
                    "condition": condition,
                    "prompt_type": prompt_type,
                    "metadata_condition": METADATA_CONDITION,
                    "metadata_text": row_metadata_text,
                    "model_family": model_family,
                    "repeat_id": REPEAT_ID,
                    "prompt_path": project_rel(prompt_path),
                    "transcript_path": project_rel(transcript_path),
                    "output_path": project_rel(output_path),
                }
                for column in label_columns:
                    row[column] = label_row[column]
                rows.append(row)

    return rows


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def validate_rows(rows: list[dict[str, str]], condition: str) -> None:
    expected_rows = 35 * 2 * 3
    if len(rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, found {len(rows)}")

    counts = {model_family: 0 for model_family in MODEL_OUTPUT_DIRS}
    for row in rows:
        if row["condition"] != condition:
            raise ValueError(f"Unexpected condition: {row}")
        if row["metadata_condition"] != METADATA_CONDITION:
            raise ValueError(f"Unexpected metadata_condition: {row}")
        expected_metadata = metadata_text(row["Gender"])
        if row["metadata_text"] != expected_metadata:
            raise ValueError(f"Gender metadata mismatch: {row}")
        counts[row["model_family"]] += 1

    for model_family, count in counts.items():
        if count != 35 * 2:
            raise ValueError(f"Expected 70 rows for {model_family}, found {count}")


def main() -> None:
    args = parse_args()
    experiment_name = args.experiment_name or default_experiment_name(args.condition)

    labels, label_columns = read_labels()
    rows = build_rows(
        labels,
        label_columns,
        condition=args.condition,
        experiment_name=experiment_name,
    )
    validate_rows(rows, condition=args.condition)

    manifest_path = MANIFEST_DIR / f"{experiment_name}_manifest.csv"
    write_manifest(manifest_path, rows)
    print(f"Wrote {project_rel(manifest_path)} with {len(rows)} rows")


if __name__ == "__main__":
    main()
