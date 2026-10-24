# Module 1 signals (clean): measurements only

Source: dataset_20261023_162220.csv (Module 1, 2026-10-23, 317.8 s, 1,513 signals, 433 MHz band).

## What is in the signal files
Only raw measurements: peak_freq_mhz, peak_db, noise_db, snr_db, band_power_dbfs, occupied_bw_khz,
spectral_flatness, plus observation_id, sequence_number, timestamp (Module 1 local time, no time zone), elapsed_s.
There is NO label, NO test phase, and NO Module 1 flag (interference, channel, signal_present, power_anomaly).
Your module must decide Normal / Jamming / Unknown Anomaly from the measurements alone.

## Folders (for the test harness only; never use folder names as features)
- known_signals/ (1,416): idle noise, the legitimate OOK transmission, and CARRIER and PULSED_50_50 jamming.
  Use for calibrating the baseline and rules (split by time, never at random).
- abnormal_signals/ (93): PULSED_5_95 and RANDOM_BURSTS jamming. Your rules must NOT be tuned on these.
  They test whether the module notices unfamiliar behaviour. Acceptable outputs: JAMMING or UNKNOWN_ANOMALY.
  NORMAL is a miss.
- ambiguous_signals/ (4): a strong signal present while the test harness said nothing was active.
  Inspect only. Do not score.

## Reference files (scoring and reporting only, never analysis input)
- ground_truth.csv: label, phase, expected class, jammer type, notes.
- module1_flags_reference.csv: Module 1's own flags. Use only to report how often they agree with your module.

## Limits
One session, one legitimate device, 49 normal rows. A perfect result here does not prove the rules
work on other devices, powers or places. Record more sessions before final results.
