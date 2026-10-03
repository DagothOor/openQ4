"""Occlusion captured vs radius, relative to a near-unlimited radius reference."""
import sys, json, numpy as np
from scipy.ndimage import gaussian_filter
i = int(sys.argv[1])
sys.argv = ["ao_real.py", f"half{i}.npz", f"sweep{i}"]
src = open("ao_real.py").read()
src = src[:src.index('if __name__ == "__main__":')]
src = src.replace("np.minimum(wr * projectionScale / np.maximum(viewDepth, 1), 256)", "np.minimum(wr * projectionScale / np.maximum(viewDepth, 1), PXCAP)")
PXCAP = 1e9   # reference: no pixel cap
exec(src)
v = ~(SKYB | FGB)
radii = [16, 32, 64, 128, 256]
ref = gtao(radius=1024, thickness=0.5, maxdist=1e9)
occ_ref = (1 - ref[v]).mean()
res = {"ref_occ": float(occ_ref), "rows": []}
for R in radii:
    for cap in (1e9,):          # 128 px at half res == 256 px at full res (shader cap)
        PXCAP = cap
        a = gtao(radius=R, thickness=0.5, maxdist=1e9)
        noise = float(np.std((a - gaussian_filter(a, 1.5))[v]))
        res["rows"].append(dict(R=R, cap=cap, frac=float((1 - a[v]).mean() / occ_ref), noise=noise))
    print(i, R, flush=True)
json.dump(res, open(f"sweepfix{i}.json", "w"))
