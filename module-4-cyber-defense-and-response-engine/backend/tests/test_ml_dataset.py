import asyncio
import csv
import json
from pathlib import Path

import pytest

from data.evaluate_scenarios import EVALUATE_SCENARIOS
from response_ml.collect import collect_rows, export_collection
from response_ml.dataset import DATASET_COLUMNS, V1_COLUMNS, DatasetRow, validate_csv, write_csv
from response_ml.features import FEATURE_COLUMNS
from response_ml.generate import STRUCTURAL_FEATURES, feature_signature, generate_rows
from services import audit_service


def test_generator_covers_scenarios_without_assigning_ground_truth():
    rows = generate_rows(1000, seed=42, session_size=10)
    assert len(rows) == 1000
    assert len({row.group for row in rows}) == 100
    assert len({row.scenario_id for row in rows}) == 18
    assert len({(row.classification, row.link_state) for row in rows}) == 12
    assert len({row.observation_id for row in rows}) == 1000
    assert len({feature_signature(row) for row in rows}) == 1000
    assert len({feature_signature(row, STRUCTURAL_FEATURES) for row in rows}) >= 180
    for family in {row.scenario_id for row in rows}:
        examples = [row for row in rows if row.scenario_id == family]
        assert len({row.risk_score for row in examples}) > 1, family
        assert len({row.rule_based_response for row in examples}) > 1, family
    assert all(
        row.link_state != "TRUSTED"
        or (row.auth_state == row.integrity_state == "VALID" and row.freshness_state == "FRESH")
        for row in rows
    )
    assert all(
        row.link_state == "UNTRUSTED"
        or row.scenario_id == "critical_monitoring_gap"
        for row in rows if row.auth_state == "INVALID" or row.integrity_state == "INVALID"
    )
    assert {row.rule_based_response for row in rows} == {
        "MONITOR", "CONTINUE_MONITORING", "INCREASE_MONITORING",
        "PREPARE_BACKUP_CHANNEL", "OPERATOR_ESCALATION", "SECURE_HOLD",
    }
    assert all(row.data_source == "SYNTHETIC" and row.label_status == "PENDING" for row in rows)
    assert {row.provenance for row in rows} == {"PYTHON_GENERATED"}
    assert all(row.validated_response is None and row.label_source == "RULE_SUGGESTED" for row in rows)
    assert rows[:10] == generate_rows(10, seed=42, session_size=10)
    assert audit_service.get_all_incidents() == []


def test_round_trip_and_no_overwrite(tmp_path):
    report = tmp_path / "observations.csv"
    rows = generate_rows(12, seed=42, session_size=4)
    write_csv(report, rows)
    before = report.read_bytes()
    assert validate_csv(report) == {
        "rows": 12, "session_groups": 3, "data_sources": {"SYNTHETIC": 12},
        "label_statuses": {"PENDING": 12}, "provenance": {"PYTHON_GENERATED": 12},
    }
    with report.open(newline="", encoding="utf-8") as stream:
        assert tuple(next(csv.reader(stream))) == DATASET_COLUMNS
    assert set(FEATURE_COLUMNS).isdisjoint({
        "observation_id", "session_id", "rule_based_response", "suggested_response", "validated_response",
    })
    with pytest.raises(FileExistsError):
        write_csv(report, [])
    assert report.read_bytes() == before


@pytest.mark.parametrize("changes, error", [
    ({"risk_score": "101"}, "less than or equal"),
    ({"risk_score": "1"}, "Derived values differ"),
    ({"link_state": "UNKNOWN"}, "link_state"),
    ({"replay_detected": "true"}, "must agree"),
    ({"validated_response": "MONITOR"}, "Leave validated_response blank"),
    ({"label_status": "APPROVED", "validated_response": "MONITOR"}, "independent label_source"),
    ({"session_id": "=1+1"}, "spreadsheet formula"),
    ({"observed_at_utc": "1700000000"}, "ISO 8601 timestamp"),
    ({"acceptable_responses": '["SWITCH_TO_BACKUP"]'}, "acceptable_responses"),
])
def test_csv_rejects_inconsistent_or_unsafe_values(tmp_path, changes, error):
    path = tmp_path / "data.csv"
    row = next(row for row in generate_rows(40, 42, 1) if row.scenario_id == "s1_normal_operation")
    write_csv(path, [row])
    with path.open(newline="", encoding="utf-8") as stream:
        record = next(csv.DictReader(stream))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=DATASET_COLUMNS)
        writer.writeheader()
        writer.writerow({**record, **changes})
    with pytest.raises(ValueError, match=error):
        validate_csv(path)


def test_label_review_is_independent_and_allows_alternatives(tmp_path):
    row = generate_rows(1, 7, 1)[0].model_dump()
    row.update(policy_version="review-v1", label_status="APPROVED", label_source="SUPERVISOR",
               validated_response="OPERATOR_ESCALATION", acceptable_responses=["SECURE_HOLD"])
    path = tmp_path / "review.csv"
    write_csv(path, [DatasetRow.model_validate(row)])
    assert validate_csv(path)["label_statuses"] == {"APPROVED": 1}


def test_csv_rejects_duplicate_observations(tmp_path):
    path = tmp_path / "duplicate.csv"
    row = generate_rows(1, 42, 10)[0]
    write_csv(path, [row, row])
    with pytest.raises(ValueError, match="Duplicate observation"):
        validate_csv(path)


def fixture_manifest(directory: Path, timestamp: str, offset: str | None = None) -> Path:
    payload = EVALUATE_SCENARIOS["s3_critical_jamming"]["payload"]
    module2 = {**payload["threat_intelligence"], "observation_id": "OBS-FIXTURE",
               "timestamp": timestamp, "schema_version": "1.0"}
    module3 = {**payload["secure_communication"], "observation_id": "OBS-FIXTURE"}
    (directory / "module 2.json").write_text(json.dumps(module2), encoding="utf-8")
    (directory / "module 3.json").write_text(json.dumps(module3), encoding="utf-8")
    manifest = directory / "manifest.json"
    manifest.write_text(json.dumps({
        "data_source": "CONTROLLED_EXPERIMENT",
        "experiment_id": "EXP-FIXTURE",
        "observations": [{
            "module2_file": "module 2.json", "module3_file": "module 3.json", "session_id": "SESSION-1",
            "scenario_id": "FIXTURE", "naive_timestamp_offset": offset, "outcome_ref": "review-log-1",
        }],
    }), encoding="utf-8")
    return manifest


@pytest.mark.parametrize("timestamp, offset", [
    ("2026-10-19T15:30:00+05:30", None),
    ("2026-10-19T15:30:00", "+05:30"),
])
def test_collection_uses_file_validation_and_preserves_provenance(tmp_path, timestamp, offset):
    manifest = fixture_manifest(tmp_path, timestamp, offset)
    output = tmp_path / "export"
    assert asyncio.run(export_collection(manifest, output)) == 1
    assert validate_csv(output / "observations.csv")["rows"] == 1
    rows, index = asyncio.run(collect_rows(manifest))
    row = rows[0]
    assert (row.risk_score, row.risk_level, row.rule_based_response) == (80, "CRITICAL", "PREPARE_BACKUP_CHANNEL")
    assert row.observed_at_utc.isoformat() == "2026-10-19T10:00:00+00:00"
    assert row.validated_response is None and row.incident_id is None
    assert index["observations"][0]["match_method"] == "observation_id"
    assert index["observations"][0]["outcome_ref"] == "review-log-1"
    assert len(index["observations"][0]["module2_sha256"]) == 64
    assert row.raw_record_ref == index["observations"][0]["raw_record_ref"]
    assert audit_service.get_all_incidents() == []


def test_collection_rejects_naive_timestamp_without_offset_and_wrong_pair(tmp_path):
    manifest = fixture_manifest(tmp_path, "2026-10-19T15:30:00")
    output = tmp_path / "export"
    with pytest.raises(ValueError, match="naive_timestamp_offset"):
        asyncio.run(export_collection(manifest, output))
    assert not output.exists()

    module3_path = tmp_path / "module 3.json"
    module3 = json.loads(module3_path.read_text(encoding="utf-8"))
    module3_path.write_text(json.dumps({**module3, "observation_id": "OTHER"}), encoding="utf-8")
    with pytest.raises(ValueError, match="OBSERVATION_ID_MISMATCH"):
        asyncio.run(export_collection(manifest, output))
    assert not output.exists()


def test_unconfirmed_collection_leaves_unknown_ids_blank(tmp_path):
    fixture = fixture_manifest(tmp_path, "2026-10-19T15:30:00+05:30")
    record = json.loads(fixture.read_text(encoding="utf-8"))["observations"][0]
    manifest_dir = tmp_path / "manifests"
    manifest_dir.mkdir()
    manifest = manifest_dir / "unconfirmed.json"
    manifest.write_text(json.dumps({
        "data_source": "UNCONFIRMED",
        "observations": [{
            "module2_file": f"../{record['module2_file']}",
            "module3_file": f"../{record['module3_file']}",
        }],
    }), encoding="utf-8")
    out = tmp_path / "result"
    assert asyncio.run(export_collection(manifest, out, csv_name="collected_dataset.csv")) == 1
    exported = out / "collected_dataset.csv"
    assert validate_csv(exported) == {
        "rows": 1, "session_groups": 0, "rows_without_session_groups": 1,
        "data_sources": {"UNCONFIRMED": 1}, "label_statuses": {"PENDING": 1},
    }
    with exported.open(newline="", encoding="utf-8") as stream:
        row = next(csv.DictReader(stream))
    assert all(row[column] == "" for column in ("session_id", "experiment_id", "scenario_id", "validated_response"))


def test_confirmed_collection_requires_reported_experiment_id(tmp_path):
    manifest = fixture_manifest(tmp_path, "2026-10-19T15:30:00+05:30")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    del data["experiment_id"]
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Confirmed sources require"):
        asyncio.run(collect_rows(manifest))


def test_chatgpt_collection_records_synthetic_origin_without_fabricating_ids(tmp_path):
    manifest = fixture_manifest(tmp_path, "2026-10-19T15:30:00Z")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data.update(data_source="SYNTHETIC", provenance="CHATGPT_GENERATED")
    del data["experiment_id"]
    for key in ("session_id", "scenario_id"):
        del data["observations"][0][key]
    manifest.write_text(json.dumps(data), encoding="utf-8")

    rows, index = asyncio.run(collect_rows(manifest))
    row = rows[0]
    assert row.data_source == "SYNTHETIC" and row.provenance == index["provenance"] == "CHATGPT_GENERATED"
    assert row.group is row.experiment_id is row.session_id is row.scenario_id is None
    assert row.validated_response is None and row.label_status == "PENDING"

    data["data_source"] = "REAL_TESTBED"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Generation provenance requires"):
        asyncio.run(collect_rows(manifest))


def test_original_v1_csv_still_validates(tmp_path):
    row = generate_rows(1, seed=1, session_size=1)[0].model_dump(mode="json")
    del row["provenance"]
    row["dataset_version"] = "1.0"
    path = tmp_path / "original.csv"
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=V1_COLUMNS)
        writer.writeheader()
        writer.writerow(row)
    assert validate_csv(path)["data_sources"] == {"SYNTHETIC": 1}
