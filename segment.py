"""Segment cells in a brightfield image on CPU.

Brightfield cells are about as bright as the background, so we segment on
local texture (standard deviation) rather than intensity.
"""

import sys

import numpy as np
import tifffile as tf
import matplotlib.pyplot as plt
from scipy import ndimage as ndi
from skimage import filters, morphology, measure, segmentation, color, exposure

path = sys.argv[1] if len(sys.argv) > 1 else "snap.tif"
img = tf.imread(path).squeeze().astype(np.float32)
img = exposure.rescale_intensity(img, out_range=(0, 1))

# 1. Denoise, then flatten uneven illumination
smooth = filters.gaussian(img, sigma=1.5)
flat = smooth - filters.gaussian(smooth, sigma=50)

# 2. Texture map: local standard deviation (cells have edges, background is flat)
win = 9
mean = ndi.uniform_filter(flat, win)
sq_mean = ndi.uniform_filter(flat**2, win)
texture = np.sqrt(np.clip(sq_mean - mean**2, 0, None))

# 3. Threshold the texture map
# Triangle threshold sits lower than Otsu, so faint, flat cells are kept too
mask = texture > filters.threshold_triangle(texture)

# 4. Clean up: close gaps, fill holes, drop specks
mask = morphology.closing(mask, morphology.disk(3))
mask = ndi.binary_fill_holes(mask)
mask = morphology.opening(mask, morphology.disk(2))
mask = morphology.remove_small_objects(mask, max_size=150)
mask = segmentation.clear_border(mask) if "--no-border" in sys.argv else mask

# 5. Label individual objects
labels = measure.label(mask)
print(f"{labels.max()} objects found")

tf.imwrite(path.rsplit(".", 1)[0] + "_labels.tif", labels.astype(np.uint16))

fig, ax = plt.subplots(1, 3, figsize=(15, 5))
ax[0].imshow(img, cmap="gray"); ax[0].set_title("input")
ax[1].imshow(texture, cmap="magma"); ax[1].set_title("texture (local std)")
ax[2].imshow(img, cmap="gray")
ax[2].contour(mask, levels=[0.5], colors="lime", linewidths=0.8)
ax[2].set_title(f"{labels.max()} objects")
for a in ax:
    a.axis("off")
plt.tight_layout()
plt.savefig(path.rsplit(".", 1)[0] + "_seg.png", dpi=100)
if "--show" in sys.argv:
    plt.show()
