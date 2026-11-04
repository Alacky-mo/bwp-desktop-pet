"""Cut Spine atlas regions out of their page texture and name them from the atlas text.

Usage: python spine_crop.py <dump_dir> [out_dir]
Writes <out_dir>/<pageId>__<regionName>.png, <out_dir>/_pages/<pageId>.png and
<out_dir>/_spine_index.json.
"""
import os, re, sys, json, shutil
from PIL import Image
import spine_match as M


def parse_atlas(text):
    """Return (page_name, page_w, page_h, [region dicts])."""
    lines = text.splitlines()
    page = next((l.strip() for l in lines[:4] if l.strip().endswith(('.png', '.ktx'))), None)
    pw = ph = None
    for l in lines:
        m = re.match(r'\s*size:\s*(\d+)\s*,\s*(\d+)', l)
        if m:
            pw, ph = int(m.group(1)), int(m.group(2))
            break
    regions, cur = [], None
    for l in lines:
        s = l.strip()
        if not s:
            continue
        if l[0] in ' \t':
            m = re.match(r'\s*(\w+):\s*(.*)', l)
            if m and cur is not None:
                k, v = m.group(1), m.group(2).strip()
                if k in ('xy', 'size', 'orig', 'offset'):
                    cur[k] = [int(x) for x in re.findall(r'-?\d+', v)]
                elif k == 'rotate':
                    cur['rotate'] = v == 'true'
        elif ':' not in s and not s.endswith(('.png', '.ktx')) and s != page:
            cur = {'name': s, 'rotate': False}
            regions.append(cur)
    return page, pw, ph, regions


def crop_region(img, r):
    x, y = r['xy']
    w, h = r['size']
    ox, oy = r.get('offset', [0, 0])
    ow, oh = r.get('orig', [w, h])
    piece = (img.crop((x, y, x + h, y + w)) if r['rotate'] else img.crop((x, y, x + w, y + h)))
    if r['rotate']:
        piece = piece.transpose(Image.ROTATE_90)
    if [ow, oh] != piece.size:
        canvas = Image.new('RGBA', (ow, oh), (0, 0, 0, 0))
        canvas.paste(piece, (ox, oy), piece)
        piece = canvas
    return piece


def run(dump_dir, out_dir, min_side=128):
    page_dir = os.path.join(out_dir, '_pages')
    os.makedirs(page_dir, exist_ok=True)
    manifest = json.load(open(os.path.join(dump_dir, '_manifest.json'), encoding='utf-8'))
    # older unpackers recorded the TOC name hash in the filename; newer ones just use {idx:04d}
    first = {}
    for f in os.listdir(dump_dir):
        m = re.match(r'(\d+)', f)
        if m:
            first.setdefault(int(m.group(1)), f)
    path_of = {e['idx']: os.path.join(dump_dir, e.get('name') or first[e['idx']])
               for e in manifest}
    png = lambda i: path_of[i]

    jobs, meta = [], {}
    for e in manifest:
        p = path_of[e['idx']]
        if not p.endswith(('.atlas', '.txt')) or not os.path.exists(p):
            continue
        page, pw, ph, regions = parse_atlas(open(p, encoding='utf-8', errors='replace').read())
        if not page or not regions or not pw:
            continue
        g, cell, mask, ink = M.grids(regions, pw, ph)
        jobs.append(dict(idx=e['idx'], pw=pw, ph=ph, grid=g, cell=cell, mask=mask, ink=ink,
                         page=p))
        meta[e['idx']] = (page, regions)
    textures = [t for t in manifest if t.get('w')]
    diag = []
    pairs = M.pair(jobs, textures, png, log=diag.append)
    for line in diag[:6]:
        print(line)
    if len(diag) > 6:
        print(f'  ... {len(diag)} unpaired total')

    index, made, dup = {}, 0, 0
    bin_idx = [e['idx'] for e in manifest if path_of[e['idx']].endswith('.bin')]
    for job in jobs:
        i = job['idx']
        page, regions = meta[i]
        stem = os.path.splitext(page)[0]
        if i not in pairs:
            continue
        tix, sc = pairs[i]
        near = [b for b in bin_idx if abs(b - i) <= 10]
        skel = os.path.basename(path_of[min(near, key=lambda b: abs(b - i))]) if near else ''
        shutil.copyfile(png(tix), os.path.join(page_dir, f'{stem}.png'))
        src = Image.open(png(tix)).convert('RGBA')
        for r in regions:
            if min(r['size']) < min_side:
                continue
            name = f"{stem}__{r['name'].replace('/', '_')}.png"
            t = os.path.join(out_dir, name)
            if os.path.exists(t):
                dup += 1
            crop_region(src, r).save(t, compress_level=1)
            made += 1
        src.close()
        index[stem] = dict(page_png=os.path.basename(path_of[tix]), page_id=stem,
                           atlas=os.path.basename(path_of[i]), skel=skel, hash=manifest[tix].get('hash'),
                           size=[job['pw'], job['ph']], cover=round(sc, 4),
                           regions=[r['name'] for r in regions])
    json.dump(index, open(os.path.join(out_dir, '_spine_index.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)
    missing = [os.path.splitext(meta[j['idx']][0])[0] for j in jobs if j['idx'] not in pairs]
    print(f"{len(pairs)}/{len(jobs)} atlases paired, {made} regions cut -> {out_dir}")
    if missing:
        print(f'  {len(missing)} pages not in this npk: {", ".join(missing[:12])} ...')


if __name__ == '__main__':
    dump = sys.argv[1]
    run(dump, sys.argv[2] if len(sys.argv) > 2 else dump.rstrip('/\\') + '_crops')
