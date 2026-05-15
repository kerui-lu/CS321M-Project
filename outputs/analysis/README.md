# Dev Analysis Tables

本目录包含已经整理好的 Dev split LLM 输出，用于和 DAIC-WOZ Dev ground truth 进行对比分析。

## Model Information

本目录目前包含三组正式模型输出：

- Provider: OpenAI
- Model: `gpt-4o`
- API: OpenAI Responses API
- Output format: strict JSON schema structured output
- Repeats: 1 次调用，没有 repeated sampling
- Metadata condition: `no_gender`
- Participant metadata text: `None provided.`
- Temperature: `1.0`，OpenAI Responses API 默认值；本次调用没有显式设置 temperature
- Top-p: `1.0`，OpenAI Responses API 默认值；本次调用没有显式设置 top_p
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
- Repeats: 1 次调用，没有 repeated sampling
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
- Repeats: 1 次调用，没有 repeated sampling
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

注意：早先的 `gpt-4o-mini` 输出保存在 `outputs/llm_raw/dev_main/gpt/`，不属于本目录的正式三模型 CSV。

## Files

- `dev_gpt4o_full_transcript_outputs.csv`
  - 输入为完整 transcript。
  - 35 rows，对应 35 个 Dev interviews。

- `dev_gpt4o_participant_only_outputs.csv`
  - 输入仅包含 Participant utterances。
  - 35 rows，对应 35 个 Dev interviews。

- `dev_gpt4o_interviewer_only_outputs.csv`
  - 输入仅包含 Interviewer/Ellie utterances。
  - 35 rows，对应 35 个 Dev interviews。

- `dev_claudesonnet46_full_transcript_outputs.csv`
- `dev_claudesonnet46_participant_only_outputs.csv`
- `dev_claudesonnet46_interviewer_only_outputs.csv`

- `dev_gemini25pro_full_transcript_outputs.csv`
- `dev_gemini25pro_participant_only_outputs.csv`
- `dev_gemini25pro_interviewer_only_outputs.csv`

同一模型的三张表没有合并在一起；每张表只包含一个 `condition`，方便分别和 ground truth CSV 做比较。

## Key Columns

标识信息：

- `interview_id`
- `provider`
- `model_name`
- `condition`
- `metadata_condition`
- `metadata_text`
- `repeat_id`

Prompt A 输出，也就是 PHQ-8-inspired item evidence scoring：

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

Prompt B 输出，也就是 holistic global binary judgment：

- `global_binary_judgment`
- `global_binary_confidence`
- `global_rationale`

Dev split ground truth：

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

路径追踪：

- `item_output_path`
- `global_output_path`

## Derived Variables

`thresholded_item_binary` 是由 Prompt A 的总分派生出来的：

```text
thresholded_item_binary = int(pred_evidence_total >= 10)
```

它和 Prompt B 的 `global_binary_judgment` 是两个不同的变量：

- `thresholded_item_binary`: structured item scoring 后按阈值转换得到。
- `global_binary_judgment`: 对应模型直接做出的整体二分类判断。

## Validation Status

这些 CSV 由 `scripts/build_analysis_table.py` 生成。该脚本现在也支持 Claude/Gemini outputs，只要传入对应的 `--model-family`、`--output-model-dir`、`--provider-label`、`--model-label` 和 `--prefix`。生成时已经检查：

- OpenAI GPT-4o raw outputs: 210/210 valid.
- Anthropic Claude Sonnet 4.6 raw outputs: 210/210 valid.
- Google Gemini 2.5 Pro raw outputs: 210/210 valid.

- 每张表有 35 rows。
- 每张表只包含一个 `condition`。
- 每个 interview 同时有 Prompt A 和 Prompt B 输出。
- 8 个 predicted item scores 都在 0 到 3 之间。
- `pred_evidence_total` 等于 8 个 predicted item scores 的和。
- `thresholded_item_binary` 与 `pred_evidence_total >= 10` 一致。
- `global_binary_judgment` 是 0 或 1。
- ground truth 标签列均存在且非空。

## Suggested Comparisons

可以先分别在三张表内比较：

- `pred_evidence_total` vs. `PHQ8_Score`
- `thresholded_item_binary` vs. `PHQ8_Binary`
- `global_binary_judgment` vs. `PHQ8_Binary`
- 每个 `pred_*` item score vs. 对应的 `PHQ8_*` item label

之后再跨三张表比较同一个 `interview_id` 在不同 input condition 下的输出差异。
