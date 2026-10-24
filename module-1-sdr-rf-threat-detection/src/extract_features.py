# Offline feature extractor. Turns a baseband recording from SDR++ plus the
# matching phases.csv into a labelled dataset for Module 2.
#   py extract_features.py recording.wav phases.csv
# Writes dataset.csv (one row per window) and summary.csv (averages per phase).

import sys, csv
import numpy as np
import wave

SAMPLE_RATE = 1_024_000
CENTER_FREQ = 433_700_000
WINDOW_S    = 0.25
FFT         = 1024
DC_GUARD_HZ = 5000
SNR_PRESENT_DB = 8.0
OCC_THRESH_DB  = 6.0


def read_iq(path):
    w = wave.open(path, 'rb')
    ch, sw, fs, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    w.close()
    if ch != 2 or sw != 2:
        sys.exit(f"Expected 16-bit stereo IQ wav, got channels={ch} width={sw}")
    raw = np.memmap(path, dtype='<i2', mode='r', offset=44, shape=(n, 2))
    return raw, fs, n


def phase_timeline(csv_path):
    rows = []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            rows.append((int(r["arduino_ms"]), r["label"]))
    if not rows:
        sys.exit("phases.csv is empty")
    t0 = rows[0][0]
    return [((ms - t0) / 1000.0, lab) for ms, lab in rows]


def label_at(timeline, t, align):
    cur = timeline[0][1]
    for start, lab in timeline:
        if t >= start + align:
            cur = lab
        else:
            break
    return cur


def features(z, freqs, binhz, win):
    m = len(z) // FFT
    seg = z[:m * FFT].reshape(m, FFT) * win
    S = np.mean(np.abs(np.fft.fftshift(np.fft.fft(seg, axis=1), axes=1)) ** 2, axis=0)
    S /= (np.sum(win ** 2) * SAMPLE_RATE)
    psd_db = 10 * np.log10(S + 1e-12)

    mid = FFT // 2
    g = int(DC_GUARD_HZ / binhz)
    search = psd_db.copy(); search[mid - g: mid + g + 1] = -300

    noise_db = float(np.percentile(psd_db, 30))
    pk = int(np.argmax(search))
    peak_db = float(search[pk]); peak_freq = float(freqs[pk])
    snr = peak_db - noise_db
    band_power = float(10 * np.log10(np.mean(np.abs(z) ** 2) + 1e-12))
    occ_bw = float(np.sum(search > (noise_db + OCC_THRESH_DB)) * binhz)

    lin = S + 1e-12
    flat = float(np.exp(np.mean(np.log(lin))) / np.mean(lin))
    present = int(snr > SNR_PRESENT_DB)

    # count separated strong clusters, ignoring side-lines within ~40 kHz
    strong = np.where(search > (noise_db + 15))[0]
    npk = int(len(np.where(np.diff(strong) > int(40000 / binhz))[0]) + 1) if len(strong) else 0

    return dict(peak_freq_mhz=round(peak_freq / 1e6, 4),
                peak_db=round(peak_db, 1), noise_db=round(noise_db, 1),
                snr_db=round(snr, 1), band_power_dbfs=round(band_power, 1),
                occupied_bw_khz=round(occ_bw / 1e3, 1),
                spectral_flatness=round(flat, 3), n_peaks=npk,
                signal_present=present)


# label by which transmitter was on, same convention as the live dashboard
def to_label(phase):
    if phase in ("IDLE", "START", "DONE"):
        return "none"
    if phase in ("OOK_DATA", "LINK_ONLY"):
        return "tx1"
    return "tx1_tx2"


def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: py extract_features.py <baseband.wav> <phases.csv>")
    wav, ph = sys.argv[1], sys.argv[2]
    raw, fs, n = read_iq(wav)
    if fs != SAMPLE_RATE:
        print(f"Note: wav is {fs} Hz, script expects {SAMPLE_RATE}. Using {fs}.")
    timeline = phase_timeline(ph)

    freqs = CENTER_FREQ + np.fft.fftshift(np.fft.fftfreq(FFT, 1 / fs))
    binhz = fs / FFT
    win = np.hanning(FFT)
    wlen = int(fs * WINDOW_S)
    nwin = n // wlen

    # align phases.csv to the audio by finding when the power first rises
    pw = np.array([10 * np.log10(np.mean(np.abs(
        (raw[i * wlen:(i + 1) * wlen, 0].astype(np.float32) +
         1j * raw[i * wlen:(i + 1) * wlen, 1].astype(np.float32)) / 32768) ** 2) + 1e-12)
        for i in range(nwin)])
    first_on = next((i for i, v in enumerate(pw) if v > pw.min() + 10), 0)
    first_sig = next((s for s, l in timeline if to_label(l) != "none"), 0)
    align = first_on * WINDOW_S - first_sig
    print(f"Auto-align offset: {align:.2f} s")

    rows = []
    for i in range(nwin):
        s = raw[i * wlen:(i + 1) * wlen]
        z = (s[:, 0].astype(np.float32) + 1j * s[:, 1].astype(np.float32)) / 32768
        t = i * WINDOW_S
        lab = label_at(timeline, t, align)
        feat = features(z, freqs, binhz, win)
        feat["signal_id"] = f"S{i + 1:03d}"
        feat["time_s"] = round(t, 2)
        feat["phase"] = lab
        feat["label"] = to_label(lab)
        rows.append(feat)

    cols = ["signal_id", "time_s", "peak_freq_mhz", "peak_db", "noise_db", "snr_db",
            "band_power_dbfs", "occupied_bw_khz", "spectral_flatness",
            "n_peaks", "signal_present", "phase", "label"]
    with open("dataset.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in cols})

    phases = {}
    for r in rows:
        phases.setdefault(r["phase"], []).append(r)
    numcols = ["snr_db", "band_power_dbfs", "occupied_bw_khz", "spectral_flatness",
               "noise_db", "n_peaks", "signal_present"]
    with open("summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["phase", "label", "windows"] + ["avg_" + c for c in numcols])
        for p, rs in phases.items():
            avg = [round(float(np.mean([x[c] for x in rs])), 2) for c in numcols]
            w.writerow([p, to_label(p), len(rs)] + avg)

    print(f"Wrote dataset.csv ({len(rows)} rows) and summary.csv")


if __name__ == "__main__":
    main()
