# Proposed ML safety policy v0.1

Status is **for review**. The existing contextual rules remain authoritative in all three mode settings. The known 85-point `CRITICAL` observation still yields `CONTINUE_MONITORING` with the existing policy-review warning in the reference baseline. The [draft response rubric](response-rubric-v0.1-draft.md) records a separate offline suggestion.

Module 3 owns the communication security state and its own `comm_decision` values `MAINTAIN`, `SWITCH`, `BACKUP` and `SECURE_HOLD`. Module 4 uses those values as context. Its six response classes describe high-level recommendations for people. The two modules use the spelling `SECURE_HOLD` in separate fields for distinct responsibilities. Module 4 has no path to execute communication or flight changes.

## Proposed handling for a future ML branch

- **Incomplete, invalid or mismatched input.** Keep the existing input rejection behavior. Stop before model evaluation. Record rejection details in the controlled collection process.
- **Confirmed replay.** Disallow a model-selected recommendation. Propose keeping the existing `SECURE_HOLD` recommendation and requesting operator review. Module 3's communication decision retains its authority.
- **Corroborated communication failure.** Where Module 3 reports an untrusted link, invalid authentication and integrity, and its own `SECURE_HOLD`, the draft recommends secure hold for operator review. The recommendation does not execute a hold.
- **Other invalid authentication, invalid integrity, or stale evidence.** Reject model-selected recommendations and propose `OPERATOR_ESCALATION` for verification. Agree how to check observation age separately. The existing five-second file pairing tolerance compares two timestamps, and Module 3's freshness category describes message evidence.
- **Conflicting evidence.** Propose operator review before accepting an ML recommendation. Preserve the existing conflict flag and its reason for reviewers.
- **Critical risk with a monitoring candidate.** Reject `MONITOR`, `CONTINUE_MONITORING`, and `INCREASE_MONITORING` as final ML recommendations in this case. Route to the approved safety recommendation. The draft routes the 85-point gap to `OPERATOR_ESCALATION`. Preserve both the raw candidate and the contextual baseline for the comparison.
- **Missing artifact, inference error, unsupported class, or low prediction score.** Revert to the contextual recommendation only when the approved policy permits it. Propose operator review for the remaining valid inputs. Select any confidence threshold on independent validation groups and record which policy condition blocked the candidate.

Before enabling ML authority, approve the label rubric and the safety policy, confirm the fallback and age rules, and approve independent evaluation results from held-out sessions. Keep the classification-only baseline and the original contextual rules available to reproduce comparisons.
