"""Segment cells in a brightfield image with micro-sam (CPU).

Uses the light-microscopy generalist model (vit_b_lm) with automatic instance
segmentation (AIS). Try --model vit_l_lm for a larger, slower model.

Usage: uv run segment-microsam.py [image.tif] [--model vit_b_lm] [--show]
"""

import sys

import numpy as np
import tifffile as tf
import matplotlib.pyplot as plt
from micro_sam.automatic_segmentation import (
    get_predictor_and_segmenter,
    automatic_instance_segmentation,
)
from skimage import segmentation

args = sys.argv[1:]
path = next((a for a in args if not a.startswith("--")), "snap.tif")
model_type = args[args.index("--model") + 1] if "--model" in args else "vit_b_lm"

img = tf.imread(path).squeeze()

predictor, segmenter = get_predictor_and_segmenter(model_type=model_type, device="cpu")
labels = automatic_instance_segmentation(
    predictor=predictor, segmenter=segmenter, input_path=img, ndim=2
)
n = len(np.unique(labels)) - (0 in labels)
print(f"{n} cells found")

stem = path.rsplit(".", 1)[0]
tf.imwrite(stem + "_microsam_labels.tif", labels.astype(np.uint16))

fig, ax = plt.subplots(1, 2, figsize=(10, 5))
ax[0].imshow(img, cmap="gray"); ax[0].set_title("input")
ax[1].imshow(segmentation.mark_boundaries(img, labels, color=(0, 1, 0)))
ax[1].set_title(f"micro-sam ({model_type}): {n} cells")
for a in ax:
    a.axis("off")
plt.tight_layout()
plt.savefig(stem + "_microsam_seg.png", dpi=100)
if "--show" in args:
    plt.show()
