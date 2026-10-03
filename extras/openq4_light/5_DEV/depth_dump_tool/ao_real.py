"""Run stock openQ4 SSAO and the GTAO variants on a real decoded depth buffer.

usage: python3 ao_real.py real1.npz out_prefix
Both shaders are line-for-line ports of the GLSL (nearest-pixel depth reads).
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

d = np.load(sys.argv[1])
prefix = sys.argv[2] if len(sys.argv) > 2 else "real"
LIN = d["depth"].astype(np.float64)          # rows top-down
SKY, FG = d["sky"], d["fg"]
P0, P5, P8, P9 = float(d["P0"]), float(d["P5"]), float(d["P8"]), float(d["P9"])
H, W = LIN.shape
LINB = LIN[::-1]                              # bottom-up, like GL textures
SKYB, FGB = SKY[::-1], FG[::-1]
projectionScale = 0.5 * H * P5
ix, iy = 1.0 / W, 1.0 / H

ys, xs = np.mgrid[0:H, 0:W]
U = (xs + 0.5) / W
V = (ys + 0.5) / H                            # GL uv, v up (row 0 = bottom)

def sample(ux, uy):
    px = np.clip((ux * W).astype(np.int32), 0, W - 1)
    py = np.clip((uy * H).astype(np.int32), 0, H - 1)
    # weapon pixels carry no world depth in the dump: treat like sky (skip)
    return LINB[py, px], SKYB[py, px] | FGB[py, px]

def recon(ux, uy, lin):
    return np.stack([lin * (ux * 2 - 1 + P8) / P0, lin * (uy * 2 - 1 + P9) / P5, -lin], -1)

def dot(a, b): return np.sum(a * b, -1)
def norm(a): return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-9)
def ign(px, py): return np.modf(52.9829189 * np.modf(px * 0.06711056 + py * 0.00583715)[0])[0]
def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

lin0, _ = sample(U, V)
import os
if os.environ.get("CRACKFIX"):
    # 1-pixel cracks: centre much farther than both neighbours on a line
    l = sample(U - ix, V)[0]; r = sample(U + ix, V)[0]
    dn = sample(U, V - iy)[0]; up = sample(U, V + iy)[0]
    tol = 0.02
    hx = (lin0 > np.maximum(l, r) * (1 + tol)) & (np.abs(l - r) < tol * np.maximum(l, r) * 4)
    hy = (lin0 > np.maximum(dn, up) * (1 + tol)) & (np.abs(dn - up) < tol * np.maximum(dn, up) * 4)
    fill = np.where(hx, 0.5 * (l + r), np.where(hy, 0.5 * (dn + up), lin0))
    print("crack pixels filled:", int((fill != lin0).sum()))
    lin0 = fill
C = recon(U, V, lin0)
def pick(c, n, p):
    a, b = c - n, p - c
    return np.where((np.abs(a[..., 2]) < np.abs(b[..., 2]))[..., None], a, b)
Lp = recon(U - ix, V, sample(U - ix, V)[0]); Rp = recon(U + ix, V, sample(U + ix, V)[0])
Dp = recon(U, V - iy, sample(U, V - iy)[0]); Up = recon(U, V + iy, sample(U, V + iy)[0])
N = norm(np.cross(pick(C, Lp, Rp), pick(C, Dp, Up)))
N = np.where((dot(N, C) > 0)[..., None], -N, N)
del Lp, Rp, Dp, Up
viewDepth = lin0
pxp, pyp = U * W, V * H
skip = SKYB | FGB

def finish(ao, maxdist):
    fade = 1 - smoothstep(maxdist * 0.5, maxdist, viewDepth)
    return np.where(skip, 1.0, 1 + (ao - 1) * fade)

def stock(radius=36, bias=2, intensity=1.35, power=1.6, samples=20, maxdist=2000):
    radPix = np.clip(radius * projectionScale / np.maximum(viewDepth, 1), 2, 96)
    rot = ign(pxp, pyp) * 2 * np.pi
    occ = np.zeros((H, W)); wsum = np.zeros((H, W))
    for i in range(samples):
        si = i + 0.5
        ang = si * 2.39996323 + rot
        sr = np.sqrt(si / samples)
        sx = U + np.cos(ang) * sr * radPix * ix
        sy = V + np.sin(ang) * sr * radPix * iy
        sl, ss = sample(sx, sy)
        ts = recon(sx, sy, sl) - C
        d2 = dot(ts, ts)
        ok = (~ss) & (d2 > 1e-4) & (d2 <= radius * radius)
        dist = np.sqrt(d2)
        aw = np.clip((dot(N, ts) - bias) / np.maximum(dist, 1e-6), 0, 1)
        rw = 1 - smoothstep(radius * 0.35, radius, dist)
        dw = 1 - smoothstep(radius * 0.5, radius * 1.5, np.abs(ts[..., 2]))
        w = np.where(ok, rw * dw, 0)
        occ += aw * w; wsum += w
    ob = np.where(wsum > 0, occ / np.maximum(wsum, 1e-9), 0)
    ao = np.clip(np.clip(1 - ob * intensity, 0, 1) ** power, 0, 1)
    return finish(ao, maxdist)

def gtao(radius=36, bias=2, intensity=1.0, power=1.0, samples=20, maxdist=2000,
         ds=0.0, ref=64.0, minpx=0.0, thickness=0.0, nbias=0.25, mind=0.0):
    pos = C + N * bias * nbias
    Vd = norm(-pos)
    wr = radius * (1 + (np.maximum(viewDepth, 1) / ref - 1) * ds)
    radPix = np.minimum(wr * projectionScale / np.maximum(viewDepth, 1), 256)
    if minpx > 0:
        radPix = np.maximum(radPix, minpx)
        wr = radPix * np.maximum(viewDepth, 1) / projectionScale
    fr = 0.615 * wr; fmul = -1 / fr; fadd = (wr - fr) / fr + 1
    T = thickness * wr
    slices = int(np.clip(np.floor(samples / 4), 2, 8)); steps = 6
    sn, stn = ign(pxp, pyp), ign(pxp + 5.588238, pyp + 5.588238)

    def upd(hc, low, sx, sy):
        sl, ss = sample(sx, sy)
        dl = recon(sx, sy, sl) - pos
        dist = np.linalg.norm(dl, axis=-1)
        sc = dot(dl / np.maximum(dist, 1e-4)[..., None], Vd)
        w = np.clip(dist * fmul + fadd, 0, 1)
        if thickness > 0:
            w = w * (1 - smoothstep(T, 2 * T, dl[..., 2]))
        if mind > 0:
            w = w * smoothstep(mind * 0.5, mind, dist)
        return np.where((~ss) & (dist >= 1e-4), np.maximum(hc, low + (sc - low) * w), hc)

    vis = np.zeros((H, W))
    for s in range(slices):
        phi = (s + sn) * np.pi / slices
        c, si_ = np.cos(phi), np.sin(phi)
        d3 = np.stack([c, si_, np.zeros_like(c)], -1)
        ortho = d3 - dot(d3, Vd)[..., None] * Vd
        axis = norm(np.cross(d3, Vd))
        pn = N - axis * dot(N, axis)[..., None]
        pl = np.linalg.norm(pn, axis=-1)
        cosN = np.clip(dot(pn, Vd) / np.maximum(pl, 1e-9), -1, 1)
        n = np.sign(dot(ortho, pn)) * np.arccos(cosN); sinN = np.sin(n)
        lowP, lowN = np.cos(n + np.pi / 2), np.cos(n - np.pi / 2)
        hP, hN = lowP.copy(), lowN.copy()
        for j in range(steps):
            t = ((j + stn) / steps) ** 2
            off = np.maximum(t * radPix, j + 1.0)
            ox, oy = c * off * ix, si_ * off * iy
            hP = upd(hP, lowP, U + ox, V + oy)
            hN = upd(hN, lowN, U - ox, V - oy)
        hp = np.minimum(np.arccos(np.clip(hP, -1, 1)), n + np.pi / 2)
        hn = np.maximum(-np.arccos(np.clip(hN, -1, 1)), n - np.pi / 2)
        arc = lambda h: (cosN + 2 * h * sinN - np.cos(2 * h - n)) * 0.25
        vis += pl * (arc(hp) + arc(hn))
    ao = np.clip(vis / slices, 0, 1) ** power
    ao = np.clip(1 - (1 - ao) * intensity, 0, 1)
    return finish(ao, maxdist)

font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
def to_img(a):
    return Image.fromarray((np.clip(a[::-1], 0, 1) * 255).astype(np.uint8)).convert("RGB")
def label(img, text):
    dr = ImageDraw.Draw(img); dr.rectangle([0, 0, img.width, 44], fill=(0, 0, 0))
    dr.text((10, 5), text, fill=(255, 255, 255), font=font); return img

if __name__ == "__main__":
    import os
    runs = [
        ("stock", "Исходный SSAO (1.35 / 1.6)", lambda: stock()),
        ("world", "GTAO world, без толщины", lambda: gtao()),
        ("world_t", "GTAO world, толщина 0.5", lambda: gtao(thickness=0.5)),
        ("screen", "GTAO screen, без толщины", lambda: gtao(ds=1.0)),
        ("screen_t", "GTAO screen, толщина 0.5", lambda: gtao(ds=1.0, thickness=0.5)),
    ]
    runs += [
        ("w_nb1", "world, сдвиг от поверхности 1·bias", lambda: gtao(nbias=1.0)),
        ("w_md2", "world, мин. дистанция 2", lambda: gtao(mind=2.0)),
        ("w_md4", "world, мин. дистанция 4", lambda: gtao(mind=4.0)),
    ]
    runs += [
        ("v_screen", "screen, толщина 0.5", lambda: gtao(ds=1.0, thickness=0.5)),
        ("v_w128", "world R=128, толщина 0.5", lambda: gtao(radius=128, thickness=0.5)),
        ("v_hyb", "world R=64 + минимум 48 px, толщина 0.5", lambda: gtao(radius=64, minpx=48, thickness=0.5)),
    ]
    if os.environ.get("RUNS"):
        keep = os.environ["RUNS"].split(",")
        runs = [r for r in runs if r[0] in keep]
    imgs = []
    for key, name, fn in runs:
        a = fn()
        np.save(f"{prefix}_{key}.npy", a.astype(np.float32))
        imgs.append(label(to_img(a).resize((1280, 720), Image.BILINEAR), name))
        print("done", key, flush=True)
    grid = Image.new("RGB", (1280 * 2 + 8, 720 * 3 + 16), (40, 40, 40))
    for k, im in enumerate(imgs):
        grid.paste(im, ((k % 2) * 1288, (k // 2) * 728))
    grid.save(f"{prefix}_compare.png")
