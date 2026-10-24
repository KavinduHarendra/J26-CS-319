"""Print the frozen two-state baseline used by the real-recording replay."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.real_detection import DETECTION_FEATURES, build_frozen_detector_v2


def main() -> None:
    baseline = build_frozen_detector_v2().baseline
    print(f"Baseline version: {baseline.version}")
    print(f"Idle-derived SNR state threshold: {baseline.state_snr_threshold:.3f} dB")
    for state in (baseline.idle, baseline.legitimate):
        print(f"\n{state.name}")
        for feature in DETECTION_FEATURES:
            print(
                f"  {feature:<22} mean={state.mean[feature]:>11.6f} "
                f"std={state.std[feature]:>10.6f}"
            )


if __name__ == "__main__":
    main()
