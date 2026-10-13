"""Segment cells in a brightfield image with Cellpose (CPU).

Usage: uv run segment-cellpose.py [image.tif] [--diameter D] [--show]
"""

import sys

import numpy as np
import tifffile as tf
import matplotlib.pyplot as plt
from cellpose import models
from skimage import segmentation

args = sys.argv[1:]
path = next((a for a in args if not a.startswith("--")), "snap.tif")
diameter = float(args[args.index("--diameter") + 1]) if "--diameter" in args else None

img = tf.imread(path).squeeze()

# Cellpose 4 default model (cpsam) handles brightfield and fluorescence
model = models.CellposeModel(gpu=False)
labels, flows, _ = model.eval(img, diameter=diameter)
print(f"{labels.max()} cells found")

stem = path.rsplit(".", 1)[0]
tf.imwrite(stem + "_cellpose_labels.tif", labels.astype(np.uint16))

fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].imshow(img, cmap="gray"); ax[0].set_title("input")
ax[1].imshow(flows[0]); ax[1].set_title("cellpose flows")
ax[2].imshow(segmentation.mark_boundaries(img, labels, color=(0, 1, 0)))
ax[2].set_title(f"cellpose: {labels.max()} cells")
for a in ax:
    a.axis("off")
plt.tight_layout()
plt.savefig(stem + "_cellpose_seg.png", dpi=100)
if "--show" in args:
    plt.show()
