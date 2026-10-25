# Module 4 — Project Progress and Remaining Work

Updated: 23 October 2026

## Overall idea

**Project:** Autonomous Cyber Defense & Response Engine, Module 4 of Project J26-CS-319.

Module 4 combines RF context supplied with Module 2, Module 2 threat intelligence, and Module 3 secure communication evidence. It checks the evidence, calculates current risk, identifies conflicting information, recommends a defensive response, and saves an explainable audit record.

The component recommends actions; it does not execute commands or control UAV hardware. Module 1 owns RF sensing, Module 2 owns threat classification, and Module 3 owns communication trust decisions.

## What my module does — simple explanation

My module is the decision-making component of the framework. It answers: **How risky is the current situation, why is it risky, and what defensive response should be recommended?**

For example, Module 2 may report jamming while Module 3 reports a degraded communication link. Module 4 combines those reports, calculates their configured risk contributions, checks whether they agree, and recommends a response with an explanation. It records the decision so it can be reviewed later.

### Input → processing → output

1. **Receive inputs:** RF context supplied with Module 2, Module 2 classification/severity/evidence, and Module 3 communication security states.
2. **Validate and normalize:** Check the input structure, match uploaded observations, and convert supported fields into the internal models.
3. **Correlate evidence:** Compare the threat classification with communication security evidence and identify agreement or conflict.
4. **Calculate risk:** Add classification, severity, link, freshness, authentication, and integrity points; cap the result at 100.
5. **Assess confidence:** Explain how reliable the decision is based on the available evidence.
6. **Recommend a response:** Apply the prioritized response rules to the current evidence and risk.
7. **Explain and record:** Return the score, risk level, recommendation, reasons, and evidence; save an audit record in SQLite.

The module does not detect RF signals itself, train the Module 2 classifier, perform Module 3 authentication, or execute the recommended UAV action.

## Main objective

**Develop an explainable RF-aware cyber-defense decision engine that combines threat intelligence and secure communication evidence to assess current risk, recommend a suitable defensive response, and preserve an auditable explanation.**

The objectives below follow the four objectives documented in this repository's revised Module 4 scope. The sub-objectives make that scope easier to track; their wording has not been checked against the official research proposal.

Status key: **Implemented** means code exists; **Pending verification** means acceptance evidence is still needed; **Remaining** means further work is required. An implemented feature is not automatically experimentally validated.

## Objective 1 — Integrate and correlate upstream evidence

Combine Module 2 threat intelligence and Module 3 secure communication evidence for the same observation, with supporting RF context.

### Sub-objectives already implemented

- [x] Define typed contracts for RF context, threat intelligence, and secure communication state.
- [x] Normalize supported upstream fields through isolated adapters.
- [x] Accept Module 2 and Module 3 JSON uploads.
- [x] Match observation identifiers and support the documented timestamp fallback.
- [x] Reject invalid or mismatched uploaded evidence with structured errors.
- [x] Correlate threat classification and communication security state.
- [x] Identify conflicting RF threat and communication evidence.
- [x] Display normalized evidence and source contributions.

### Sub-objectives still remaining or pending verification

- [ ] Agree the final file contracts with the Module 2 and Module 3 developers.
- [ ] Demonstrate integration using representative outputs produced by those modules, beyond preset/manual test cases.
- [ ] Record acceptance results for valid pairs, missing evidence, mismatched observations, and timestamp edge cases using agreed upstream files.

## Objective 2 — Calculate explainable current cyber-risk

Produce a risk score and level from the current threat and communication security evidence.

### Sub-objectives already implemented

- [x] Define configurable points for classification and severity from Module 2.
- [x] Define configurable points for link, freshness, authentication, and integrity from Module 3.
- [x] Calculate `Risk = min(100, C + S + L + F + A + I)`.
- [x] Assign LOW, MEDIUM, HIGH, or CRITICAL using configured thresholds.
- [x] Return the individual score contributions and total.
- [x] Keep RF measurements, statistical deviations, and reported threat confidence as supporting evidence rather than adding undocumented score terms.
- [x] Provide decision confidence with a rationale.
- [x] Display the formula and the current evaluation's calculation.
- [x] Cover risk calculations with automated regression tests.

### Sub-objectives still remaining or pending verification

- [ ] Calibrate scoring weights and risk thresholds using controlled, labeled experimental cases.
- [ ] Evaluate whether the score and confidence outputs match expected outcomes across representative operating conditions.
- [ ] Record the justification for the final weights and thresholds in the research report.

## Objective 3 — Recommend a context-aware defensive response

Choose an explainable recommendation from the current risk and evidence without executing the response.

### Sub-objectives already implemented

- [x] Define prioritized response rules in `backend/config/response_rules.py`.
- [x] Apply the first matching rule to select a response.
- [x] Support recommendations such as monitoring, preparing backup communication, switching to backup, secure hold, and operator escalation where matched by the policy.
- [x] Return a response rationale and recommendation-only status.
- [x] Include a baseline recommendation for comparison.
- [x] Test response selection through automated scenarios.

### Sub-objectives still remaining or pending verification

- [ ] Review the full response priority order and edge cases with the supervisor/team.
- [ ] Confirm expected recommendations for representative upstream integration cases.
- [ ] Perform and document an experimental comparison with the baseline to assess whether the proposed policy improves decisions.

## Objective 4 — Explain, display, and audit decisions

Make each decision understandable and traceable for demonstration, review, and research evaluation.

### Sub-objectives already implemented

- [x] Explain the risk breakdown, evidence agreement/conflict, confidence, and response rationale.
- [x] Persist incident evidence and decision details in SQLite with observation identifiers and timestamps.
- [x] Provide APIs for incident retrieval and risk history.
- [x] Provide file-based evaluation and manual/preset testing interfaces.
- [x] Display normalized Module 2/3 evidence and supporting RF context.
- [x] Simplify the interface by hiding missing RF values and synthetic scenario label messages.
- [x] Run backend tests and frontend checks during implementation.

### Sub-objectives still remaining or pending verification

- [ ] Complete browser acceptance testing of the latest interface changes.
- [ ] Verify that the displayed result and saved audit record agree for final demonstration cases.
- [ ] Update setup/navigation documentation to match the current interface.
- [ ] Prepare demonstration inputs, screenshots, evaluation results, and the final report/presentation.
- [ ] Confirm the required delivery environment and document deployment if hosting beyond localhost is required.

## Work still to do — recommended order

1. Obtain agreed Module 2 and Module 3 output files and expected results.
2. Run those files through the integration pipeline and record acceptance results.
3. Review scoring weights, thresholds, and response priorities using controlled cases.
4. Compare the engine's decisions against the baseline and report the findings.
5. Complete browser checks and reconcile displayed results with saved audit records.
6. Update documentation and prepare the final demonstration and handover.

These sub-objectives expand the same four remaining delivery milestones below. They are not extra equally weighted milestones and do not change the 75% planning estimate. RF sensing, classifier training, cryptographic implementation, and autonomous action execution are outside the documented Module 4 scope, rather than unfinished Module 4 tasks.

## Completion percentage

**Estimated Module 4 delivery progress: 75% — 12 of 16 equally weighted milestones implemented.**

Calculation: `12 / 16 × 100 = 75%`.

This is a planning estimate based on the checklist below and the code and checks reviewed in this session. It is not an official assessment score, a measured research-validation percentage, or the completion percentage of the entire four-module project. The final project rubric and real integration results have not been provided. Implemented items still need final acceptance testing.

## Completed tasks — 12 milestones

- [x] **1. Backend API:** FastAPI endpoints support evaluation, scenarios, status, incident retrieval, and risk history.
- [x] **2. Input contracts and normalization:** Models and adapters define RF context, threat intelligence, and secure communication inputs.
- [x] **3. JSON file integration:** Module 2 and Module 3 files pass through a shared validation and evaluation pipeline, including observation matching.
- [x] **4. Risk scoring:** Six configurable contributions produce a score capped at 100 and a risk level.
- [x] **5. Evidence correlation:** Module 2 and Module 3 evidence is combined for interpretation.
- [x] **6. Conflict detection:** The engine identifies conflicting threat and communication evidence.
- [x] **7. Decision confidence:** Confidence and its explanation are included in evaluation results.
- [x] **8. Response recommendations:** Prioritized rules choose a recommended response; the first matching rule wins.
- [x] **9. Explainability:** Results include reasons, scoring contributions, response rationale, and baseline comparison.
- [x] **10. Audit persistence:** SQLite stores incidents and supports risk-history retrieval.
- [x] **11. Evaluation and testing interface:** File uploads, manual inputs, presets, normalized evidence, and results are implemented. Recent interface changes are listed below.
- [x] **12. Automated checks and local startup:** Backend tests, frontend production build, frontend lint, and local server responses were verified during this session.

## Recent interface tasks completed

- Expanded the three normalized evidence panels to include the supported input fields.
- Hid RF fields when no value is supplied.
- Hid Reported Threat Confidence when no value is supplied.
- Hid synthetic test and synthetic communication label messages in the normalized evidence and correlation panels. The underlying evidence remains available to the backend and audit records.
- Added `Risk = min(100, C + S + L + F + A + I)` with definitions, individual points, and the current evaluation calculation.
- Removed the Defense Dashboard navigation item. Its underlying page and route were not deleted.

## Risk calculation

`Risk = min(100, C + S + L + F + A + I)`

- **C — Threat classification:** Normal = 0; Unknown Anomaly = 20; Jamming = 35.
- **S — Threat severity:** None = 0; Low = 10; Medium = 20; High = 30.
- **L — Communication link state:** TRUSTED = 0; DEGRADED = 15; SUSPICIOUS = 25; UNTRUSTED = 35.
- **F — Message freshness:** FRESH = 0; STALE = 10; REPLAY = 25.
- **A — Authentication status:** VALID = 0; SUSPICIOUS = 10; INVALID = 25.
- **I — Integrity status:** VALID = 0; SUSPICIOUS = 10; INVALID = 25.

Example: Jamming + Medium severity + DEGRADED link + FRESH messages + VALID authentication + VALID integrity gives `min(100, 35 + 20 + 15 + 0 + 0 + 0) = 70`, classified as HIGH.

Configured risk bands are LOW (0–24.9), MEDIUM (25–49.9), HIGH (50–74.9), and CRITICAL (75–100).

RF measurements and reported threat confidence provide supporting evidence; they do not add separate points to this formula. The correlation alignment indicator is also context, not an extra score contribution. Current weights are prototype values awaiting experimental calibration.

## Remaining tasks — 4 milestones

These items are pending or unverified, rather than confirmed absent from all previous work.

- [ ] **13. Validate real upstream integration:** Obtain representative Module 2 and Module 3 outputs, confirm their agreed schemas and matching identifiers, and record successful and rejected evaluations. Test missing fields, mismatched observations, timestamps, replay, and integrity failures with the upstream developers.
- [ ] **14. Calibrate and evaluate the research rules:** Review weights, thresholds, and response priorities against controlled experiments and labeled cases. Record expected versus actual decisions and compare the proposed engine with its baseline. Obtain supervisor or team agreement on the final policies.
- [ ] **15. Complete browser acceptance testing:** Check file upload, manual input, all presets, validation errors, evidence panels, formula values, recommendations, persistence after refresh, and small-screen layout. Confirm synthetic label messages are hidden in both evidence areas while meaningful evidence remains visible.
- [ ] **16. Finalize documentation and handover:** Update README navigation descriptions to match the removed Dashboard menu item, document setup for a fresh machine, prepare the demonstration inputs and presentation, and record final acceptance results. Confirm whether deployment beyond localhost is required; document it if required.

## Verification evidence

- Latest backend test run in this session: **137 passed**, with two FastAPI startup-event deprecation warnings.
- Latest frontend production build after the navigation change: **passed**.
- Frontend lint: **passed earlier in this session**, before the final display and navigation edits; run it again for final handover.
- Build output reports a JavaScript bundle-size warning. The build succeeds; review loading performance if needed for the intended deployment.
- Both local servers responded successfully when checked during this session; the backend status reported OPERATIONAL.
- Final visual browser acceptance testing and real UAV or live upstream integration have not been verified in this session.

## Important files to show

- `backend/config/scoring_weights.py` — scoring points and risk thresholds.
- `backend/config/response_rules.py` — prioritized response decision rules.
- `backend/services/risk_service.py` — adds the six score contributions and applies the cap.
- `backend/services/pipeline.py` — coordinates the evaluation stages.
- `backend/services/correlation_service.py` — combines source evidence.
- `backend/services/conflict_service.py` — identifies evidence conflicts.
- `backend/services/confidence_service.py` — assesses decision confidence.
- `backend/services/file_integration_service.py` — validates and matches uploaded files.
- `backend/services/audit_service.py` — stores and retrieves audit records.
- `backend/main.py` — API routes.
- `frontend/src/pages/Evaluate.tsx` — evaluation/testing interface and result explanations.
- `frontend/src/components/Layout.tsx` — navigation.
- `backend/tests/` — automated regression checks.

## How to check the project before presenting

1. Start the backend from `backend` with `py -m uvicorn main:app --reload --port 8000`.
2. Start the frontend from `frontend` with `npm run dev`.
3. Open `http://127.0.0.1:5173` and evaluate a preset or matching Module 2 and Module 3 JSON files.
4. Confirm the six displayed points add up to the shown risk score after applying the cap of 100.
5. Check the recommendation, reasons, evidence, and saved incident.
6. Run `py -m pytest tests/ -q` from `backend`.
7. Run `npm run build` and `npm run lint` from `frontend`.

The `py` command was not available in this session's terminal. The installed interpreter used successfully was `C:\Users\ranas\AppData\Local\Programs\Python\Python313\python.exe`. In PowerShell, replace `py` with `& 'C:\Users\ranas\AppData\Local\Programs\Python\Python313\python.exe'` if necessary. Use `npm.cmd` if PowerShell cannot run `npm`.

## Suggested next task

Start with milestone 13: evaluate an agreed pair of real Module 2 and Module 3 output files and save the result with the expected decision. This provides evidence for integration readiness and the later calibration work.
