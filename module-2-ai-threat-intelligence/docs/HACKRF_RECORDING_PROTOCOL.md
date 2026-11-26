# HackRF recording protocol for Module 1

This is a checklist for recording the HackRF One sessions that Module 2 will be
recalibrated and evaluated on. Following it makes every session usable; a
session that breaks a rule here usually has to be recorded again.

Before handing a session over, run the checker described at the end. It must
report `RESULT: PASS`.

## 1. Sessions to record

Record each item below as its own session, in its own folder. Repeat the
whole set on at least two different days (see section 5).

Normal sessions:

- [ ] **Idle**: no drone link, no jammer, nothing deliberately transmitting.
- [ ] **Drone link on**: the normal drone-to-ground-station link, as flown.
- [ ] **Ambient Wi-Fi and Bluetooth**: ordinary nearby phones, laptops and
      routers active, no jammer.
- [ ] **Narrowband legitimate device**: a legitimate transmitter with a narrow
      signal (for example a 433 MHz remote or telemetry beacon). R1 could
      mistake this for jamming, so it must be measured.

Jamming sessions. For **each** pattern, record at least three jammer powers
(low, medium, high) and at least three distances (near, middle, far). Each
pattern x power x distance combination is a separate session:

- [ ] Continuous (carrier)
- [ ] Pulsed
- [ ] Random bursts
- [ ] Sweep
- [ ] **Wideband jammer**: a jammer whose signal is wider than the narrowband
      limit. R1 may miss it, so it must be measured.

Abnormal but not jamming. Module 2 cannot currently be tested on these, because
the 2026-10-23 recording has none:

- [ ] Unknown transmitter (a device not used anywhere else in the recordings)
- [ ] Wideband interference that is not a jammer (for example a noisy power
      supply or motor)
- [ ] Microwave oven running nearby (2.4 GHz band)
- [ ] Bluetooth burst (pairing or file transfer close to the antenna)
- [ ] Drone link on an unusual frequency (the normal link moved off its usual
      frequency)

Give every session a **neutral** session ID, such as `S20261201_03`: date plus
a running number. The ID must not describe the content: no `idle`, `carrier`,
`jam` or similar. What each session contains goes in the session log and
`ground_truth.csv`, never in the ID or in the capture files.

## 2. Fixed and logged radio settings

For each session, before the first capture:

- [ ] Choose the **centre frequency**, **sample rate** and **gain** (LNA, VGA
      and the amplifier on/off), and turn off any automatic gain.
- [ ] **Clipping check**: switch on the strongest signal of the session at its
      closest distance (for example the high-power jammer, near). Confirm the
      raw IQ samples stay clear of full scale (HackRF samples are 8-bit, so
      stay well below +/-127) and `band_power_dbfs` stays below -1 dBFS. If
      not, lower the gain and check again. A clipped session is not usable.
- [ ] Keep these settings **unchanged** for the whole session. If anything has
      to change, stop and start a new session.
- [ ] Write the settings into every capture file: `center_freq_hz`,
      `sample_rate_hz` and `gain_db` (total gain in dB, 0 to 100).
- [ ] Also note them in a session log, together with the date, place, antenna,
      HackRF serial number, jammer model, jammer power and jammer distance.

## 3. Ground truth, kept separate

Each session folder has one `ground_truth.csv`, written from your notes and
timings. It is used only to score Module 2 and is never read when classifying.

- [ ] Columns: `sequence_number`, `observation_id`, `timestamp`,
      `expected_class`, `event_type`, `jammer_on`.
- [ ] `expected_class` is `NORMAL`, `JAMMING` or `UNKNOWN_ANOMALY` (for the
      abnormal-but-not-jamming events).
- [ ] `event_type` says what was happening, for example `idle`,
      `drone_link`, `ambient_wifi_bt`, `narrowband_legit`, `carrier`,
      `pulsed`, `random_bursts`, `sweep`, `wideband_jammer`,
      `unknown_transmitter`, `wideband_interference`, `microwave_oven`,
      `bluetooth_burst`, `link_unusual_frequency`.
- [ ] `jammer_on` is `1` while the jammer transmits and `0` otherwise, taken
      from the timestamps when you switched it on and off.
- [ ] One row per capture, nothing missing and nothing extra.
- [ ] **Never** put any of this inside a capture JSON. Module 2 rejects a
      capture that contains keys such as `label`, `phase`, `jammer`,
      `jammer_on`, `event_type` or `expected_class`.
- [ ] Leave about 10 seconds after switching anything on or off, and mark
      those captures as transitions in the session log, so mixed captures are
      not scored as clean examples.

## 4. Folder layout

```text
recordings/
  S20261201_01/
    ground_truth.csv
    000001_S20261201_01_00001.json
    000002_S20261201_01_00002.json
    ...
  S20261201_02/
    ...
```

- [ ] One folder per session; all of that session's captures directly inside
      it, no subfolders.
- [ ] One JSON file per capture, in the existing Module 1 format.
- [ ] `sequence_number` starts at 1 and increases by exactly 1, with no gaps
      and no repeats. A capture that fails is still numbered and noted, not
      skipped silently.
- [ ] `observation_id` is unique within the session.
- [ ] `session_id` (the folder name) is in every capture file.
- [ ] Optional, if Module 1 can compute them: `distance_m` (UAV to ground
      station), and in `measurements`: `occupied_fraction` (0 to 1),
      `peak_count` (whole number, 0 to 1000) and `duty_cycle` (0 to 1).
      Module 2 checks and stores these but does not yet use them for any
      decision.

## 5. How much to record

- [ ] At least **200 captures of each class present in a session** (for
      example 200 NORMAL in an idle session; 200 JAMMING in a jammer session).
      Idle sessions: at least **600**.
- [ ] Record on **at least two different days**, repeating the same sessions
      with the same settings. Three days is better.

Why: Module 2 calibrates on the first half of each session and validates on
the second half, so 200 captures give 100 for each half. The 2026-10-23
recording had only 24 captures per jammer type in each half, which made the
thresholds and severity coarse; about 100 per half gives stable percentiles
and is enough for the normality test. Idle noise varies more slowly, so it
needs a longer recording. A second day shows whether results hold up after the
equipment is moved and set up again, instead of only within one sitting.

## 6. Never mix setups

- [ ] Results from different frequency bands (for example 433 MHz and
      2.4 GHz), different gains, antennas or radios are **never** combined
      into one calibration. Each band and setup is calibrated and evaluated on
      its own.
- [ ] The RTL-SDR recording from 2026-10-23 is not mixed with HackRF
      recordings either.

## Before you hand a session over

Run the checker from the Module 2 folder on each session folder:

```powershell
.\.venv\Scripts\python.exe scripts\validate_recording.py recordings\S20261201_01
```

It reads the folder without changing anything and checks:
- every capture against the Module 2 input format;
- gaps and duplicates;
- timestamp order;
- clipping;
- that the session ID and radio settings stay the same throughout;
- that `ground_truth.csv` covers every capture;
- how many captures each class has.

It must end with `RESULT: PASS`. Warnings, such as fewer than 200 captures of
a class, are reported but do not fail the session; fix them if you can.
