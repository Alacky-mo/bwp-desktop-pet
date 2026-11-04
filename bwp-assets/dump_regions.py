"""Dump selected atlas regions as PNGs + area-weighted mean colour of a name prefix.

usage: python dump_regions.py <model_dir> <out_dir> [region ...]
       python dump_regions.py <model_dir> <out_dir> --avg <prefix>
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from region_stats import parse_atlas


def main():
    root, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    pages = {}
    args = sys.argv[3:]

    if args and args[0] == "--avg":
        prefix = args[1] if len(args) > 1 else ""
        tot = np.zeros(3)
        area = 0
        names = []
        for page, name, x, y, w, h, rot in parse_atlas(next(root.glob("*.atlas"))):
            if not name.startswith(prefix):
                continue
            if page not in pages:
                pages[page] = np.asarray(Image.open(root / page).convert("RGBA"))
            box = pages[page][y:y + h, x:x + w].astype(np.float32)
            rgb, a = box[..., :3], box[..., 3]
            solid = a > 0.5
            if not solid.any():
                continue
            tot += rgb[solid].mean(0) * solid.sum()
            area += int(solid.sum())
            names.append(name)
        if area:
            m = tot / area
            print(f"prefix={prefix or '*'} regions={len(names)} solidPx={area} "
                  f"meanRGB=({m[0]:.0f},{m[1]:.0f},{m[2]:.0f})  B-R={m[2] - m[0]:+.0f}")
        return

    for page, name, x, y, w, h, rot in parse_atlas(next(root.glob("*.atlas"))):
        if name not in args:
            continue
        img = Image.open(root / page).convert("RGBA").crop((x, y, x + w, y + h))
        if rot:
            img = img.transpose(Image.ROTATE_90)
        img.save(out / f"{name}.png")
        print(f"  {out / (name + '.png')}  {img.size}")


if __name__ == "__main__":
    main()
