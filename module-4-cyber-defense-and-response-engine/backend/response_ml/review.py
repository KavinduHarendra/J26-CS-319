"""Export a representative synthetic review pack and its private comparison key."""

import csv
import json
from collections import Counter
from pathlib import Path
from random import Random

from response_ml.dataset import DATASET_VERSION, DatasetRow, load_csv, write_csv
from response_ml.evaluation import plan_split, summarize_novel_structures, summarize_split
from response_ml.features import FEATURE_COLUMNS
from response_ml.generate import feature_signature
from response_ml.rubric import MONITORING, RUBRIC_VERSION, suggest_response

REVIEW_FIELDS = ("validated_response", "label_status", "reviewer_notes", "acceptable_responses")
BLIND_COLUMNS = ("review_id", *FEATURE_COLUMNS, *REVIEW_FIELDS)
KEY_COLUMNS = ("review_id", "observation_id", "partition", "rubric_version", "rubric_suggestion", "rubric_criterion")
SPLIT_COLUMNS = ("observation_id", "session_id", "scenario_id", "partition")
CONDITIONS = (
    "risk_level", "classification", "severity", "link_state", "auth_state", "integrity_state",
    "freshness_state", "comm_decision", "replay_detected", "evidence_conflict",
)


def _strata(row: DatasetRow, partition: str) -> tuple:
    keys = (
        ("contextual", partition, row.rule_based_response),
        ("draft", partition, suggest_response(row).response),
        ("family", row.scenario_id),
        *((field, getattr(row, field)) for field in CONDITIONS),
    )
    if row.risk_level == "CRITICAL" and row.rule_based_response in MONITORING:
        return (*keys, ("critical_gap",))
    return keys


def select_review_rows(rows: list[DatasetRow], assignment: dict[str, str], count: int, seed: int) -> list[DatasetRow]:
    pool = list(rows)
    rng = Random(seed)
    rng.shuffle(pool)
    unique = {}
    for row in pool:
        unique.setdefault(feature_signature(row), row)
    if count < 1 or count > len(unique):
        raise ValueError(f"Review count must be between 1 and {len(unique)} distinct observations.")
    options = [(row, _strata(row, assignment[row.scenario_id])) for row in unique.values()]
    available = Counter(key for _, strata in options for key in strata)
    targets = {
        key: min(n, {"contextual": 6, "draft": 6, "critical_gap": 12}.get(key[0], 4))
        for key, n in available.items()
    }
    counts = Counter()
    sessions = Counter()
    selected = []
    for _ in range(count):
        index = max(range(len(options)), key=lambda i: (
            sum(max(targets[key] - counts[key], 0) / targets[key] for key in options[i][1]),
            -sessions[options[i][0].group],
        ))
        row, keys = options.pop(index)
        counts.update(keys)
        sessions[row.group] += 1
        selected.append(row)
    rng.shuffle(selected)
    return selected


def _write_csv(path: Path, columns: tuple[str, ...], records) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(records)


def prepare_review(dataset_path: Path, output_dir: Path, count: int, seed: int) -> dict:
    rows = load_csv(dataset_path)
    if any(row.dataset_version != DATASET_VERSION or row.provenance != "PYTHON_GENERATED" for row in rows):
        raise ValueError("Use only the v1.2 Python-generated dataset for this review and split plan.")
    if any(row.label_status != "PENDING" or row.validated_response is not None for row in rows):
        raise ValueError("Prepare blind review from the pending export so existing decisions stay private.")

    assignment, components = plan_split(rows, seed)
    selected = select_review_rows(rows, assignment, count, seed)
    blind, key = [], []
    for index, row in enumerate(selected, start=1):
        review_id = f"REVIEW-{index:04d}"
        document = row.model_dump(mode="json")
        blind.append({"review_id": review_id, **{field: document[field] for field in (*FEATURE_COLUMNS, *REVIEW_FIELDS)}})
        draft = suggest_response(row)
        key.append({
            "review_id": review_id, "observation_id": row.observation_id, "partition": assignment[row.scenario_id],
            "rubric_version": RUBRIC_VERSION, "rubric_suggestion": draft.response, "rubric_criterion": draft.criterion,
        })

    result = {
        "seed": seed, "rubric_version": RUBRIC_VERSION, "independent_components": components,
        "dataset": summarize_split(rows, assignment), "review": summarize_split(selected, assignment),
        "structurally_novel_dataset": summarize_novel_structures(rows, assignment),
    }

    output_dir.mkdir(parents=True)
    write_csv(output_dir / "labeling-review.csv", selected)
    _write_csv(output_dir / "blind-review.csv", BLIND_COLUMNS, blind)
    _write_csv(output_dir / "review-key.csv", KEY_COLUMNS, key)
    _write_csv(output_dir / "split-manifest.csv", SPLIT_COLUMNS, (
        {"observation_id": row.observation_id, "session_id": row.session_id, "scenario_id": row.scenario_id,
         "partition": assignment[row.scenario_id]} for row in rows
    ))
    with (output_dir / "split-coverage.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    return result
