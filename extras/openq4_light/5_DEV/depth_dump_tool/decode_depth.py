"""Decode a depth-dump screenshot (zzz_depthdump.pk4 + r_ssaoDebug 1) into
linear view depth + projection, saved as an .npz for the AO test harness.

usage: python3 decode_depth.py shot.tga [out.npz]
"""
import sys
import numpy as np
from PIL import Image

MAGIC = 0x2A2A5


def load(path):
    img = np.asarray(Image.open(path).convert("RGB")).astype(np.int32)
    return img  # rows top-down


def build_luts(img):
    """Calibration ramp: top 8 rows, columns 0..255 hold grey x/255."""
    ramp = np.median(img[1:7, :256, :], axis=0)  # (256, 3) observed values
    luts = []
    for c in range(3):
        obs = ramp[:, c]
        # observed -> original level, nearest monotone match
        lut = np.zeros(256)
        for v in range(256):
            lut[v] = np.argmin(np.abs(obs - v))
        luts.append(lut)
    return luts


def undo(img, luts):
    out = np.empty(img.shape, float)
    for c in range(3):
        out[..., c] = luts[c][np.clip(img[..., c], 0, 255)]
    return out


def digits(v):
    # stored as (d*4+2)/255 -> d = round((v-2)/4)
    return np.clip(np.rint((v - 2.0) / 4.0), 0, 63)


def decode18(rgb):
    d = digits(rgb)
    return d[..., 0] * 4096 + d[..., 1] * 64 + d[..., 2]


def main(path, out):
    img = load(path)
    luts = build_luts(img)
    lin = undo(img, luts)
    codes = decode18(lin)

    cells = [np.median(codes[10:14, 8 * k + 2:8 * k + 6]) for k in range(5)]
    if int(cells[2]) != MAGIC:
        raise SystemExit(f"layout check failed (got {int(cells[2]):#x}); was the screenshot taken with r_ssaoDebug 1 and nothing over the top-left corner?")
    invP0, invP5 = cells[0] / 16384.0, cells[1] / 16384.0
    P8, P9 = cells[3] / 65536.0 - 1.0, cells[4] / 65536.0 - 1.0

    depth = codes / 64.0
    sky = codes >= 262143
    fg = codes == 0
    # the header area has no depth: copy from the row just below
    depth[:16, :256] = depth[16:17, :256]
    sky[:16, :256] = sky[16:17, :256]
    fg[:16, :256] = fg[16:17, :256]
    np.savez_compressed(out, depth=depth.astype(np.float32), sky=sky, fg=fg,
                        P0=1 / invP0, P5=1 / invP5, P8=P8, P9=P9)
    valid = ~(sky | fg)
    print(f"{img.shape[1]}x{img.shape[0]}  P0={1/invP0:.4f} P5={1/invP5:.4f} jitter=({P8:.5f},{P9:.5f})")
    print(f"depth range {depth[valid].min():.1f}..{depth[valid].max():.1f} units, sky {sky.mean():.1%}, weapon {fg.mean():.1%}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "depth.npz")
