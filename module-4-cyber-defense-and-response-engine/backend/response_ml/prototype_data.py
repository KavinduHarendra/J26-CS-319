"""Validated inputs for an offline synthetic prototype."""

import csv
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from response_ml.dataset import DATASET_COLUMNS, DatasetRow, load_csv
from response_ml.evaluation import PARTITIONS
from response_ml.generate import STRUCTURAL_FEATURES, feature_signature
from response_ml.review import SPLIT_COLUMNS
from response_ml.rubric import MONITORING, RESPONSE_CLASSES, RUBRIC_VERSION, suggest_response

LABEL_EXPORT_VERSION = "1.0"
PROTOTYPE_DATASET_VERSION = "1.2"
LABEL_COLUMNS = (*DATASET_COLUMNS, "provisional_response", "provisional_criterion", "rubric_version", "label_export_version")
PARTITION_SIZES = dict(zip(PARTITIONS, (560, 220, 220)))


@dataclass(frozen=True)
class LabeledObservation:
    row: DatasetRow
    target: str
    criterion: str


@dataclass(frozen=True)
class Study:
    partitions: dict[str, list[LabeledObservation]]
    hashes: dict[str, str]
    overlap: dict

    @property
    def novel_test_ids(self) -> set[str]:
        earlier = {
            feature_signature(case.row, STRUCTURAL_FEATURES)
            for partition in ("train", "validation")
            for case in self.partitions[partition]
        }
        return {
            case.row.observation_id for case in self.partitions["test"]
            if feature_signature(case.row, STRUCTURAL_FEATURES) not in earlier
        }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_records(path: Path, header: tuple[str, ...]) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if tuple(reader.fieldnames or ()) != header:
            raise ValueError(f"{path.name} has an unexpected CSV header.")
        records = list(reader)
        if any(None in row or None in row.values() for row in records):
            raise ValueError(f"{path.name} has an incomplete CSV row.")
        return records


def draft_labels(rows: list[DatasetRow]) -> list[LabeledObservation]:
    for row in rows:
        if (row.dataset_version, row.data_source, row.provenance) != (PROTOTYPE_DATASET_VERSION, "SYNTHETIC", "PYTHON_GENERATED"):
            raise ValueError("Use the v1.2 Python-generated dataset for this provisional prototype.")
        if row.label_status != "PENDING" or row.validated_response is not None:
            raise ValueError("Automatic labeling requires the original pending dataset.")
    return [LabeledObservation(row, suggestion.response, suggestion.criterion)
            for row in rows for suggestion in (suggest_response(row),)]


def labeled_record(case: LabeledObservation) -> dict[str, str]:
    fields = {
        **case.row.model_dump(mode="json"),
        "label_source": "RUBRIC_GENERATED",
        "provisional_response": case.target,
        "provisional_criterion": case.criterion,
        "rubric_version": RUBRIC_VERSION,
        "label_export_version": LABEL_EXPORT_VERSION,
    }
    return {
        key: "" if value is None else json.dumps(value, separators=(",", ":")) if isinstance(value, (bool, list))
        else str(value)
        for key, value in fields.items()
    }


def label_summary(cases: list[LabeledObservation]) -> dict:
    counts = Counter(case.target for case in cases)
    return {
        "rows": len(cases), "rubric_version": RUBRIC_VERSION,
        "label_source": "RUBRIC_GENERATED", "label_status": "PENDING",
        "provisional_labels": {action: counts[action] for action in RESPONSE_CLASSES},
        "rubric_criteria": dict(Counter(case.criterion for case in cases)),
        "review_flags": {
            "conflicting_evidence": sum(case.row.evidence_conflict for case in cases),
            "low_evidence_confidence": sum(case.row.decision_confidence == "LOW" for case in cases),
            "critical_contextual_monitoring": sum(
                case.row.risk_level == "CRITICAL" and case.row.rule_based_response in MONITORING for case in cases
            ),
        },
        "unsupported_cases": sum(case.target not in RESPONSE_CLASSES for case in cases),
        "approved_responses": sum(case.row.validated_response is not None for case in cases),
    }


def load_study(source: Path, labels: Path, manifest: Path) -> Study:
    hashes = {name: sha256(path) for name, path in (("source", source), ("labels", labels), ("split_manifest", manifest))}
    cases = draft_labels(load_csv(source))
    if read_records(labels, LABEL_COLUMNS) != [labeled_record(case) for case in cases]:
        raise ValueError("The provisional CSV differs from the draft rubric export of the original dataset.")

    manifest_rows = read_records(manifest, SPLIT_COLUMNS)
    by_id = {row["observation_id"]: row for row in manifest_rows}
    if len(by_id) != len(manifest_rows) or set(by_id) != {case.row.observation_id for case in cases}:
        raise ValueError("Split manifest IDs must cover the original dataset exactly once.")

    partitions = {name: [] for name in PARTITIONS}
    family_fold, session_fold, exact_fold = {}, {}, {}
    for case in cases:
        row = case.row
        entry = by_id[row.observation_id]
        partition = entry["partition"]
        if partition not in partitions or row.group is None or row.scenario_id is None:
            raise ValueError(f"Missing or unsupported split metadata for {row.observation_id}.")
        if (entry["session_id"], entry["scenario_id"]) != (row.session_id, row.scenario_id):
            raise ValueError(f"Split manifest metadata differs for {row.observation_id}.")
        for kind, assigned, value in (
            ("family", family_fold, row.scenario_id),
            ("session", session_fold, row.group),
            ("exact feature vector", exact_fold, feature_signature(row)),
        ):
            if assigned.setdefault(value, partition) != partition:
                raise ValueError(f"A {kind} overlaps partitions.")
        partitions[partition].append(case)

    if {name: len(part) for name, part in partitions.items()} != PARTITION_SIZES:
        raise ValueError("Expected the frozen 560 / 220 / 220 partition sizes.")
    if any({case.target for case in part} != set(RESPONSE_CLASSES) for part in partitions.values()):
        raise ValueError("Expected all six provisional response classes in each partition.")

    earlier_structures = set()
    structural_overlap = {}
    for name, cases_in_fold in partitions.items():
        signatures = [feature_signature(case.row, STRUCTURAL_FEATURES) for case in cases_in_fold]
        structural_overlap[name] = sum(vector in earlier_structures for vector in signatures)
        earlier_structures.update(signatures)

    if any(sha256(path) != hashes[name] for name, path in (("source", source), ("labels", labels), ("split_manifest", manifest))):
        raise ValueError("Study inputs changed during verification.")
    return Study(partitions, hashes, {
        "exact_cross_partition_feature_vectors": 0, "cross_partition_sessions": 0, "cross_partition_families": 0,
        "rows_matching_an_earlier_partition_without_threat_confidence": structural_overlap,
    })
