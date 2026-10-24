import duckdb
from pathlib import Path

con = duckdb.connect()
f_floor = "data/external/archive/rf_jamming/active_scan/benign/floor/5ghz_activescan_floor_1.csv"
f_mal = "data/external/archive/rf_jamming/active_scan/malicious/gaussian_noise/0dbm/5805mhz_jamming_0dbm_gaussiannoise_1.csv"

print("Floor freq1 values:")
for row in con.execute(f"SELECT freq1, count(*) FROM read_csv_auto('{f_floor}') GROUP BY freq1 ORDER BY freq1").fetchall():
    print(" ", row)

print("\nMalicious freq1 values:")
for row in con.execute(f"SELECT freq1, count(*) FROM read_csv_auto('{f_mal}') GROUP BY freq1 ORDER BY freq1").fetchall():
    print(" ", row)
