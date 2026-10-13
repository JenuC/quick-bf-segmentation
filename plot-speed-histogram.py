"""Histogram of TrackMate track speeds, converted from pixels/frame to µm/min.

TrackMate on an uncalibrated image exports speed in pixels/frame (the unit
row reads "( /frame)"). This converts with the pixel size and frame interval,
saves a histogram PNG and a CSV with the converted speeds next to the input.

Defaults are for justcells2d_brightfield_1 (0.653 µm/pixel, 180 s/frame,
from parse-metadata.py).

Usage: uv run plot-speed-histogram.py <trackmate.csv> [--um-per-px 0.653] [--s-per-frame 180]
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

args = sys.argv[1:]


def opt(name, default):
    return float(args[args.index(name) + 1]) if name in args else default


option_values = {args[args.index(o) + 1] for o in ("--um-per-px", "--s-per-frame") if o in args}
path = Path(next(a for a in args if not a.startswith("--") and a not in option_values))
um_per_px = opt("--um-per-px", 0.653)
s_per_frame = opt("--s-per-frame", 180)

# TrackMate CSVs have 3 header rows: feature keys, names, units
df = pd.read_csv(path, skiprows=[1, 2])
col = next(c for c in df.columns if "speed" in c.lower())
px_per_frame = df[col].astype(float)
um_per_min = px_per_frame * um_per_px / (s_per_frame / 60)
df["speed_um_per_min"] = um_per_min
df["speed_um_per_h"] = um_per_min * 60

out_csv = path.with_name(path.stem + "_um_per_min.csv")
df.to_csv(out_csv, index=False)

median = np.median(um_per_min)
fig, ax = plt.subplots(figsize=(6, 4))
ax.hist(um_per_min, bins=30, color="#2a78d6", edgecolor="#fcfcfb", linewidth=1)
ax.axvline(median, color="#52514e", linestyle="--", linewidth=1)
ax.text(median, ax.get_ylim()[1] * 0.95, f"  median {median:.2f} µm/min",
        color="#0b0b0b", va="top", fontsize=9)
ax.set_xlabel(f"{col} (µm/min)")
ax.set_ylabel("Tracks")
ax.set_title(f"{col} per track (n = {len(um_per_min)})", loc="left", fontsize=11)
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#e5e4df", linewidth=0.6)
ax.set_axisbelow(True)
fig.text(0.99, 0.01, f"{um_per_px} µm/px, {s_per_frame:g} s/frame",
         ha="right", va="bottom", fontsize=7, color="#52514e")
fig.tight_layout()
out_png = path.with_name(path.stem + "_histogram.png")
fig.savefig(out_png, dpi=150)

print(f"{len(um_per_min)} tracks, column '{col}'")
print(f"px/frame : median {np.median(px_per_frame):.2f}, range {px_per_frame.min():.2f}-{px_per_frame.max():.2f}")
print(f"um/min   : median {median:.2f}, mean {um_per_min.mean():.2f}, range {um_per_min.min():.2f}-{um_per_min.max():.2f}")
print(f"um/h     : median {median * 60:.1f}")
print(f"saved {out_png}\nsaved {out_csv}")
