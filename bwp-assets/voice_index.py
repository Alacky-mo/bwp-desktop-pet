"""语音名册: 把「清单上的语音单元 → 设备上有没有 → 本地解出来几句 → 能不能对上表情骨架」归成一张表。

用法: python voice_index.py            产物 out/voice_roster.tsv + 屏幕摘要
前置(只读它们的产物, 不碰设备):
  python voice_pull.py ls                      -> out/voice_wwise.tsv(设备文件清单)
  python voice_bnk.py parse voice/raw -o out/voice_clips.tsv
                                               -> out/voice_clips_unit.tsv(逐单元句数/时长/分组)
                                               -> out/voice_clips_external.tsv(走外部 .wem 的 media)
名字从哪来: meta/subpack_version.json 的 810 个 vo_* 单元是唯一权威的「有哪些语音单元」;
单元名里的 数字 id + 拼音 是唯一能读出的「这段语音属于谁」。bank 内部没有任何文字(见 voice_bnk.py),
所以「哪一句配哪一个表情」不在离线可算的范围里 —— 这张表到「哪个式神有几句、几个分组」为止。
中文名列读 voice_names.tsv(拼音<TAB>中文名, 只有你确认过的才写在里面), 没确认的留空。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'out'
RAW = ROOT / 'voice' / 'raw'
GRID = ROOT / 'sheets' / 'spine_emotion' / '_grid_index.tsv'
NAMES = ROOT / 'voice_names.tsv'
ID_LIKE = re.compile(r'^vo_(battle|biography|emotion|street)(_player)?(?:_(\d+))?(?:_([0-9a-z_]+))?$')
IDLE = re.compile(r'^idle\d*$')


def tsv_rows(path):
    lines = path.read_text(encoding='utf-8').splitlines()
    hdr = lines[0].split('\t')
    for row in (l.split('\t') for l in lines[1:]):
        if len(row) == len(hdr):
            yield dict(zip(hdr, row))


def read_tsv(path, cols=None):
    return [{k: r[k] for k in cols if k in r} if cols else r for r in tsv_rows(path)]


def spine_emo():
    """表情骨架名册: {基础拼音: {骨架目录: [动画名]}}。"""
    by = {}
    for r in tsv_rows(GRID):
        by.setdefault(r['page'], {})[r['stem']] = r['anims'].split(',')
    return by


def match_tier(slug, keys):
    """语音拼音 -> 骨架拼音 的三种对法, 按可信度排; 对不上就明说对不上, 不硬猜。"""
    if slug in keys:
        return '同名', {slug}
    bag = sorted(slug)
    same = {k for k in keys if sorted(k) == bag}          # ciqiqingwa / qingwaciqi
    if same:
        return '同字母异序', same
    pre = {k for k in keys if k.startswith(slug) or slug.startswith(k)}
    if pre:
        return '前缀互含', pre
    return '对不上', set()


def main():
    dev_tsv = OUT / 'voice_wwise.tsv'
    unit_tsv = OUT / 'voice_clips_unit.tsv'
    if not dev_tsv.exists() or not unit_tsv.exists():
        sys.exit('先跑 voice_pull.py ls 和 voice_bnk.py parse(见文件头)')
    manifest = {k for k in json.loads((ROOT / 'meta' / 'subpack_version.json')
                                      .read_text(encoding='utf-8')) if k.startswith('vo_')}
    device = {r.split('\t')[0]: int(r.split('\t')[1]) for r in
              dev_tsv.read_text(encoding='utf-8').splitlines() if '\t' in r}
    dev_wem = {n for n in device if n.endswith('.wem')}
    local_wem = {p.name for p in RAW.glob('*.wem')}
    parsed = {r['unit']: r for r in read_tsv(unit_tsv)}
    external = {}
    for r in read_tsv(OUT / 'voice_clips_external.tsv'):
        external.setdefault(r['unit'], []).append(r['media_id'])
    spines = spine_emo()
    keys = set(spines)
    names = {}
    if NAMES.exists():
        names = dict(l.split('\t')[:2] for l in NAMES.read_text(encoding='utf-8').splitlines()
                     if '\t' in l and not l.startswith('#'))

    # 数字 id -> 拼音: 只有「这个 id 全库只对应一个拼音」时才敢拿来补空。
    # 实测 17 个 id 对应多个拼音(146 既是 fanqie 又是 tiaotiaomeimei, 194 有 guishibai/guishihei),
    # 同类别内也有 23 个这种冲突, 所以含糊的一律不补, 宁可空着。
    seen = defaultdict(set)
    for unit in manifest | set(device) | set(parsed):
        m = ID_LIKE.match(unit)
        if m and m.group(3) and m.group(4):
            seen[m.group(3)].add(m.group(4))
    id2slug = {k: next(iter(v)) for k, v in seen.items() if len(v) == 1}
    ambiguous = {k for k, v in seen.items() if len(v) > 1}

    hdr = ['unit', 'category', 'view', 'hero_id', 'slug', '中文名', '清单里', '设备上', '本地已解',
           '句数', '走外部wem', '外部wem缺', '估分钟', '分组数', '分组sizes',
           '表情骨架目录', '表情动画', '表情动画数', '对上方式']
    rows, covered = [], set()
    tally = defaultdict(Counter)
    for unit in sorted(manifest | {p[:-4] for p in device if p.startswith('vo_') and p.endswith('.bnk')}
                       | set(parsed)):
        m = ID_LIKE.match(unit)
        cat, player, hid, slug = (m.groups() if m else ('?', '', None, None))
        hid, slug = hid or '', slug or id2slug.get(hid, '')
        p = parsed.get(unit)
        ext = external.get(unit, [])
        miss_ext = sorted({f'{i}.wem' for i in ext if f'{i}.wem' not in local_wem})
        if slug:
            tier, hits = match_tier(slug, keys)
        elif hid in ambiguous:
            tier, hits = '只有数字 id(拼音不唯一)', set()
        else:
            tier, hits = '名字里没有拼音', set()
        stems = sorted({s for k in hits for s in spines[k]})
        anims = sorted({a for k in hits for s in spines[k].values() for a in s})
        emo_anim = [a for a in anims if not IDLE.match(a)]
        rows.append([unit, cat, '玩家' if player else '式神', hid, slug, names.get(slug, ''),
                     '是' if unit in manifest else '否', '是' if f'{unit}.bnk' in device else '否',
                     '是' if p else '否',
                     int(p['clips']) if p else 0, len(ext), len(miss_ext),
                     round(float(p['seconds']) / 60, 1) if p else 0,
                     len(p['group_sizes'].split(',')) if p else 0, p['group_sizes'] if p else '',
                     ','.join(stems), ','.join(anims), len(emo_anim), tier])
        t = tally[cat]
        t['单元'] += 1
        t['本地'] += bool(p)
        t['句数'] += rows[-1][9]
        t['分钟'] += rows[-1][12]
        t['对上骨架'] += bool(hits)
        if cat == 'emotion':
            covered |= hits

    out = OUT / 'voice_roster.tsv'
    out.write_text('\n'.join('\t'.join(map(str, r)) for r in [hdr] + rows) + '\n', encoding='utf-8')
    orphans = [r[0] for r in rows if r[6] == '否' and r[7] == '否']
    print(f'VOICE INDEX {"OK" if not orphans else "FAIL"}: {len(rows)} 个语音单元 -> {out}')
    print(f'  {"类别":<11}{"单元":>5}{"本地已解":>9}{"句数":>8}{"估分钟":>8}{"对上表情骨架":>13}')
    for cat, t in sorted(tally.items()):
        print(f'  {cat:<13}{t["单元"]:>5}{t["本地"]:>9}{t["句数"]:>8}{t["分钟"]:>8.0f}{t["对上骨架"]:>13}')
    if orphans:
        print(f'  既不在清单也不在设备上的(不该出现): {len(orphans)} -> {orphans[:8]}')
    emo = [r for r in rows if r[1] == 'emotion' and r[4]]
    bad = [r for r in emo if r[18] == '对不上']
    print(f'  带拼音的表情语音单元 {len(emo)} 个: 能对到表情骨架 {len(emo) - len(bad)}, '
          f'对不上 {len(bad)}(涉及 {len({r[4] for r in bad})} 种拼音)')
    print(f'    对不上的拼音: {", ".join(sorted({r[4] for r in bad})[:24])}')
    print(f'  对上方式分布: {dict(Counter(r[18] for r in rows))}')
    silent = sorted(keys - covered)
    print(f'  表情骨架 {len(keys)} 种拼音里, 没有任何表情语音单元对上的: {len(silent)}')
    print(f'    例: {", ".join(silent[:20])}')
    got = [r for r in emo if r[18] != '对不上' and r[9]]
    lines = [r[9] for r in got]
    anims = [r[17] for r in got]
    an_med = median(anims)
    ratio = f', 平均 {median(lines) / an_med:.1f} 句抢 1 个表情' if an_med else ''
    print(f'  「一句配一个表情」成不成立: 对上骨架的 {len(got)} 个单元里, '
          f'每单元句数中位 {median(lines)}(区间 {min(lines)}~{max(lines)}), '
          f'骨架的表情动画数中位 {an_med}(区间 {min(anims)}~{max(anims)}){ratio}; '
          f'包内也没有按表情分开的分组(判据见 voice_bnk.py slots)')
    print(f'  外部 .wem: 清单 {sum(len(v) for v in external.values())} 条, '
          f'本地缺 {sum(r[11] for r in rows)} 条(设备上也没有的就算缺)')


if __name__ == '__main__':
    main()
