# Module 1 real signals: one JSON file per signal

Source: dataset_20261023_162220.csv (Module 1, session started 2026-10-23 16:22:20, 317.8 s, 1,513 signals,
about 5 signals per second, 433 MHz band).

## Contents
- 1,513 files named <6-digit sequence>_<signal id>.json. Each one is what Module 2 would receive for ONE signal.
- ground_truth.csv: the labels (original label, test phase, expected class, jammer type, note).
  It is kept OUT of the signal files on purpose, so the analysis cannot see the answer.

## Signal file fields
- observation_id: Module 1's signal_id (for example S00001). sequence_number: row order, starting at 1.
- timestamp: Module 1's local time, with no time zone. elapsed_s: seconds since the session started.
- measurements: peak_freq_mhz, peak_db, noise_db, snr_db, band_power_dbfs, occupied_bw_khz, spectral_flatness.
- module1_flags: interference, channel, signal_present, power_anomaly. These are Module 1's own indicators.
  In this session interference is identical to signal_present, and power_anomaly is always 0.

## Rules for using this data
1. Never use phase or any label column as an input feature. They are for scoring only.
2. interference / signal_present means a signal was detected. It is 1 for jamming AND for the legitimate
   OOK transmission, so it does not mean jamming.
3. Split by phase or time block, never at random. Neighbouring signals are almost identical.
4. 7 rows are labelled none inside jammer phases and 4 rows are signal-present but labelled none.
   See label_quality_note in ground_truth.csv.
