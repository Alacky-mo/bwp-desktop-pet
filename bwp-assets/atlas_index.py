"""Pair every atlas in a dump with its page texture and key the result by atlas entry index.

spine_crop.py keys its index by the page *name* the atlas declares, which collapses the ~80
page names that several atlases share in spine.npk (they reuse one texture for different
region layouts). Keying by atlas index keeps every atlas addressable, so a skeleton can be
matched to the atlas whose region names actually equal its own.
usage: python atlas_index.py <dump_dir> [out_json]
"""
import json, os, sys

import spine_match as M
from spine_crop import parse_atlas


def build(dump_dir, out_json=None):
    manifest = json.load(open(os.path.join(dump_dir, '_manifest.json'), encoding='utf-8'))
    first = {}
    for f in os.listdir(dump_dir):
        stem = f.split('.')[0]
        if stem.isdigit():
            first.setdefault(int(stem), f)
    path_of = {e['idx']: os.path.join(dump_dir, e.get('name') or first[e['idx']]) for e in manifest}
    png = lambda i: path_of[i]

    jobs, meta = [], {}
    for e in manifest:
        p = path_of[e['idx']]
        if not p.endswith(('.atlas', '.txt')):
            continue
        page, pw, ph, regions = parse_atlas(open(p, encoding='utf-8', errors='replace').read())
        if not page or not regions or not pw:
            continue
        g, cell, mask, ink = M.grids(regions, pw, ph)
        jobs.append(dict(idx=e['idx'], pw=pw, ph=ph, grid=g, cell=cell, mask=mask, ink=ink, page=p))
        meta[e['idx']] = (page, pw, ph, regions)

    textures = [t for t in manifest if t.get('w')]
    diag = []
    pairs = M.pair(jobs, textures, png, log=diag.append)
    out = {}
    for job in jobs:
        i = job['idx']
        page, pw, ph, regions = meta[i]
        tix, sc = pairs.get(i, (None, None))
        out[str(i)] = dict(atlas=os.path.basename(path_of[i]), page=os.path.splitext(page)[0],
                           page_png=os.path.basename(path_of[tix]) if tix is not None else '',
                           tex=tix, size=[pw, ph], cover=sc,
                           regions=[r['name'] for r in regions])
    out_json = out_json or os.path.join(dump_dir, '_atlas_index.json')
    json.dump(out, open(out_json, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print(f'{len(pairs)}/{len(jobs)} atlases paired with a page texture -> {out_json}')
    names = {}
    for v in out.values():
        names[v['page']] = names.get(v['page'], 0) + 1
    print(f'{len(names)} distinct page names, {sum(1 for n in names.values() if n > 1)} shared by several atlases')
    return out


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
