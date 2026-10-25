# Real signal feature audit

Generated from the validated measurement records through `src/real_data.py`. Ground truth is joined only in this offline report to form groups and calculate scores; it is not available to the detector.

## Group summary

| Group | Feature | N | Mean | Std | Min | Max | Unique | Resolution |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| idle | peak_db | 1264 | -103.011234 | 0.205237 | -103.600000 | -102.300000 | 14 | 0.100000 |
| idle | noise_db | 1264 | -106.006013 | 0.023782 | -106.100000 | -106.000000 | 2 | 0.100000 |
| idle | snr_db | 1264 | 3.007674 | 0.204338 | 2.400000 | 3.700000 | 14 | 0.100000 |
| idle | band_power_dbfs | 1264 | -45.100000 | 0.000000 | -45.100000 | -45.100000 | 1 | 0.000000 |
| idle | occupied_bw_khz | 1264 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 1 | 0.000000 |
| idle | spectral_flatness | 1264 | 0.850945 | 0.001808 | 0.844000 | 0.858000 | 13 | 0.001000 |
| idle | peak_freq_mhz | 1264 | 433.662575 | 0.122510 | 433.572000 | 433.883000 | 3 | 0.055000 |
| legit_ook | peak_db | 49 | -56.126531 | 0.592585 | -57.400000 | -55.000000 | 20 | 0.100000 |
| legit_ook | noise_db | 49 | -105.236735 | 0.083401 | -105.500000 | -105.100000 | 5 | 0.100000 |
| legit_ook | snr_db | 49 | 49.116327 | 0.596988 | 47.900000 | 50.200000 | 17 | 0.100000 |
| legit_ook | band_power_dbfs | 49 | -19.804082 | 0.444391 | -21.000000 | -18.900000 | 18 | 0.100000 |
| legit_ook | occupied_bw_khz | 49 | 357.795918 | 27.635258 | 218.000000 | 397.000000 | 29 | 1.000000 |
| legit_ook | spectral_flatness | 49 | 0.008959 | 0.000978 | 0.007000 | 0.011000 | 5 | 0.001000 |
| legit_ook | peak_freq_mhz | 49 | 433.957694 | 0.000895 | 433.956000 | 433.962000 | 5 | 0.001000 |
| CARRIER | peak_db | 48 | -47.272917 | 0.900766 | -52.800000 | -46.700000 | 14 | 0.100000 |
| CARRIER | noise_db | 48 | -107.277083 | 0.160106 | -107.400000 | -106.300000 | 5 | 0.100000 |
| CARRIER | snr_db | 48 | 59.997917 | 1.038512 | 53.500000 | 60.600000 | 15 | 0.100000 |
| CARRIER | band_power_dbfs | 48 | -15.033333 | 0.572168 | -18.900000 | -14.900000 | 3 | 0.100000 |
| CARRIER | occupied_bw_khz | 48 | 16.895833 | 7.421188 | 6.000000 | 36.000000 | 21 | 1.000000 |
| CARRIER | spectral_flatness | 48 | 0.001021 | 0.000144 | 0.001000 | 0.002000 | 2 | 0.001000 |
| CARRIER | peak_freq_mhz | 48 | 433.960000 | 0.001031 | 433.959000 | 433.963000 | 5 | 0.001000 |
| PULSED_50_50 | peak_db | 48 | -51.666667 | 0.606817 | -52.900000 | -50.600000 | 19 | 0.100000 |
| PULSED_50_50 | noise_db | 48 | -106.208333 | 0.100707 | -106.400000 | -106.000000 | 5 | 0.100000 |
| PULSED_50_50 | snr_db | 48 | 54.554167 | 0.695260 | 53.100000 | 55.800000 | 23 | 0.100000 |
| PULSED_50_50 | band_power_dbfs | 48 | -18.108333 | 0.468512 | -19.000000 | -17.400000 | 17 | 0.100000 |
| PULSED_50_50 | occupied_bw_khz | 48 | 46.312500 | 8.415174 | 30.000000 | 62.000000 | 25 | 1.000000 |
| PULSED_50_50 | spectral_flatness | 48 | 0.002292 | 0.000459 | 0.002000 | 0.003000 | 2 | 0.001000 |
| PULSED_50_50 | peak_freq_mhz | 48 | 433.959521 | 0.000618 | 433.959000 | 433.961000 | 3 | 0.001000 |
| PULSED_5_95 | peak_db | 48 | -62.870833 | 1.429173 | -65.000000 | -60.100000 | 26 | 0.100000 |
| PULSED_5_95 | noise_db | 48 | -105.629167 | 0.103056 | -105.900000 | -105.500000 | 5 | 0.100000 |
| PULSED_5_95 | snr_db | 48 | 42.752083 | 1.388247 | 40.700000 | 45.400000 | 26 | 0.100000 |
| PULSED_5_95 | band_power_dbfs | 48 | -27.841667 | 1.463577 | -29.900000 | -25.100000 | 25 | 0.100000 |
| PULSED_5_95 | occupied_bw_khz | 48 | 37.979167 | 16.412877 | 14.000000 | 100.000000 | 25 | 1.000000 |
| PULSED_5_95 | spectral_flatness | 48 | 0.023458 | 0.006401 | 0.014000 | 0.036000 | 18 | 0.001000 |
| PULSED_5_95 | peak_freq_mhz | 48 | 433.958000 | 0.000000 | 433.958000 | 433.958000 | 1 | 0.000000 |
| RANDOM_BURSTS | peak_db | 45 | -54.997778 | 5.437140 | -67.100000 | -48.000000 | 29 | 0.100000 |
| RANDOM_BURSTS | noise_db | 45 | -106.033333 | 0.295420 | -106.700000 | -105.600000 | 11 | 0.100000 |
| RANDOM_BURSTS | snr_db | 45 | 51.024444 | 5.625920 | 38.800000 | 58.700000 | 32 | 0.100000 |
| RANDOM_BURSTS | band_power_dbfs | 45 | -21.402222 | 5.718133 | -34.800000 | -14.400000 | 32 | 0.100000 |
| RANDOM_BURSTS | occupied_bw_khz | 45 | 31.511111 | 18.383073 | 10.000000 | 91.000000 | 24 | 1.000000 |
| RANDOM_BURSTS | spectral_flatness | 45 | 0.012289 | 0.022224 | 0.001000 | 0.079000 | 14 | 0.001000 |
| RANDOM_BURSTS | peak_freq_mhz | 45 | 433.960533 | 0.001036 | 433.958000 | 433.962000 | 5 | 0.001000 |

## Single-feature discrimination

AUC is direction-adjusted so 0.5 means chance and 1.0 means complete separation. The direction column says whether lower or higher values indicate jamming. AUC is descriptive, not a permission to use a session artefact.

| Feature | Jamming vs idle AUC | Direction | Jamming vs legit OOK AUC | Direction | Audit flag |
|---|---:|---|---:|---|---|
| peak_db | 1.0000 | higher | 0.6760 | higher | none |
| noise_db | 0.6070 | lower | 0.9996 | lower | quantised; session artefact |
| snr_db | 1.0000 | higher | 0.6813 | higher | none |
| band_power_dbfs | 1.0000 | higher | 0.6263 | higher | constant in at least one group |
| occupied_bw_khz | 1.0000 | higher | 1.0000 | lower | constant in at least one group |
| spectral_flatness | 1.0000 | lower | 0.6919 | lower | quantised |
| peak_freq_mhz | 1.0000 | higher | 0.8900 | higher | constant in at least one group; quantised; session artefact |

## Findings in plain words

- `noise_db` changes with the scripted phase: its mean is about -107.28 dB for CARRIER, -106.21 dB for PULSED_50_50, and -105.24 dB for legitimate OOK. That looks like session order or receiver state, not portable threat evidence, so v2 excludes it.
- `peak_freq_mhz` has very few distinct bins and follows the one transmitter/channel used in this session. It could identify this recording setup instead of jamming, so v2 excludes it.
- Idle `band_power_dbfs` is constant at -45.1 and idle `occupied_bw_khz` is constant at 0. The v2 baseline retains them because they have physical meaning, but applies 0.1 dB and 1 kHz standard-deviation floors.
- Several fields are rounded to 0.1 dB, 1 kHz, or 0.001. Small differences inside one output step should not be treated as precise changes.
- The selected anomaly features are: `peak_db`, `snr_db`, `band_power_dbfs`, `occupied_bw_khz`, `spectral_flatness`.
- Labels, phase names, jammer names, paths, and Module 1 flags are used only to assemble or score offline groups. None is present in the runtime feature object.
