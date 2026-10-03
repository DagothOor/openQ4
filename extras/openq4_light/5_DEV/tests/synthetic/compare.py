"""Side-by-side: stock openQ4 SSAO vs the GTAO replacement on one depth buffer.

The depth buffer is ray-traced from a Quake-4-style tech corridor: floor,
ceiling, side walls with ribs, pipes along a wall and the ceiling, crates,
a step and a pillar. Both shaders are ported line-for-line from GLSL.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

W, H = 640, 360
fov_x = np.radians(90)
P0 = 1 / np.tan(fov_x / 2)
P5 = P0 * W / H
P8 = P9 = 0.0
NEAR = 3.0
P10, P14 = -0.999, -2 * NEAR
projectionScale = 0.5 * H * P5

# ---------------- scene ----------------
ys, xs = np.mgrid[0:H, 0:W]
U = (xs + 0.5) / W
Vv = 1 - (ys + 0.5) / H
dirs = np.stack([(U * 2 - 1) / P0, (Vv * 2 - 1) / P5, -np.ones_like(U)], -1)
# camera: eye height 56 above floor, slightly right of centre, pitched down a bit
pitch = np.radians(-8)
cp, sp = np.cos(pitch), np.sin(pitch)
Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
D = dirs @ Rx.T                       # world-space ray dirs
O = np.array([20.0, 56.0, 0.0])       # world-space eye

T = np.full((H, W), np.inf)

def hit(t):
    global T
    t = np.where(np.isfinite(t) & (t > 1e-3), t, np.inf)
    T = np.minimum(T, t)

def box(lo, hi):
    lo, hi = np.array(lo, float), np.array(hi, float)
    with np.errstate(divide='ignore', invalid='ignore'):
        t1 = (lo - O) / D
        t2 = (hi - O) / D
    tmin = np.nanmax(np.minimum(t1, t2), -1)
    tmax = np.nanmin(np.maximum(t1, t2), -1)
    hit(np.where((tmax >= tmin) & (tmax > 0), np.where(tmin > 0, tmin, np.inf), np.inf))

def cyl_z(cx, cy, r, z0, z1):
    ox, oy = O[0] - cx, O[1] - cy
    a = D[..., 0] ** 2 + D[..., 1] ** 2
    b = 2 * (ox * D[..., 0] + oy * D[..., 1])
    c = ox * ox + oy * oy - r * r
    disc = b * b - 4 * a * c
    with np.errstate(invalid='ignore', divide='ignore'):
        t = (-b - np.sqrt(disc)) / (2 * a)
    z = O[2] + t * D[..., 2]
    hit(np.where((disc > 0) & (z <= z1) & (z >= z0), t, np.inf))

def cyl_y(cx, cz, r, y0, y1):
    ox, oz = O[0] - cx, O[2] - cz
    a = D[..., 0] ** 2 + D[..., 2] ** 2
    b = 2 * (ox * D[..., 0] + oz * D[..., 2])
    c = ox * ox + oz * oz - r * r
    disc = b * b - 4 * a * c
    with np.errstate(invalid='ignore', divide='ignore'):
        t = (-b - np.sqrt(disc)) / (2 * a)
    y = O[1] + t * D[..., 1]
    hit(np.where((disc > 0) & (y <= y1) & (y >= y0), t, np.inf))

Z0, Z1 = -2000, 10
box([-140, -10, Z0], [140, 0, Z1])        # floor
box([-140, 160, Z0], [140, 170, Z1])      # ceiling
box([-150, 0, Z0], [-120, 160, Z1])       # left wall
box([120, 0, Z0], [150, 160, Z1])         # right wall
box([-140, 0, -900], [140, 160, -880])    # end wall
for z in range(-60, -880, -110):          # wall ribs / panel frames
    box([-120, 0, z - 10], [-108, 160, z])
    box([108, 0, z - 10], [120, 160, z])
    box([-120, 150, z - 10], [120, 160, z])
box([-120, 0, Z0], [-110, 14, Z1])        # skirting on the left
for (y, r) in [(120, 6), (104, 4), (92, 4)]:   # pipes on the right wall
    cyl_z(114 - r, y, r, Z0, Z1)
cyl_z(-30, 150, 7, Z0, Z1)                # ceiling pipe
cyl_z(10, 152, 5, Z0, Z1)
box([-108, 0, -330], [-60, 40, -282])     # crates
box([-104, 40, -324], [-72, 64, -292])
box([40, 0, -520], [96, 32, -470])
box([-120, 0, -700], [120, 12, -640])     # step
cyl_y(-40, -600, 14, 0, 160)              # pillar

# world -> view (camera space)
Pw = O + D * T[..., None]
Pv = (Pw - O) @ Rx                         # inverse rotation
zview = Pv[..., 2]
ndcz = (P10 * zview + P14) / (-zview)
depthbuf = np.where(np.isfinite(T), ndcz * 0.5 + 0.5, 1.0)

# ---------------- shared helpers (ported from ssao.fs) ----------------
ix, iy = 1 / W, 1 / H
def sample_depth(ux, uy):
    px = np.clip((ux * W).astype(int), 0, W - 1)
    py = np.clip(((1 - uy) * H).astype(int), 0, H - 1)
    return depthbuf[py, px]
def view_z(dep):
    den = dep * 2 - 1 + P10
    den = np.where(np.abs(den) < 1e-5, np.where(den < 0, -1e-5, 1e-5), den)
    return -P14 / den
def recon(ux, uy, dep):
    z = view_z(dep)
    return np.stack([-z * (ux * 2 - 1 + P8) / P0, -z * (uy * 2 - 1 + P9) / P5, z], -1)
def dot(a, b): return np.sum(a * b, -1)
def norm(a): return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-9)
def ign(px, py): return np.modf(52.9829189 * np.modf(px * 0.06711056 + py * 0.00583715)[0])[0]
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

dep = sample_depth(U, Vv)
C = recon(U, Vv, dep)
def pick(c, n, p):
    a, b = c - n, p - c
    return np.where((np.abs(a[..., 2]) < np.abs(b[..., 2]))[..., None], a, b)
Lp = recon(U - ix, Vv, sample_depth(U - ix, Vv)); Rp = recon(U + ix, Vv, sample_depth(U + ix, Vv))
Dp = recon(U, Vv - iy, sample_depth(U, Vv - iy)); Up = recon(U, Vv + iy, sample_depth(U, Vv + iy))
N = norm(np.cross(pick(C, Lp, Rp), pick(C, Dp, Up)))
N = np.where((dot(N, C) > 0)[..., None], -N, N)
viewDepth = -C[..., 2]
pxp, pyp = U * W, Vv * H
sky = dep >= 0.99999

radius, bias, maxdist, samples = 36.0, 2.0, 1200.0, 20.0   # engine defaults, except max distance
fade = 1 - smoothstep(maxdist * 0.5, maxdist, viewDepth)

# ---------------- stock SSAO ----------------
def stock(intensity=1.35, power=1.6):
    radPix = np.clip(radius * projectionScale / np.maximum(viewDepth, 1), 2, 96)
    rot = ign(pxp, pyp) * 2 * np.pi
    occ = np.zeros((H, W)); wsum = np.zeros((H, W))
    for i in range(int(samples)):
        si = i + 0.5
        ang = si * 2.39996323 + rot
        sr = np.sqrt(si / samples)
        sx = U + np.cos(ang) * sr * radPix * ix
        sy = Vv + np.sin(ang) * sr * radPix * iy
        sd = sample_depth(sx, sy)
        ts = recon(sx, sy, sd) - C
        d2 = dot(ts, ts)
        ok = (sd < 0.99999) & (d2 > 1e-4) & (d2 <= radius * radius)
        dist = np.sqrt(d2)
        aw = np.clip((dot(N, ts) - bias) / np.maximum(dist, 1e-6), 0, 1)
        rw = 1 - smoothstep(radius * 0.35, radius, dist)
        dw = 1 - smoothstep(radius * 0.5, radius * 1.5, np.abs(ts[..., 2]))
        w = np.where(ok, rw * dw, 0)
        occ += aw * w; wsum += w
    ob = np.where(wsum > 0, occ / np.maximum(wsum, 1e-9), 0)
    ao = np.clip(np.clip(1 - ob * intensity, 0, 1) ** power, 0, 1)
    return np.where(sky, 1, 1 + (ao - 1) * fade)

# ---------------- GTAO ----------------
def gtao(intensity=1.0, power=1.0):
    pos = C + N * bias * 0.25
    V = norm(-pos)
    radPix = np.minimum(radius * projectionScale / np.maximum(viewDepth, 1), 256)
    fr = 0.615 * radius; fmul = -1 / fr; fadd = (radius - fr) / fr + 1
    slices = int(np.clip(np.floor(samples / 4), 2, 8)); steps = 6
    sn, stn = ign(pxp, pyp), ign(pxp + 5.588238, pyp + 5.588238)
    def upd(hc, low, sx, sy):
        sd = sample_depth(sx, sy)
        dl = recon(sx, sy, sd) - pos
        dist = np.linalg.norm(dl, axis=-1)
        sc = dot(dl / np.maximum(dist, 1e-4)[..., None], V)
        w = np.clip(dist * fmul + fadd, 0, 1)
        return np.where((sd < 0.99999) & (dist >= 1e-4), np.maximum(hc, low + (sc - low) * w), hc)
    vis = np.zeros((H, W))
    for s in range(slices):
        phi = (s + sn) * np.pi / slices
        d2 = np.stack([np.cos(phi), np.sin(phi)], -1)
        d3 = np.concatenate([d2, np.zeros((H, W, 1))], -1)
        ortho = d3 - dot(d3, V)[..., None] * V
        axis = norm(np.cross(d3, V))
        pn = N - axis * dot(N, axis)[..., None]
        pl = np.linalg.norm(pn, axis=-1)
        cosN = np.clip(dot(pn, V) / np.maximum(pl, 1e-9), -1, 1)
        n = np.sign(dot(ortho, pn)) * np.arccos(cosN); sinN = np.sin(n)
        lowP, lowN = np.cos(n + np.pi / 2), np.cos(n - np.pi / 2)
        hP, hN = lowP.copy(), lowN.copy()
        for j in range(steps):
            tt = ((j + stn) / steps) ** 2
            off = np.maximum(tt * radPix, j + 1.0)
            ox, oy = d2[..., 0] * off * ix, d2[..., 1] * off * iy
            hP = upd(hP, lowP, U + ox, Vv + oy)
            hN = upd(hN, lowN, U - ox, Vv - oy)
        hp = np.minimum(np.arccos(np.clip(hP, -1, 1)), n + np.pi / 2)
        hn = np.maximum(-np.arccos(np.clip(hN, -1, 1)), n - np.pi / 2)
        arc = lambda h: (cosN + 2 * h * sinN - np.cos(2 * h - n)) * 0.25
        vis += pl * (arc(hp) + arc(hn))
    ao = np.clip(vis / slices, 0, 1) ** power
    ao = np.clip(1 - (1 - ao) * intensity, 0, 1)
    return np.where(sky, 1, 1 + (ao - 1) * fade)

# ---------------- output ----------------
a_stock, a_gtao = stock(), gtao()

def depth_vis():
    z = np.where(sky, viewDepth.max(), viewDepth)
    g = 1 - np.clip(np.log(z) / np.log(900), 0, 1)
    return g

def lit():  # simple headlamp-like diffuse so the geometry reads
    l = np.clip(dot(N, norm(-C)), 0, 1)
    return 0.15 + 0.85 * l

def to_img(a): return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("RGB")

try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
except OSError:
    font = ImageFont.load_default()

def label(img, text):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, img.width, 28], fill=(0, 0, 0))
    d.text((8, 4), text, fill=(255, 255, 255), font=font)
    return img

panels = [
    label(to_img(depth_vis()), "Буфер глубины (для ориентира)"),
    label(to_img(lit()), "Сцена без AO (простое освещение)"),
    label(to_img(a_stock), "Исходный SSAO openQ4 (1.35 / 1.6)"),
    label(to_img(a_gtao), "GTAO (1.0 / 1.0)"),
    label(to_img(lit() * a_stock), "Сцена × исходный SSAO"),
    label(to_img(lit() * a_gtao), "Сцена × GTAO"),
]
grid = Image.new("RGB", (W * 2 + 6, H * 3 + 12), (40, 40, 40))
for k, p in enumerate(panels):
    grid.paste(p, ((k % 2) * (W + 6), (k // 2) * (H + 6)))
grid.save("compare.png")

# 4x zoom crop: crates + pipes area, to show noise and contact detail
x0, y0, cw, ch = 60, 150, 160, 110
crops = []
for a, name in [(a_stock, "SSAO, ×4"), (a_gtao, "GTAO, ×4")]:
    c = to_img(a).crop((x0, y0, x0 + cw, y0 + ch)).resize((cw * 4, ch * 4), Image.NEAREST)
    crops.append(label(c, name))
zoom = Image.new("RGB", (cw * 8 + 6, ch * 4), (40, 40, 40))
zoom.paste(crops[0], (0, 0)); zoom.paste(crops[1], (cw * 4 + 6, 0))
zoom.save("compare_zoom.png")

flat = (~sky) & (np.abs(N[..., 1]) > 0.98) & (viewDepth < 150)
print("open-floor mean: stock %.3f  gtao %.3f" % (a_stock[flat].mean(), a_gtao[flat].mean()))
