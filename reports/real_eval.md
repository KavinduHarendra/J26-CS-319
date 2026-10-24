# Real signal detector evaluation

All signal values were read through `src/real_data.py`. Ground truth and Module 1 flags were loaded separately for split construction and scoring only. Runtime classification receives a `RealSignal`, which contains measurements but no labels, phase, jammer type, folder, or Module 1 flags.

## Non-random split

| Partition | Contents | N |
|---|---|---:|
| Calibration normal | First half by timestamp of clean idle (632) and legitimate OOK (24) | 656 |
| Calibration jamming | All clean CARRIER and PULSED_50_50 jamming | 96 |
| Validation | Second half by timestamp of clean idle (632) and legitimate OOK (25) | 657 |
| Unseen | PULSED_5_95 and RANDOM_BURSTS; never used for fitting or threshold selection | 93 |

The 11 rows carrying label-quality notes are excluded from calibration, validation, and unseen scoring and are reported separately below.

## Baseline v2

Version: `real-baseline-v2`. The normal state is selected as legitimate when SNR is above the idle-only 99th-percentile threshold of 3.500 dB; otherwise it is idle. Anomaly distance is evaluated against both states and uses the nearer one.

| State | Feature | Mean | Std used | Resolution floor |
|---|---|---:|---:|---:|
| idle | peak_db | -103.004272 | 0.203840 | 0.100000 |
| idle | snr_db | 3.011234 | 0.203574 | 0.100000 |
| idle | band_power_dbfs | -45.100000 | 0.100000 | 0.100000 |
| idle | occupied_bw_khz | 0.000000 | 1.000000 | 1.000000 |
| idle | spectral_flatness | 0.851628 | 0.001703 | 0.001000 |
| legitimate | peak_db | -56.333333 | 0.661794 | 0.100000 |
| legitimate | snr_db | 48.958333 | 0.699016 | 0.100000 |
| legitimate | band_power_dbfs | -19.866667 | 0.503610 | 0.100000 |
| legitimate | occupied_bw_khz | 347.416667 | 33.183176 | 1.000000 |
| legitimate | spectral_flatness | 0.008750 | 0.001032 | 0.001000 |

## Rules and anomaly threshold

`R2-NARROWBAND`: IF SNR > 3.500 dB AND occupied bandwidth <= 62.000 kHz AND spectral flatness <= 0.003, THEN Jamming. Grid search used calibration rows only and selected the tightest thresholds among equal-recall candidates satisfying normal FPR <= 1%.

Calibration rule FPR: 0.0000%; calibration jammer recall: 100.0000%.

The nearest-state RMS robust-z anomaly threshold is 1.699486. It is the higher empirical 99th percentile of calibration-normal distances; a record must be strictly above it.

Legacy J01 is retired because a noise-floor rise is not present in these real captures and `noise_db` shifts with phase. Legacy J02 is retired because RSSI/packet-rate fields do not exist in the Module 1 real contract. Neither legacy rule is called by the v2 classifier.

Severity cut-offs remain placeholders at robust-z magnitudes 3.0 and 6.0; they need incident-impact data before operational use.

## Confusion matrices

Unknown Anomaly counts as detected abnormal behaviour for jammer recall, but it remains separate from rule-confirmed Jamming.

### Calibration: known jammers plus first normal halves

| Expected \ Output | NORMAL | JAMMING | UNKNOWN_ANOMALY |
|---|---:|---:|---:|
| NORMAL | 650 | 0 | 6 |
| JAMMING | 0 | 96 | 0 |

### Validation: second normal halves

| Expected \ Output | NORMAL | JAMMING | UNKNOWN_ANOMALY |
|---|---:|---:|---:|
| NORMAL | 647 | 0 | 10 |
| JAMMING | 0 | 0 | 0 |

### Unseen jammer types

| Expected \ Output | NORMAL | JAMMING | UNKNOWN_ANOMALY |
|---|---:|---:|---:|
| NORMAL | 0 | 0 | 0 |
| JAMMING | 0 | 19 | 74 |

## Rule-only versus Rule + Anomaly

| Set | Rule-only detected | Combined detected | Total positive | Rule-only normal FP | Combined normal FP | Total normal |
|---|---:|---:|---:|---:|---:|---:|
| Calibration | 96 | 96 | 96 | 0 | 6 | 656 |
| Validation | 0 | 0 | 0 | 0 | 10 | 657 |
| Unseen | 19 | 93 | 93 | 0 | 0 | 0 |

## Recall and false-positive rates

| Jammer type | Rule hits | Anomaly-only hits | Misses | Recall |
|---|---:|---:|---:|---:|
| CARRIER | 48 | 0 | 0 | 100.00% |
| PULSED_50_50 | 48 | 0 | 0 | 100.00% |
| PULSED_5_95 | 0 | 48 | 0 | 100.00% |
| RANDOM_BURSTS | 19 | 26 | 0 | 100.00% |

| Normal state / partition | False positives | N | FPR |
|---|---:|---:|---:|
| Idle calibration | 5 | 632 | 0.79% |
| Idle validation | 10 | 632 | 1.58% |
| Legitimate OOK calibration | 1 | 24 | 4.17% |
| Legitimate OOK validation | 0 | 25 | 0.00% |

## Leave-one-known-jammer-type-out

The unseen types remain untouched. The only valid threshold-selection leave-one-out exercise is therefore across the two known calibration types; each fold calibrates on one known type and tests the other.

| Held out | Training jammer | Rule hits | Combined hits | N |
|---|---|---:|---:|---:|
| CARRIER | PULSED_50_50 | 48 | 48 | 48 |
| PULSED_50_50 | CARRIER | 5 | 48 | 48 |

PULSED_5_95 and RANDOM_BURSTS are a stricter two-type holdout: neither appears in any fitting step. Their results are the Unseen matrix and per-type rows above.

## Label-quality exceptions

These rows are descriptive only and do not affect thresholds or headline scores.

| Observation | Reference note | Output | Rule |
|---|---|---|---|
| S00083 | labelled none inside a jammer phase (jammer off or label timing) | NORMAL | - |
| S00180 | labelled none inside a jammer phase (jammer off or label timing) | NORMAL | - |
| S00344 | labelled none inside a jammer phase (jammer off or label timing) | NORMAL | - |
| S00346 | labelled none inside a jammer phase (jammer off or label timing) | NORMAL | - |
| S00358 | labelled none inside a jammer phase (jammer off or label timing) | NORMAL | - |
| S00365 | labelled none inside a jammer phase (jammer off or label timing) | NORMAL | - |
| S00368 | labelled none inside a jammer phase (jammer off or label timing) | NORMAL | - |
| S00132 | signal present but labelled none (ambient signal or label timing); inspect only | JAMMING | R2-NARROWBAND |
| S00133 | signal present but labelled none (ambient signal or label timing); inspect only | JAMMING | R2-NARROWBAND |
| S00229 | signal present but labelled none (ambient signal or label timing); inspect only | JAMMING | R2-NARROWBAND |
| S00424 | signal present but labelled none (ambient signal or label timing); inspect only | NORMAL | - |

Counts: 7 `none inside jammer phase` rows and 4 `signal present but labelled none` rows.

## Module 1 flag agreement (reference only)

The detector's abnormal/normal decision agrees with Module 1's `interference` flag on 1439/1502 clean records (95.81%). This is an agreement statistic, not detector input.

`signal_present` is 1 for 49/49 legitimate OOK records and 189/189 jamming records. It therefore says that energy is present, not whether the energy is hostile, and is not used as sole evidence.

## Limits

- This is one approximately 318-second session, one receiver setup, one frequency band, and one legitimate OOK device.
- The normal legitimate state contains only 49 records. Its estimated spread and the state boundary need more devices, powers, distances, locations, and days.
- Thresholds may describe this receiver and scripted schedule. They must be revalidated prospectively before deployment.
- The anomaly threshold controls calibration false alarms, not future-site false alarms; the chronological validation result is the more honest in-session check.
- Severity levels are presentation placeholders and are not calibrated to operational harm.
