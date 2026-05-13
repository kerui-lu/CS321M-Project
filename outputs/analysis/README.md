# GPT-4o Dev Analysis Tables

本目录包含已经整理好的 GPT-4o Dev split 输出，用于和 DAIC-WOZ Dev ground truth 进行对比分析。

## Model Information

这些表格对应的模型是：

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

原始模型输出保存在：

```text
outputs/llm_raw/dev_main/gpt-4o/
```

验证摘要保存在：

```text
outputs/validation/dev_main_gpt4o_validation.csv
```

注意：早先的 `gpt-4o-mini` 输出保存在 `outputs/llm_raw/dev_main/gpt/`，不属于本目录这三张 GPT-4o CSV。

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

三张表没有合并在一起；每张表只包含一个 `condition`，方便分别和 ground truth CSV 做比较。

## Key Columns

标识信息：

- `interview_id`
- `openai_model`
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
- `global_binary_judgment`: GPT-4o 直接做出的整体二分类判断。

## Validation Status

这些 CSV 由 `scripts/build_analysis_table.py` 生成。生成时已经检查：

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
