"""
scripts/run_full_demo.py — End-to-end AI Threat Intelligence pipeline demo.

Demonstrates full pipeline execution:
  RFDataSource -> NormalBaseline -> Rule Engine -> Anomaly Engine -> ThreatOutput

All observations are ingested strictly via RFDataSource instances (SyntheticDataSource).
No CSV or file operations are performed downstream of RFDataSource.

Usage:
    python scripts/run_full_demo.py [--seed 42]
"""

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_source import RFDataSource, SyntheticDataSource
from src.baseline import NormalBaseline
from src.rule_engine import build_default_ruleset
from src.anomaly_engine import StatisticalAnomalyEngine
from src.classifier import ThreatIntelligenceModule, ThreatOutput


def run_full_demo(
    normal_source: RFDataSource,
    jamming_source: RFDataSource,
    anomaly_source: RFDataSource,
    n_calib: int = 200,
    n_eval_each: int = 50,
) -> None:
    print("=================================================================")
    print("        UAV RF THREAT INTELLIGENCE - FULL SYSTEM PIPELINE        ")
    print("=================================================================")
    print("Data Sources: RFDataSource (SyntheticDataSource)")

    # 1. Baseline Calibration
    print(f"\n[Step 1] Ingesting {n_calib} normal samples to calibrate baseline...")
    calib_samples = normal_source.fetch_batch(n_calib)
    baseline = NormalBaseline()
    baseline.add_normal_samples(calib_samples)
    baseline.calibrate()
    print("Baseline calibrated successfully.")

    # 2. Module Assembly
    rule_detector = build_default_ruleset(snr_thresh=2.0, noise_thresh=2.0)
    anomaly_engine = StatisticalAnomalyEngine(z_threshold=3.0)
    module = ThreatIntelligenceModule(baseline, rule_detector, anomaly_engine)
    print("[Step 2] ThreatIntelligenceModule initialized with Rule Detector & Anomaly Engine.")

    # 3. Ingest Evaluation Batches via RFDataSource
    print(f"\n[Step 3] Fetching evaluation batches ({n_eval_each} per scenario)...")
    eval_normal = normal_source.fetch_batch(n_eval_each)
    eval_jamming = jamming_source.fetch_batch(n_eval_each)
    eval_anomaly = anomaly_source.fetch_batch(n_eval_each)

    test_suite = [
        ("Normal", eval_normal),
        ("Jamming", eval_jamming),
        ("Unknown Anomaly", eval_anomaly),
    ]

    # 4. Evaluation and Classification
    print("\n[Step 4] Running observations through ThreatIntelligenceModule...")
    results: list[tuple[str, ThreatOutput, float]] = []

    for ground_truth, obs_list in test_suite:
        for obs in obs_list:
            t0 = time.perf_counter()
            output = module.classify(obs)
            latency_ms = (time.perf_counter() - t0) * 1000
            results.append((ground_truth, output, latency_ms))

    # 5. Performance Summary
    print("\n--- Classification Performance Breakdown ---")
    header = f"{'True Scenario':<18} | {'Classified Normal':<18} | {'Classified Jamming':<19} | {'Classified Anomaly':<18}"
    print(header)
    print("-" * len(header))

    for scenario_name in ["Normal", "Jamming", "Unknown Anomaly"]:
        scenario_outputs = [out.classification for truth, out, _ in results if truth == scenario_name]
        counts = Counter(scenario_outputs)
        print(f"{scenario_name:<18} | {counts.get('Normal', 0):<18} | {counts.get('Jamming', 0):<19} | {counts.get('Unknown Anomaly', 0):<18}")

    latencies = [lat for _, _, lat in results]
    mean_latency = sum(latencies) / len(latencies) if latencies else 0.0
    print("-" * len(header))
    print(f"Total evaluated: {len(results)} | Mean classification latency: {mean_latency:.4f} ms")

    # 6. Sample Explainable Outputs
    print("\n--- Sample Explainable Outputs (One from each true scenario) ---")
    for scenario_name in ["Normal", "Jamming", "Unknown Anomaly"]:
        for truth, out, _ in results:
            if truth == scenario_name:
                print(f"\n[True Scenario: {truth}] -> Classified as: {out.classification.upper()}")
                print(f"  Observation ID: {out.observation_id}")
                print(f"  Severity:       {out.severity or 'None'}")
                print(f"  Triggered Rule: {out.triggered_rule or 'None'}")
                print(f"  Evidence:       {out.evidence}")
                break

    print("\nFull pipeline demo completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Run full AI threat intelligence pipeline demo.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility (default: 42)")
    args = parser.parse_args()

    normal_source = SyntheticDataSource(scenario="normal", seed=args.seed)
    jamming_source = SyntheticDataSource(scenario="jamming", seed=args.seed + 100)
    anomaly_source = SyntheticDataSource(scenario="unknown_anomaly", seed=args.seed + 200)

    run_full_demo(normal_source, jamming_source, anomaly_source)


if __name__ == "__main__":
    main()
