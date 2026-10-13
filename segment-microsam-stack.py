"""Segment every frame of a timelapse TIFF stack with micro-sam, in 256x256 tiles (CPU).

micro-sam's tiled mode runs the model on 256x256 tiles with an overlapping
halo and stitches cells that cross tile borders, so cells aren't cut at seams.

Each frame is saved as soon as it finishes (<stack>_microsam_frames/t0000.tif),
so an interrupted run resumes where it stopped. When all frames are done they
are combined into <stack>_microsam_labels.tif next to the input.

Usage: uv run segment-microsam-stack.py <stack.tif> [--model vit_b_lm] [--frames 0:10]
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

TILE = (256, 256)
HALO = (64, 64)

args = sys.argv[1:]
path = Path(next(a for a in args if not a.startswith("--")))
model_type = args[args.index("--model") + 1] if "--model" in args else "vit_b_lm"

with tf.TiffFile(path) as fid:
    n_frames = len(fid.series[0].pages)
frames = range(n_frames)
if "--frames" in args:
    start, stop = args[args.index("--frames") + 1].split(":")
    frames = range(int(start or 0), min(int(stop or n_frames), n_frames))

stem = path.name.removesuffix(".ome.tif").removesuffix(".tif")
frame_dir = path.parent / f"{stem}_microsam_frames"
frame_dir.mkdir(exist_ok=True)


def to_uint8(img):
    # Percentile scaling so bright debris doesn't squash the cell contrast
    lo, hi = np.percentile(img, (0.5, 99.8))
    return (np.clip((img - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)


predictor, segmenter = get_predictor_and_segmenter(
    model_type=model_type, device="cpu", is_tiled=True
)

for t in frames:
    out = frame_dir / f"t{t:04d}.tif"
    if out.exists():
        continue
    t0 = time.time()
    img = to_uint8(tf.imread(path, key=t).astype(np.float32))
    labels = automatic_instance_segmentation(
        predictor=predictor,
        segmenter=segmenter,
        input_path=img,
        ndim=2,
        tile_shape=TILE,
        halo=HALO,
        verbose=False,
    )
    tf.imwrite(out, labels.astype(np.uint16), compression="zlib")
    print(f"frame {t + 1}/{n_frames}: {labels.max()} cells, {time.time() - t0:.0f}s", flush=True)

done = sorted(frame_dir.glob("t*.tif"))
if len(done) == n_frames:
    stack = np.stack([tf.imread(f) for f in done])
    out = path.parent / f"{stem}_microsam_labels.tif"
    tf.imwrite(out, stack, imagej=True, metadata={"axes": "TYX"}, compression="zlib")
    print(f"saved {out}")
else:
    print(f"{len(done)}/{n_frames} frames done; rerun to continue")
