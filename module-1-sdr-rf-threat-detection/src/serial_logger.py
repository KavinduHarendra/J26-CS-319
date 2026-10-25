# Logs the Arduino's phase labels with a host timestamp into phases.csv.
# Use this only when recording with SDR++ separately; the dashboard reads the
# Arduino on its own and doesn't need it.
#   py serial_logger.py COM15

import csv, sys, time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"

with serial.Serial(PORT, 115200, timeout=1) as ser, open("phases.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["host_time", "arduino_ms", "label"])
    print("Logging... Ctrl+C to stop")
    try:
        while True:
            line = ser.readline().decode(errors="ignore").strip()
            if "," not in line:
                continue
            ms, label = line.split(",", 1)
            w.writerow([f"{time.time():.3f}", ms, label])
            f.flush()
            print(ms, label)
            if label == "DONE":
                break
    except KeyboardInterrupt:
        pass
