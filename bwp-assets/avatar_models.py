"""Attribute each skeleton in a dump to the atlas pages it really uses, then pack chosen groups.

spine.npk reuses one page name for several atlases and has region names as generic as "1", so
neither npk order nor a plain region-name intersection identifies a character. Attribution here
is: prefer the atlas whose region set is exactly the skeleton's, otherwise take the fewest paired
atlases that cover it, tie-broken by entry-index proximity to the skeleton.

usage: python avatar_models.py <pkg> <group> [out_root]
groups: emotion | head | deck | other | all (comma list ok)
"""
import collections, csv, json, os, re, shutil, sys

from pack_models import merge

EMO = {'happy', 'sad', 'angry', 'smile', 'surprise', 'thinking', 'serious',
       'emotion1', 'emotion2', 'emotion3', 'emotion4', 'emotion5', 'emotion6'}


def load_all(pkg):
    ix = json.load(open(f't/{pkg}/_atlas_index.json', encoding='utf-8'))
    rows = [r for r in csv.DictReader(open(f'out/{pkg}_census.tsv', encoding='utf-8', newline=''),
                                      delimiter='\t') if r['err'] == 'ok']
    return {k: set(v['regions']) for k, v in ix.items() if v['page_png']}, ix, rows


def pick(reg, want, anchor=0):
    """Atlas ids whose region names cover `want`; an exact-equality atlas wins outright."""
    exact = [k for k, r in reg.items() if r == want]
    if exact:
        return [min(exact, key=lambda k: abs(int(k) - anchor))], set()
    left, chosen = set(want), []
    while left:
        cands = sorted((-len(r & left), abs(int(k) - anchor), k) for k, r in reg.items() if r & left)
        if not cands:
            break
        chosen.append(cands[0][2])
        left -= reg[cands[0][2]]
    return chosen, left


def group_of(names, page, size):
    """What kind of asset a skeleton is, from its animation vocabulary and canvas size."""
    s = set(names)
    if len(s & EMO) >= 2 or any(n.endswith('_mouth_say') for n in s):
        return 'emotion'
    try:
        w, h = (float(x) for x in size.split('x')[:2])
    except ValueError:
        w = h = 0
    if w * h <= 40000:                      # <= ~200x200: head- or icon-sized rig
        return 'head'
    if s and all(n.startswith('deck_') for n in s):
        return 'deck'                       # the 图鉴/card-list idle pose, a shrunken 卡面
    return 'other'


def link(src, dst):
    if not os.path.exists(dst):
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)


def run(pkg, group='emotion', out_root=None):
    out_root = out_root or f't/{pkg}_{group}'
    reg, ix, rows = load_all(pkg)
    # a region set that several atlases share carries no identity: those skeletons stay unpacked
    share = collections.Counter(frozenset(v) for v in reg.values())
    dump = f't/{pkg}'
    shutil.rmtree(out_root, ignore_errors=True)
    os.makedirs(out_root)
    made, short, frames, tags, pages = {}, [], [], [], []
    for r in rows:
        names = [a.split(':')[0] for a in r['animations'].split(';') if a]
        want = {x for x in r['regions'].split(';') if x}
        pids, left = pick(reg, want, int(os.path.splitext(r['skel'])[0]))
        if not pids or left:
            short.append((r['skel'], f'{len(left)} parts elsewhere'))
            continue
        twins = share[frozenset(reg[pids[0]])]
        if twins > 2:
            short.append((r['skel'], f'atlas shared by {twins}, identity unknown'))
            continue
        g = group_of(names, ix[pids[0]]['page'], r['size'])
        if group != 'all' and g not in group.split(','):
            continue
        page = ix[pids[0]]['page']
        stem = re.sub(r'[^\w.\-]+', '_', f'{page}_{r["skel"][:-4]}')[:70]
        if stem in made:
            continue
        dst = os.path.join(out_root, stem)
        os.makedirs(dst, exist_ok=True)
        merge(dump, ix, pids, dst, stem, copy_page=link)
        link(os.path.join(dump, r['skel']), os.path.join(dst, f'{stem}.skel'))
        made[stem] = pids
        w, h = (r['size'].split('x') + ['0', '0'])[:2]
        frames.append((stem, w, h))
        tags.append((stem, pkg, r['skel'], g, r['animations'], r['regions']))
        pages.append((stem, page, '+'.join(ix[p]['page'] for p in pids), len(pids), r['size'],
                      ','.join(sorted(set(names))), len(want), g, twins))
    with open(os.path.join(out_root, '_models.tsv'), 'w', encoding='utf-8') as f:
        f.writelines('\t'.join(t) + '\n' for t in tags)
    with open(os.path.join(out_root, '_frame.tsv'), 'w', encoding='utf-8') as f:
        f.writelines(f'{s}\t{w}\t{h}\n' for s, w, h in frames)
    with open(os.path.join(out_root, '_pages.tsv'), 'w', encoding='utf-8') as f:
        f.write('stem\tpage\tpages\tnpages\tcanvas\tanimations\tparts\tgroup\ttwins\n')
        f.writelines('\t'.join(map(str, p)) + '\n' for p in pages)
    amb = sum(1 for s in short if 'identity' in s[1])
    print(f'{pkg}/{group}: {len(made)} models -> {out_root}; '
          f'{len(short) - amb} skels need parts outside this npk, {amb} have an unattributable atlas')
    for s in short[:6]:
        print('   skipped', s)
    print('   groups:', collections.Counter(p[7] for p in pages).most_common())
    return made


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'emotion',
        sys.argv[3] if len(sys.argv) > 3 else None)
