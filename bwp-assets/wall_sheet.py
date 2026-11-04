"""Compose rendered model thumbnails into labelled contact sheets.

The raw PNG contact sheets were useless for identification -- they show loose atlas pieces,
not assembled characters. These sheets show each skeleton rendered in its idle pose, labelled
with the model id and the character name, taken from the region prefix the skeleton itself
references (merged atlases also carry other characters' pages, so the atlas lies).
usage: python wall_sheet.py <thumbDir> <modelRoot> <outDir> [tile=220] [cols=8]
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

SCENE_JUNK = ('bg', 'bj', 'guang', 'beijing', 'qianjing', 'tx', 'flare', 'glow',
              'shadow', 'guan', 'ms_', 'fengge', 'yincang', 'mask', 'zhezhao')


def token(region):
    """jiutun_shangshen_01 / BJ/jiutun_00002 / #dajiangshan_00 -> the character part."""
    return region.rsplit('/', 1)[-1].lstrip('#').split('_')[0].lower()


def load_index(model_root):
    """stem -> (character prefix, animation names) for the skeleton that owns that folder."""
    tsv = Path(model_root) / '_models.tsv'
    if not tsv.exists():
        return {}, {}
    # a pack made by avatar_models.py already knows which atlas page each skeleton came from,
    # which beats guessing a name from region prefixes
    pages = {r[0]: r[1] for r in csv.reader((Path(model_root) / '_pages.tsv').open(encoding='utf-8'),
                                            delimiter='\t') if r and r[0] != 'stem'} \
        if (Path(model_root) / '_pages.tsv').exists() else {}
    out, grp = {}, {}
    for r in csv.reader(tsv.open(encoding='utf-8'), delimiter='\t'):
        stem, anims, regions = r[0], r[4], r[5]
        grp[stem] = r[1] if len(r) > 1 else '?'
        if stem in pages:
            out[stem] = (pages[stem], [a.split(':')[0] for a in anims.split(';') if a])
            continue
        c = collections.Counter(token(reg) for reg in regions.split(';') if reg)
        for junk in SCENE_JUNK:
            c.pop(junk, None)
        # a prefix only names the character if the skeleton actually leans on it
        best, n = (c.most_common(1)[0] if c else ('?', 0))
        out[stem] = (best if n >= 3 else '?', [a.split(':')[0] for a in anims.split(';') if a])
    return out, grp


def main():
    thumbs, models, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    tile, cols = (int(sys.argv[4]) if len(sys.argv) > 4 else 220), (int(sys.argv[5]) if len(sys.argv) > 5 else 8)
    cap = 40
    out.mkdir(parents=True, exist_ok=True)
    index, grp = load_index(models)

    # grep-able roster: one character may own several model ids (skins, shared pages)
    by_name = collections.defaultdict(list)
    for stem, (name, _) in index.items():
        by_name[name].append(stem)
    with (out / '_index.tsv').open('w', encoding='utf-8') as f:
        for name, stems in sorted(by_name.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            f.write(f'{name}\t{len(stems)}\t{",".join(sorted(stems))}\n')

    items = []
    for png in sorted(thumbs.glob('*.png')):
        stem = png.stem
        im = Image.open(png).convert('RGBA')
        alpha = im.split()[3]
        # crop on solid ink: wide faint additive glow would otherwise blow the crop up
        box = alpha.point(lambda v: 255 if v > 128 else 0).getbbox() or alpha.getbbox()
        if box is None:
            continue
        im = im.crop(box)
        side = max(im.size)
        canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
        canvas.alpha_composite(im, ((side - im.size[0]) // 2, (side - im.size[1]) // 2))
        # a mid grey backdrop: the art is authored dark, white backgrounds hide the silhouette
        bg = Image.new('RGBA', canvas.size, (96, 96, 104, 255))
        bg.alpha_composite(canvas)
        name, anims = index.get(stem, ('?', []))
        mark = ' 有登场' if {'born', 'born_break'} & set(anims) else ''
        items.append((stem, f'{name} · {len(anims)}个动画{mark}', bg.resize((tile, tile), Image.LANCZOS)))

    rowH = tile + cap
    per_sheet = cols * 6
    sheets = collections.defaultdict(list)
    for it in items:
        sheets[grp.get(it[0], '?')].append(it)
    for pkg, its in sorted(sheets.items()):
        for part in range(0, len(its), per_sheet):
            chunk = its[part:part + per_sheet]
            rows = (len(chunk) + cols - 1) // cols
            sheet = Image.new('RGB', (cols * tile, rows * rowH), (24, 24, 28))
            d = ImageDraw.Draw(sheet)
            for i, (stem, tag, img) in enumerate(chunk):
                x, y = (i % cols) * tile, (i // cols) * rowH
                sheet.paste(img.convert('RGB'), (x, y))
                d.text((x + 3, y + tile + 3), stem, fill=(240, 240, 240), font=FONT)
                d.text((x + 3, y + tile + 20), tag, fill=(150, 210, 255), font=FONT2)
            fn = out / f'wall_{pkg}_{part // per_sheet + 1}.png'
            sheet.save(fn)
            print(f'  {fn}  {len(chunk)} tiles')
    print(f'{len(items)} thumbnails -> {out}')


if __name__ == '__main__':
    main()
