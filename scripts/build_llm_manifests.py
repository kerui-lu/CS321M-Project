#!/usr/bin/env python3
"""Build local LLM-call manifests and rendered prompt previews for Dev."""

from __future__ import annotations

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
RENDERED_DIR = OUTPUT_DIR / "rendered_prompts" / "pilot_examples"
FULL_TRANSCRIPT_DIR = OUTPUT_DIR / "transcripts" / "dev_full"

MODEL_FAMILIES = ("gpt", "claude", "gemini")
CONDITIONS = ("full_transcript", "participant_only", "interviewer_only")
PROMPTS = {
    "item_evidence": PROMPT_DIR / "prompt_a_item_evidence.txt",
    "global_binary": PROMPT_DIR / "prompt_b_global_binary.txt",
}
METADATA_CONDITION = "no_gender"
METADATA_TEXT = "None provided."
REPEAT_ID = "1"
LABEL_ID_COLUMN = "Participant_ID"


def project_rel(path: Path) -> str:
    return path.relative_to(PROJECT_DIR).as_posix()


def read_labels() -> tuple[list[dict[str, str]], list[str]]:
    with DEV_LABELS.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        if reader.fieldnames is None or LABEL_ID_COLUMN not in reader.fieldnames:
            raise ValueError(f"{DEV_LABELS} must include {LABEL_ID_COLUMN}")
        return sorted(rows, key=lambda row: int(row[LABEL_ID_COLUMN])), reader.fieldnames


def read_zip_transcript(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as zf:
        names = [
            name
            for name in zf.namelist()
            if name.endswith("_TRANSCRIPT.csv") and not name.endswith("/")
        ]
        if len(names) != 1:
            raise ValueError(
                f"{zip_path.name} should contain exactly one transcript; "
                f"found {len(names)}"
            )
        return zf.read(names[0]).decode("utf-8-sig")


def ensure_full_transcripts(labels: list[dict[str, str]]) -> dict[str, Path]:
    FULL_TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    transcript_paths: dict[str, Path] = {}

    for row in labels:
        interview_id = row[LABEL_ID_COLUMN]
        zip_path = DEV_DIR / f"{interview_id}_P.zip"
        if not zip_path.exists():
            raise FileNotFoundError(zip_path)

        out_path = FULL_TRANSCRIPT_DIR / f"{interview_id}_TRANSCRIPT_FULL.csv"
        text = read_zip_transcript(zip_path)
        if not text.endswith("\n"):
            text += "\n"
        out_path.write_text(text, encoding="utf-8")
        transcript_paths[interview_id] = out_path

    return transcript_paths


def condition_transcript_path(interview_id: str, condition: str) -> Path:
    participant_dir = DEV_DIR / f"{interview_id}_P"
    if condition == "participant_only":
        return participant_dir / f"{interview_id}_TRANSCRIPT_PARTICIPANT.csv"
    if condition == "interviewer_only":
        return participant_dir / f"{interview_id}_TRANSCRIPT_INTERVIEWER.csv"
    raise ValueError(f"Unexpected split transcript condition: {condition}")


def select_pilot_ids(labels: list[dict[str, str]]) -> list[str]:
    by_score = sorted(
        labels,
        key=lambda row: (int(row["PHQ8_Score"]), int(row[LABEL_ID_COLUMN])),
    )
    selected: list[str] = []

    def add(interview_id: str) -> None:
        if interview_id not in selected:
            selected.append(interview_id)

    add(by_score[0][LABEL_ID_COLUMN])
    add(by_score[len(by_score) // 2][LABEL_ID_COLUMN])
    add(by_score[-1][LABEL_ID_COLUMN])

    qc_path = DEV_DIR / "transcript_split_qc.csv"
    no_interviewer_ids: list[str] = []
    if qc_path.exists():
        with qc_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if "no_interviewer_rows" in row.get("anomalies", ""):
                    no_interviewer_ids.append(row["participant_id"])
    for preferred_id in ("451", "458"):
        if preferred_id in no_interviewer_ids:
            add(preferred_id)
            break
    else:
        if no_interviewer_ids:
            add(sorted(no_interviewer_ids, key=int)[0])

    for row in by_score:
        if len(selected) >= 4:
            break
        add(row[LABEL_ID_COLUMN])

    return selected[:4]


def build_rows(
    labels: list[dict[str, str]],
    label_columns: list[str],
    full_transcripts: dict[str, Path],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for label_row in labels:
        interview_id = label_row[LABEL_ID_COLUMN]
        for condition in CONDITIONS:
            if condition == "full_transcript":
                transcript_path = full_transcripts[interview_id]
            else:
                transcript_path = condition_transcript_path(interview_id, condition)
            if not transcript_path.exists():
                raise FileNotFoundError(transcript_path)

            for prompt_type, prompt_path in PROMPTS.items():
                if not prompt_path.exists():
                    raise FileNotFoundError(prompt_path)

                for model_family in MODEL_FAMILIES:
                    output_path = (
                        OUTPUT_DIR
                        / "llm_raw"
                        / "dev_main"
                        / model_family
                        / condition
                        / prompt_type
                        / f"{interview_id}.json"
                    )
                    row = {
                        "interview_id": interview_id,
                        "condition": condition,
                        "prompt_type": prompt_type,
                        "metadata_condition": METADATA_CONDITION,
                        "metadata_text": METADATA_TEXT,
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


def render_prompt(prompt_path: Path, transcript_path: Path, metadata_text: str) -> str:
    prompt = prompt_path.read_text(encoding="utf-8")
    transcript = transcript_path.read_text(encoding="utf-8")
    rendered = prompt.replace("{METADATA}", metadata_text)
    rendered = rendered.replace("{TRANSCRIPT}", transcript)
    return rendered


def write_pilot_previews(pilot_rows: list[dict[str, str]]) -> None:
    RENDERED_DIR.mkdir(parents=True, exist_ok=True)
    seen: set[tuple[str, str, str]] = set()

    for row in pilot_rows:
        key = (row["interview_id"], row["condition"], row["prompt_type"])
        if key in seen:
            continue
        seen.add(key)

        prompt_path = PROJECT_DIR / row["prompt_path"]
        transcript_path = PROJECT_DIR / row["transcript_path"]
        rendered = render_prompt(prompt_path, transcript_path, row["metadata_text"])
        if "{METADATA}" in rendered or "{TRANSCRIPT}" in rendered:
            raise ValueError(f"Unrendered placeholder remains in {key}")
        for condition in CONDITIONS:
            if condition in rendered:
                raise ValueError(f"Condition leaked into rendered prompt for {key}")

        out_path = RENDERED_DIR / f"{row['interview_id']}_{row['condition']}_{row['prompt_type']}.txt"
        out_path.write_text(rendered, encoding="utf-8")


def validate_manifest(rows: list[dict[str, str]], expected_count: int) -> None:
    if len(rows) != expected_count:
        raise ValueError(f"Expected {expected_count} rows, found {len(rows)}")
    for row in rows:
        if row["repeat_id"] != REPEAT_ID:
            raise ValueError(f"Unexpected repeat_id in row: {row}")
        for path_key in ("prompt_path", "transcript_path"):
            if not (PROJECT_DIR / row[path_key]).exists():
                raise FileNotFoundError(row[path_key])


def main() -> None:
    labels, label_columns = read_labels()
    full_transcripts = ensure_full_transcripts(labels)
    main_rows = build_rows(labels, label_columns, full_transcripts)
    validate_manifest(main_rows, expected_count=35 * 3 * 2 * 3)

    pilot_ids = set(select_pilot_ids(labels))
    pilot_rows = [row for row in main_rows if row["interview_id"] in pilot_ids]
    validate_manifest(pilot_rows, expected_count=4 * 3 * 2 * 3)

    main_manifest = MANIFEST_DIR / "dev_main_manifest.csv"
    pilot_manifest = MANIFEST_DIR / "dev_pilot_manifest.csv"
    write_manifest(main_manifest, main_rows)
    write_manifest(pilot_manifest, pilot_rows)
    write_pilot_previews(pilot_rows)

    print(f"Wrote {project_rel(main_manifest)} with {len(main_rows)} rows")
    print(f"Wrote {project_rel(pilot_manifest)} with {len(pilot_rows)} rows")
    print(f"Pilot interview IDs: {', '.join(sorted(pilot_ids, key=int))}")
    print(f"Wrote rendered prompt previews to {project_rel(RENDERED_DIR)}")


if __name__ == "__main__":
    main()
