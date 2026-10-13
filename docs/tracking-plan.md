# Plan: linking micro-sam labels over time with TrackMate

Goal: turn the per-frame micro-sam label stack into cell tracks (positions, shapes and lineages over time) for `justcells2d_brightfield_1` Pos0, then reuse the same steps for other positions and acquisitions.

Status: planned, not started. It starts once the label stack from the 512-tile run exists (see [discussion.md](discussion.md)).

## Inputs

| Item | Value | Source |
|---|---|---|
| Label stack | `justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0_microsam_tile512_labels.tif` (75 × 2048 × 2048, uint16, TYX) | `segment-microsam-stack.py --tile 512` |
| Raw brightfield (for checking by eye) | `justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0.ome.tif` | Micro-Manager |
| Pixel size | 0.653 µm | `PixelSizeUm` in `..._metadata.txt` |
| Frame interval | 180 s (3 min) | `Interval_ms`; `ElapsedTime-ms` confirms ~180 s steps |
| Duration | 75 frames ≈ 3.7 h (planned 100, stopped at 75) | metadata |
| Software | Fiji at `C:\Fiji.app`, TrackMate 8.1.6 | already installed |

The label stack is written without calibration, so pixel size and frame interval must be set before tracking. Either set them in Fiji (Image > Properties) or have the tracking script set them.

## Approach

### 1. Detection: TrackMate *Label image detector*

- Each label in each frame becomes one TrackMate spot with its real outline, not a circle. TrackMate then computes shape features per spot: area, perimeter, circularity, solidity, ellipse axes and aspect ratio.
- Check that Fiji reads the stack as 75 time points, not 75 z-slices (Image > Properties: Slices = 1, Frames = 75). Fix it there if needed.
- Turn off "simplify contours" at first, to keep the thin spindle shapes.

### 2. Spot filtering (remove debris and detached cells)

- Remove very small objects (area threshold, e.g. < 50 µm², to be tuned).
- Optionally remove round, bright objects, which are likely detached or dead cells, with a circularity filter (e.g. circularity > 0.85 together with small area). Decide whether these should be tracked or excluded from the analysis.
- Tune the thresholds on the TrackMate feature histograms for frames 1–10.

### 3. Linking: compare two trackers on a subset (frames 1–20)

| Tracker | How it links | Pros | Cons |
|---|---|---|---|
| **LAP tracker** (start here) | Nearest centroid, with a maximum distance | Gap closing (cell missed in one frame) and **track splitting (cell division)** | Centroids of long spindle cells can jump when the shape changes |
| **Overlap tracker** | Outline overlap (IoU) between frames | Natural fit for segmentation outlines; robust to shape change | No gap closing; weaker if cells move far between frames |

Starting LAP parameters (to tune):
- Max linking distance: ~15 µm (~23 px). Fibroblast-like cells move roughly 0.5–1 µm/min, i.e. 1.5–3 µm per 3-min frame, so 15 µm leaves room for centroid jumps.
- Gap closing: max distance ~20 µm, max frame gap 2. This covers a cell missed in one frame.
- Track splitting: on, max distance ~15 µm, to capture divisions over 3.7 h.
- Track merging: off. Cells merging is usually a segmentation error, not biology.
- Feature penalties: add area (e.g. weight 1.0) so a link prefers a cell of similar size.

### 4. Track filtering

- Drop short tracks (e.g. < 5 frames = 15 min) for motility analysis. Keep them for counting.
- Optionally drop tracks that touch the image edge.

### 5. Checking by eye (before trusting numbers)

- Overlay tracks on the raw brightfield in the TrackMate GUI for frames 1–20 and scroll through.
- Use TrackScheme to look at divisions and broken tracks.
- Pick ~20 random tracks and verify them by eye. Note how often errors come from segmentation (a cell split or merged in one frame) versus linking.
- If segmentation flicker between frames is the main problem, consider fixing it before linking (see risks).

### 6. Batch run (headless)

Once parameters are settled in the GUI:
- Save the TrackMate settings, or write a Jython script with the same settings (`scripts/trackmate_labels.py`).
- Run it with Fiji headless, so no GUI is needed and it works for many positions:
  ```
  C:\Fiji.app\fiji-windows-x64.exe --headless --console --run scripts/trackmate_labels.py "labels='...', raw='...'"
  ```
- Outputs next to the input data:
  - `..._tracks.xml`: the full TrackMate model, which reopens in the GUI for checking.
  - `..._spots.csv`, `..._edges.csv`, `..._tracks.csv`: features per spot, link and track.
  - Optionally a label image coloured by track ID (each cell keeps one label through time).

### 7. Analysis (Python, in this uv project)

From the CSV exports:
- Cell counts over time (per frame), division events and timing.
- Speed, persistence and mean squared displacement (MSD) per track.
- Shape over time (area, aspect ratio) per cell.
- Plots and summary tables per position.

## Risks and fallbacks

- **Segmentation changes between frames.** A cell can be one object in one frame and two in the next, which breaks tracks or creates false divisions. Mitigations: gap closing; an area penalty in linking; filtering short tracks. If still bad, segment with a fixed micro-sam setting and accept, or try a tracking-aware method.
- **Dense clusters.** Touching cells are where both segmentation and linking fail most. Check those regions in particular.
- **Calibration.** Without the right pixel size and frame interval, TrackMate distances and speeds are wrong. Always set 0.653 µm and 180 s.
- **Large data.** 75 × 2048² with ~700–800 cells per frame means about 55,000 spots. TrackMate handles this, but the GUI can be slow. Do parameter tuning on a cropped region or on frames 1–20.
- **Python alternative** if TrackMate doesn't fit: `trackastra` is already installed as a micro-sam dependency and links label stacks directly in Python. Keep it as a comparison or fallback.

## Steps

1. Wait for the 512-tile label stack (running; ~6 h on CPU).
2. Open labels and raw data in Fiji. Set calibration. Check it reads as T = 75.
3. Run TrackMate in the GUI on frames 1–20: Label image detector, filter spots, LAP tracker. Compare with the Overlap tracker.
4. Check by eye; tune parameters; record final parameters in this file.
5. Write `scripts/trackmate_labels.py` (Jython) and run it headless on the full stack.
6. Write Python analysis of the CSV exports.
7. Extend to other positions and acquisitions.
