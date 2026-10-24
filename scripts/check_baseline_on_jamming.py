"""Check the frozen v2 detector against the labelled real jammer captures."""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DATA = ROOT / "data" / "real" / "module1_signals_clean"

from src.classifier import Classification
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
    ]
    outputs = Counter(classifier.classify(signal).classification for signal in rows)
    detected = len(rows) - outputs[Classification.NORMAL.value]
    print(f"Real jammer records: {len(rows)}")
    print(f"Detected abnormal: {detected}/{len(rows)} ({100 * detected / len(rows):.2f}%)")
    for label, count in sorted(outputs.items()):
        print(f"  {label:<18} {count}")


if __name__ == "__main__":
    main()
