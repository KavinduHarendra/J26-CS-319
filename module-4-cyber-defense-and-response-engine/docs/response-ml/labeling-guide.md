# Reviewing response labels

A label is the response a reviewer judges appropriate for an observation. The CSV export puts the engine's current recommendation in `rule_based_response` and `suggested_response`. Each new row starts with a blank `validated_response` and `PENDING` status.

Use [labeling-template.csv](labeling-template.csv) for the exact column names. For a real review, use a copy of an exported dataset, so the evidence and provenance columns are already populated. [example-synthetic.csv](example-synthetic.csv) contains generated rows for practice. Set spreadsheet imports to UTF-8 and preserve IDs, timestamps and version strings as text.

1. Agree on a versioned response rubric with the supervisor and note who reviewed each observation. Review normalized evidence and any permitted experimental outcomes first. Keep the rule suggestions hidden during that first judgment where practical.
2. Pick one primary Module 4 recommendation. If the evidence is insufficient, use `UNCERTAIN`. If reviewers disagree, use `DISPUTED` until the case is adjudicated. Leave `validated_response` blank for both states.
3. After independent review, enter the chosen action in `validated_response`, set `label_status` to `APPROVED`, pick the appropriate `label_source` and enter the approved rubric identifier in `policy_version`. Use `reviewer_notes` for the reasoning and review record. An `EXPERIMENT` label should cite the outcome record that supports it.
4. For an approved primary action with other acceptable choices, enter them as a JSON list in the `acceptable_responses` cell. For example, if an approved primary action is `OPERATOR_ESCALATION`, a reviewer could record `["SECURE_HOLD"]` where the approved rubric allows it. These codes describe recommendations for review.
5. Save as UTF-8 CSV under a new filename. Run the validation command in the project README. Fix the row identified by the error and validate again before sharing the reviewed copy.

Keep the original evidence, both rule fields, and the source and session IDs for comparison. Keep synthetic and controlled/real observations distinguishable. Reviewers can practice on synthetic rows. Independent experiments and labels are required to measure performance on real observations. Keep related observations together for future training, validation and testing, and reserve independent test sessions for final evaluation.

## v1.2 blind review and labeling effort

Review and approve the [draft rubric](response-rubric-v0.1-draft.md) before assigning independent labels. Give the reviewer `blind-review.csv` and the approved rubric. Keep `labeling-review.csv`, `review-key.csv`, and the comparison report private until their first pass is complete. The blind file lists the input evidence and a review ID. It omits the baseline answers, draft suggestions, case-family names, and split assignments.

Start with the 144 selected rows. The sample deliberately covers both sets of suggested classes, all risk bands, security states, conflict cases, and all 18 families. It includes every v1.2 critical monitoring case. A second reviewer can adjudicate disagreements and inspect a small random sample of easy cases. Use the private key to match a completed review ID to its observation ID in a copy of `labeling-review.csv`. Fill `validated_response` and `label_status` from the human decision and record the independent label source and approved rubric version. Run `validate` on the reviewed copy.

Keep the contextual and draft suggestions as separate reference fields. If a future approved prototype uses draft-rubric suggestions for the remaining synthetic training rows, treat them as provisional training labels and preserve their rubric version. Keep those rows out of the independently labeled validation and test sets. Measure and report results on independently reviewed cases separately. If a class lacks support after review, add targeted cases from independent families or limit the claims for that class.

The 23 paired fixtures use `SYNTHETIC` and `CHATGPT_GENERATED`. Leave their session, experiment, and scenario IDs blank. These fixtures can help reviewers practice and test integration. Preserve the provenance when approving a synthetic label. The Python-generated file uses `PYTHON_GENERATED` and has seeded session groups. Keep repeated feature combinations and scenario families together if you develop a synthetic evaluation later. Reports from that evaluation describe prototype behavior on synthetic data.

For future measured observations, retain the original Module 2 and Module 3 files and confirm the collection source, documented session and experiment IDs, and reviewer rubric before using them in experimental evaluation.
