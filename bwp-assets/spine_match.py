"""Pair each Spine atlas with the page texture it actually describes.

The npk TOC only stores name hashes, so page textures arrive index-named. spine_hero1 stores
atlas/skeleton/page adjacently but spine_hero2 and 3 do not, so the pairing has to come from
content: a real page has no opaque pixels outside the region rects its atlas lists, and its
total ink is close to the area of those rects.
"""
import os
import numpy as np
from PIL import Image

GRID = 256
GOOD = 0.995
TOPK = 12

_fp = {}


def fingerprint(png_path, pw, ph):
    """Mean alpha per coarse cell, so total ink and out-of-rect ink are both estimable."""
    if png_path not in _fp:
        im = Image.open(png_path)
        fp = None
        if im.size == (pw, ph) and 'A' in im.getbands():
            fp = np.asarray(im.getchannel('A').resize((GRID, GRID), Image.BOX),
                            dtype=np.float32) / 255.0
        _fp[png_path] = fp
        im.close()
    return _fp[png_path]


def grids(regions, pw, ph):
    """Return (coarse rect union, cell area, full-res rect union, expected ink)."""
    g = np.zeros((GRID, GRID), dtype=bool)
    m = np.zeros((ph, pw), dtype=bool)
    cell = (pw / GRID) * (ph / GRID)
    ink = 0.0
    for r in regions:
        x, y = r['xy']
        w, h = r['size']
        if r['rotate']:
            w, h = h, w
        ink += w * h
        g[max(0, int(y * GRID / ph)):min(GRID, -(-int(y + h) * GRID // ph)),
          max(0, int(x * GRID / pw)):min(GRID, -(-int(x + w) * GRID // pw))] = True
        m[max(y, 0):min(y + h, ph), max(x, 0):min(x + w, pw)] = True
    return g, cell, m, ink


def rank(png_path, pw, ph, grid, cell, ink):
    fp = fingerprint(png_path, pw, ph)
    if fp is None:
        return None
    got = float(fp.sum()) * cell
    outside = float(fp[~grid].sum()) * cell
    return (outside / max(got, 1.0), abs(got - ink) / max(ink, 1.0))


def verify(png_path, mask, pw, ph):
    """Fraction of the page's opaque pixels that fall inside the atlas rect union."""
    im = Image.open(png_path)
    ok = im.size == (pw, ph)
    a = np.asarray(im.getchannel('A')) if ok and 'A' in im.getbands() else None
    im.close()
    if a is None:
        return 1.0 if ok else -1.0
    opaque = a > 0
    tot = int(opaque.sum())
    return float((opaque & mask).sum() / tot) if tot else -1.0


def pair(atlas_jobs, textures, png_of, log=None):
    """atlas_jobs: [{idx, pw, ph, grid, cell, mask, ink, page}]. -> {atlas_idx: (tex_idx, score)}"""
    out = {}
    for job in atlas_jobs:
        pw, ph = job['pw'], job['ph']
        scored = []
        for t in textures:
            if (t['w'], t['h']) != (pw, ph):
                continue
            r = rank(png_of(t['idx']), pw, ph, job['grid'], job['cell'], job['ink'])
            if r is not None:
                scored.append((r[0], r[1], abs(t['idx'] - job['idx']), t['idx']))
        scored.sort()
        for _, _, _, tix in scored[:TOPK]:
            s = verify(png_of(tix), job['mask'], pw, ph)
            if s >= GOOD:
                out[job['idx']] = (tix, s)
                break
        if job['idx'] not in out and log:
            log(f"  atlas {job['idx']} ({os.path.basename(job['page'])}) unmatched"
                + (f"; best outside={scored[0][0]:.4f} ink-err={scored[0][1]:.3f}" if scored else ''))
    return out
