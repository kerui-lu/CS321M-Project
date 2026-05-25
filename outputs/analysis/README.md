# Dev Analysis Tables

This directory contains analysis-ready Dev split LLM outputs for comparison with the DAIC-WOZ Dev ground truth labels.

## Model Information

This directory currently includes formal outputs from three model families:

- Provider: OpenAI
- Model: `gpt-4o`
- API: OpenAI Responses API
- Output format: strict JSON schema structured output
- Repeats: 1 call, with no repeated sampling
- Metadata condition: `no_gender`
- Participant metadata text: `None provided.`
- Temperature: `1.0`; for the original no-gender GPT-4o run this was the OpenAI Responses API default and was not set explicitly
- Top-p: `1.0`; for the original no-gender GPT-4o run this was the OpenAI Responses API default and was not set explicitly
- Max output tokens: `600`
- Store: `false`
- Truncation: `disabled`
- Tools: none (`tools: []`)
- Tool choice: `auto`

```text
raw outputs: outputs/llm_raw/dev_main/gpt-4o/
validation: outputs/validation/dev_main_gpt4o_validation.csv
```

- Provider: Anthropic
- Model: `claude-sonnet-4-6`
- API: Anthropic Messages API
- Output format: JSON schema structured output
- Repeats: 1 call, with no repeated sampling
- Metadata condition: `no_gender`
- Participant metadata text: `None provided.`
- Temperature: `1.0`
- Top-p: omitted because Claude Sonnet 4.6 rejects setting both `temperature` and `top_p`
- Max output tokens: `600`
- Tools: none
- Streaming: off

```text
raw outputs: outputs/llm_raw/dev_main/claude/
validation: outputs/validation/dev_main_claude_validation.csv
```

- Provider: Google
- Model: `gemini-2.5-pro`
- API: Gemini generateContent REST API
- Output format: `responseMimeType=application/json` with `responseSchema`; strict validation is enforced locally
- Repeats: 1 call, with no repeated sampling
- Metadata condition: `no_gender`
- Participant metadata text: `None provided.`
- Temperature: `1.0`
- Top-p: `1.0`
- Max output tokens: `600`
- Thinking budget: `128`; this caps Gemini Pro thinking at the minimum available budget so it can return JSON within the 600-token output budget
- Tools: none
- Streaming: off

```text
raw outputs: outputs/llm_raw/dev_main/gemini/
validation: outputs/validation/dev_main_gemini_validation.csv
```

The earlier `gpt-4o-mini` outputs are stored under `outputs/llm_raw/dev_main/gpt/`. They are not part of the formal three-model CSV tables documented here.

## Gender Metadata Runs

This directory also includes Dev actual-gender metadata experiments. These are not counterfactual gender sensitivity runs: each participant receives only the gender recorded in the dataset.

- Input conditions: `participant_only` and `full_transcript`
- Metadata condition: `actual_gender`
- Gender mapping: `0 = female`, `1 = male`
- Metadata text:
  - `Gender: female.` when `Gender == 0`
  - `Gender: male.` when `Gender == 1`
- Repeats: 1 call

Formal model settings:

- OpenAI `gpt-4o`: `temperature=1.0`, `top_p=1.0`, `max_output_tokens=600`
- Anthropic `claude-sonnet-4-6`: `temperature=1.0`, `top_p` omitted, `max_output_tokens=600`
- Google `gemini-2.5-pro`: `temperature=1.0`, `top_p=1.0`, `thinking_budget=128`, `max_output_tokens=600`

```text
participant-only manifest: outputs/manifests/dev_gender_participant_only_manifest.csv
participant-only gpt raw outputs: outputs/llm_raw/dev_gender_participant_only/gpt-4o/
participant-only claude raw outputs: outputs/llm_raw/dev_gender_participant_only/claude-sonnet-4-6/
participant-only gemini raw outputs: outputs/llm_raw/dev_gender_participant_only/gemini-2.5-pro/
participant-only gpt validation: outputs/validation/dev_gender_participant_only_gpt_validation.csv
participant-only claude validation: outputs/validation/dev_gender_participant_only_claude_validation.csv
participant-only gemini validation: outputs/validation/dev_gender_participant_only_gemini_validation.csv

full-transcript manifest: outputs/manifests/dev_gender_full_transcript_manifest.csv
full-transcript gpt raw outputs: outputs/llm_raw/dev_gender_full_transcript/gpt-4o/
full-transcript claude raw outputs: outputs/llm_raw/dev_gender_full_transcript/claude-sonnet-4-6/
full-transcript gemini raw outputs: outputs/llm_raw/dev_gender_full_transcript/gemini-2.5-pro/
full-transcript gpt validation: outputs/validation/dev_gender_full_transcript_gpt_validation.csv
full-transcript claude validation: outputs/validation/dev_gender_full_transcript_claude_validation.csv
full-transcript gemini validation: outputs/validation/dev_gender_full_transcript_gemini_validation.csv
```

## Files

- `dev_gpt4o_full_transcript_outputs.csv`
  - Input: full transcript.
  - 35 rows, one for each Dev interview.

- `dev_gpt4o_participant_only_outputs.csv`
  - Input: Participant utterances only.
  - 35 rows, one for each Dev interview.

- `dev_gpt4o_interviewer_only_outputs.csv`
  - Input: Interviewer/Ellie utterances only.
  - 35 rows, one for each Dev interview.

- `dev_claudesonnet46_full_transcript_outputs.csv`
- `dev_claudesonnet46_participant_only_outputs.csv`
- `dev_claudesonnet46_interviewer_only_outputs.csv`

- `dev_gemini25pro_full_transcript_outputs.csv`
- `dev_gemini25pro_participant_only_outputs.csv`
- `dev_gemini25pro_interviewer_only_outputs.csv`

- `dev_gender_participant_only_gpt4o_outputs.csv`
- `dev_gender_participant_only_claudesonnet46_outputs.csv`
- `dev_gender_participant_only_gemini25pro_outputs.csv`

- `dev_gender_full_transcript_gpt4o_outputs.csv`
- `dev_gender_full_transcript_claudesonnet46_outputs.csv`
- `dev_gender_full_transcript_gemini25pro_outputs.csv`

For the no-gender main run, each model has three separate CSV files rather than one combined three-condition table. Each CSV contains exactly one `condition`, which makes separate comparison against the ground truth CSV easier.

For the gender-metadata runs, the CSV files are also separate by model and condition. Each file contains either `participant_only` or `full_transcript`.

## Key Columns

Identifier columns:

- `interview_id`
- `provider`
- `model_name`
- `condition`
- `metadata_condition`
- `metadata_text`
- `repeat_id`

Prompt A outputs, corresponding to PHQ-8-inspired item evidence scoring:

- `pred_no_interest`
- `pred_depressed_mood`
- `pred_sleep`
- `pred_tired`
- `pred_appetite`
- `pred_failure`
- `pred_concentration`
- `pred_psychomotor`
- `pred_evidence_total`
- `thresholded_item_binary`
- `item_rationale`

Prompt B outputs, corresponding to holistic global binary judgment:

- `global_binary_judgment`
- `global_binary_confidence`
- `global_rationale`

Dev split ground truth columns:

- `PHQ8_Binary`
- `PHQ8_Score`
- `Gender`
- `PHQ8_NoInterest`
- `PHQ8_Depressed`
- `PHQ8_Sleep`
- `PHQ8_Tired`
- `PHQ8_Appetite`
- `PHQ8_Failure`
- `PHQ8_Concentrating`
- `PHQ8_Moving`

Path tracing columns:

- `item_output_path`
- `global_output_path`

## Derived Variables

`thresholded_item_binary` is derived from the Prompt A total score:

```text
thresholded_item_binary = int(pred_evidence_total >= 10)
```

It is distinct from Prompt B's `global_binary_judgment`:

- `thresholded_item_binary`: derived by thresholding the structured item evidence total.
- `global_binary_judgment`: the model's direct holistic binary judgment.

## Validation Status

These CSV files were generated with `scripts/build_analysis_table.py`. The script supports OpenAI, Anthropic, and Gemini outputs through the corresponding `--model-family`, `--output-model-dir`, `--provider-label`, `--model-label`, and `--prefix` arguments.

Validation summaries:

- OpenAI GPT-4o raw outputs: 210/210 valid.
- Anthropic Claude Sonnet 4.6 raw outputs: 210/210 valid.
- Google Gemini 2.5 Pro raw outputs: 210/210 valid.
- Dev participant-only actual-gender GPT-4o raw outputs: 70/70 valid.
- Dev participant-only actual-gender Claude Sonnet 4.6 raw outputs: 70/70 valid.
- Dev participant-only actual-gender Gemini 2.5 Pro raw outputs: 70/70 valid.
- Dev full-transcript actual-gender GPT-4o raw outputs: 70/70 valid.
- Dev full-transcript actual-gender Claude Sonnet 4.6 raw outputs: 70/70 valid.
- Dev full-transcript actual-gender Gemini 2.5 Pro raw outputs: 70/70 valid.

The generated analysis tables were checked for the following:

- Each table has 35 rows.
- Each table contains exactly one `condition`.
- Each interview has both Prompt A and Prompt B outputs.
- The 8 predicted item scores are integers from 0 to 3.
- `pred_evidence_total` equals the sum of the 8 predicted item scores.
- `thresholded_item_binary` is consistent with `pred_evidence_total >= 10`.
- `global_binary_judgment` is either 0 or 1.
- Ground truth label columns are present and non-empty.
- For the actual-gender run, `metadata_text` matches the Dev split `Gender` column using `0 = female` and `1 = male`.

## Suggested Comparisons

Within each table, start by comparing:

- `pred_evidence_total` vs. `PHQ8_Score`
- `thresholded_item_binary` vs. `PHQ8_Binary`
- `global_binary_judgment` vs. `PHQ8_Binary`
- Each `pred_*` item score vs. the corresponding `PHQ8_*` item label

After that, compare the same `interview_id` across input conditions or across model families.
