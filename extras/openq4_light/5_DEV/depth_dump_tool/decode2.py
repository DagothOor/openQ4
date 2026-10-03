"""Robust decoder: header if intact, else projection from fallback npz; sky = pixels without a valid code."""
import sys, numpy as np, importlib.util
from scipy.ndimage import binary_opening
spec = importlib.util.spec_from_file_location("dd", "decode_depth.py"); dd = importlib.util.module_from_spec(spec); spec.loader.exec_module(dd)
src, out, fallback = sys.argv[1], sys.argv[2], sys.argv[3]
img = dd.load(src)
codes = dd.decode18(img.astype(float))
cells = [np.median(codes[10:14, 8 * k + 2:8 * k + 6]) for k in range(5)]
if int(cells[2]) == dd.MAGIC:
    P = dict(P0=16384 / cells[0], P5=16384 / cells[1], P8=cells[3] / 65536 - 1, P9=cells[4] / 65536 - 1); how = "header"
else:
    h = np.load(fallback); P = {k: float(h[k]) for k in ("P0", "P5", "P8", "P9")}; how = "fallback"
valid = np.all(img % 4 == 2, axis=-1)
sky = ~valid | (codes >= 262143)
sky = sky | ~binary_opening(~sky, iterations=1)
fg = (codes == 0) & valid
depth = codes / 64.0
depth[:16, :256] = depth[16:17, :256]; sky[:16, :256] = sky[16:17, :256]; fg[:16, :256] = fg[16:17, :256]
np.savez_compressed(out, depth=depth.astype(np.float32), sky=sky, fg=fg, **P)
v = ~(sky | fg)
print(f"{src}: proj from {how}, P0={P['P0']:.3f}, depth {np.percentile(depth[v],1):.0f}..{np.percentile(depth[v],99):.0f}, sky {sky.mean():.0%}, weapon {fg.mean():.0%}")
