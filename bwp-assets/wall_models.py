"""Materialise every packable skeleton as a render-ready model folder, without copying textures.

pack_models.py copies each atlas page into the model folder, which for ~600 battle skeletons
would duplicate the same 2048x2048 pages many times over. Hard links give the runtime the
flat "skel + atlas + page.png" layout it wants at zero extra disk cost.
usage: python wall_models.py <pkg> [out_root] [kinds]
"""
import os, shutil, sys

from pack_models import cover, load, merge


def link(src, dst):
    if os.path.exists(dst):
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def run(pkg, out_root='t/wall_models', kinds='battle'):
    ix, pages, rows = load(pkg)
    dump = f't/{pkg}'
    os.makedirs(out_root, exist_ok=True)
    made, short = 0, 0
    index = []
    for r in rows:
        if r['err'] != 'ok':
            continue
        names = [a.split(':')[0] for a in r['animations'].split(';') if a]
        kind = 'born' if names == ['born'] else 'battle'
        if kind not in kinds:
            continue
        want = set(x for x in r['regions'].split(';') if x)
        pids, left = cover(pages, want)
        if not pids or left:
            short += 1
            continue
        stem = f'{pkg[-1]}_{pids[0]}_{kind}'
        dst = os.path.join(out_root, stem)
        os.makedirs(dst, exist_ok=True)
        merge(dump, ix, pids, dst, stem, copy_page=link)
        link(os.path.join(dump, r['skel']), os.path.join(dst, f'{stem}.skel'))
        # the merged atlas lists every region on the shared pages, so the character name has to
        # come from what this skeleton actually references
        index.append((stem, pkg, r['skel'], kind, r['animations'], r['regions']))
        made += 1
    with open(os.path.join(out_root, '_models.tsv'), 'a', encoding='utf-8') as f:
        for row in index:
            f.write('\t'.join(row) + '\n')
    print(f'{pkg}: {made} models ready in {out_root}, {short} skipped (missing parts)')
    return made


if __name__ == '__main__':
    run(sys.argv[1],
        sys.argv[2] if len(sys.argv) > 2 else 't/wall_models',
        sys.argv[3] if len(sys.argv) > 3 else 'battle')
