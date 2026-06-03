# CS321M Project: LLM Depression Judgment Robustness

This repository contains the code, prompts, analysis-ready outputs, and documentation for a CS321M project studying zero-shot LLM judgments on DAIC-WOZ development split transcripts.

The project asks whether LLM-generated depression judgments are driven mainly by participant speech, or whether they are sensitive to interviewer-side transcript structure and demographic metadata. The experiments compare GPT-4o, Claude Sonnet 4.6, and Gemini 2.5 Pro across transcript input conditions and two judgment formats.

This repository is intended to be reviewable by course staff without requiring API reruns. The analysis-ready CSVs and metric summary are tracked. Restricted raw DAIC-WOZ archives, generated split transcript files, raw API responses, validation logs, and local API keys are intentionally not tracked.

## Main Results To Inspect

Start here:

- `outputs/analysis/evaluation_metrics_summary.md`
  - Defines all metrics.
  - Reports model performance against `Data/dev_split_Depression_AVEC2017.csv`.
  - Includes no-gender and actual-gender comparisons.
  - Includes cross-API reliability and Krippendorff's alpha.
- `outputs/analysis/README.md`
  - Documents analysis CSV schemas, model settings, raw-output locations, and validation status.

The final analysis CSVs are tracked in `outputs/analysis/`. Each file has 35 rows, one for each DAIC-WOZ Dev interview.

## Repository Structure

```text
.
|-- Data/
|   |-- dev_split_Depression_AVEC2017.csv
|   |-- test_split_Depression_AVEC2017.csv
|   `-- train_split_Depression_AVEC2017.csv
|-- prompts/
|   |-- prompt_a_item_evidence.txt
|   `-- prompt_b_global_binary.txt
|-- scripts/
|   |-- split_test_transcripts.py
|   |-- build_llm_manifests.py
|   |-- build_gender_participant_manifest.py
|   |-- run_openai_manifest.py
|   |-- run_anthropic_manifest.py
|   |-- run_gemini_manifest.py
|   |-- validate_llm_outputs.py
|   |-- build_analysis_table.py
|   |-- fit_gtheory.py
|   `-- fit_mfrm.py
`-- outputs/
    `-- analysis/
        |-- README.md
        |-- evaluation_metrics_summary.md
        `-- *_outputs.csv
```

## What Is Not Tracked

The following files are intentionally excluded:

- `.env` with API keys.
- `Data/Data_DEV/` and `Data/Data_Test/`, which contain restricted DAIC-WOZ zip archives and generated transcript splits.
- `outputs/llm_raw/`, `outputs/manifests/`, `outputs/validation/`, `outputs/rendered_prompts/`, and `outputs/transcripts/`, which are generated locally.
- Python caches and local operating-system files.

Because the DAIC-WOZ transcripts are restricted data, graders should not expect the raw zip archives in the public repository. The tracked scripts document the local pipeline, and the tracked analysis CSVs provide the completed experiment outputs.

## Experimental Design

Dataset:

- DAIC-WOZ development split.
- Ground truth binary label: `PHQ8_Binary`.
- Ground truth total score: `PHQ8_Score`.
- Gender metadata mapping used in metadata experiments: `0 = female`, `1 = male`.

Transcript conditions:

- `full_transcript`: interviewer and participant utterances.
- `participant_only`: participant utterances only.
- `interviewer_only`: interviewer/Ellie utterances only, used as a shortcut and leakage check.

Metadata conditions:

- `no_gender`: prompt metadata is `None provided.`
- `actual_gender`: prompt metadata is `Gender: female.` or `Gender: male.` from the Dev split.

Prompt outputs:

- Prompt A: PHQ-8-inspired item evidence scores.
  - Binary prediction is derived as `thresholded_item_binary = int(pred_evidence_total >= 10)`.
- Prompt B: direct holistic binary judgment.
  - Binary prediction is `global_binary_judgment`.

Models:

- OpenAI GPT-4o.
- Anthropic Claude Sonnet 4.6.
- Google Gemini 2.5 Pro.

Formal run settings:

- Repeats: 1 call per model, prompt, transcript condition, and interview.
- Temperature: `1.0`.
- Top-p: `1.0` for GPT-4o and Gemini; omitted for Claude because the API rejected setting both `temperature` and `top_p`.
- Max output tokens: `600`.
- Structured JSON outputs.
- No tools.
- No streaming.
- Gemini Pro thinking budget: `128`.

## Environment Setup

Python 3.10 or newer is recommended.

```bash
cd Project
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Create a local `.env` file if you need to rerun model calls:

```text
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
GEMINI_API_KEY=...
```

An example file is provided at `.env.example`. Do not commit `.env`.

## Local Reproduction Workflow

The tracked analysis CSVs are already sufficient for reviewing the reported results. To rerun the pipeline from raw transcripts, place the restricted DAIC-WOZ Dev zip files under:

```text
Data/Data_DEV/<ID>_P.zip
```

Then run the local steps below from the repository root.

### 1. Split Dev transcripts

```bash
python3 scripts/split_test_transcripts.py \
  --data-dir Data/Data_DEV \
  --split-file Data/dev_split_Depression_AVEC2017.csv \
  --id-column Participant_ID
```

This writes participant-only and interviewer-only transcript files next to each Dev zip file, plus a split QC report. It does not modify the original zip archives.

### 2. Build no-gender manifests

```bash
python3 scripts/build_llm_manifests.py
```

Expected generated files:

```text
outputs/manifests/dev_main_manifest.csv
outputs/manifests/dev_pilot_manifest.csv
```

### 3. Run model manifests

GPT-4o example:

```bash
python3 scripts/run_openai_manifest.py \
  --manifest outputs/manifests/dev_main_manifest.csv \
  --model-family gpt \
  --openai-model gpt-4o \
  --output-model-dir gpt-4o \
  --temperature 1.0 \
  --top-p 1.0 \
  --max-output-tokens 600
```

Claude example:

```bash
python3 scripts/run_anthropic_manifest.py \
  --manifest outputs/manifests/dev_main_manifest.csv \
  --anthropic-model claude-sonnet-4-6 \
  --temperature 1.0 \
  --max-output-tokens 600
```

Gemini example:

```bash
python3 scripts/run_gemini_manifest.py \
  --manifest outputs/manifests/dev_main_manifest.csv \
  --gemini-model gemini-2.5-pro \
  --temperature 1.0 \
  --top-p 1.0 \
  --thinking-budget 128 \
  --max-output-tokens 600
```

Use `--dry-run` first to inspect pending calls without sending API requests.

### 4. Validate raw model outputs

```bash
python3 scripts/validate_llm_outputs.py \
  --manifest outputs/manifests/dev_main_manifest.csv \
  --model-family gpt \
  --output-model-dir gpt-4o
```

Repeat with `--model-family claude` and `--model-family gemini`.

### 5. Build analysis tables

No-gender GPT-4o example:

```bash
python3 scripts/build_analysis_table.py \
  --manifest outputs/manifests/dev_main_manifest.csv \
  --model-family gpt \
  --output-model-dir gpt-4o \
  --provider-label OpenAI \
  --model-label gpt-4o \
  --prefix dev_gpt4o
```

The same script is used for Claude and Gemini by changing `--model-family`, `--output-model-dir`, `--provider-label`, `--model-label`, and `--prefix`.

### 6. Build actual-gender manifests

Participant-only actual-gender:

```bash
python3 scripts/build_gender_participant_manifest.py \
  --condition participant_only
```

Full-transcript actual-gender:

```bash
python3 scripts/build_gender_participant_manifest.py \
  --condition full_transcript
```

Then run, validate, and build analysis tables with the same runner and analysis-table scripts.

## Statistical Analysis Scripts

The repository also includes exploratory measurement-analysis scripts:

- `scripts/fit_gtheory.py`
  - Computes G-theory variance components and dependability summaries from `outputs/analysis/*_outputs.csv`.
- `scripts/fit_mfrm.py`
  - Fits a many-facet Rasch-style logistic model using `pandas` and `statsmodels`.

These scripts are optional analysis extensions. They are not required to inspect the main reported metric tables.

## Notes For Grading

This repository includes enough local code to inspect and rerun the full pipeline if the restricted DAIC-WOZ zip archives and API keys are available locally. It also includes analysis-ready outputs, so course staff can review the completed experiments without spending API credits.

The work should be interpreted as a research measurement study, not a clinical diagnostic system. The prompts explicitly ask for transcript evidence ratings and binary evidence judgments, not clinical diagnoses.
