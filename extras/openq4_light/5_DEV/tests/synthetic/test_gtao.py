"""CPU port of the GTAO ssao.fs, run on a synthetic scene to check signs and ranges.

Scene (view space, camera at origin looking down -z, Quake units):
  floor at y = -48, back wall at z = -400, left wall at x = -150,
  a box sitting on the floor in front of the back wall.
Expected: open floor / walls ~1.0, darkening only along the floor-wall seams,
the wall-wall corner and around the base of the box.
"""
import numpy as np
from PIL import Image

W, H = 320, 240
fov_y = np.radians(75)
near = 3.0
P5 = 1 / np.tan(fov_y / 2)
P0 = P5 * H / W
P8 = P9 = 0.0
P10 = -0.999  # idTech4 infinite far plane
P14 = -2 * near

radius, bias, intensity, power, maxdist, samples = 36.0, 2.0, 1.0, 1.0, 2000.0, 20.0
projectionScale = 0.5 * H * P5

# ---------- ray-trace depth ----------
ys, xs = np.mgrid[0:H, 0:W]
u = (xs + 0.5) / W
v = 1 - (ys + 0.5) / H          # GL: v=0 bottom
ndcx, ndcy = u * 2 - 1, v * 2 - 1
d = np.stack([ndcx / P0, ndcy / P5, -np.ones_like(ndcx)], -1)

t = np.full((H, W), np.inf)
def plane(axis, val, keep=lambda p: np.ones(p.shape[:2], bool)):
    global t
    with np.errstate(divide='ignore', invalid='ignore'):
        tt = val / d[..., axis]
    p = d * tt[..., None]
    ok = (tt > 0) & keep(p)
    t = np.where(ok & (tt < t), tt, t)

plane(1, -48.0)
plane(2, -400.0)
plane(0, -150.0)
# box: x in [20,100], y in [-48,10], z in [-300,-230]
bx, by, bz = (20, 100), (-48, 10), (-300, -230)
def inside(p, a, lo, hi): return (p[..., a] >= lo - 1e-3) & (p[..., a] <= hi + 1e-3)
plane(0, bx[0], lambda p: inside(p, 1, *by) & inside(p, 2, *bz))
plane(2, bz[1], lambda p: inside(p, 0, *bx) & inside(p, 1, *by))
plane(1, by[1], lambda p: inside(p, 0, *bx) & inside(p, 2, *bz))
plane(0, bx[1], lambda p: inside(p, 1, *by) & inside(p, 2, *bz))

zview = -t
ndcz = (P10 * zview + P14) / (-zview)
depthbuf = np.where(np.isfinite(t), ndcz * 0.5 + 0.5, 1.0)

# ---------- shader port ----------
def sample_depth(uvx, uvy):
    px = np.clip((uvx * W).astype(int), 0, W - 1)
    py = np.clip(((1 - uvy) * H).astype(int), 0, H - 1)
    return depthbuf[py, px]

def view_z(dep):
    ndc = dep * 2 - 1
    den = ndc + P10
    den = np.where(np.abs(den) < 1e-5, np.where(den < 0, -1e-5, 1e-5), den)
    return -P14 / den

def recon(uvx, uvy, dep):
    z = view_z(dep)
    return np.stack([-z * (uvx * 2 - 1 + P8) / P0, -z * (uvy * 2 - 1 + P9) / P5, z], -1)

def dot(a, b): return np.sum(a * b, -1)
def norm(a): return a / np.linalg.norm(a, axis=-1, keepdims=True)

def ign(px, py):
    return np.modf(52.9829189 * np.modf(px * 0.06711056 + py * 0.00583715)[0])[0]

uvx, uvy = u, v
dep = sample_depth(uvx, uvy)
C = recon(uvx, uvy, dep)
ix, iy = 1 / W, 1 / H
def pick(c, n, p):
    a, b = c - n, p - c
    return np.where((np.abs(a[..., 2]) < np.abs(b[..., 2]))[..., None], a, b)
L = recon(uvx - ix, uvy, sample_depth(uvx - ix, uvy)); R = recon(uvx + ix, uvy, sample_depth(uvx + ix, uvy))
D = recon(uvx, uvy - iy, sample_depth(uvx, uvy - iy)); U = recon(uvx, uvy + iy, sample_depth(uvx, uvy + iy))
N = norm(np.cross(pick(C, L, R), pick(C, D, U)))
N = np.where((dot(N, C) > 0)[..., None], -N, N)

viewDepth = -C[..., 2]
pos = C + N * bias * 0.25
V = norm(-pos)
radPix = np.minimum(radius * projectionScale / np.maximum(viewDepth, 1), 256)
fr = 0.615 * radius; ff = radius - fr; fmul = -1 / fr; fadd = ff / fr + 1
slices = int(np.clip(np.floor(samples / 4), 2, 8)); steps = 6
pxp, pyp = uvx * W, uvy * H
sn, stn = ign(pxp, pyp), ign(pxp + 5.588238, pyp + 5.588238)

def upd(hc, low, sx, sy):
    sd = sample_depth(sx, sy)
    dl = recon(sx, sy, sd) - pos
    dist = np.linalg.norm(dl, axis=-1)
    sc = dot(dl / np.maximum(dist, 1e-4)[..., None], V)
    w = np.clip(dist * fmul + fadd, 0, 1)
    cand = low + (sc - low) * w
    valid = (sd < 0.99999) & (dist >= 1e-4)
    return np.where(valid, np.maximum(hc, cand), hc)

vis = np.zeros((H, W))
for s in range(slices):
    phi = (s + sn) * np.pi / slices
    d2 = np.stack([np.cos(phi), np.sin(phi)], -1)
    d3 = np.concatenate([d2, np.zeros((H, W, 1))], -1)
    ortho = d3 - dot(d3, V)[..., None] * V
    axis = norm(np.cross(d3, V))
    pn = N - axis * dot(N, axis)[..., None]
    pl = np.linalg.norm(pn, axis=-1)
    cosN = np.clip(dot(pn, V) / pl, -1, 1)
    n = np.sign(dot(ortho, pn)) * np.arccos(cosN)
    sinN = np.sin(n)
    lowP, lowN = np.cos(n + np.pi / 2), np.cos(n - np.pi / 2)
    hP, hN = lowP.copy(), lowN.copy()
    for j in range(steps):
        tt = ((j + stn) / steps) ** 2
        off = np.maximum(tt * radPix, j + 1.0)
        ox, oy = d2[..., 0] * off * ix, d2[..., 1] * off * iy
        hP = upd(hP, lowP, uvx + ox, uvy + oy)
        hN = upd(hN, lowN, uvx - ox, uvy - oy)
    hp = np.minimum(np.arccos(np.clip(hP, -1, 1)), n + np.pi / 2)
    hn = np.maximum(-np.arccos(np.clip(hN, -1, 1)), n - np.pi / 2)
    arc = lambda h: (cosN + 2 * h * sinN - np.cos(2 * h - n)) * 0.25
    vis += pl * (arc(hp) + arc(hn))

ao = np.clip(vis / slices, 0, 1) ** power
ao = np.clip(1 - (1 - ao) * intensity, 0, 1)
ao = np.where(dep >= 0.99999, 1.0, ao)

Image.fromarray((ao * 255).astype(np.uint8)).resize((W * 2, H * 2), Image.NEAREST).save("ao_test.png")

def region(name, mask):
    if not mask.any(): print(name, "EMPTY"); return
    print(f"{name:28s} mean={ao[mask].mean():.3f} min={ao[mask].min():.3f}")
P = recon(uvx, uvy, dep)
floor = np.abs(P[..., 1] + 48) < 0.5
region("open floor (far from walls)", floor & (P[..., 0] > -100) & (P[..., 2] > -200) & ~((P[..., 0] > 0) & (P[..., 0] < 120) & (P[..., 2] < -210)))
region("floor-backwall seam", floor & (P[..., 2] < -375) & (P[..., 0] > -100) & ((P[..., 0] < 0) | (P[..., 0] > 120)))
region("open back wall", (np.abs(P[..., 2] + 400) < 0.5) & (P[..., 1] > 20) & (P[..., 0] > -100))
region("floor near box base", floor & (P[..., 0] > 0) & (P[..., 0] < 120) & (P[..., 2] > -229) & (P[..., 2] < -215))
print("overall min/max", ao.min(), ao.max())
