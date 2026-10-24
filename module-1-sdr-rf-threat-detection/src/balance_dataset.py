# Makes a balanced copy of a dataset so every label has the same number of rows.
#   py balance_dataset.py dataset_xxx.csv        (even split)
#   py balance_dataset.py dataset_xxx.csv 40      (40 rows per label)
# Writes balanced.csv.

import sys, csv, collections, random

src = sys.argv[1] if len(sys.argv) > 1 else "dataset.csv"
force = int(sys.argv[2]) if len(sys.argv) > 2 else None
random.seed(42)

keep = {"tx1", "tx1_tx2", "none", "normal", "jamming"}
rows = [r for r in csv.DictReader(open(src)) if r.get("label") in keep]
if not rows:
    sys.exit("No usable labels found in " + src)
cols = list(rows[0].keys())

by = collections.defaultdict(list)
for r in rows:
    by[r["label"]].append(r)
print("Available per label:", {k: len(v) for k, v in by.items()})

n = force if force else min(len(v) for v in by.values())
out = []
for lab, group in by.items():
    out += group if len(group) <= n else random.sample(group, n)
random.shuffle(out)
for i, r in enumerate(out, 1):
    r["signal_id"] = f"S{i:03d}"

with open("balanced.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(out)
print("Wrote balanced.csv:", len(out), dict(collections.Counter(r["label"] for r in out)))
