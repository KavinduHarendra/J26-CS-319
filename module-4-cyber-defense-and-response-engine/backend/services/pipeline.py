"""Module 4 — Complete Evaluation Pipeline Orchestrator.

This module wires together all services to execute the full Module 4
decision pipeline in sequence:

  Module 1 / RF context
              +
  Module 2 Threat Intelligence
              +
  Module 3 Secure Communication State
              ↓
  INPUT VALIDATION
              ↓
  DATA NORMALIZATION (adapters)
              ↓
  MULTI-SOURCE EVIDENCE CORRELATION
              ↓
  DYNAMIC RISK SCORING
              ↓
  DECISION CONFIDENCE / UNCERTAINTY HANDLING
              ↓
  RESPONSE PRIORITIZATION
              ↓
  EXPLAINABLE DECISION
              ↓
  INCIDENT / AUDIT LOGGING

All intermediate results are preserved for explainability and audit.
"""

from datetime import datetime

from models.defense import EvaluateRequest, EvaluateResponse
from adapters import module1_adapter, module2_adapter, module3_adapter
from services import (
    correlation_service,
    risk_service,
    conflict_service,
    confidence_service,
    response_service,
    explanation_service,
    audit_service,
)


def run_pipeline(request: EvaluateRequest, integration_metadata: dict | None = None) -> EvaluateResponse:
    """Execute the complete Module 4 defense decision pipeline.

    Each stage is executed in order. All intermediate results are
    captured for audit logging and explainability output.
    """
    timestamp = datetime.now().isoformat()
    incident_id = audit_service.get_next_incident_id()

    # ── STAGE 1: DATA NORMALIZATION (via adapters) ────────────────────────────
    # Adapters normalize and validate each module's output.
    # If a module is unavailable, adapters return safe defaults.
    rf = module1_adapter.adapt(request.rf_context.model_dump())
    ti = module2_adapter.adapt(request.threat_intelligence.model_dump())
    sc = module3_adapter.adapt(request.secure_communication.model_dump())

    observation_id = rf.observation_id or "OBS-UNSET"

    # ── STAGE 2: MULTI-SOURCE EVIDENCE CORRELATION ────────────────────────────
    # Explicitly correlates Module 2 and Module 3 evidence.
    # This is NOT a simple merge — it tracks agreement/disagreement.
    correlation = correlation_service.correlate(ti, sc)

    # ── STAGE 3: DYNAMIC RISK SCORING ────────────────────────────────────────
    # Computes an explainable, config-driven risk score (0–100).
    # All weights are loaded from config/scoring_weights.py.
    risk_score, risk_level, risk_breakdown = risk_service.compute_risk(ti, sc)

    # ── STAGE 5: CONFLICT DETECTION ──────────────────────────────────────────
    # Detect conflicting evidence between Module 2 and Module 3.
    # When conflict exists: confidence is reduced, response is conservative.
    conflict = conflict_service.detect_conflict(ti, sc)

    # ── STAGE 6: DECISION CONFIDENCE ─────────────────────────────────────────
    # Assess how confident Module 4 is in its decision.
    confidence = confidence_service.assess_confidence(ti, sc, conflict)

    # ── STAGE 7: RESPONSE PRIORITIZATION ─────────────────────────────────────
    # Select response from prioritized rule table.
    recommended_response, response_rationale, baseline_response = response_service.select_response(
        ti, sc, risk_score, conflict
    )

    # ── STAGE 8: BASELINE COMPARISON ─────────────────────────────────────────
    baseline_vs_proposed = response_service.compare_baseline(recommended_response, baseline_response)

    # ── STAGE 9: EXPLAINABLE DECISION ────────────────────────────────────────
    # Build ordered list of human-readable reasons for the decision.
    reasons = explanation_service.build_reasons(
        rf, ti, sc, risk_score, risk_level, risk_breakdown,
        correlation, conflict, confidence.level, recommended_response,
    )
    reasons.append(f"Response selection rationale: {response_rationale}")
    pipeline_stages = explanation_service.build_pipeline_stages()

    # ── STAGE 10: BUILD RESPONSE ──────────────────────────────────────────────
    response = EvaluateResponse(
        incident_id=incident_id,
        observation_id=observation_id,
        timestamp=timestamp,

        risk_score=risk_score,
        risk_level=risk_level,
        risk_breakdown=risk_breakdown,

        correlation=correlation,

        evidence_conflict=conflict.evidence_conflict,
        conflict_reason=conflict.conflict_reason,

        decision_confidence=confidence.level,
        confidence_rationale=confidence.rationale,

        recommended_response=recommended_response,
        response_status="RECOMMENDED",
        response_rationale=response_rationale,

        reasons=reasons,
        pipeline_stages=pipeline_stages,

        baseline_response=baseline_response,
        baseline_vs_proposed=baseline_vs_proposed,

        module1_context=module1_adapter.summary_dict(rf),
        module2_context=module2_adapter.summary_dict(ti),
        module3_context=module3_adapter.summary_dict(sc),
        integration_status="SUCCESS" if integration_metadata else None,
        input_sources=integration_metadata or {},
        match_method=(integration_metadata or {}).get("match_method"),
    )

    # ── STAGE 11: INCIDENT / AUDIT LOGGING ───────────────────────────────────
    # Persist the complete evaluation record to SQLite.
    audit_service.save_incident(response)

    return response
