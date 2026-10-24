"""
scripts/test_anomaly_on_unknown.py — End-to-end validation of the unknown-anomaly detection path.

Loads generate_unknown_anomaly() data from data/unknown_anomaly.csv, calibrates a
NormalBaseline from data/normal.csv (70% split), then for every unknown-anomaly
observation:
  1. Checks that NO jamming rule fires (proving the "held-out" design invariant).
  2. Runs StatisticalAnomalyEngine and counts how many are correctly flagged.

Prints a concise summary confirming both properties.

Usage:
    python scripts/test_anomaly_on_unknown.py [--seed 42] [--z-threshold 3.0]
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.schema import RFObservation
from src.baseline import NormalBaseline
from src.rule_engine import build_default_ruleset
from src.anomaly_engine import StatisticalAnomalyEngine


# ---------------------------------------------------------------------------
# CSV Loader
# ---------------------------------------------------------------------------

def load_csv(path: Path) -> list[RFObservation]:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    obs_list = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            obs_list.append(RFObservation(
                observation_id=row["observation_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                rssi=float(row["rssi"]),
                snr=float(row["snr"]),
                noise_floor=float(row["noise_floor"]),
                packet_rate=float(row["packet_rate"]),
            ))
    return obs_list


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run(z_threshold: float = 3.0) -> None:
    data_dir = PROJECT_ROOT / "data"

    print("=================================================================")
    print("   UAV RF THREAT INTEL - ANOMALY ENGINE ON UNKNOWN-ANOMALY DATA  ")
    print("=================================================================")

    # 1. Load datasets
    normal_obs = load_csv(data_dir / "normal.csv")
    unknown_obs = load_csv(data_dir / "unknown_anomaly.csv")
    print(f"Loaded {len(normal_obs)} normal observations for baseline calibration.")
    print(f"Loaded {len(unknown_obs)} unknown-anomaly observations for evaluation.")

    # 2. Calibrate NormalBaseline on 70% of normal.csv (same split as run_baseline_demo.py)
    split_idx = int(len(normal_obs) * 0.70)
    calibration_set = normal_obs[:split_idx]
    baseline = NormalBaseline()
    baseline.add_normal_samples(calibration_set)
    baseline.calibrate()
    print(f"\nBaseline calibrated on {len(calibration_set)} normal samples (70% split).")
    print(f"  SNR  : mean={baseline.baseline['snr'].mean:.2f} dB, std={baseline.baseline['snr'].std:.2f}")
    print(f"  Noise: mean={baseline.baseline['noise_floor'].mean:.2f} dBm, std={baseline.baseline['noise_floor'].std:.2f}")

    # 3. Build rule detector and anomaly engine
    rule_detector = build_default_ruleset()
    anomaly_engine = StatisticalAnomalyEngine(z_threshold=z_threshold)
    print(f"\nRule detector: J01 (snr_drop AND noise_floor_increase) + J02 (rssi AND packet_rate)")
    print(f"Anomaly engine: z_threshold = {z_threshold}")

    # 4. Evaluate every unknown-anomaly observation
    rule_fires = []          # should be ALL 0 (no rule must fire)
    anomaly_detected = []    # should be mostly 1 (engine catches them)
    anomalous_features_seen: dict[str, int] = {}

    for obs in unknown_obs:
        dev = baseline.deviations(obs)

        # Rule check
        rule_result = rule_detector.evaluate(dev)
        rule_fires.append(1 if rule_result is not None else 0)

        # Anomaly engine
        anomaly_result = anomaly_engine.evaluate(dev)
        anomaly_detected.append(1 if anomaly_result is not None else 0)
        if anomaly_result:
            for feat in anomaly_result["anomalous_features"]:
                anomalous_features_seen[feat] = anomalous_features_seen.get(feat, 0) + 1

    n = len(unknown_obs)
    rules_fired_count = sum(rule_fires)
    anomalies_caught = sum(anomaly_detected)

    # 5. Print results
    print("\n" + "=" * 65)
    print("  RESULTS")
    print("=" * 65)

    # --- Rule check
    rule_status = "PASSED" if rules_fired_count == 0 else "FAILED"
    print(f"\n  [1] Held-Out Invariant Check - No Jamming Rule Should Fire")
    print(f"      Rule fires on unknown-anomaly set : {rules_fired_count} / {n}")
    print(f"      Status: {rule_status}")
    if rules_fired_count == 0:
        print("      --> CONFIRMED: J01 requires SNR drop AND noise floor rise together.")
        print("          Unknown-anomaly only has SNR drop (noise floor stays near-normal),")
        print("          so neither J01 nor J02 trigger. The held-out design works correctly.")
    else:
        print(f"      --> WARNING: {rules_fired_count} observations incorrectly triggered a rule!")
        print("          Check that the unknown-anomaly generator matches the design intent.")

    # --- Anomaly detection
    pct = anomalies_caught / n * 100
    print(f"\n  [2] Statistical Anomaly Engine Detection Rate")
    print(f"      Observations flagged as anomalous : {anomalies_caught} / {n}  ({pct:.1f}%)")
    print(f"      Observations missed               : {n - anomalies_caught} / {n}  ({100 - pct:.1f}%)")

    if anomalous_features_seen:
        print(f"\n      Features triggering the engine (across all flagged observations):")
        for feat, count in sorted(anomalous_features_seen.items(), key=lambda x: -x[1]):
            print(f"        {feat:<15}: {count} observations  ({count/anomalies_caught*100:.0f}% of flagged)")

    print(f"\n  z_threshold used: {z_threshold}")
    print("  (Lower threshold catches more but risks false alarms on held-out normal data.)")
    print("=" * 65)

    # 6. Show 3 sample observations with their full deviation readout
    print("\n--- Sample Observations (first 3 unknown-anomaly records) ---")
    for i, obs in enumerate(unknown_obs[:3], 1):
        dev = baseline.deviations(obs)
        ae_result = anomaly_engine.evaluate(dev)
        detected = "FLAGGED" if ae_result else "MISSED"
        z = dev["z_scores"]
        print(f"\n  [{i}] {obs.observation_id}  ->  {detected}")
        print(f"      rssi={obs.rssi:.2f} dBm  snr={obs.snr:.2f} dB  "
              f"noise={obs.noise_floor:.2f} dBm  rate={obs.packet_rate:.2f} pkts/s")
        print(f"      z-scores: snr={z['snr']:+.2f}, rssi={z['rssi']:+.2f}, "
              f"noise={z['noise_floor']:+.2f}, rate={z['packet_rate']:+.2f}")
        if ae_result:
            for feat in ae_result["anomalous_features"]:
                print(f"      Anomalous: {feat} (z={ae_result['z_scores'][feat]:+.2f})")


def main():
    parser = argparse.ArgumentParser(
        description="Validate anomaly engine on unknown-anomaly dataset."
    )
    parser.add_argument("--z-threshold", type=float, default=3.0,
                        help="z-score threshold for anomaly engine (default: 3.0)")
    args = parser.parse_args()
    run(z_threshold=args.z_threshold)


if __name__ == "__main__":
    main()
