# Module 1 - live RF signal monitor for the UAV anti-jamming project.
# Reads the RTL-SDR for the spectrum and features, reads the Arduino over serial
# to tag each row with which transmitter was on, and saves a labelled dataset.
# Deciding whether a signal is actually jamming is left to Module 2.
#
# Close SDR++ before running (only one program can use the SDR at a time).
# Don't run serial_logger.py alongside this - it reads the Arduino itself.
#   py rf_dashboard.py

import sys, time, json, csv, collections, datetime, threading
import numpy as np

try:
    from rtlsdr import RtlSdr
except ImportError:
    sys.exit("pyrtlsdr not loaded - check rtlsdr.dll and libusb-1.0.dll are on the path.")
try:
    import pyqtgraph as pg
    from pyqtgraph.Qt import QtWidgets, QtCore
except ImportError:
    sys.exit("pyqtgraph missing - run: py -m pip install pyqtgraph PyQt5")
try:
    import serial
except ImportError:
    serial = None

CENTER_FREQ = 433.70e6
SAMPLE_RATE = 1.024e6
GAIN        = 3.0
CHUNK       = 262144
FFT         = 1024
WATERFALL_ROWS = 220
TRACE_LEN   = 300

ARDUINO_PORT = "COM15"
ARDUINO_BAUD = 115200

SNR_PRESENT_DB = 8.0
OCC_THRESH_DB  = 6.0
DUP_PEAK_DB    = 15.0
DC_GUARD       = 5000.0

# Labels describe which transmitter(s) were on - ground truth about the test rig,
# not a jamming verdict. TX1 is the normal link, TX2 the second transmitter.
BOTH_TX_PHASES = {"JAM_CONSTANT", "JAM_PULSED", "JAM_RANDOM",
                  "CARRIER", "PULSED_50_50", "PULSED_5_95", "RANDOM_BURSTS"}
TX1_PHASES     = {"OOK_DATA", "LINK_ONLY"}
NONE_PHASES    = {"IDLE", "START", "DONE"}

BG, PANEL, TEXT, MUTED = "#0e1116", "#161b22", "#e6edf3", "#8b949e"
ACCENT, GREEN, AMBER, RED = "#2f81f7", "#2ea043", "#d29922", "#f85149"


class SdrReader(QtCore.QThread):
    def __init__(self, sdr):
        super().__init__(); self.sdr = sdr; self.latest = None; self.running = True

    def run(self):
        while self.running:
            try: self.latest = self.sdr.read_samples(CHUNK)
            except Exception as e: print("SDR read error:", e); time.sleep(0.2)

    def stop(self): self.running = False; self.wait(1000)


class ArduinoReader(threading.Thread):
    # Tracks the current phase label the sketch prints as "millis,LABEL".
    # Optional - if the port can't open, rows just stay unlabelled.
    def __init__(self, port, baud):
        super().__init__(daemon=True)
        self.phase = "(waiting)"; self.ok = False; self.running = True; self.ser = None
        if serial is None:
            print("pyserial not installed - dataset will be unlabelled.")
            return
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            time.sleep(2.5)                 # the Uno resets when the port opens
            self.ser.reset_input_buffer()
            self.ok = True
            print(f"Arduino connected on {port}.")
        except Exception as e:
            self.phase = "(no arduino)"
            print(f"Could not open {port}: {e} - dataset will be unlabelled.")

    def run(self):
        if not self.ser: return
        while self.running:
            try:
                line = self.ser.readline().decode(errors="ignore").strip()
                if "," in line:
                    self.phase = line.split(",", 1)[1]
            except Exception:
                time.sleep(0.2)

    def stop(self):
        self.running = False
        if self.ser:
            try: self.ser.close()
            except Exception: pass


def make_lut():
    pts = [(0, (6, 12, 30)), (0.25, (0, 70, 150)), (0.5, (0, 170, 170)),
           (0.75, (240, 200, 0)), (1.0, (230, 40, 0))]
    lut = np.zeros((256, 3), np.uint8)
    for i in range(256):
        x = i / 255.0
        for j in range(len(pts) - 1):
            x0, c0 = pts[j]; x1, c1 = pts[j + 1]
            if x0 <= x <= x1:
                t = (x - x0) / (x1 - x0)
                lut[i] = [int(c0[k] + t * (c1[k] - c0[k])) for k in range(3)]; break
    return lut


def phase_to_label(phase, present):
    if not present:
        return "none"
    if phase in BOTH_TX_PHASES: return "tx1_tx2"
    if phase in TX1_PHASES:     return "tx1"
    if phase in NONE_PHASES:    return "none"
    return "unlabelled"


class Dashboard(QtWidgets.QWidget):
    def __init__(self, sdr, sdr_reader, ard):
        super().__init__()
        self.sdr = sdr; self.reader = sdr_reader; self.ard = ard
        self.freqs = (CENTER_FREQ + np.fft.fftshift(np.fft.fftfreq(FFT, 1 / SAMPLE_RATE))) / 1e6
        self.binhz = SAMPLE_RATE / FFT
        self.wf = np.full((WATERFALL_ROWS, FFT), -110.0, np.float32)
        self.win = np.hanning(FFT)
        self.baseline = collections.deque(maxlen=200)
        self.t_hist = collections.deque(maxlen=TRACE_LEN)
        self.pw_hist = collections.deque(maxlen=TRACE_LEN)
        self.snr_hist = collections.deque(maxlen=TRACE_LEN)
        self.t0 = time.time(); self.count = 0
        self.n_tx1 = self.n_both = self.n_none = 0
        self._build_ui(); self._open_logs()
        self.timer = QtCore.QTimer(); self.timer.timeout.connect(self.update); self.timer.start(200)

    def _build_ui(self):
        self.setWindowTitle("Module 1  -  SDR RF Monitor + Live Dataset")
        self.resize(1300, 840); self.setStyleSheet(f"background:{BG}; color:{TEXT};")
        pg.setConfigOption('background', BG); pg.setConfigOption('foreground', MUTED)
        pg.setConfigOptions(antialias=True)
        root = QtWidgets.QHBoxLayout(self); root.setContentsMargins(12, 12, 12, 12); root.setSpacing(12)
        glw = pg.GraphicsLayoutWidget(); root.addWidget(glw, 3)
        ts = {'color': TEXT, 'size': '11pt'}

        self.p_spec = glw.addPlot(row=0, col=0); self.p_spec.setTitle("Spectrum", **ts)
        self.p_spec.setLabel('left', 'Power (dB)'); self.p_spec.showGrid(x=True, y=True, alpha=0.15)
        self.p_spec.setYRange(-120, -30); self.p_spec.enableAutoRange('y', False)
        self.curve = self.p_spec.plot(self.freqs, np.full(FFT, -120),
                                      pen=pg.mkPen(ACCENT, width=1.5), fillLevel=-120, brush=(47, 129, 247, 60))
        self.noise_line = pg.InfiniteLine(angle=0, pen=pg.mkPen(AMBER, width=1, style=QtCore.Qt.DashLine))
        self.p_spec.addItem(self.noise_line)
        self.peak_dot = pg.ScatterPlotItem(size=10, brush=pg.mkBrush(RED), pen=None); self.p_spec.addItem(self.peak_dot)

        self.p_wf = glw.addPlot(row=1, col=0); self.p_wf.setTitle("Waterfall", **ts)
        self.p_wf.setLabel('bottom', 'Frequency (MHz)'); self.p_wf.hideAxis('left'); self.p_wf.setXLink(self.p_spec)
        self.img = pg.ImageItem(); self.img.setLookupTable(make_lut()); self.p_wf.addItem(self.img)
        self.img.setRect(QtCore.QRectF(self.freqs[0], 0, self.freqs[-1] - self.freqs[0], WATERFALL_ROWS))

        self.p_tr = glw.addPlot(row=2, col=0)
        self.p_tr.setTitle("Signal over time (watch it change when TX2 turns on)", **ts)
        self.p_tr.setLabel('left', 'Power / SNR (dB)'); self.p_tr.setLabel('bottom', 'Time (s)')
        self.p_tr.showGrid(x=True, y=True, alpha=0.15); self.p_tr.addLegend(offset=(10, 5))
        self.tr_pw = self.p_tr.plot([], [], pen=pg.mkPen(ACCENT, width=2), name="Strength (dBFS)")
        self.tr_snr = self.p_tr.plot([], [], pen=pg.mkPen(GREEN, width=2), name="SNR (dB)")
        glw.ci.layout.setRowStretchFactor(0, 3); glw.ci.layout.setRowStretchFactor(1, 3); glw.ci.layout.setRowStretchFactor(2, 2)

        side = QtWidgets.QVBoxLayout(); side.setSpacing(10); root.addLayout(side, 1)
        self.status = QtWidgets.QLabel("NO SIGNAL"); self.status.setAlignment(QtCore.Qt.AlignCenter)
        self.status.setStyleSheet("font-size:22px; font-weight:700; padding:14px; color:white; background:#30363d; border-radius:10px;")
        side.addWidget(self.status)

        self.lbl = QtWidgets.QLabel("label: -"); self.lbl.setAlignment(QtCore.Qt.AlignCenter)
        self.lbl.setStyleSheet(f"font-size:15px; font-weight:700; padding:8px; color:{TEXT}; background:{PANEL}; border-radius:8px;")
        side.addWidget(self.lbl)

        box = QtWidgets.QFrame(); box.setStyleSheet(f"background:{PANEL}; border-radius:10px;")
        bl = QtWidgets.QVBoxLayout(box); bl.setContentsMargins(16, 14, 16, 14)
        h = QtWidgets.QLabel("MEASURED FEATURES"); h.setStyleSheet(f"color:{MUTED}; font-size:11px; font-weight:700; letter-spacing:1px;")
        bl.addWidget(h)
        self.info = QtWidgets.QLabel(); self.info.setAlignment(QtCore.Qt.AlignTop)
        self.info.setStyleSheet("font-family:Consolas,monospace; font-size:14px;")
        bl.addWidget(self.info); side.addWidget(box, 1)

        self.counter = QtWidgets.QLabel(); self.counter.setStyleSheet(f"color:{MUTED}; font-size:12px; padding:4px;")
        side.addWidget(self.counter)
        note = QtWidgets.QLabel("Label = which transmitter(s) were ON (tx1 / tx1_tx2).\n"
                                "Deciding if it is jamming is Module 2.")
        note.setStyleSheet(f"color:{MUTED}; font-size:11px; padding:2px;"); note.setWordWrap(True); side.addWidget(note)

    def _open_logs(self):
        self.cols = ["signal_id", "timestamp", "elapsed_s", "peak_freq_mhz", "peak_db",
                     "noise_db", "snr_db", "band_power_dbfs", "occupied_bw_khz",
                     "spectral_flatness", "interference", "channel", "signal_present",
                     "power_anomaly", "phase", "label"]
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.ds_name = f"dataset_{stamp}.csv"
        self.csv_f = open(self.ds_name, "w", newline="")
        self.csv_w = csv.DictWriter(self.csv_f, fieldnames=self.cols); self.csv_w.writeheader()
        print("Saving dataset to:", self.ds_name)

    def update(self):
        x = self.reader.latest
        if x is None: return
        m = len(x) // FFT
        seg = x[:m * FFT].reshape(m, FFT) * self.win
        S = np.mean(np.abs(np.fft.fftshift(np.fft.fft(seg, axis=1), axes=1)) ** 2, axis=0)
        S /= (np.sum(self.win ** 2) * SAMPLE_RATE); psd_db = 10 * np.log10(S + 1e-12)
        mid = FFT // 2; g = int(DC_GUARD / self.binhz)
        search = psd_db.copy(); search[mid - g: mid + g + 1] = -300
        noise_db = float(np.percentile(psd_db, 30)); pk = int(np.argmax(search))
        peak_db = float(search[pk]); peak_freq = float(self.freqs[pk]); snr = peak_db - noise_db
        band_power = float(10 * np.log10(np.mean(np.abs(x) ** 2) + 1e-12))
        occ_bw = float(np.sum(search > (noise_db + OCC_THRESH_DB)) * self.binhz)
        lin = S + 1e-12; flat = float(np.exp(np.mean(np.log(lin))) / np.mean(lin))
        present = snr > SNR_PRESENT_DB
        strong = np.where(search > (noise_db + DUP_PEAK_DB))[0]
        inter = int(len(np.where(np.diff(strong) > int(40000 / self.binhz))[0]) + 1) if len(strong) else 0
        anomaly = False
        if present:
            if len(self.baseline) >= 20 and band_power - np.median(self.baseline) > 15: anomaly = True
            self.baseline.append(band_power)
        channel = ("bad" if snr < 10 else "moderate" if snr < 25 else "good") if present else "idle"

        phase = self.ard.phase
        label = phase_to_label(phase, present)

        self.curve.setData(self.freqs, psd_db); self.noise_line.setValue(noise_db)
        self.peak_dot.setData([peak_freq], [peak_db]) if present else self.peak_dot.setData([], [])
        self.wf = np.roll(self.wf, 1, axis=0); self.wf[0] = psd_db
        lo, hi = noise_db, max(noise_db + 5, peak_db)
        self.img.setImage(np.clip((self.wf.T - lo) / (hi - lo), 0, 1), autoLevels=False, levels=(0, 1))
        now = time.time() - self.t0
        self.t_hist.append(now); self.pw_hist.append(band_power); self.snr_hist.append(snr if present else 0.0)
        self.tr_pw.setData(list(self.t_hist), list(self.pw_hist)); self.tr_snr.setData(list(self.t_hist), list(self.snr_hist))

        if present:
            self.status.setText("SIGNAL  PRESENT")
            self.status.setStyleSheet(f"font-size:22px; font-weight:700; padding:14px; color:white; background:{ACCENT}; border-radius:10px;")
        else:
            self.status.setText("NO  SIGNAL")
            self.status.setStyleSheet("font-size:22px; font-weight:700; padding:14px; color:white; background:#30363d; border-radius:10px;")
        lbl_col = {"tx1_tx2": RED, "tx1": GREEN, "none": MUTED}.get(label, AMBER)
        self.lbl.setText(f"phase: {phase}    |    label: {label}")
        self.lbl.setStyleSheet(f"font-size:14px; font-weight:700; padding:8px; color:white; background:{lbl_col}; border-radius:8px;")

        def row(k, v): return f"<span style='color:{MUTED}'>{k:<12}</span> {v}<br>"
        self.info.setText("<div style='font-family:Consolas,monospace; font-size:14px;'>" +
            row("Frequency", f"{peak_freq:.4f} MHz") + row("Strength", f"{band_power:.1f} dBFS") +
            row("Peak power", f"{peak_db:.1f} dB") + row("Noise floor", f"{noise_db:.1f} dB") +
            row("SNR", f"{snr:.1f} dB") + row("Bandwidth", f"{occ_bw/1e3:.1f} kHz") +
            row("Flatness", f"{flat:.2f}") + row("Interference", f"{inter}") +
            row("Channel", channel) + row("Signal", "YES" if present else "no") +
            row("Power anom.", "YES" if anomaly else "no") + "</div>")

        self.count += 1
        if label == "tx1": self.n_tx1 += 1
        elif label == "tx1_tx2": self.n_both += 1
        elif label == "none": self.n_none += 1
        self.counter.setText(f"Rows saved: {self.count}   "
                             f"(tx1 {self.n_tx1}, tx1_tx2 {self.n_both}, none {self.n_none})")

        rec = {"signal_id": f"S{self.count:05d}",
               "timestamp": datetime.datetime.now().isoformat(timespec="milliseconds"),
               "elapsed_s": round(now, 2), "peak_freq_mhz": round(peak_freq, 4),
               "peak_db": round(peak_db, 1), "noise_db": round(noise_db, 1), "snr_db": round(snr, 1),
               "band_power_dbfs": round(band_power, 1), "occupied_bw_khz": round(occ_bw / 1e3, 1),
               "spectral_flatness": round(flat, 3), "interference": inter, "channel": channel,
               "signal_present": int(present), "power_anomaly": int(anomaly),
               "phase": phase, "label": label}
        self.csv_w.writerow(rec); self.csv_f.flush()

    def closeEvent(self, e):
        self.timer.stop(); self.reader.stop(); self.ard.stop()
        try: self.sdr.close()
        except Exception: pass
        self.csv_f.close(); e.accept()


def main():
    try:
        sdr = RtlSdr()
    except Exception as e:
        sys.exit(f"Cannot open RTL-SDR ({e}). Close SDR++ and check the dongle is plugged in.")
    sdr.sample_rate = SAMPLE_RATE; sdr.center_freq = CENTER_FREQ
    try: sdr.gain = GAIN
    except Exception: sdr.gain = 'auto'
    ard = ArduinoReader(ARDUINO_PORT, ARDUINO_BAUD); ard.start()
    app = QtWidgets.QApplication(sys.argv)
    sdr_reader = SdrReader(sdr); sdr_reader.start()
    w = Dashboard(sdr, sdr_reader, ard); w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
