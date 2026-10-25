"""Print the calibrated two-state raw-measurement baseline."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.baseline import BASELINE_FEATURES, Baseline
from src.classifier import DEFAULT_CONFIG_PATH


def main() -> None:
    baseline = Baseline.load(DEFAULT_CONFIG_PATH)
    print(f"Baseline version: {baseline.version}")
    for state in (baseline.idle, baseline.legitimate):
        print(f"\n{state.name}")
        for feature in BASELINE_FEATURES:
            print(
                f"  {feature:<22} mean={state.mean[feature]:>11.6f} "
                f"spread={state.spread[feature]:>10.6f}"
            )
        print(f"  anomaly_limit          {state.anomaly_limit:>10.6f}")


if __name__ == "__main__":
    main()
