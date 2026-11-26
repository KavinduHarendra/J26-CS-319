# Response datasets v1.1 and v1.2

An observation is one paired evaluation of Module 2 and Module 3 evidence. A feature is a value available when Module 4 is about to recommend a response. Only the first 15 columns are model inputs. Blank optional cells mean the source omitted the value. Import CSVs as UTF-8 and keep ID and version columns as text.

## Feature columns

1. `classification` (Module 2, required category) — `Normal`, `Jamming`, `Unknown Anomaly`.
2. `severity` (Module 2, optional category) — `Low`, `Medium`, `High`, or blank.
3. `threat_confidence` (Module 2, optional unitless number) — 0 through 1, or blank. This is the upstream confidence in threat evidence.
4. `triggered_rule_present` (Module 2, required boolean) — true when the reported `triggered_rule` is non-null. This follows the existing evidence-confidence check.
5. `abnormal_feature_count` (Module 2, required count) — length of `abnormal_features`, an integer of at least 0. The input schema uses an empty list when omitted.
6. `link_state` (Module 3, required category) — `TRUSTED`, `DEGRADED`, `SUSPICIOUS`, `UNTRUSTED`.
7. `freshness_state` (Module 3, required category) — `FRESH`, `STALE`, `REPLAY`.
8. `auth_state` (Module 3, required category) — `VALID`, `SUSPICIOUS`, `INVALID`.
9. `integrity_state` (Module 3, required category) — `VALID`, `SUSPICIOUS`, `INVALID`.
10. `replay_detected` (Module 3, required boolean) — true exactly when `freshness_state` is `REPLAY`.
11. `comm_decision` (Module 3, optional category) — `MAINTAIN`, `SWITCH`, `BACKUP`, `SECURE_HOLD`, or blank. It records Module 3's own decision.
12. `risk_score` (Module 4, required number) — 0 through 100 points, from the existing deterministic scorer.
13. `risk_level` (Module 4, required category) — `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`, from the existing risk thresholds.
14. `evidence_conflict` (Module 4, required boolean) — the existing conflict detector's flag.
15. `decision_confidence` (Module 4, required category) — `LOW`, `MEDIUM`, `HIGH`, from the existing evidence-confidence logic. Prediction scores from a future model will have a separate meaning.

## Provenance columns

16. `dataset_version` (required text) — `1.2` for current exports. Versions 1.1 and 1.2 share this header. The validator also accepts the v1.0 header and matching version. The 15 input features retain their original schema.
17. `policy_version` (required text) — `UNREVIEWED` on export. Record the rubric version for an approved label.
18. `observation_id` (required text) — Module 2's observation ID or the generated synthetic ID.
19. `incident_id` (optional text) — an existing incident reference if the collector supplies one.
20. `session_id` (text) — shared by related observations from one run. Required for Python-generated and confirmed experimental or testbed records.
21. `experiment_id` (text) — identifies the actual experiment or the Python generator configuration. Required for the same sources as `session_id`.
22. `scenario_id` (text) — a reported scenario or generator family. Required for the same sources as `session_id`.
23. `observed_at_utc` (required datetime) — evidence time in UTC using ISO 8601, e.g. `2026-01-01T00:00:00Z`.
24. `data_source` (required category) — `SYNTHETIC`, `CONTROLLED_EXPERIMENT`, `REAL_TESTBED`, `UNCONFIRMED`. All 23 paired exports supplied for this batch are synthetic.
25. `provenance` (category) — `CHATGPT_GENERATED` or `PYTHON_GENERATED` for v1.1 and v1.2 synthetic data. Leave it blank for experimental, testbed, or unconfirmed data. ChatGPT scenario fixtures and unconfirmed records may leave unknown group IDs blank.
26. `raw_record_ref` (required text) — a generator reference or a digest referencing the collection evidence index. The collector indexes the originals using their file paths and SHA-256 hashes.

## Baseline and label columns

27. `rule_based_response` (required action) — the existing contextual selector's recommendation.
28. `baseline_response` (required action) — the existing classification-only baseline.
29. `suggested_response` (optional action) — the initial suggestion. Export starts with the contextual rule output.
30. `validated_response` (optional action) — the target for a future supervised model. Fill it for approved independent reviews only.
31. `label_source` (optional category) — `RULE_SUGGESTED`, `MANUAL`, `SUPERVISOR`, `EXPERT`, `EXPERIMENT`. For an approved label the source must identify independent review.
32. `label_status` (required category) — `PENDING`, `APPROVED`, `DISPUTED`, `UNCERTAIN`.
33. `reviewer_notes` (optional text) — rationale, reviewer identifier, or an outcome reference if needed.
34. `acceptable_responses` (optional JSON list of actions) — other acceptable recommendations. Each alternative may appear once. Keep the primary response in `validated_response`.

The six action values are `MONITOR`, `CONTINUE_MONITORING`, `INCREASE_MONITORING`, `PREPARE_BACKUP_CHANNEL`, `OPERATOR_ESCALATION` and `SECURE_HOLD`. Boolean values are exported as `true` or `false`. The validator recomputes the score, band, conflict flag, evidence confidence and both rule recommendations, and checks for duplicate observations and raw references.
