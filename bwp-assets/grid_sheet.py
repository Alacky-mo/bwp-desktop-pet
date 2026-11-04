"""Compose one row per character, one column per animation, so emotion sets can be compared.

The idle-pose wall (wall_sheet.py) can only answer "who is this"; for the chibi head rigs the
question is whether the same head actually changes expression, so every animation of a skeleton
gets its own cell. Thumbnails come from `bwp-render-wall <root> <thumbs> 1600 0.5 all 512`, which
names them `<model>@<animation>.png`.
usage: python grid_sheet.py <thumbDir> <modelRoot> <outDir> [tile=170] [rows=18]
"""
import collections
import csv
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

try:
    FONT = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 13)
    FONT2 = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 12)
except OSError:
    FONT = FONT2 = ImageFont.load_default()

ORDER = ['idle', 'idle1', 'idle2', 'happy', 'smile', 'sad', 'angry', 'surprise', 'thinking',
         'serious', 'emotion1', 'emotion2', 'emotion3', 'emotion4', 'emotion5', 'emotion6',
         'stand', 'walk', 'deck_idle', 'born', 'born_break']
# per-part take-offs of one expression; they only ever move one layer, so they add nothing to a grid
PART_SUFFIX = ('_body', '_eye', '_head', '_mouth', '_mouth_say')


def load_models(model_root):
    tsv = Path(model_root) / '_pages.tsv'
    out = {}
    if tsv.exists():
        for r in csv.reader(tsv.open(encoding='utf-8'), delimiter='\t'):
            out[r[0]] = r
    return out


def tile_of(png, size):
    im = Image.open(png).convert('RGBA')
    alpha = im.split()[3]
    box = alpha.point(lambda v: 255 if v > 128 else 0).getbbox() or alpha.getbbox()
    if box is None:
        return None
    im = im.crop(box)
    side = max(im.size)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
    bg = Image.new('RGBA', canvas.size, (96, 96, 104, 255))
    bg.alpha_composite(canvas)
    return bg.resize((size, size), Image.LANCZOS)


def main():
    thumbs, models, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    tile = int(sys.argv[4]) if len(sys.argv) > 4 else 170
    per_sheet = int(sys.argv[5]) if len(sys.argv) > 5 else 18
    cap, head = 34, 24
    out.mkdir(parents=True, exist_ok=True)
    info = load_models(models)

    cells = collections.defaultdict(dict)
    for png in sorted(thumbs.glob('*@*.png')):
        stem, anim = png.stem.split('@', 1)
        if anim.endswith(PART_SUFFIX):
            continue
        cells[stem][anim] = png

    def sort_key(anim):
        return (ORDER.index(anim) if anim in ORDER else len(ORDER), anim)
    every = collections.Counter(a for v in cells.values() for a in v)
    # a column only earns its width if more than one character has that animation
    cols = sorted([a for a, n in every.items() if n >= 2], key=sort_key)
    faces = set(ORDER[:10])
    # a face rig answers "which expression does this head make"; an emotion1..6 overlay only
    # swaps a whole picture, so the faces are what the sheet is actually for
    rows = sorted(cells, key=lambda s: (-len(set(cells[s]) & faces), info.get(s, [s, s])[1], s))

    index = out / '_grid_index.tsv'
    with index.open('w', encoding='utf-8') as f:
        f.write('stem\tpage\tpages\tcanvas\tparts\tanims\tgroup\n')
        for s in rows:
            r = info.get(s, [s, '', '', '', '', '', '', ''])
            f.write(f'{s}\t{r[1]}\t{r[2]}\t{r[4]}\t{r[6]}\t'
                    f'{",".join(sorted(cells[s], key=sort_key))}\t{r[7]}\n')

    ncol = len(cols)
    width = 210 + ncol * tile
    for part in range(0, len(rows), per_sheet):
        chunk = rows[part:part + per_sheet]
        sheet = Image.new('RGB', (width, head + len(chunk) * (tile + cap)), (24, 24, 28))
        d = ImageDraw.Draw(sheet)
        for j, a in enumerate(cols):
            d.text((210 + j * tile + 4, 6), a, fill=(255, 210, 120), font=FONT)
        for i, stem in enumerate(chunk):
            y = head + i * (tile + cap)
            r = info.get(stem, [stem, stem, '', '', '', ''])
            d.text((6, y + 4), r[1], fill=(240, 240, 240), font=FONT)
            d.text((6, y + 22), f'{r[4]} · {r[6]}件 · {r[3]}页', fill=(150, 210, 255), font=FONT2)
            for j, a in enumerate(cols):
                png = cells[stem].get(a)
                if not png:
                    continue
                t = tile_of(png, tile)
                if t:
                    sheet.paste(t.convert('RGB'), (210 + j * tile, y))
        fn = out / f'grid_{part // per_sheet + 1}.png'
        sheet.save(fn)
        print(f'  {fn}  {len(chunk)} rows x {ncol} cols')
    print(f'{len(rows)} characters, {len(cols)} animations -> {out}')


if __name__ == '__main__':
    main()
