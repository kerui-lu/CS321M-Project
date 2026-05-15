#!/usr/bin/env python3
"""Build Dev participant-only gender-metadata LLM-call manifest."""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "Data"
DEV_DIR = DATA_DIR / "Data_DEV"
DEV_LABELS = DATA_DIR / "dev_split_Depression_AVEC2017.csv"
PROMPT_DIR = PROJECT_DIR / "prompts"
OUTPUT_DIR = PROJECT_DIR / "outputs"
MANIFEST_DIR = OUTPUT_DIR / "manifests"

LABEL_ID_COLUMN = "Participant_ID"
CONDITION = "participant_only"
METADATA_CONDITION = "actual_gender"
REPEAT_ID = "1"
PROMPTS = {
    "item_evidence": PROMPT_DIR / "prompt_a_item_evidence.txt",
    "global_binary": PROMPT_DIR / "prompt_b_global_binary.txt",
}
MODEL_OUTPUT_DIRS = {
    "gpt": "gpt-4o",
    "claude": "claude-sonnet-4-6",
    "gemini": "gemini-2.5-pro",
}


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


def build_rows(labels: list[dict[str, str]], label_columns: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for label_row in labels:
        interview_id = label_row[LABEL_ID_COLUMN]
        transcript_path = participant_transcript_path(interview_id)
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
                    / "dev_gender_participant_only"
                    / output_model_dir
                    / CONDITION
                    / prompt_type
                    / f"{interview_id}.json"
                )
                row = {
                    "interview_id": interview_id,
                    "condition": CONDITION,
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


def validate_rows(rows: list[dict[str, str]]) -> None:
    expected_rows = 35 * 2 * 3
    if len(rows) != expected_rows:
        raise ValueError(f"Expected {expected_rows} rows, found {len(rows)}")

    counts = {model_family: 0 for model_family in MODEL_OUTPUT_DIRS}
    for row in rows:
        if row["condition"] != CONDITION:
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
    labels, label_columns = read_labels()
    rows = build_rows(labels, label_columns)
    validate_rows(rows)

    manifest_path = MANIFEST_DIR / "dev_gender_participant_only_manifest.csv"
    write_manifest(manifest_path, rows)
    print(f"Wrote {project_rel(manifest_path)} with {len(rows)} rows")


if __name__ == "__main__":
    main()
