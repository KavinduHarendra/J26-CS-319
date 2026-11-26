"""Export reproducible draft-rubric labels without human approval."""

import argparse
import csv
import json
from pathlib import Path

from response_ml.dataset import load_csv
from response_ml.prototype_data import LABEL_COLUMNS, draft_labels, label_summary, labeled_record


def export_labels(source: Path, output: Path) -> dict:
    cases = draft_labels(load_csv(source))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=LABEL_COLUMNS)
        writer.writeheader()
        writer.writerows(labeled_record(case) for case in cases)
    return label_summary(cases)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(export_labels(args.source, args.output), indent=2))
    except (ValueError, OSError, csv.Error) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()
