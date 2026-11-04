"""Measure every atlas region of one packed model: colour, alpha, additive brightness.

Why: additive glow layers look fine over the game's dark backdrop but wash out over a
bright desktop, so ranking regions by how much light they add names the white blob.
usage: python region_stats.py <model_dir> [region ...]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SKIP = ("size:", "format:", "filter:", "repeat:")


def parse_atlas(path):
    """Return [(page, region, x, y, w, h, rotated)] with w/h being the packed box size."""
    lines = path.read_text(errors="replace").splitlines()
    out, page, i = [], None, 0
    while i < len(lines):
        line = lines[i].rstrip()
        i += 1
        if not line.strip():
            continue
        if line.startswith(" "):
            continue
        if line.startswith(SKIP):
            continue
        if "." in line and line.rsplit(".", 1)[-1].lower() in ("png", "jpg", "jpeg", "dds", "ktx"):
            page = line
            continue
        name, fields = line, {}
        while i < len(lines) and lines[i].startswith(" "):
            k, _, v = lines[i].strip().partition(":")
            fields[k] = v.strip()
            i += 1
        if page is None or "xy" not in fields or "size" not in fields:
            continue
        x, y = (int(t) for t in fields["xy"].split(","))
        w, h = (int(t) for t in fields["size"].split(","))
        rot = fields.get("rotate", "false") == "true"
        out.append((page, name, x, y, h, w, rot) if rot else (page, name, x, y, w, h, rot))
    return out


def main():
    root = Path(sys.argv[1])
    atlas = next(root.glob("*.atlas"))
    wanted = set(sys.argv[2:])
    pages = {}
    rows = []
    for page, name, x, y, w, h, _ in parse_atlas(atlas):
        if wanted and name not in wanted:
            continue
        if page not in pages:
            pages[page] = np.asarray(Image.open(root / page).convert("RGBA"))
        box = pages[page][max(y, 0):max(y, 0) + h, max(x, 0):max(x, 0) + w].astype(np.float32) / 255.0
        if box.size == 0:
            continue
        rgb, a = box[..., :3], box[..., 3]
        solid = a > 0.5
        # what a single additive pass contributes per covered pixel, averaged over the box
        add = (rgb * a[..., None]).mean((0, 1))
        core = rgb[solid].mean(0) if solid.any() else np.zeros(3)
        rows.append((add.mean(), name, w, h, a.mean(), add, core))
    rows.sort(reverse=True)
    print(f"{'region':<18}{'box':>10}{'alpha':>7}{'add/pix':>9}  {'lightRGB':>18}  {'opaqueCoreRGB':>18}")
    for add, name, w, h, alpha, vec, core in rows[:20]:
        print(f"{name:<18}{f'{w}x{h}':>10}{alpha:7.2f}{add:9.4f}  "
              f"{' '.join(f'{v:.3f}' for v in vec):>18}  {' '.join(f'{v:.3f}' for v in core):>18}")


if __name__ == "__main__":
    main()
