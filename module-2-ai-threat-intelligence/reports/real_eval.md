# Real Module 1 measurement evaluation

This report evaluates the frozen measurement-only Module 2 pipeline on the 2026-10-23 recording.
Reference metadata is joined only after classification; expected and actual values are compared at the same observation index.

## Thresholds and provenance

- Source: data/real/module1_signals_clean/known_signals
- Split: first chronological half of idle, legit_ook, CARRIER and PULSED_50_50
- Date: 2026-10-25
- Script: scripts/calibrate_real.py
- T_SNR: 25.800000 dB
- T_BW: 137.500000 kHz
- Idle anomaly limit: 3.000000
- Legitimate OOK anomaly limit: 4.979938

## Calibration

| Expected | NORMAL | JAMMING | UNKNOWN_ANOMALY |
|---|---:|---:|---:|
| NORMAL | 659 | 0 | 0 |
| JAMMING | 0 | 48 | 0 |

| Group | Metric | Result |
|---|---|---:|
| idle | false-positive rate | 0/635 (0.00%) |
| legit_ook | false-positive rate | 0/24 (0.00%) |
| CARRIER | rule-only recall | 24/24 (100.00%) |
| CARRIER | rule + anomaly recall | 24/24 (100.00%) |
| PULSED_50_50 | rule-only recall | 24/24 (100.00%) |
| PULSED_50_50 | rule + anomaly recall | 24/24 (100.00%) |

## Validation

| Expected | NORMAL | JAMMING | UNKNOWN_ANOMALY |
|---|---:|---:|---:|
| NORMAL | 661 | 0 | 0 |
| JAMMING | 0 | 48 | 0 |

| Group | Metric | Result |
|---|---|---:|
| idle | false-positive rate | 0/636 (0.00%) |
| legit_ook | false-positive rate | 0/25 (0.00%) |
| CARRIER | rule-only recall | 24/24 (100.00%) |
| CARRIER | rule + anomaly recall | 24/24 (100.00%) |
| PULSED_50_50 | rule-only recall | 24/24 (100.00%) |
| PULSED_50_50 | rule + anomaly recall | 24/24 (100.00%) |

## Unseen abnormal

| Expected | NORMAL | JAMMING | UNKNOWN_ANOMALY |
|---|---:|---:|---:|
| NORMAL | 0 | 0 | 0 |
| JAMMING | 0 | 93 | 0 |

| Group | Metric | Result |
|---|---|---:|
| PULSED_5_95 | rule-only recall | 48/48 (100.00%) |
| PULSED_5_95 | rule + anomaly recall | 48/48 (100.00%) |
| RANDOM_BURSTS | rule-only recall | 45/45 (100.00%) |
| RANDOM_BURSTS | rule + anomaly recall | 45/45 (100.00%) |

## Leave-one-jammer-type-out

| Held out | Threshold training jammer | T_SNR | T_BW | Non-normal recall |
|---|---|---:|---:|---:|
| CARRIER | PULSED_50_50 | 25.800 | 137.500 | 48/48 (100.00%) |
| PULSED_50_50 | CARRIER | 25.800 | 127.000 | 48/48 (100.00%) |
| PULSED_5_95 | CARRIER + PULSED_50_50 | 25.800 | 137.500 | 48/48 (100.00%) |
| RANDOM_BURSTS | CARRIER + PULSED_50_50 | 25.800 | 137.500 | 45/45 (100.00%) |

## Label-quality rows reported separately

### signal present but labelled none (ambient signal or label timing); inspect only (4)

- sequence 132, S00132: JAMMING
- sequence 133, S00133: JAMMING
- sequence 229, S00229: JAMMING
- sequence 424, S00424: NORMAL

### labelled none inside a jammer phase (jammer off or label timing) (7)

- sequence 83, S00083: NORMAL
- sequence 180, S00180: NORMAL
- sequence 344, S00344: NORMAL
- sequence 346, S00346: NORMAL
- sequence 358, S00358: NORMAL
- sequence 365, S00365: NORMAL
- sequence 368, S00368: NORMAL

## Latency

- classify() mean: 0.0185 ms
- classify() p95: 0.0356 ms
- timed loop mean: 0.0262 ms per record
- NFR01 classify p95 under 50 ms: True

## Decision and limits

The retired four-feature path is not used. R1 identifies a strong narrowband measurement; otherwise the nearest-state anomaly score decides between unknown anomaly and normal.

This evidence comes from one session and one legitimate device. The measured class margins are wide and may not transfer to other radios or environments. R1 could flag a narrowband legitimate device and may miss a wideband jammer. Severity cut-offs are uncalibrated placeholders.
