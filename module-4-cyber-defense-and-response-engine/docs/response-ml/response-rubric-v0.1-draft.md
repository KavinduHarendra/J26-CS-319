# Draft response-labeling rubric v0.1

Identifier `response-rubric-v0.1-draft`. Proposed for reviewer approval. The offline rubric emits a suggestion and a criterion in the private review key. The existing rule selectors still supply the two baseline columns and all application recommendations.

Use this rubric to choose one high-level Module 4 recommendation. Module 3 owns authentication, integrity, freshness, replay detection, and communication decisions. Its reported `comm_decision` is evidence for your review. Module 4 recommendations do not execute actions.

## Choose the first applicable category

1. **SECURE_HOLD.** Confirmed replay with consistent evidence, or corroborated communication failure when the link is untrusted, both authentication and integrity are invalid, and Module 3 reports `SECURE_HOLD`. Recommend holding the affected communication path for operator review. Example: Normal RF can coexist with confirmed replay.
2. **OPERATOR_ESCALATION.** Ask a human to verify and decide when evidence is conflicting, stale, suspicious or invalid, the link is suspicious or untrusted, or Module 3 reports a hold outside rule 1. Example: a single invalid integrity check calls for verification. It does not by itself establish the corroborated failure in rule 1.
3. **PREPARE_BACKUP_CHANNEL.** Recommend checking backup readiness when Module 2 reports confirmed jamming, the link is degraded, and authentication, integrity, and freshness are valid with no unresolved conflict. Backup preparation is a recommendation for the operator. Module 3 retains authority for any communication change.
4. **OPERATOR_ESCALATION for any remaining critical risk.** Never choose a monitoring-only response when the evidence and current score place a case in `CRITICAL`. The 85-point family has suspicious link status, stale messages and invalid authentication and integrity. The contextual baseline still returns `CONTINUE_MONITORING`. This draft recommends operator escalation under rule 2.
5. **INCREASE_MONITORING.** Ask for **more frequent checks or additional evidence** for an RF anomaly or interference when security evidence remains valid, no earlier rule applies, and the situation is suitable for monitoring. Example: Unknown Anomaly with a trusted and authenticated link.
6. **CONTINUE_MONITORING.** Keep the **current observation cadence with an explicit follow-up** when a limited issue remains visible and security checks stay valid. Example: routine RF and a slightly degraded, authenticated link. The follow-up should state what change would prompt reassessment.
7. **MONITOR.** Keep **routine observation** when RF is Normal, the link is trusted, security checks are valid and fresh, there is no unresolved conflict, and risk is LOW. Use the ordinary monitoring cadence.

Use `UNCERTAIN` if the evidence cannot support a primary response. During adjudication, record the primary choice separately from any defensible alternatives. Keep `validated_response` blank until a human decision is approved independently. If a reviewer disagrees with an earlier suggestion, record their reasoning and use `DISPUTED` while agreement is pending. Preserve the rule and rubric suggestions for comparison.

The rubric is an offline proposal for synthetic-case review. Prototype performance on these labels describes behavior under this rubric on synthetic data. Independent experimental evidence is a separate requirement.
