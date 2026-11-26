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
from response_ml.modes import ResponseMode, read_response_mode
from services import (
    response_service,
    explanation_service,
    audit_service,
)
from services.evidence_service import assess_evidence
from services.response_selection_service import select_research_response


def run_pipeline(request: EvaluateRequest, integration_metadata: dict | None = None) -> EvaluateResponse:
    """Execute the complete Module 4 defense decision pipeline.

    Each stage is executed in order. All intermediate results are
    captured for audit logging and explainability output.
    """
    mode = read_response_mode()
    timestamp = datetime.now().isoformat()
    incident_id = audit_service.get_next_incident_id()

    # Share normalization and deterministic assessment with offline collection.
    evidence = assess_evidence(request)
    rf, ti, sc = evidence.rf, evidence.threat, evidence.communication
    risk_score, risk_level, risk_breakdown = evidence.risk_score, evidence.risk_level, evidence.risk_breakdown
    correlation, conflict, confidence = evidence.correlation, evidence.conflict, evidence.confidence
    observation_id = rf.observation_id or "OBS-UNSET"

    # ── STAGE 7: RESPONSE PRIORITIZATION ─────────────────────────────────────
    rule_response, rule_rationale, baseline_response = response_service.select_response(
        ti, sc, risk_score, conflict
    )
    recommended_response, response_rationale = rule_response, rule_rationale
    response_selection = None
    if mode != ResponseMode.RULE_BASED:
        recommended_response, response_rationale, response_selection = select_research_response(
            mode, evidence, rule_response, rule_rationale,
        )

    # ── STAGE 8: BASELINE COMPARISON ─────────────────────────────────────────
    baseline_vs_proposed = response_service.compare_baseline(rule_response, baseline_response)

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
        response_selection=response_selection,
    )

    # ── STAGE 11: INCIDENT / AUDIT LOGGING ───────────────────────────────────
    # Persist the complete evaluation record to SQLite.
    audit_service.save_incident(response)

    return response
