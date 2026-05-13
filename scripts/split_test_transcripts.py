#!/usr/bin/env python3
"""Generate participant-only and interviewer-only DAIC-WOZ transcripts."""

from __future__ import annotations

import argparse
import csv
import re
import zipfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "Data"
TEST_SPLIT = DATA_DIR / "test_split_Depression_AVEC2017.csv"
DATA_TEST = DATA_DIR / "Data_Test"
FIELDNAMES = ["start_time", "stop_time", "speaker", "value"]
INTERVIEWER = "Ellie"
PARTICIPANT = "Participant"
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+\s*\((.+)\)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Split DAIC-WOZ transcript CSVs from participant zip files into "
            "interviewer-only and participant-only transcript files."
        )
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_TEST,
        help="Directory containing *_P.zip files.",
    )
    parser.add_argument(
        "--split-file",
        type=Path,
        default=TEST_SPLIT,
        help="Split CSV whose participant IDs must match the zip files.",
    )
    parser.add_argument(
        "--id-column",
        default=None,
        help=(
            "Participant ID column in the split CSV. If omitted, the script "
            "uses Participant_ID or participant_ID."
        ),
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return PROJECT_DIR / path


def read_split_ids(split_file: Path, id_column: str | None) -> tuple[set[str], str]:
    with split_file.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"{split_file} has no header row")

        resolved_id_column = id_column
        if resolved_id_column is None:
            for candidate in ("Participant_ID", "participant_ID"):
                if candidate in reader.fieldnames:
                    resolved_id_column = candidate
                    break

        if resolved_id_column is None or resolved_id_column not in reader.fieldnames:
            raise ValueError(
                f"Could not find participant ID column in {split_file}. "
                f"Available columns: {reader.fieldnames}"
            )

        return {row[resolved_id_column] for row in reader}, resolved_id_column


def clean_interviewer_value(value: str) -> tuple[str, bool]:
    stripped = value.strip()
    match = IDENTIFIER_PATTERN.match(stripped)
    if not match:
        return value, False
    return match.group(1).strip(), True


def read_transcript_from_zip(zip_path: Path) -> tuple[str, list[dict[str, str]]]:
    with zipfile.ZipFile(zip_path) as zf:
        transcript_names = [
            name
            for name in zf.namelist()
            if name.endswith("_TRANSCRIPT.csv") and not name.endswith("/")
        ]
        if len(transcript_names) != 1:
            raise ValueError(
                f"{zip_path.name} should contain exactly one transcript; "
                f"found {len(transcript_names)}"
            )

        transcript_name = transcript_names[0]
        with zf.open(transcript_name) as raw:
            text = raw.read().decode("utf-8-sig")

    rows = list(csv.DictReader(text.splitlines(), delimiter="\t"))
    if not rows:
        raise ValueError(f"{zip_path.name}:{transcript_name} has no transcript rows")
    if list(rows[0].keys()) != FIELDNAMES:
        raise ValueError(
            f"{zip_path.name}:{transcript_name} has unexpected columns "
            f"{list(rows[0].keys())}"
        )
    return transcript_name, rows


def write_transcript(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def split_transcripts(data_dir: Path, split_file: Path, id_column: str | None) -> None:
    split_ids, resolved_id_column = read_split_ids(split_file, id_column)
    zip_paths = sorted(data_dir.glob("*_P.zip"))
    zip_ids = {path.name.split("_", 1)[0] for path in zip_paths}

    missing_zips = sorted(split_ids - zip_ids)
    extra_zips = sorted(zip_ids - split_ids)
    if missing_zips or extra_zips:
        raise SystemExit(
            f"{data_dir} zip files do not match {split_file}: "
            f"missing={missing_zips}, extra={extra_zips}"
        )

    qc_rows: list[dict[str, str | int]] = []

    for zip_path in zip_paths:
        participant_id = zip_path.name.split("_", 1)[0]
        transcript_name, rows = read_transcript_from_zip(zip_path)

        interviewer_rows: list[dict[str, str]] = []
        participant_rows: list[dict[str, str]] = []
        other_speaker_rows = 0
        cleaned_identifier_rows = 0

        for row in rows:
            speaker = row["speaker"]
            if speaker == INTERVIEWER:
                clean_value, was_cleaned = clean_interviewer_value(row["value"])
                clean_row = dict(row)
                clean_row["value"] = clean_value
                interviewer_rows.append(clean_row)
                cleaned_identifier_rows += int(was_cleaned)
            elif speaker == PARTICIPANT:
                participant_rows.append(dict(row))
            else:
                other_speaker_rows += 1

        output_dir = data_dir / f"{participant_id}_P"
        write_transcript(
            output_dir / f"{participant_id}_TRANSCRIPT_INTERVIEWER.csv",
            interviewer_rows,
        )
        write_transcript(
            output_dir / f"{participant_id}_TRANSCRIPT_PARTICIPANT.csv",
            participant_rows,
        )

        anomalies = []
        if not interviewer_rows:
            anomalies.append("no_interviewer_rows")
        if not participant_rows:
            anomalies.append("no_participant_rows")
        if other_speaker_rows:
            anomalies.append("unexpected_speaker_rows")

        qc_rows.append(
            {
                "participant_id": participant_id,
                "zip_file": zip_path.name,
                "transcript_name": transcript_name,
                "original_rows": len(rows),
                "interviewer_rows": len(interviewer_rows),
                "participant_rows": len(participant_rows),
                "other_speaker_rows": other_speaker_rows,
                "cleaned_identifier_rows": cleaned_identifier_rows,
                "anomalies": ";".join(anomalies),
            }
        )

    qc_path = data_dir / "transcript_split_qc.csv"
    with qc_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(qc_rows[0].keys()))
        writer.writeheader()
        writer.writerows(qc_rows)

    print(f"Processed {len(qc_rows)} transcripts")
    print(f"Validated split IDs from {split_file.relative_to(PROJECT_DIR)}")
    print(f"Used ID column: {resolved_id_column}")
    print(f"Wrote QC report: {qc_path.relative_to(PROJECT_DIR)}")


def main() -> None:
    args = parse_args()
    split_transcripts(
        data_dir=resolve_path(args.data_dir),
        split_file=resolve_path(args.split_file),
        id_column=args.id_column,
    )


if __name__ == "__main__":
    main()
