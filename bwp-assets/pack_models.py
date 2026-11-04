"""Pack DeskSpine-ready model folders from the npk dump.

Pairing is derived from what each skeleton actually references (the region names the runtime
reported in out/<pkg>_census.tsv), not from npk file order -- the adjacency guess in
_spine_index.json is wrong for a lot of models.

A character can be split over several single-page atlas files, and stock DeskSpine only ever
hands one atlas to the runtime, so every model folder gets one merged .atlas listing all the
pages its skeleton needs.
"""
import csv, json, os, re, shutil, sys

PAGE_LINE = re.compile(r'\.(png|jpg|webp)\s*$')


def load(pkg):
    ix = json.load(open(f'crops/{pkg}/_spine_index.json', encoding='utf-8'))
    pages = {pid: set(v['regions']) for pid, v in ix.items()}
    rows = [r for r in csv.DictReader(open(f'out/{pkg}_census.tsv', encoding='utf-8', newline=''),
                                      delimiter='\t') if r['err'] == 'ok']
    return ix, pages, rows


def cover(pages, want):
    """Fewest atlas pages whose region names together include everything the skeleton needs."""
    left, chosen = set(want), []
    while left:
        gain, pid = max((len(reg & left), pid) for pid, reg in pages.items())
        if not gain:
            break
        chosen.append(pid)
        left -= pages[pid]
    return chosen, left


def merge(dump, ix, pids, out_dir, stem, copy_page=shutil.copyfile):
    blocks = []
    for pid in pids:
        lines = open(os.path.join(dump, ix[pid]['atlas']), encoding='utf-8', errors='replace').read().split('\n')
        for i, line in enumerate(lines):
            if PAGE_LINE.search(line.strip()):
                lines[i] = f'{pid}.png'
                break
        blocks.append('\n\n' + '\n'.join(lines).strip('\n'))
        copy_page(os.path.join(dump, ix[pid]['page_png']), os.path.join(out_dir, f'{pid}.png'))
    open(os.path.join(out_dir, f'{stem}.atlas'), 'w', encoding='utf-8').write(''.join(blocks) + '\n')


def run(pkg, out_root, kinds='battle', limit=None):
    ix, pages, rows = load(pkg)
    dump = f't/{pkg}'
    made, short = [], []
    for r in rows:
        names = [a.split(':')[0] for a in r['animations'].split(';') if a]
        kind = 'born' if names == ['born'] else 'battle'
        if kind not in kinds:
            continue
        want = set(x for x in r['regions'].split(';') if x)
        pids, left = cover(pages, want)
        if not pids:
            short.append((r['skel'], 'no region used')); continue
        if left:
            short.append((r['skel'], f'{len(left)} parts absent from package: ' + ','.join(sorted(left)[:3])))
            continue
        stem = f'{pkg[-1]}_{pids[0]}_{kind}'
        dst = os.path.join(out_root, stem)
        shutil.rmtree(dst, ignore_errors=True)
        os.makedirs(dst)
        merge(dump, ix, pids, dst, stem)
        shutil.copyfile(os.path.join(dump, r['skel']), os.path.join(dst, f'{stem}.skel'))
        made.append((stem, len(pids)))
        if limit and len(made) >= limit:
            break
    print(f'{pkg}: {len(made)} models -> {out_root} '
          f'({sum(1 for _, n in made if n > 1)} needed a merged multi-page atlas)')
    for s in short[:6]:
        print('   skipped', s)
    if len(short) > 6:
        print(f'   ... {len(short)} skipped in total')
    return made


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else f'models/{sys.argv[1]}',
        sys.argv[3] if len(sys.argv) > 3 else 'battle',
        int(sys.argv[4]) if len(sys.argv) > 4 else None)
