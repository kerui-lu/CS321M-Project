# Evaluation Metrics Summary

This report summarizes binary evaluation results for the Dev split LLM outputs in `outputs/analysis/`. Ground truth is read directly from `Data/dev_split_Depression_AVEC2017.csv`, using `PHQ8_Binary` as the binary label.

## Prediction Types

- `Item-threshold`: `thresholded_item_binary = int(pred_evidence_total >= 10)`. This is derived from Prompt A, the PHQ-8-inspired item evidence scoring prompt.
- `Global`: `global_binary_judgment`. This is produced directly by Prompt B, the holistic global binary judgment prompt.

## Metric Definitions

- `TP`: true positives, where `PHQ8_Binary = 1` and the model predicts `1`.
- `TN`: true negatives, where `PHQ8_Binary = 0` and the model predicts `0`.
- `FP`: false positives, where `PHQ8_Binary = 0` and the model predicts `1`.
- `FN`: false negatives, where `PHQ8_Binary = 1` and the model predicts `0`.
- `Accuracy`: `(TP + TN) / N`.
- `Balanced accuracy`: `(recall + specificity) / 2`.
- `Precision`: `TP / (TP + FP)`.
- `Recall` or `sensitivity`: `TP / (TP + FN)`.
- `Specificity`: `TN / (TN + FP)`.
- `F1`: harmonic mean of precision and recall.
- `MCC`: Matthews correlation coefficient.
- `Cohen kappa`: chance-corrected agreement with `PHQ8_Binary`.

`NA` appears when a metric is undefined, such as precision or F1 when a method predicts no positives.

## Main Results

`Combined` pools the three model outputs for the same condition, so `N = 105` rather than 35. It is not a majority-vote ensemble.

| Condition | Model | Method | N | Label+ | Pred+ | TP | TN | FP | FN | Acc | Bal Acc | Precision | Recall | Specificity | F1 | MCC | Kappa |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| no_gender_full_transcript | GPT-4o | Item-threshold | 35 | 12 | 4 | 4 | 23 | 0 | 8 | 0.771 | 0.667 | 1.000 | 0.333 | 1.000 | 0.500 | 0.497 | 0.397 |
| no_gender_full_transcript | GPT-4o | Global | 35 | 12 | 21 | 12 | 14 | 9 | 0 | 0.743 | 0.804 | 0.571 | 1.000 | 0.609 | 0.727 | 0.590 | 0.516 |
| no_gender_full_transcript | Claude Sonnet 4.6 | Item-threshold | 35 | 12 | 2 | 2 | 23 | 0 | 10 | 0.714 | 0.583 | 1.000 | 0.167 | 1.000 | 0.286 | 0.341 | 0.208 |
| no_gender_full_transcript | Claude Sonnet 4.6 | Global | 35 | 12 | 18 | 11 | 16 | 7 | 1 | 0.771 | 0.806 | 0.611 | 0.917 | 0.696 | 0.733 | 0.582 | 0.547 |
| no_gender_full_transcript | Gemini 2.5 Pro | Item-threshold | 35 | 12 | 6 | 5 | 22 | 1 | 7 | 0.771 | 0.687 | 0.833 | 0.417 | 0.957 | 0.556 | 0.470 | 0.424 |
| no_gender_full_transcript | Gemini 2.5 Pro | Global | 35 | 12 | 20 | 11 | 14 | 9 | 1 | 0.714 | 0.763 | 0.550 | 0.917 | 0.609 | 0.687 | 0.504 | 0.453 |
| no_gender_full_transcript | Combined | Item-threshold | 105 | 36 | 12 | 11 | 68 | 1 | 25 | 0.752 | 0.646 | 0.917 | 0.306 | 0.986 | 0.458 | 0.434 | 0.346 |
| no_gender_full_transcript | Combined | Global | 105 | 36 | 59 | 34 | 44 | 25 | 2 | 0.743 | 0.791 | 0.576 | 0.944 | 0.638 | 0.716 | 0.557 | 0.505 |
| no_gender_participant_only | GPT-4o | Item-threshold | 35 | 12 | 4 | 4 | 23 | 0 | 8 | 0.771 | 0.667 | 1.000 | 0.333 | 1.000 | 0.500 | 0.497 | 0.397 |
| no_gender_participant_only | GPT-4o | Global | 35 | 12 | 22 | 12 | 13 | 10 | 0 | 0.714 | 0.783 | 0.545 | 1.000 | 0.565 | 0.706 | 0.555 | 0.471 |
| no_gender_participant_only | Claude Sonnet 4.6 | Item-threshold | 35 | 12 | 2 | 2 | 23 | 0 | 10 | 0.714 | 0.583 | 1.000 | 0.167 | 1.000 | 0.286 | 0.341 | 0.208 |
| no_gender_participant_only | Claude Sonnet 4.6 | Global | 35 | 12 | 20 | 11 | 14 | 9 | 1 | 0.714 | 0.763 | 0.550 | 0.917 | 0.609 | 0.687 | 0.504 | 0.453 |
| no_gender_participant_only | Gemini 2.5 Pro | Item-threshold | 35 | 12 | 8 | 5 | 20 | 3 | 7 | 0.714 | 0.643 | 0.625 | 0.417 | 0.870 | 0.500 | 0.324 | 0.311 |
| no_gender_participant_only | Gemini 2.5 Pro | Global | 35 | 12 | 20 | 11 | 14 | 9 | 1 | 0.714 | 0.763 | 0.550 | 0.917 | 0.609 | 0.687 | 0.504 | 0.453 |
| no_gender_participant_only | Combined | Item-threshold | 105 | 36 | 14 | 11 | 66 | 3 | 25 | 0.733 | 0.631 | 0.786 | 0.306 | 0.957 | 0.440 | 0.366 | 0.307 |
| no_gender_participant_only | Combined | Global | 105 | 36 | 62 | 34 | 41 | 28 | 2 | 0.714 | 0.769 | 0.548 | 0.944 | 0.594 | 0.694 | 0.520 | 0.459 |
| no_gender_interviewer_only | GPT-4o | Item-threshold | 35 | 12 | 0 | 0 | 23 | 0 | 12 | 0.657 | 0.500 | NA | 0.000 | 1.000 | NA | NA | 0.000 |
| no_gender_interviewer_only | GPT-4o | Global | 35 | 12 | 1 | 0 | 22 | 1 | 12 | 0.629 | 0.478 | 0.000 | 0.000 | 0.957 | NA | -0.124 | -0.056 |
| no_gender_interviewer_only | Claude Sonnet 4.6 | Item-threshold | 35 | 12 | 0 | 0 | 23 | 0 | 12 | 0.657 | 0.500 | NA | 0.000 | 1.000 | NA | NA | 0.000 |
| no_gender_interviewer_only | Claude Sonnet 4.6 | Global | 35 | 12 | 17 | 11 | 17 | 6 | 1 | 0.800 | 0.828 | 0.647 | 0.917 | 0.739 | 0.759 | 0.623 | 0.596 |
| no_gender_interviewer_only | Gemini 2.5 Pro | Item-threshold | 35 | 12 | 0 | 0 | 23 | 0 | 12 | 0.657 | 0.500 | NA | 0.000 | 1.000 | NA | NA | 0.000 |
| no_gender_interviewer_only | Gemini 2.5 Pro | Global | 35 | 12 | 2 | 0 | 21 | 2 | 12 | 0.600 | 0.457 | 0.000 | 0.000 | 0.913 | NA | -0.178 | -0.109 |
| no_gender_interviewer_only | Combined | Item-threshold | 105 | 36 | 0 | 0 | 69 | 0 | 36 | 0.657 | 0.500 | NA | 0.000 | 1.000 | NA | NA | 0.000 |
| no_gender_interviewer_only | Combined | Global | 105 | 36 | 20 | 11 | 60 | 9 | 25 | 0.676 | 0.588 | 0.550 | 0.306 | 0.870 | 0.393 | 0.212 | 0.196 |
| actual_gender_participant_only | GPT-4o | Item-threshold | 35 | 12 | 3 | 3 | 23 | 0 | 9 | 0.743 | 0.625 | 1.000 | 0.250 | 1.000 | 0.400 | 0.424 | 0.305 |
| actual_gender_participant_only | GPT-4o | Global | 35 | 12 | 22 | 12 | 13 | 10 | 0 | 0.714 | 0.783 | 0.545 | 1.000 | 0.565 | 0.706 | 0.555 | 0.471 |
| actual_gender_participant_only | Claude Sonnet 4.6 | Item-threshold | 35 | 12 | 1 | 1 | 23 | 0 | 11 | 0.686 | 0.542 | 1.000 | 0.083 | 1.000 | 0.154 | 0.237 | 0.107 |
| actual_gender_participant_only | Claude Sonnet 4.6 | Global | 35 | 12 | 20 | 11 | 14 | 9 | 1 | 0.714 | 0.763 | 0.550 | 0.917 | 0.609 | 0.687 | 0.504 | 0.453 |
| actual_gender_participant_only | Gemini 2.5 Pro | Item-threshold | 35 | 12 | 4 | 3 | 22 | 1 | 9 | 0.714 | 0.603 | 0.750 | 0.250 | 0.957 | 0.375 | 0.308 | 0.246 |
| actual_gender_participant_only | Gemini 2.5 Pro | Global | 35 | 12 | 22 | 11 | 12 | 11 | 1 | 0.657 | 0.719 | 0.500 | 0.917 | 0.522 | 0.647 | 0.431 | 0.366 |
| actual_gender_participant_only | Combined | Item-threshold | 105 | 36 | 8 | 7 | 68 | 1 | 29 | 0.714 | 0.590 | 0.875 | 0.194 | 0.986 | 0.318 | 0.322 | 0.221 |
| actual_gender_participant_only | Combined | Global | 105 | 36 | 64 | 34 | 39 | 30 | 2 | 0.695 | 0.755 | 0.531 | 0.944 | 0.565 | 0.680 | 0.496 | 0.430 |

## Cross-API Comparison

The table below aggregates each API across participant-containing runs: `no_gender_full_transcript`, `no_gender_participant_only`, and `actual_gender_participant_only`. This gives a compact API-level comparison for transcripts that include participant speech. It does not include `interviewer_only`, because that condition is primarily a sensitivity and leakage check rather than a viable prediction input.

| API | Method | N | Label+ | Pred+ | Acc | Bal Acc | Precision | Recall | Specificity | F1 | MCC |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-4o | Item-threshold | 105 | 36 | 11 | 0.762 | 0.653 | 1.000 | 0.306 | 1.000 | 0.468 | 0.474 |
| GPT-4o | Global | 105 | 36 | 65 | 0.724 | 0.790 | 0.554 | 1.000 | 0.580 | 0.713 | 0.567 |
| Claude Sonnet 4.6 | Item-threshold | 105 | 36 | 5 | 0.705 | 0.569 | 1.000 | 0.139 | 1.000 | 0.244 | 0.310 |
| Claude Sonnet 4.6 | Global | 105 | 36 | 58 | 0.733 | 0.777 | 0.569 | 0.917 | 0.638 | 0.702 | 0.529 |
| Gemini 2.5 Pro | Item-threshold | 105 | 36 | 18 | 0.733 | 0.644 | 0.722 | 0.361 | 0.928 | 0.481 | 0.364 |
| Gemini 2.5 Pro | Global | 105 | 36 | 62 | 0.695 | 0.748 | 0.532 | 0.917 | 0.580 | 0.673 | 0.479 |

Across participant-containing runs, the `Global` method is stronger than `Item-threshold` for all three APIs on balanced accuracy, recall, F1, and MCC. GPT-4o has the highest global balanced accuracy, recall, F1, and MCC in this aggregate. Claude Sonnet 4.6 has slightly higher global raw accuracy and specificity than GPT-4o, reflecting a somewhat less positive-leaning decision pattern. Gemini 2.5 Pro is close to the other two APIs on global recall, but lower on specificity, F1, and MCC in this aggregate.

The next table compares agreement across the three APIs. Agreement is computed on the same 35 interviews within each condition. `Avg Pairwise Agreement` is the mean of GPT-4o vs Claude, GPT-4o vs Gemini, and Claude vs Gemini exact binary agreement. `Avg Pairwise Kappa` is the corresponding mean Cohen's kappa. `Range of Pred+ Across APIs` shows the minimum and maximum number of positive predictions made by the three APIs in that condition.

| Condition | Method | Avg Pairwise Agreement | Avg Pairwise Kappa | Range of Pred+ Across APIs |
|---|---|---:|---:|---:|
| no_gender_full_transcript | Item-threshold | 0.905 | 0.543 | 2-6 |
| no_gender_full_transcript | Global | 0.924 | 0.845 | 18-21 |
| no_gender_participant_only | Item-threshold | 0.848 | 0.397 | 2-8 |
| no_gender_participant_only | Global | 0.962 | 0.921 | 20-22 |
| actual_gender_participant_only | Item-threshold | 0.943 | 0.563 | 1-4 |
| actual_gender_participant_only | Global | 0.943 | 0.880 | 20-22 |
| no_gender_interviewer_only | Item-threshold | 1.000 | NA | 0-0 |
| no_gender_interviewer_only | Global | 0.676 | 0.047 | 1-17 |

For participant-containing transcripts, `Global` is more consistent across APIs than `Item-threshold`, with much higher average pairwise kappa. The `interviewer_only` condition is the exception: `Global` agreement collapses because the APIs respond very differently when participant speech is absent. The apparent perfect agreement for `interviewer_only` item-threshold is not meaningful, because all three APIs simply predict zero positives.

## Actual Gender Metadata vs No-Gender Participant-Only

This comparison uses participant-only transcripts and contrasts the no-gender prompt condition with the actual-gender prompt condition. `Changed Outputs` counts binary output flips between the two conditions for the same interview and model. For `Combined`, it sums changes across the three models, so the denominator is 105.

| Model | Method | No-gender Pred+ | Actual-gender Pred+ | Changed Outputs | Acc Delta | Bal Acc Delta | F1 Delta | MCC Delta |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-4o | Item-threshold | 4 | 3 | 3 | -0.029 | -0.042 | -0.100 | -0.073 |
| GPT-4o | Global | 22 | 22 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| Claude Sonnet 4.6 | Item-threshold | 2 | 1 | 1 | -0.029 | -0.042 | -0.132 | -0.103 |
| Claude Sonnet 4.6 | Global | 20 | 20 | 0 | 0.000 | 0.000 | 0.000 | 0.000 |
| Gemini 2.5 Pro | Item-threshold | 8 | 4 | 6 | 0.000 | -0.040 | -0.125 | -0.015 |
| Gemini 2.5 Pro | Global | 20 | 22 | 2 | -0.057 | -0.043 | -0.040 | -0.073 |
| Combined | Item-threshold | 14 | 8 | 10 | -0.019 | -0.041 | -0.122 | -0.044 |
| Combined | Global | 62 | 64 | 2 | -0.019 | -0.014 | -0.014 | -0.024 |

## Conclusions

- For participant-containing transcripts, `global_binary_judgment` has higher balanced accuracy, recall, F1, and MCC than `thresholded_item_binary`.
- `thresholded_item_binary` is more conservative: it has high specificity but low recall, meaning it rarely predicts positives but misses many `PHQ8_Binary = 1` cases.
- `global_binary_judgment` is more sensitive: it has high recall but lower specificity, meaning it catches most `PHQ8_Binary = 1` cases but produces more false positives.
- Adding actual gender metadata changes global outputs very little: 2/105 combined output changes, compared with 10/105 for item-threshold outputs.
- `interviewer_only` should not be treated as a reliable depression-prediction input. It is better interpreted as a condition-sensitivity or leakage check.
- Recommended framing: use `global_binary_judgment` as the primary binary outcome for participant-containing transcripts, while retaining item-threshold results as a structured robustness check.
