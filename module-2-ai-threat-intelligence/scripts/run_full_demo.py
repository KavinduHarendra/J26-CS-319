"""
scripts/run_full_demo.py — End-to-end AI Threat Intelligence pipeline demo.

Demonstrates the integrated Month-1 milestone pipeline:
  Observation -> NormalBaseline -> Rule Engine -> Anomaly Engine -> ThreatOutput

Loads the calibrated NormalBaseline, RuleBasedJammingDetector, and StatisticalAnomalyEngine,
runs them over a mixed sample of observations from all three synthetic datasets
(Normal, Jamming, Unknown Anomaly), and prints a per-observation table comparing
True Label vs Predicted Classification vs Severity vs Evidence.

Usage:
    python scripts/run_full_demo.py [--samples-per-class 5] [--seed 42]
"""

import argparse
import csv
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.schema import RFObservation
from src.baseline import NormalBaseline
from src.rule_engine import build_default_ruleset
from src.anomaly_engine import StatisticalAnomalyEngine
from src.classifier import ThreatIntelligenceModule, ThreatOutput
from src.data_source import SyntheticDataSource


def load_observations_from_csv(csv_path: Path) -> list[RFObservation]:
    """Load RFObservation instances from a dataset CSV file."""
    observations = []
    with open(csv_path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            observations.append(RFObservation(
                observation_id=row["observation_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                rssi=float(row["rssi"]),
                snr=float(row["snr"]),
                noise_floor=float(row["noise_floor"]),
                packet_rate=float(row["packet_rate"]),
            ))
    return observations


def get_dataset(scenario: str, count: int, seed: int) -> list[RFObservation]:
    """Fetch observations from data/ CSV if available, else generate via SyntheticDataSource."""
    data_dir = PROJECT_ROOT / "data"
    csv_file = data_dir / f"{scenario}.csv"
    if csv_file.exists():
        obs_list = load_observations_from_csv(csv_file)
        return obs_list[:count]
    source = SyntheticDataSource(scenario=scenario, seed=seed)
    return source.fetch_batch(count)


def run_full_demo(samples_per_class: int = 5, seed: int = 42) -> None:
    print("=========================================================================================")
    print("           UAV CYBER DEFENSE - AI THREAT INTELLIGENCE MODULE DEMO                       ")
    print("            (Explainable Rule Engine + Statistical Anomaly Engine)                      ")
    print("=========================================================================================")

    # 1. Calibrate Baseline using Normal Data (70% calibration split)
    data_dir = PROJECT_ROOT / "data"
    normal_csv = data_dir / "normal.csv"
    if normal_csv.exists():
        all_normal = load_observations_from_csv(normal_csv)
        calib_normal = all_normal[:int(len(all_normal) * 0.70)]
    else:
        calib_normal = SyntheticDataSource("normal", seed=seed).fetch_batch(140)

    baseline = NormalBaseline()
    baseline.add_normal_samples(calib_normal)
    baseline.calibrate()
    print(f"\n[1] NormalBaseline calibrated on {len(calib_normal)} normal observations.")
    for f in NormalBaseline.FEATURES:
        fb = baseline.baseline[f]
        print(f"    - {f:<12}: mean={fb.mean:>7.2f}, std={fb.std:>5.2f}")

    # 2. Build Pipeline Engines
    rule_detector = build_default_ruleset()
    anomaly_engine = StatisticalAnomalyEngine(z_threshold=3.0)
    module = ThreatIntelligenceModule(baseline, rule_detector, anomaly_engine)
    print("\n[2] ThreatIntelligenceModule assembled:")
    print("    - Rule Detector : J01 (SNR Drop & Noise Rise) + J02 (RSSI & Packet Rate)")
    print("    - Anomaly Engine: Statistical z-score outlier detection (|z| >= 3.0)")

    # 3. Assemble Mixed Sample Dataset
    print(f"\n[3] Ingesting mixed sample ({samples_per_class} observations from each scenario)...")
    eval_normal = get_dataset("normal", count=samples_per_class, seed=seed)
    eval_jamming = get_dataset("jamming", count=samples_per_class, seed=seed + 10)
    eval_unknown = get_dataset("unknown_anomaly", count=samples_per_class, seed=seed + 20)

    # Interleave samples for a realistic live-stream demo
    mixed_observations: list[tuple[str, RFObservation]] = []
    max_len = max(len(eval_normal), len(eval_jamming), len(eval_unknown))
    for i in range(max_len):
        if i < len(eval_normal):
            mixed_observations.append(("Normal", eval_normal[i]))
        if i < len(eval_jamming):
            mixed_observations.append(("Jamming", eval_jamming[i]))
        if i < len(eval_unknown):
            mixed_observations.append(("Unknown Anomaly", eval_unknown[i]))

    # 4. Run Classifications and Record Results
    results: list[tuple[str, ThreatOutput, float]] = []
    for true_label, obs in mixed_observations:
        t0 = time.perf_counter()
        output = module.classify(obs)
        latency_ms = (time.perf_counter() - t0) * 1000
        results.append((true_label, output, latency_ms))

    # 5. Print Per-Observation Output Table
    print("\n" + "=" * 115)
    print("                        PER-OBSERVATION CLASSIFICATION & EVIDENCE LOG                     ")
    print("=" * 115)
    table_header = (
        f"{'Obs ID':<11} | {'True Label':<16} | {'Predicted Label':<16} | "
        f"{'Severity':<9} | {'Detection Evidence'}"
    )
    print(table_header)
    print("-" * 115)

    correct_count = 0
    for true_label, out, _ in results:
        is_correct = (true_label == out.classification)
        if is_correct:
            correct_count += 1

        sev_str = out.severity if out.severity else "None"
        evidence_str = "; ".join(out.evidence) if out.evidence else "None"

        # Truncate evidence string if exceedingly long for neat table formatting
        if len(evidence_str) > 52:
            evidence_display = evidence_str[:49] + "..."
        else:
            evidence_display = evidence_str

        print(
            f"{out.observation_id:<11} | {true_label:<16} | {out.classification:<16} | "
            f"{sev_str:<9} | {evidence_display}"
        )

    print("-" * 115)

    # 6. Performance Summary & Defense-Readiness Metrics
    latencies = [lat for _, _, lat in results]
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    accuracy = (correct_count / len(results)) * 100 if results else 0.0

    print("\n--- Summary Performance Metrics ---")
    print(f"  Total Observations Evaluated : {len(results)}")
    print(f"  Classification Accuracy      : {correct_count}/{len(results)} ({accuracy:.1f}%)")
    print(f"  Mean Detection Latency       : {mean_latency:.4f} ms per observation (Real-time bound < 50ms)")

    # Breakdown by category
    print("\n--- Confusion Matrix Breakdown ---")
    print(f"  {'True Scenario':<18} | {'Classified Normal':<18} | {'Classified Jamming':<18} | {'Classified Anomaly':<18}")
    print("  " + "-" * 78)
    for scenario_name in ["Normal", "Jamming", "Unknown Anomaly"]:
        preds = [out.classification for truth, out, _ in results if truth == scenario_name]
        counts = Counter(preds)
        print(
            f"  {scenario_name:<18} | {counts.get('Normal', 0):<18} | "
            f"{counts.get('Jamming', 0):<18} | {counts.get('Unknown Anomaly', 0):<18}"
        )
    print("  " + "-" * 78)
    print("Demo completed successfully.\n")


def main():
    parser = argparse.ArgumentParser(description="Run end-to-end AI threat intelligence demo.")
    parser.add_argument("--samples-per-class", type=int, default=5,
                        help="Number of samples to draw per scenario (default: 5)")
    parser.add_argument("--seed", type=int, default=42,
                        help="RNG seed for reproducibility (default: 42)")
    args = parser.parse_args()

    run_full_demo(samples_per_class=args.samples_per_class, seed=args.seed)


if __name__ == "__main__":
    main()
