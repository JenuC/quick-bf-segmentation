"""Downscale every frame of a timelapse TIFF stack, then segment it with micro-sam (CPU).

Each frame is shrunk to --size x --size (default 512) by averaging pixel blocks,
which also reduces noise, and segmented whole (no tiling). Much faster than
segmenting full resolution in tiles, at the cost of detail on thin cell ends.

Each frame is saved as soon as it finishes (<stack>_microsam<size>_frames/t0000.tif),
so an interrupted run resumes where it stopped. When all frames are done they
are combined into <stack>_microsam<size>_labels.tif next to the input.

Usage: uv run segment-microsam-stack-resized.py <stack.tif> [--size 512] [--model vit_b_lm] [--frames 0:10]
"""

import sys
import time
from pathlib import Path

import numpy as np
import tifffile as tf
from micro_sam.automatic_segmentation import (
    get_predictor_and_segmenter,
    automatic_instance_segmentation,
)
from skimage.transform import downscale_local_mean

args = sys.argv[1:]


def opt(name, default):
    return args[args.index(name) + 1] if name in args else default


option_values = {opt(o, None) for o in ("--size", "--model", "--frames")}
path = Path(next(a for a in args if not a.startswith("--") and a not in option_values))
size = int(opt("--size", 512))
model_type = opt("--model", "vit_b_lm")

with tf.TiffFile(path) as fid:
    series = fid.series[0]
    n_frames = len(series.pages)
    height, width = series.shape[-2:]
if height % size or width % size:
    sys.exit(f"--size {size} must divide the frame size {height}x{width}")
factor = (height // size, width // size)

frames = range(n_frames)
if "--frames" in args:
    start, stop = opt("--frames", ":").split(":")
    frames = range(int(start or 0), min(int(stop or n_frames), n_frames))

stem = path.name.removesuffix(".ome.tif").removesuffix(".tif")
frame_dir = path.parent / f"{stem}_microsam{size}_frames"
frame_dir.mkdir(exist_ok=True)


def to_uint8(img):
    # Percentile scaling so bright debris doesn't squash the cell contrast
    lo, hi = np.percentile(img, (0.5, 99.8))
    return (np.clip((img - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


predictor, segmenter = get_predictor_and_segmenter(model_type=model_type, device="cpu")

for t in frames:
    out = frame_dir / f"t{t:04d}.tif"
    if out.exists():
        continue
    t0 = time.time()
    img = downscale_local_mean(tf.imread(path, key=t).astype(np.float32), factor)
    labels = automatic_instance_segmentation(
        predictor=predictor,
        segmenter=segmenter,
        input_path=to_uint8(img),
        ndim=2,
        verbose=False,
    )
    tf.imwrite(out, labels.astype(np.uint16), compression="zlib")
    n = len(np.unique(labels)) - (0 in labels)
    print(f"frame {t + 1}/{n_frames}: {n} cells, {time.time() - t0:.0f}s", flush=True)

done = sorted(frame_dir.glob("t*.tif"))
if len(done) == n_frames:
    stack = np.stack([tf.imread(f) for f in done])
    out = path.parent / f"{stem}_microsam{size}_labels.tif"
    tf.imwrite(out, stack, imagej=True, metadata={"axes": "TYX"}, compression="zlib")
    print(f"saved {out}")
else:
    print(f"{len(done)}/{n_frames} frames done; rerun to continue")
