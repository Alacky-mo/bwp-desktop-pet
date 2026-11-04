"""Index a spine_hero*.npk dump: group atlas / skel / page-texture by character-skin id.

Atlas text files name their own page texture on line 2; skel binaries carry the
region names they reference. Both use ids like 14409 / 14409_2, so the numeric root
is the natural group key.
"""
import os, re, sys, json, collections

STR = re.compile(rb'[\x20-\x7e]{4,}')


def skel_strings(path):
    d = open(path, 'rb').read()
    out = []
    for m in STR.finditer(d):
        s = m.group().decode('ascii')
        if s in ('Linear', 'repeat', 'none', 'size', 'index') or s.startswith('  '):
            continue
        out.append(s)
    return out


def parse_atlas(path):
    lines = open(path, encoding='utf-8', errors='replace').read().splitlines()
    page = next((l.strip() for l in lines[:3] if l.strip().endswith(('.png', '.ktx'))), None)
    regions = [l.strip() for l in lines
               if l.strip() and not l.startswith((' ', '\t')) and l.strip() != page
               and ':' not in l.strip() and not l.strip().endswith(('.png', '.ktx'))]
    return page, regions


def root_id(name):
    m = re.match(r'(\d+)', name or '')
    return m.group(1) if m else None


def build(dump_dir, out_json=None):
    groups = collections.defaultdict(lambda: dict(skels=[], atlases=[], pages=[], regions=set()))
    files = sorted(os.listdir(dump_dir))
    for f in files:
        p = os.path.join(dump_dir, f)
        if not os.path.isfile(p):
            continue
        stem, ext = os.path.splitext(f)
        if ext in ('.atlas', '.txt'):
            page, regions = parse_atlas(p)
            rid = root_id(page) or root_id(regions[0] if regions else None) or stem
            g = groups[rid]
            g['atlases'].append(f)
            if page:
                g['pages'].append(page)
            g['regions'].update(regions)
        elif ext == '.bin':
            strs = skel_strings(p)
            ids = {root_id(s) for s in strs if root_id(s)}
            rid = max(ids, key=lambda x: len(x or '')) if ids else stem
            g = groups[rid or stem]
            g['skels'].append(f)
            g['regions'].update(s for s in strs if re.match(r'^\d+(_\d+)?$', s))
        elif ext == '.png':
            rid = root_id(f) or stem
            groups[rid]['pngs'] = groups[rid].get('pngs', []) + [f]
    result = {k: {**v, 'regions': sorted(v['regions'])} for k, v in sorted(groups.items())}
    out_json = out_json or os.path.join(dump_dir, '_spine_index.json')
    json.dump(result, open(out_json, 'w'), indent=1, ensure_ascii=False)
    print(f'{len(result)} groups -> {out_json}')
    for k in list(result)[:8]:
        v = result[k]
        print(f'  {k}: skel={len(v["skels"])} atlas={len(v["atlases"])} pages={v["pages"][:3]} regions={len(v["regions"])}')
    return result


if __name__ == '__main__':
    build(sys.argv[1])
