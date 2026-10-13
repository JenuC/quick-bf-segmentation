"""Segment cells in a brightfield image with StarDist (CPU).

StarDist's pretrained models are trained on nuclei, not whole brightfield
cells, and assume star-convex (roundish) shapes. Treat this as a comparison.

Usage: uv run segment-stardist.py [image.tif] [--show]
"""

import sys
from pathlib import Path

import numpy as np
import tifffile as tf
import matplotlib.pyplot as plt
from csbdeep.utils import normalize
from stardist.models import StarDist2D
from skimage import filters, segmentation

args = sys.argv[1:]
path = next((a for a in args if not a.startswith("--")), "snap.tif")

img = tf.imread(path).squeeze().astype(np.float32)

# Cells and background have similar brightness in brightfield, so feed StarDist
# a contrast map (absolute deviation from local background) instead: cells
# become bright objects on a dark background, like fluorescent nuclei.
smooth = filters.gaussian(img, sigma=1.5)
contrast = np.abs(smooth - filters.gaussian(smooth, sigma=50))
contrast = filters.gaussian(contrast, sigma=3)

# from_pretrained() needs symlink rights on Windows; on failure, load the
# already-extracted model folder directly.
try:
    model = StarDist2D.from_pretrained("2D_versatile_fluo")
except OSError:
    model_dir = Path.home() / ".keras/models/StarDist2D/2D_versatile_fluo"
    model = StarDist2D(None, name="2D_versatile_fluo_extracted", basedir=str(model_dir))
labels, _ = model.predict_instances(normalize(contrast, 1, 99.8))
print(f"{labels.max()} objects found")

stem = path.rsplit(".", 1)[0]
tf.imwrite(stem + "_stardist_labels.tif", labels.astype(np.uint16))

fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].imshow(img, cmap="gray"); ax[0].set_title("input")
ax[1].imshow(contrast, cmap="magma"); ax[1].set_title("stardist input (contrast)")
ax[2].imshow(segmentation.mark_boundaries(img / img.max(), labels, color=(0, 1, 0)))
ax[2].set_title(f"stardist: {labels.max()} objects")
for a in ax:
    a.axis("off")
plt.tight_layout()
plt.savefig(stem + "_stardist_seg.png", dpi=100)
if "--show" in args:
    plt.show()
