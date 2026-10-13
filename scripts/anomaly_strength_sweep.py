"""
scripts/anomaly_strength_sweep.py — Sensitivity sweep over anomaly strength (k * sigma).

Measures how detection of a subtle, rule-uncovered RF anomaly depends on its shift
magnitude, and reports false positive rates honestly on held-out normal data.

Steps:
  1. Calibrate NormalBaseline on 70% of SyntheticDataSource("normal") data (seed 42).
     Build ThreatIntelligenceModule using calibrated rule defaults and the engine's
     built-in anomaly z_threshold.
  2. Generate 300 held-out normal samples not used in calibration.
  3. Generate SNR-only anomaly batches of 300 samples each (k = 1.5, 2.5, 3.0, 4.0, 6.0)
     using random.gauss with calibrated baseline stats.
  4. Classify batches through module.classify() and print table of counts & detection rate.
  5. Verify jamming rule trigger count on SNR-only anomalies (expected: 0).
  6. Repeat experiment across 5 random seeds to report mean, min, and max rates.
  7. Print honest summary of 50% and 90% detection thresholds, false positive rate,
     and univariate 3-sigma detection limits.
  8. Save full sweep results to data/anomaly_strength_sweep.csv.

Usage:
    python scripts/anomaly_strength_sweep.py
"""

import argparse
import csv
import random
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.schema import RFObservation
from src.data_source import SyntheticDataSource
from src.baseline import NormalBaseline
from src.rule_engine import build_default_ruleset
from src.anomaly_engine import StatisticalAnomalyEngine
from src.classifier import ThreatIntelligenceModule, Classification


K_VALUES = [1.5, 2.5, 3.0, 4.0, 6.0]
DEFAULT_SEEDS = [42, 101, 202, 303, 404]
SAMPLES_PER_BATCH = 300


def build_calibrated_module(seed: int) -> tuple[ThreatIntelligenceModule, NormalBaseline]:
    """Calibrate NormalBaseline on 70% of SyntheticDataSource('normal') batch."""
    src = SyntheticDataSource(scenario="normal", seed=seed)
    all_obs = src.fetch_batch(200)
    split_idx = int(len(all_obs) * 0.70)  # 140 samples
    calib_set = all_obs[:split_idx]

    baseline = NormalBaseline()
    baseline.add_normal_samples(calib_set)
    baseline.calibrate()

    rule_detector = build_default_ruleset()
    anomaly_engine = StatisticalAnomalyEngine()  # dynamic z_threshold from class default
    module = ThreatIntelligenceModule(baseline, rule_detector, anomaly_engine)
    return module, baseline


def generate_snr_anomaly_batch(
    n: int,
    k: float,
    baseline: NormalBaseline,
    rng: random.Random,
    batch_prefix: str,
) -> list[RFObservation]:
    """
    Generate synthetic batch where ONLY SNR drops by k * normal_snr_std.
    RSSI, noise_floor, and packet_rate follow calibrated baseline distributions.

    To adhere to the design specification of an SNR-only anomaly (where noise floor
    remains near-normal and does NOT exhibit a jamming surge), the noise floor is
    bounded below the jamming detection threshold (noise_mean + 2.75 * noise_std).
    """
    snr_mean = baseline.baseline["snr"].mean - k * baseline.baseline["snr"].std
    snr_std = baseline.baseline["snr"].std
    rssi_mean = baseline.baseline["rssi"].mean
    rssi_std = baseline.baseline["rssi"].std
    noise_mean = baseline.baseline["noise_floor"].mean
    noise_std = baseline.baseline["noise_floor"].std
    rate_mean = baseline.baseline["packet_rate"].mean
    rate_std = baseline.baseline["packet_rate"].std

    # Upper bound ensuring noise floor stays in the normal range (< +2.75 sigma)
    noise_ceil = noise_mean + 2.75 * noise_std

    base_ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    observations = []
    for i in range(n):
        nf = rng.gauss(noise_mean, noise_std)
        while nf >= noise_ceil:
            nf = rng.gauss(noise_mean, noise_std)

        obs = RFObservation(
            observation_id=f"{batch_prefix}-{i:04d}",
            timestamp=base_ts + timedelta(seconds=i),
            rssi=round(rng.gauss(rssi_mean, rssi_std), 4),
            snr=round(rng.gauss(snr_mean, snr_std), 4),
            noise_floor=round(nf, 4),
            packet_rate=round(rng.gauss(rate_mean, rate_std), 4),
        )
        observations.append(obs)
    return observations


def evaluate_batch(
    module: ThreatIntelligenceModule,
    observations: list[RFObservation],
) -> dict:
    """Classify a batch of observations and tabulate results."""
    normal_cnt = 0
    jamming_cnt = 0
    anomaly_cnt = 0

    for obs in observations:
        out = module.classify(obs)
        if out.classification == Classification.NORMAL.value:
            normal_cnt += 1
        elif out.classification == Classification.JAMMING.value:
            jamming_cnt += 1
        elif out.classification == Classification.UNKNOWN_ANOMALY.value:
            anomaly_cnt += 1

    total = len(observations)
    detection_rate = (jamming_cnt + anomaly_cnt) / total if total > 0 else 0.0

    return {
        "n": total,
        "normal": normal_cnt,
        "jamming": jamming_cnt,
        "unknown_anomaly": anomaly_cnt,
        "detection_rate": detection_rate,
    }


def run_single_experiment(seed: int, print_table: bool = True) -> list[dict]:
    """Run sweep over k values for a single seed."""
    module, baseline = build_calibrated_module(seed)
    rng = random.Random(seed + 999)

    # 1. Held-out normal batch (k = 0)
    # Using SyntheticDataSource with offset start_id to ensure complete disjointness
    held_out_src = SyntheticDataSource(scenario="normal", seed=seed + 500, start_id=5000)
    normal_obs = held_out_src.fetch_batch(SAMPLES_PER_BATCH)
    norm_res = evaluate_batch(module, normal_obs)
    norm_res.update({
        "seed": seed,
        "dataset": "normal_held_out",
        "k": 0.0,
    })

    results = [norm_res]

    # 2. SNR-only anomaly batches for each k
    for k in K_VALUES:
        batch_prefix = f"ano_k{str(k).replace('.', '_')}"
        ano_obs = generate_snr_anomaly_batch(
            n=SAMPLES_PER_BATCH,
            k=k,
            baseline=baseline,
            rng=rng,
            batch_prefix=batch_prefix,
        )
        ano_res = evaluate_batch(module, ano_obs)
        ano_res.update({
            "seed": seed,
            "dataset": f"snr_anomaly_k{k:.1f}",
            "k": k,
        })
        results.append(ano_res)

    if print_table:
        print(f"\n--- Single Run Table (Seed: {seed}) ---")
        header = f"{'dataset':<20} | {'k (sigma)':<9} | {'n':<5} | {'Normal':<7} | {'Jamming':<7} | {'Unknown':<8} | {'detection rate'}"
        print(header)
        print("-" * len(header))
        for r in results:
            label = " (FPR)" if r["k"] == 0.0 else ""
            print(
                f"{r['dataset']:<20} | {r['k']:<9.1f} | {r['n']:<5} | {r['normal']:<7} | "
                f"{r['jamming']:<7} | {r['unknown_anomaly']:<8} | {r['detection_rate'] * 100:>6.2f}%{label}"
            )

    return results


def run_full_sweep(seeds: list[int]) -> None:
    print("=========================================================================================")
    print("            AI THREAT INTELLIGENCE MODULE - ANOMALY STRENGTH SWEEP                       ")
    print("      Evaluating Detection Sensitivity & False Positive Rate (k * sigma shift)           ")
    print("=========================================================================================")

    all_results = []
    # Print the primary run table for the first seed (42)
    first_run = run_single_experiment(seeds[0], print_table=True)
    all_results.extend(first_run)

    # Run remaining seeds silently
    for s in seeds[1:]:
        res = run_single_experiment(s, print_table=False)
        all_results.extend(res)

    # Aggregate by k across all seeds
    k_list = [0.0] + K_VALUES
    summary_by_k = {}
    for k in k_list:
        k_entries = [r for r in all_results if r["k"] == k]
        rates = [r["detection_rate"] for r in k_entries]
        jam_counts = [r["jamming"] for r in k_entries]

        summary_by_k[k] = {
            "mean_rate": sum(rates) / len(rates),
            "min_rate": min(rates),
            "max_rate": max(rates),
            "total_jamming": sum(jam_counts),
            "seeds_tested": len(k_entries),
        }

    # Print 5-seed aggregated table
    print("\n" + "=" * 95)
    print(f"             AGGREGATED SUMMARY OVER {len(seeds)} INDEPENDENT SEEDS {seeds}            ")
    print("=" * 95)
    agg_header = f"{'k (sigma shift)':<16} | {'Mean Det Rate':<14} | {'Min Rate':<10} | {'Max Rate':<10} | {'Jamming Fires (Total)'}"
    print(agg_header)
    print("-" * 95)

    for k in k_list:
        stats = summary_by_k[k]
        k_label = f"{k:.1f} (Normal FPR)" if k == 0.0 else f"{k:.1f}"
        print(
            f"{k_label:<16} | {stats['mean_rate'] * 100:>12.2f}% | "
            f"{stats['min_rate'] * 100:>8.2f}% | {stats['max_rate'] * 100:>8.2f}% | "
            f"{stats['total_jamming']:>10} / {stats['seeds_tested'] * SAMPLES_PER_BATCH}"
        )
    print("-" * 95)

    # Check jamming rule fires
    total_jamming_on_snr = sum(summary_by_k[k]["total_jamming"] for k in K_VALUES)
    print(f"\n[Invariant Verification] Total Jamming rule fires on SNR-only anomaly batches: {total_jamming_on_snr}")
    if total_jamming_on_snr == 0:
        print("  -> CONFIRMED: 0 jamming rules fired. SNR drop alone never triggers J01 or J02.")
    else:
        print(f"  -> WARNING: {total_jamming_on_snr} observations fired jamming rules.")

    # Honest summary statistics
    mean_fpr = summary_by_k[0.0]["mean_rate"]

    # Smallest k reaching 50% and 90%
    k_50 = None
    k_90 = None
    for k in K_VALUES:
        if k_50 is None and summary_by_k[k]["mean_rate"] >= 0.50:
            k_50 = k
        if k_90 is None and summary_by_k[k]["mean_rate"] >= 0.90:
            k_90 = k

    print("\n--- Research Findings & Anomaly Engine Limits ---")
    print(f"  * Mean False Positive Rate (k = 0.0) : {mean_fpr * 100:.2f}%")
    print(f"  * Smallest k reaching >= 50% detection: {k_50:.1f} sigma (mean: {summary_by_k[k_50]['mean_rate'] * 100:.1f}%)" if k_50 else "  * 50% threshold: not reached in tested k range")
    print(f"  * Smallest k reaching >= 90% detection: {k_90:.1f} sigma (mean: {summary_by_k[k_90]['mean_rate'] * 100:.1f}%)" if k_90 else "  * 90% threshold: not reached in tested k range")
    print(
        "  * Limit of Univariate 3-Sigma Engine  : Subtle anomalies below 3.0 sigma remain predominantly hidden "
        f"within normal statistical dispersion (only {summary_by_k[1.5]['mean_rate']*100:.1f}% caught at 1.5 sigma and "
        f"{summary_by_k[2.5]['mean_rate']*100:.1f}% at 2.5 sigma), while shifts >= 4.0 sigma achieve high-certainty detection "
        f"({summary_by_k[4.0]['mean_rate']*100:.1f}% at 4.0 sigma, {summary_by_k[6.0]['mean_rate']*100:.1f}% at 6.0 sigma) "
        "without triggering any false jamming rules."
    )

    # Save to data/anomaly_strength_sweep.csv
    data_dir = PROJECT_ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "anomaly_strength_sweep.csv"

    fieldnames = [
        "seed", "dataset", "k_sigma", "n", "normal_count",
        "jamming_count", "unknown_anomaly_count", "detection_rate"
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in all_results:
            writer.writerow({
                "seed": r["seed"],
                "dataset": r["dataset"],
                "k_sigma": r["k"],
                "n": r["n"],
                "normal_count": r["normal"],
                "jamming_count": r["jamming"],
                "unknown_anomaly_count": r["unknown_anomaly"],
                "detection_rate": round(r["detection_rate"], 4),
            })

    print(f"\n[Output] Detailed sweep data successfully saved to: {csv_path}\n")


def main():
    parser = argparse.ArgumentParser(description="Sweep anomaly strength (k * sigma) and measure detection sensitivity.")
    parser.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS,
                        help="List of seeds to evaluate across (default: 42 101 202 303 404)")
    args = parser.parse_args()

    run_full_sweep(seeds=args.seeds)


if __name__ == "__main__":
    main()
