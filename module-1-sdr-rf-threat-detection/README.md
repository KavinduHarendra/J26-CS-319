# SDR RF Threat Detection (Module 1)

Module 1 of the final-year project *AI-Driven SDR-Based Anti-Jamming Framework
for UAV Cyber Defense* (J26-CS-319).

This module monitors the 433 MHz band with a low-cost RTL-SDR, measures RF
features in real time, and saves a labelled dataset that Module 2 uses to
classify threats. It also drives a controlled test transmitter setup so the
captures have known ground truth.

Module 1 only **detects and measures**. Deciding whether a signal is jamming,
normal, or unauthorized is Module 2's job, so the labels here describe the test
setup (which transmitter was on), not a verdict.

## Hardware

- RTL-SDR (RX only) with antenna
- Arduino Uno
- 1-2 x FS1000A 433 MHz transmitter modules
- Breadboard and jumper wires

One FS1000A gives a single test source. Two FS1000A give a normal link plus a
second transmitter on the same band, which is the setup used for the
`tx1` / `tx1_tx2` dataset.

## Software setup (Windows)

1. Install the RTL-SDR driver with Zadig (WinUSB on "Bulk-In, Interface 0").
2. Put `rtlsdr.dll` and `libusb-1.0.dll` on the path (e.g. the Python folder).
3. Install the Python packages:
   ```
   py -m pip install pyrtlsdr pyqtgraph PyQt5 numpy pyserial "setuptools<81"
   ```

## Files

| File | What it does |
|------|--------------|
| `rf_dashboard.py` | Live dashboard: reads the SDR + Arduino, shows the spectrum/waterfall/features, and saves a labelled dataset. |
| `fs1000a_two_tx_jamming.ino` | Two-transmitter sketch: TX1 normal link, TX2 second transmitter during JAM phases. |
| `fs1000a_test_patterns.ino` | Single-transmitter test patterns. |
| `serial_logger.py` | Logs Arduino phase labels to `phases.csv` (only needed when recording with SDR++). |
| `extract_features.py` | Builds a labelled dataset from a saved SDR++ recording + `phases.csv`. |
| `balance_dataset.py` | Makes a balanced copy with equal rows per label. |

## Usage

Live capture (reads the Arduino itself, no SDR++):

```
py rf_dashboard.py
```

Close SDR++ and the Arduino Serial Monitor first so the SDR and COM port are
free. The dashboard writes `dataset_<date_time>.csv`.

Offline from a recording:

```
py extract_features.py recording.wav phases.csv
py balance_dataset.py dataset.csv
```

## Dataset

One row per time window. Key columns:

`signal_id, timestamp, peak_freq_mhz, snr_db, band_power_dbfs,
occupied_bw_khz, spectral_flatness, noise_db, signal_present, phase, label`

Labels: `tx1` (normal link only), `tx1_tx2` (both transmitters), `none`
(no signal).

## Note on the hardware

The FS1000A is a simple OOK transmitter on a fixed 433 MHz channel. This setup
supports energy- and time-based features (power, SNR, bandwidth, duty cycle).
Source authentication and an unauthorized-channel class need an HC-12 (planned)
and are out of scope for the current hardware.
