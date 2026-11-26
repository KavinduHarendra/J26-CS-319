"""Command-line entry points for preparing and checking response research data."""

import argparse
import asyncio
import csv
import json
from pathlib import Path

from response_ml.collect import export_collection, load_pair
from response_ml.dataset import DATASET_COLUMNS, validate_csv, write_csv
from response_ml.features import extract_features
from response_ml.generate import generate_rows
from response_ml.review import prepare_review
from services.evidence_service import assess_evidence
from services.response_service import select_response


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare Module 4 response datasets.")
    subcommands = parser.add_subparsers(dest="command", required=True)

    generate = subcommands.add_parser("generate", help="Create unreviewed synthetic observations.")
    generate.add_argument("--output", type=Path, required=True)
    generate.add_argument("--count", type=int, default=1000)
    generate.add_argument("--seed", type=int, default=42)
    generate.add_argument("--session-size", type=int, default=10)

    validate = subcommands.add_parser("validate", help="Check schema, review fields, and derived values.")
    validate.add_argument("csv_file", type=Path)

    collect = subcommands.add_parser("collect", help="Collect paired Module 2/3 JSON exports.")
    collect.add_argument("--manifest", type=Path, required=True)
    collect.add_argument("--output-dir", type=Path, required=True)
    collect.add_argument("--csv-name", default="observations.csv", help="Filename of the dataset in the output folder.")

    inspect = subcommands.add_parser("inspect-pair", help="Verify one pair with the current rules.")
    inspect.add_argument("module2_file", type=Path)
    inspect.add_argument("module3_file", type=Path)
    inspect.add_argument("--expect-observation-id")
    inspect.add_argument("--expect-risk-score", type=float)
    inspect.add_argument("--expect-risk-level")
    inspect.add_argument("--expect-response")

    template = subcommands.add_parser("template", help="Create a header-only reviewer CSV template.")
    template.add_argument("--output", type=Path, required=True)

    review = subcommands.add_parser("prepare-review", help="Create the representative and blind review exports.")
    review.add_argument("dataset", type=Path)
    review.add_argument("--output-dir", type=Path, required=True)
    review.add_argument("--count", type=int, default=144)
    review.add_argument("--seed", type=int, default=42)
    return parser


async def inspect_pair(args: argparse.Namespace) -> dict:
    request, receipt = await load_pair(args.module2_file, args.module3_file)
    evidence = assess_evidence(request)
    recommendation, rationale, baseline = select_response(
        evidence.threat, evidence.communication, evidence.risk_score, evidence.conflict
    )
    result = {
        "observation_id": evidence.rf.observation_id,
        "match_method": receipt["match_method"],
        "risk_score": evidence.risk_score,
        "risk_level": evidence.risk_level,
        "recommended_response": recommendation,
        "response_rationale": rationale,
        "baseline_response": baseline,
        "features": extract_features(evidence).model_dump(mode="json"),
    }
    checks = {
        "observation_id": args.expect_observation_id,
        "risk_score": args.expect_risk_score,
        "risk_level": args.expect_risk_level,
        "recommended_response": args.expect_response,
    }
    for field, expected in checks.items():
        if expected is not None and result[field] != expected:
            raise ValueError(f"Expected {field}={expected}, got {result[field]}.")
    return result


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "generate":
            rows = generate_rows(args.count, args.seed, args.session_size)
            write_csv(args.output, rows)
            print(f"Wrote {len(rows)} SYNTHETIC observations to {args.output}")
        elif args.command == "validate":
            print(json.dumps(validate_csv(args.csv_file), indent=2))
        elif args.command == "collect":
            count = asyncio.run(export_collection(args.manifest, args.output_dir, csv_name=args.csv_name))
            print(f"Wrote {count} observations and their evidence index to {args.output_dir}")
        elif args.command == "inspect-pair":
            print(json.dumps(asyncio.run(inspect_pair(args)), indent=2))
        elif args.command == "template":
            write_csv(args.output, ())
            print(f"Wrote {len(DATASET_COLUMNS)} column headers to {args.output}")
        elif args.command == "prepare-review":
            prepare_review(args.dataset, args.output_dir, args.count, args.seed)
            print(f"Wrote {args.count} review cases, a private key and the split plan to {args.output_dir}")
    except (ValueError, OSError, csv.Error) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
