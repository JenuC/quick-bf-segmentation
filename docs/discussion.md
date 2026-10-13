# Brightfield cell segmentation: methods tried and current pipeline

Dataset: `20261012_flucolandcells` (Micro-Manager acquisitions, adherent spindle-shaped cells, brightfield).
Machine used for development: Windows 11, CPU only (no GPU).

## Summary

- Four approaches were compared on a test image (`snap.tif`): a classical texture filter, Cellpose, StarDist and micro-sam.
- **micro-sam (`vit_b_lm`) gave the best results** and was chosen for the timelapse, with Cellpose a close second.
- The timelapse `justcells2d_brightfield_1/..._Pos0.ome.tif` (75 frames, 2048×2048, uint16) is segmented at full resolution in **512×512 tiles** with micro-sam: about **4.8 min per frame (~6 h for the stack)** on this CPU. The full run is in progress (frames 1–3 done, 700–735 cells per frame).
- Shrinking the frames to 512×512 or 1024×1024 before segmenting was tried and rejected: it misses most cells.
- A GPU version of the script exists for faster processing on another machine.
- Acquisition timing was checked from the Micro-Manager metadata with `parse-metadata.py`: the brightfield timelapse was imaged every **180 s (3 min)**, with no missing frames or irregular gaps.
- Next step: link cells over time with TrackMate; see [tracking-plan.md](tracking-plan.md).

## Data

| File | Contents |
|---|---|
| `snap.tif` | 513×513 uint8 brightfield test image |
| `justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0.ome.tif` | Timelapse, 75 frames × 2048×2048 uint16 (TYX), 0.653 µm/pixel, one frame every 180 s (~3.7 h). The acquisition was planned for 100 frames but stopped at 75; tifffile warns about the missing files. |
| `justcells2d_1/`, `justcells2d_2/` | Timelapses, 3 positions each, every 300 s, 0.6938 µm/pixel. Not segmented yet. |
| `pollen1012/` | Single image, 1.0394 µm/pixel. Not segmented yet. |

### Acquisition timing (`parse-metadata.py`)

`parse-metadata.py` reads the Micro-Manager `*_metadata.txt` JSON next to each `.ome.tif`. It reports the planned interval (`Summary` → `Interval_ms`) and the actual one, from each frame's `ElapsedTime-ms`. It also flags missing frames and any gap more than 10% off the median.

```
uv run parse-metadata.py .                                   # every acquisition below a folder
uv run parse-metadata.py justcells2d_brightfield_1 --csv     # also write per-frame times
```

`--csv` writes `<metadata>_times.csv` (columns `frame,elapsed_s,interval_s`). One has been written for the brightfield timelapse: `justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0_metadata_times.csv`.

Results (all acquisitions on 2026-10-12):

| Acquisition | Start | Planned interval | Actual interval (median, range) | Frames | Duration | Pixel size |
|---|---|---|---|---|---|---|
| justcells2d_1 (Pos0–2) | 11:13 | 300 s | 300.0 s (299.9–300.15) | 10 of 45 | 0.75 h | 0.6938 µm |
| justcells2d_2 (Pos0–2) | 12:03 | 300 s | 300.0 s (299.9–300.3) | 4 of 45 | 0.25 h | 0.6938 µm |
| **justcells2d_brightfield_1 (Pos0)** | **12:40** | **180 s** | **180.00 s (179.88–180.11)** | **75 of 100** | **3.70 h** | **0.653 µm** |
| pollen1012 (Pos0) | n/a | not set | single image | 1 | n/a | 1.0394 µm |

- Timing is very regular. No acquisition has missing frames or irregular gaps.
- All timelapses stopped before their planned number of frames.
- The `justcells2d` acquisitions have a different pixel size (0.6938 µm, probably a different objective or binning) from the brightfield timelapse (0.653 µm). Tracking distances in µm carry over, but pixel-based settings do not.

In the timelapse, cells are about the same size in pixels as in `snap.tif`, so settings tuned on the test image carry over. Some bright debris pushes the maximum intensity to ~1134 against a much lower background, so each frame is scaled to 8-bit by percentiles (0.5–99.8%) before segmentation.

## Methods compared (on `snap.tif`)

Each script writes `<image>_<method>_labels.tif` (16-bit label image, one integer per object) and `<image>_<method>_seg.png` (outlines drawn on the image).

| Method | Script | Objects | Assessment |
|---|---|---|---|
| Texture filter (classical) | `segment.py` | 26 | Finds most cells, but touching cells merge into one object. Not good enough. |
| Cellpose 4 (`cpsam`) | `segment-cellpose.py` | 50 | Very good. Splits touching cells and finds faint, flat cells. Outlines slightly looser. |
| StarDist (`2D_versatile_fluo`) | `segment-stardist.py` | 56 | Weakest. The model was trained on nuclei, so it fits rounded blobs, cuts off thin cell ends and splits some cells. |
| **micro-sam (`vit_b_lm`, AIS)** | `segment-microsam.py` | 46 | **Best.** Tightest outlines and follows thin cell ends. Slightly weaker on the faintest flat cells. |

### Texture filter

Brightfield cells have about the same brightness as the background, so an intensity threshold does not work. The background is flat, though, while cells have edges and internal structure. The script smooths the image, removes uneven illumination, computes the local standard deviation in a 9-pixel window, thresholds it (triangle method; Otsu missed faint cells), then cleans up the mask and labels objects. It is fast and needs no model, but it cannot separate touching cells.

![Texture filter](../snap_seg.png)

### Cellpose

Uses the Cellpose 4 default model (`cpsam`) on CPU. The first run downloads a 1.15 GB model; including that, it took about 3.5 min. `--diameter` can be set if automatic size estimation is off.

![Cellpose](../snap_cellpose_seg.png)

### StarDist

StarDist only provides pretrained models for nuclei (fluorescence or H&E) and assumes star-convex shapes, which doesn't suit spindle cells. As a workaround, the script feeds it a smoothed contrast map (absolute deviation from local background) so cells look like bright objects on a dark background.

On Windows, `StarDist2D.from_pretrained()` fails with `WinError 1314` because unpacking the model needs symlink permissions. The script falls back to loading the already-extracted folder in `~/.keras/models/StarDist2D/2D_versatile_fluo/`.

Not recommended for this data. StarDist also pulls in TensorFlow, which makes the environment much larger; it could be removed.

![StarDist](../snap_stardist_seg.png)

### micro-sam

[micro-sam](https://github.com/computational-cell-analytics/micro-sam) (Segment Anything fine-tuned for microscopy). Uses the light-microscopy generalist model `vit_b_lm` with automatic instance segmentation (AIS). The first run took about 6 min including model download. `--model vit_l_lm` is a larger, slower alternative.

![micro-sam](../snap_microsam_seg.png)

## Timelapse pipeline (micro-sam)

### CPU: `segment-microsam-stack.py`

```
uv run segment-microsam-stack.py justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0.ome.tif --tile 512
```

- Uses micro-sam's tiled mode on the full-resolution frame: `--tile` × `--tile` tiles (default 512) with a 64-pixel overlapping halo. Cells crossing tile borders are stitched, and no seams were visible in the test frames.
- Each frame is saved as soon as it finishes, to `justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0_microsam_tile512_frames/t0000.tif`, `t0001.tif`, ... (the folder name includes the tile size, so runs with different settings don't mix).
- Rerunning skips frames that already exist, so an interrupted run resumes. `--frames 10:20` processes only a range.
- When all 75 frames exist, they are combined into `justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0_microsam_tile512_labels.tif` (16-bit label stack, TYX, opens in Fiji). The label stack has no pixel-size or time calibration; set 0.653 µm and 180 s in Fiji.
- Progress is logged to `justcells2d_brightfield_1/microsam_tile512.log`.

### Choosing tile size and resolution (frame 1)

micro-sam enlarges every input (each tile, or the whole image) to 1024 pixels before running the model. It worked well when cells ended up at about 2× their original size, and poorly when they ended up smaller. So the cost depends on the number of tiles, and shrinking the image throws away the detail the model needs.

| Setting | Cells found | Time per frame | Effective scale in the model | Verdict |
|---|---|---|---|---|
| Full res, 256 tiles | 827 | 1011 s (~17 min) | ~2.7× | Best, but ~21 h for the stack |
| **Full res, 512 tiles** | **735** | **288 s (~4.8 min)**; 273–286 s on frames 2–3 | ~1.6× | **Chosen.** Outlines close to 256 tiles; ~6 h for the stack |
| Frame resized to 1024×1024, no tiles | 200 | 19 s | 0.5× | Rejected: misses most cells |
| Frame resized to 512×512, no tiles | 145 | 21 s | 0.5× | Rejected: misses most cells, merges neighbours into blobs |

The resize experiment is kept as `segment-microsam-stack-resized.py` (`--size`), but it is not recommended for this data. Frame 1 from the 256-tile test is kept in `..._microsam_tile256_frames/` for comparison.

Another possible speed-up, not tested: `--model vit_t_lm` is several times faster with slightly rougher outlines.

### GPU: `segment-microsam-stack-gpu.py`

Same output and resume behaviour as the CPU script, but runs on an NVIDIA GPU via CUDA and sends several tiles through the model at once.

On the GPU machine:

```
uv sync --extra gpu
uv run --extra gpu segment-microsam-stack-gpu.py justcells2d_brightfield_1/justcells2d_brightfield_1_MMStack_Pos0.ome.tif
```

- Always include `--extra gpu` with `uv run`; without it uv switches torch back to the CPU build.
- Options: `--tile 512` (halo is a quarter of the tile), `--batch 8` (lower if the GPU runs out of memory), `--model`, `--frames`.
- Prints the GPU name on start. If no CUDA GPU is visible, it stops with a message instead of running on CPU.
- Writes to the same `_microsam_tile<N>_frames` folder as the CPU script, so frames finished on either machine (with the same tile size) are skipped.
- **Not tested on a GPU yet** (the development machine has none). Run `--frames 1:2` first to measure time per frame.

## Environment (uv)

Everything is managed with uv in this folder: `pyproject.toml` lists the direct dependencies, and `uv.lock` pins the exact version of every package.

- To recreate the environment on another machine, copy `pyproject.toml`, `uv.lock` and `.python-version`, then run `uv sync` (CPU) or `uv sync --extra gpu` (NVIDIA GPU).
- Python 3.13.
- micro-sam is installed from GitHub (it is mainly distributed through conda), pinned to release `v1.8.14`. To upgrade, change `rev` under `[tool.uv.sources]` and run `uv lock`.
- PyTorch 2.14.1:
  - Default: CPU build from PyPI.
  - `gpu` option: CUDA 12.6 build (`torch 2.14.1+cu126`, `torchvision 0.29.1+cu126`) from `https://download.pytorch.org/whl/cu126`. It needs an NVIDIA driver that supports CUDA 12.6 or higher (check with `nvidia-smi`).
- Other main packages: cellpose 4.2.1, stardist 0.9.2 + tensorflow 2.21, scikit-image 0.26, tifffile.

Model weights are downloaded on first use and cached outside the project:

| Tool | Cache location |
|---|---|
| Cellpose | `~/.cellpose/models` (1.15 GB) |
| StarDist | `~/.keras/models/StarDist2D` |
| micro-sam | `%LOCALAPPDATA%\micro_sam\micro_sam\Cache\models` |

## Open decisions and next steps

1. Finish the 512-tile run on CPU (~6 h) and check the label stack in Fiji.
2. Link cells over time with TrackMate (Fiji at `C:\Fiji.app`, TrackMate 8.1.6), using 0.653 µm/pixel and 180 s/frame: see [tracking-plan.md](tracking-plan.md).
3. Check micro-sam output on a few more frames and positions, including the other acquisitions (`justcells2d_1`, `justcells2d_2`, `pollen1012`).
4. Optionally filter round, bright objects (likely detached or dead cells) by shape if they should not be counted.
5. If segmentation needs improving, correct results in micro-sam's napari annotator, or fine-tune Cellpose or micro-sam on a few hand-corrected frames.
6. Consider removing StarDist and TensorFlow from the environment.
7. `trackastra` (installed as a micro-sam dependency) is a Python alternative to TrackMate for linking.
