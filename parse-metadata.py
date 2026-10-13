"""Report the planned vs actual time interval of Micro-Manager acquisitions.

Reads the *_metadata.txt JSON written next to each MMStack .ome.tif:
  - Summary: planned interval (Interval_ms), planned frames, start time
  - FrameKey-<t>-<c>-<z>: per-frame ElapsedTime-ms and pixel size

Usage:
  uv run parse-metadata.py <metadata.txt | folder> [...] [--csv]

A folder is searched for *_metadata.txt. --csv also writes
<metadata>_times.csv with the elapsed time of every frame.
"""

import json
import sys
from pathlib import Path

import numpy as np


def frame_times(meta):
    """Elapsed time (s) of each time point, using the first channel/z-slice."""
    times = {}
    for key, entry in meta.items():
        if not key.startswith("FrameKey-"):
            continue
        t, c, z = (int(i) for i in key.split("-")[1:4])
        if c == 0 and z == 0:
            times[t] = entry["ElapsedTime-ms"] / 1000
    t_index = np.array(sorted(times))
    return t_index, np.array([times[t] for t in t_index])


def first_frame(meta):
    return next(v for k, v in meta.items() if k.startswith("FrameKey-"))


def report(path, write_csv):
    meta = json.loads(path.read_text(encoding="utf-8"))
    summary = meta["Summary"]
    t_index, elapsed = frame_times(meta)
    planned_s = summary["Interval_ms"] / 1000 if "Interval_ms" in summary else None
    custom = summary.get("CustomIntervals_ms") or []
    planned_frames = summary.get("IntendedDimensions", {}).get("time", summary.get("Frames"))

    print(f"== {path}")
    print(f"start time        : {summary.get('StartTime', '?')}")
    print(f"pixel size        : {first_frame(meta).get('PixelSizeUm', '?')} um")
    if planned_s is None:
        print("planned interval  : not set (single snapshot?)")
    else:
        print(f"planned interval  : {planned_s:g} s ({planned_s / 60:g} min)")
    if custom:
        print(f"custom intervals  : {[c / 1000 for c in custom]} s")
    print(f"frames            : {len(t_index)} acquired of {planned_frames or '?'} planned")

    if len(elapsed) < 2:
        print("not enough frames to measure an interval\n")
        return
    dt = np.diff(elapsed)
    print(
        f"actual interval   : median {np.median(dt):.2f} s, mean {dt.mean():.2f} s, "
        f"min {dt.min():.2f} s, max {dt.max():.2f} s, sd {dt.std():.2f} s"
    )
    print(f"total duration    : {elapsed[-1] - elapsed[0]:.0f} s ({(elapsed[-1] - elapsed[0]) / 3600:.2f} h)")

    # Gaps more than 10% off the median, e.g. a pause or a dropped frame
    odd = np.flatnonzero(np.abs(dt - np.median(dt)) > 0.1 * np.median(dt))
    missing = sorted(set(range(t_index[0], t_index[-1] + 1)) - set(t_index))
    if missing:
        print(f"missing frames    : {missing}")
    if len(odd):
        for i in odd:
            print(f"irregular gap     : frame {t_index[i]} -> {t_index[i + 1]}: {dt[i]:.1f} s")
    else:
        print("irregular gaps    : none (all within 10% of the median)")

    if write_csv:
        out = path.with_name(path.stem + "_times.csv")
        rows = np.column_stack([t_index, elapsed, np.r_[np.nan, dt]])
        np.savetxt(out, rows, delimiter=",", fmt=["%d", "%.3f", "%.3f"],
                   header="frame,elapsed_s,interval_s", comments="")
        print(f"saved             : {out}")
    print()


args = sys.argv[1:]
paths = []
for a in (a for a in args if not a.startswith("--")):
    p = Path(a)
    paths += sorted(p.rglob("*_metadata.txt")) if p.is_dir() else [p]
if not paths:
    sys.exit(__doc__)
for p in paths:
    report(p, "--csv" in args)
