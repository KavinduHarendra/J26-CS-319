"""Inspect anomaly-only hits on the two jammer types held out from calibration."""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data" / "real" / "module1_signals_clean"

from src.real_classifier import RealThreatClassifierV2
from src.real_data import SignalCollectionSource
from src.scoring_data import load_ground_truth
from src.real_detection import build_frozen_detector_v2


def main() -> None:
    truth = load_ground_truth(DATA / "ground_truth.csv")
    classifier = RealThreatClassifierV2(build_frozen_detector_v2())
    rows = [
        signal
        for signal in SignalCollectionSource(DATA)
        if truth[signal.observation_id]["expected_class"] == "JAMMING"
        and truth[signal.observation_id]["jammer_type"] in {"PULSED_5_95", "RANDOM_BURSTS"}
    ]
    counts = Counter(classifier.classify(signal).classification for signal in rows)
    print(f"Held-out real jammer records: {len(rows)}")
    for label, count in sorted(counts.items()):
        print(f"  {label:<18} {count}")


if __name__ == "__main__":
    main()
