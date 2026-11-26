"""Versioned CSV contract for observations and independently reviewed labels."""

import csv
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Iterable, Literal

from pydantic import AfterValidator, AwareDatetime, BaseModel, StringConstraints, field_validator, model_validator

from models.defense import EvaluateRequest
from response_ml.features import ResponseAction, ResponseFeatures, extract_features
from services.evidence_service import AssessedEvidence, assess_evidence
from services.response_service import select_response


def spreadsheet_text(value: str) -> str:
    if value.startswith(("=", "+", "-", "@")):
        raise ValueError("Use plain text that cannot be interpreted as a spreadsheet formula.")
    return value


CsvText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1), AfterValidator(spreadsheet_text)]
DataSource = Literal["SYNTHETIC", "CONTROLLED_EXPERIMENT", "REAL_TESTBED", "UNCONFIRMED"]
GenerationProvenance = Literal["CHATGPT_GENERATED", "PYTHON_GENERATED"]
DatasetVersion = Literal["1.0", "1.1", "1.2"]
DATASET_VERSION: DatasetVersion = "1.2"
LabelSource = Literal["RULE_SUGGESTED", "MANUAL", "SUPERVISOR", "EXPERT", "EXPERIMENT"]
LabelStatus = Literal["PENDING", "APPROVED", "DISPUTED", "UNCERTAIN"]
UNREVIEWED = "UNREVIEWED"


class Provenance(BaseModel, extra="forbid"):
    dataset_version: DatasetVersion = DATASET_VERSION
    policy_version: CsvText = UNREVIEWED
    observation_id: CsvText
    incident_id: CsvText | None = None
    session_id: CsvText | None = None
    experiment_id: CsvText | None = None
    scenario_id: CsvText | None = None
    observed_at_utc: AwareDatetime
    data_source: DataSource
    provenance: GenerationProvenance | None = None
    raw_record_ref: CsvText

    @model_validator(mode="after")
    def require_confirmed_provenance(self):
        if self.provenance is not None and (self.data_source != "SYNTHETIC" or self.dataset_version == "1.0"):
            raise ValueError("Generation provenance requires a v1.1 or v1.2 SYNTHETIC record.")
        if self.dataset_version != "1.0" and self.data_source == "SYNTHETIC" and self.provenance is None:
            raise ValueError("v1.1 and v1.2 SYNTHETIC records require generation provenance.")

        group_required = self.data_source != "UNCONFIRMED" and self.provenance != "CHATGPT_GENERATED"
        if group_required and any(
            value is None for value in (self.session_id, self.experiment_id, self.scenario_id)
        ):
            raise ValueError("Confirmed sources require session_id, experiment_id and scenario_id.")
        return self

    @field_validator("observed_at_utc", mode="before")
    @classmethod
    def require_utc(cls, value):
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("observed_at_utc must be an ISO 8601 timestamp.") from exc
        if not isinstance(value, datetime) or value.utcoffset() != timedelta(0):
            raise ValueError("observed_at_utc must be in UTC. Use a timestamp ending in Z.")
        return value


class DatasetRow(ResponseFeatures, Provenance):
    rule_based_response: ResponseAction
    baseline_response: ResponseAction
    suggested_response: ResponseAction | None = None
    validated_response: ResponseAction | None = None
    label_source: LabelSource | None = None
    label_status: LabelStatus = "PENDING"
    reviewer_notes: CsvText | None = None
    acceptable_responses: list[ResponseAction] | None = None

    @property
    def group(self) -> tuple[str, str, str] | None:
        if self.experiment_id is None or self.session_id is None:
            return None
        return self.data_source, self.experiment_id, self.session_id

    @model_validator(mode="after")
    def validate_review(self):
        if self.label_status == "APPROVED":
            if not self.validated_response or self.label_source in (None, "RULE_SUGGESTED"):
                raise ValueError("APPROVED needs a validated_response and an independent label_source.")
            if self.policy_version == UNREVIEWED:
                raise ValueError("APPROVED needs the version of the rubric used to review the label.")
        elif self.validated_response is not None:
            raise ValueError("Leave validated_response blank until label_status is APPROVED.")
        if self.acceptable_responses is not None:
            if len(set(self.acceptable_responses)) != len(self.acceptable_responses):
                raise ValueError("Each acceptable alternative may appear once.")
            if self.validated_response in self.acceptable_responses:
                raise ValueError("Keep the primary validated_response out of the alternatives list.")
        return self


DATASET_COLUMNS = (*ResponseFeatures.model_fields, *Provenance.model_fields,
                   "rule_based_response", "baseline_response", "suggested_response",
                   "validated_response", "label_source", "label_status", "reviewer_notes",
                   "acceptable_responses")
V1_COLUMNS = tuple(column for column in DATASET_COLUMNS if column != "provenance")


def make_row(evidence: AssessedEvidence, provenance: Provenance) -> DatasetRow:
    contextual, _, classification_only = select_response(
        evidence.threat, evidence.communication, evidence.risk_score, evidence.conflict
    )
    return DatasetRow(
        **extract_features(evidence).model_dump(),
        **provenance.model_dump(),
        rule_based_response=contextual,
        baseline_response=classification_only,
        suggested_response=contextual,
        label_source="RULE_SUGGESTED",
    )


def validate_derived_columns(row: DatasetRow) -> None:
    """Recompute fields used by the existing scorer and both existing selectors."""
    request = EvaluateRequest.model_validate({
        "threat_intelligence": {
            "classification": row.classification,
            "severity": row.severity,
            "triggered_rule": "PRESENT" if row.triggered_rule_present else None,
        },
        "secure_communication": {
            "link_state": row.link_state,
            "freshness_state": row.freshness_state,
            "auth_state": row.auth_state,
            "integrity_state": row.integrity_state,
            "replay_detected": row.replay_detected,
            "comm_decision": row.comm_decision,
        },
    })
    evidence = assess_evidence(request)
    expected = extract_features(evidence).model_dump(
        include={"risk_score", "risk_level", "evidence_conflict", "decision_confidence"}
    )
    contextual, _, classification_only = select_response(
        evidence.threat, evidence.communication, evidence.risk_score, evidence.conflict
    )
    expected.update(rule_based_response=contextual, baseline_response=classification_only)
    if difference := [field for field, value in expected.items() if getattr(row, field) != value]:
        raise ValueError(f"Derived values differ from the existing engine: {', '.join(difference)}.")


def require_unique(row: DatasetRow, observations: set, raw_refs: set) -> None:
    observation = (row.data_source, row.experiment_id, row.session_id, row.observation_id)
    if observation in observations:
        raise ValueError("Duplicate observation within the same source, experiment and session.")
    if row.raw_record_ref in raw_refs:
        raise ValueError("Duplicate raw_record_ref. Keep repeated copies of the same evidence out of the dataset.")
    observations.add(observation)
    raw_refs.add(row.raw_record_ref)


def write_csv(path: Path, rows: Iterable[DatasetRow]) -> None:
    """Create an export without replacing an existing review file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("x", encoding="utf-8", newline="")
    try:
        with stream:
            writer = csv.DictWriter(stream, fieldnames=DATASET_COLUMNS)
            writer.writeheader()
            for row in rows:
                record = row.model_dump(mode="json")
                for key, value in record.items():
                    if isinstance(value, (bool, list)):
                        record[key] = json.dumps(value, separators=(",", ":"))
                writer.writerow(record)
    except (OSError, csv.Error):
        path.unlink(missing_ok=True)
        raise


def load_csv(path: Path) -> list[DatasetRow]:
    observations: set = set()
    raw_refs: set = set()
    rows = []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        headers = reader.fieldnames or []
        if len(headers) == len(V1_COLUMNS) and set(headers) == set(V1_COLUMNS):
            accepted_versions = ("1.0",)
        elif len(headers) == len(DATASET_COLUMNS) and set(headers) == set(DATASET_COLUMNS):
            accepted_versions = ("1.1", "1.2")
        else:
            raise ValueError("Invalid header. Use the current template with every column appearing once. "
                             "The original v1.0 header is also supported for v1.0 records.")
        for record in reader:
            try:
                if None in record or None in record.values():
                    raise ValueError("This row has a different number of cells from its header.")
                values = {key: value if value.strip() else None for key, value in record.items()}
                if values["dataset_version"] not in accepted_versions:
                    raise ValueError(f"This header requires dataset_version {' or '.join(accepted_versions)}.")
                if values["acceptable_responses"] is not None:
                    values["acceptable_responses"] = json.loads(values["acceptable_responses"])
                row = DatasetRow.model_validate(values)
                validate_derived_columns(row)
                require_unique(row, observations, raw_refs)
            except ValueError as exc:
                raise ValueError(f"{path.name}, CSV line {reader.line_num}: {exc}") from exc
            rows.append(row)
    if not rows:
        raise ValueError("The CSV has a header but no observations to validate.")
    return rows


def validate_csv(path: Path) -> dict:
    rows = load_csv(path)
    groups = {row.group for row in rows if row.group is not None}
    ungrouped = sum(row.group is None for row in rows)
    provenance = Counter(row.provenance for row in rows if row.provenance is not None)
    summary = {
        "rows": len(rows), "session_groups": len(groups),
        "data_sources": dict(Counter(row.data_source for row in rows)),
        "label_statuses": dict(Counter(row.label_status for row in rows)),
    }
    if ungrouped:
        summary["rows_without_session_groups"] = ungrouped
    if provenance:
        summary["provenance"] = dict(provenance)
    return summary
