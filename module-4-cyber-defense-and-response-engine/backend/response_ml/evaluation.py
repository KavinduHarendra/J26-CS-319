"""Plan grouped evaluation without training a model or reading approved labels."""

from collections import Counter, defaultdict
from random import Random

from response_ml.dataset import DatasetRow
from response_ml.generate import STRUCTURAL_FEATURES, feature_signature
from response_ml.rubric import RESPONSE_CLASSES, suggest_response

PARTITIONS = ("train", "validation", "test")


def _family_components(rows: list[DatasetRow]) -> list[tuple[str, ...]]:
    """Families sharing a session or exact feature vector must stay together."""
    edges = defaultdict(set)
    session_owner = {}
    feature_owner = {}
    for row in rows:
        family = row.scenario_id
        if row.group is None or family is None:
            raise ValueError("Split planning needs session, experiment and scenario IDs.")
        for related in (
            session_owner.setdefault(row.group, family),
            feature_owner.setdefault(feature_signature(row), family),
        ):
            edges[family].add(related)
            edges[related].add(family)

    remaining = set(edges)
    components = []
    while remaining:
        pending = [min(remaining)]
        connected = set()
        while pending:
            family = pending.pop()
            if family in connected:
                continue
            connected.add(family)
            pending.extend(edges[family] - connected)
        remaining.difference_update(connected)
        components.append(tuple(sorted(connected)))
    return components


def plan_split(rows: list[DatasetRow], seed: int) -> tuple[dict[str, str], int]:
    components = _family_components(rows)
    if len(components) < 3:
        raise ValueError("Fewer than three independent family components survive grouping; a three-way split is unsupported.")

    family_counts = defaultdict(Counter)
    family_sizes = Counter()
    for row in rows:
        family_counts[row.scenario_id][("contextual", row.rule_based_response)] += 1
        family_counts[row.scenario_id][("draft", suggest_response(row).response)] += 1
        family_sizes[row.scenario_id] += 1

    rng = Random(seed)
    evaluation_size = max(1, round(len(components) * 0.22))
    train_size = len(components) - 2 * evaluation_size
    best_score, best = None, None
    for _ in range(1_000):
        rng.shuffle(components)
        folds = (
            components[:train_size],
            components[train_size:train_size + evaluation_size],
            components[train_size + evaluation_size:],
        )
        families = [[name for component in fold for name in component] for fold in folds]
        counts = [sum((family_counts[name] for name in fold), Counter()) for fold in families]
        coverage = [count[(kind, action)] for count in counts
                    for kind in ("contextual", "draft") for action in RESPONSE_CLASSES]
        size_error = sum(abs(sum(family_sizes[name] for name in fold) - target * len(rows))
                         for fold, target in zip(families, (0.6, 0.2, 0.2)))
        score = (-coverage.count(0), min(coverage), -size_error)
        if best_score is None or score > best_score:
            best_score = score
            best = {family: partition for partition, fold in zip(PARTITIONS, families) for family in fold}
    return best, len(components)


def summarize_split(rows: list[DatasetRow], assignment: dict[str, str]) -> dict:
    result = {}
    for name in PARTITIONS:
        fold = [row for row in rows if assignment[row.scenario_id] == name]
        labels = (
            ("contextual", [(row, row.rule_based_response) for row in fold]),
            ("draft", [(row, suggest_response(row).response) for row in fold]),
        )
        result[name] = {
            "rows": len(fold),
            "sessions": len({row.group for row in fold}),
            "families": sorted({row.scenario_id for row in fold}),
            "classes": {
                kind: {
                    action: {
                        "rows": sum(label == action for _, label in observations),
                        "distinct_vectors": len({feature_signature(row) for row, label in observations if label == action}),
                        "sessions": len({row.group for row, label in observations if label == action}),
                    }
                    for action in RESPONSE_CLASSES
                }
                for kind, observations in labels
            },
        }
    return result


def summarize_novel_structures(rows: list[DatasetRow], assignment: dict[str, str]) -> dict:
    """Check held-out inputs again after ignoring confidence differences."""
    earlier = set()
    novel = []
    for partition in PARTITIONS:
        fold = [row for row in rows if assignment[row.scenario_id] == partition]
        novel.extend(row for row in fold if feature_signature(row, STRUCTURAL_FEATURES) not in earlier)
        earlier.update(feature_signature(row, STRUCTURAL_FEATURES) for row in fold)
    return summarize_split(novel, assignment)
