"""把联系表导成桌宠能直接读的语音包：一个骨架目录一份，manifest 认「表情动画名」，不认角色名。

用法:
  python voice_pack.py --slug buzhihuo            硬链 wav + 出 manifest 到 t/spine_emotion/<骨架目录>/voice/
  python voice_pack.py --slug buzhihuo --check    只验收(表情名是不是真动画、wav 在不在、秒数对不对)
  python voice_pack.py --slug buzhihuo --dry      只打印要放什么，不落盘

包放在**骨架自己那个目录**旁边(`t/spine_emotion/<骨架目录>/voice/`)，桌宠拿到 .skel 路径就能就近找到语音，
不用再维护一张「拼音→包路径」的表; 骨架换目录或装进 res/ 里，重跑一次就跟着走。
manifest 叫 `_manifest.tsv`(t/ 下只有 `_*.tsv` 入库)，wav 是版权素材一律不进版本库，用 os.link 硬链不占双倍空间。
**没出字和没规则的句不进池**——那些要人耳定，宁可不出声也别乱配脸。
"""
import argparse
import csv
import os
import shutil
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHEET = ROOT / 'out' / 'voice_emo_sheet.tsv'
ROSTER = ROOT / 'out' / 'voice_roster.tsv'
SPINE = ROOT / 't' / 'spine_emotion'
MAN = '_manifest.tsv'
HDR = ['表情', '秒', '文件', '日语原文', '中文意思', '来源单元', '置信']

ap = argparse.ArgumentParser()
ap.add_argument('--slug', required=True, help='包名里的拼音，例: buzhihuo')
ap.add_argument('--check', action='store_true', help='只验收已落盘的包')
ap.add_argument('--dry', action='store_true', help='只打印不写文件')
a = ap.parse_args()
for p in (SHEET, ROSTER):
    if not p.exists():
        sys.exit(f'缺少 {p}(先跑 voice_emo_map.py)')


def tsv(path):
    with open(path, encoding='utf-8') as fh:
        rd = csv.reader(fh, delimiter='\t')
        head = next(rd)
        for row in rd:
            if len(row) == len(head) and not row[0].startswith('#'):
                yield dict(zip(head, row))


def rows_of(man):
    """读已落盘的 manifest(跳过表头)。"""
    return [x.split('\t') for x in man.read_text(encoding='utf-8-sig').splitlines()][1:]


# 该角色的表情单元 → 骨架目录，和该骨架实际有的动画名(池子里的表情名必须是它的子集)
skel, moods = {}, {}
for r in tsv(ROSTER):
    if r['category'] == 'emotion' and r['slug'] == a.slug and r['表情骨架目录']:
        skel[r['unit']] = r['表情骨架目录']
        moods.setdefault(r['表情骨架目录'], set()).update(x for x in r['表情动画'].split(',') if x)
if not moods:
    sys.exit(f'{a.slug} 在名册里没有表情骨架目录(名册没重跑 voice_index.py?)')

pool, skip = defaultdict(list), defaultdict(int)
for s in tsv(SHEET):
    if s['unit'] not in skel:
        continue
    if s['日语原文'] == '(没出字)':
        skip['没出字(要听)'] += 1
        continue
    if s['命中方式'] not in ('exact', 'contains') or not s['实际动画']:
        skip['没规则'] += 1
        continue
    src = Path(s['wav'])
    pool[s['unit']].append((s['实际动画'], float(s['秒']), s['日语原文'], s['中文意思'], s['置信'],
                            src if src.is_absolute() else ROOT.parent / src))

if a.check:
    bad, n = [], 0
    for d in moods:
        man = SPINE / d / 'voice' / MAN
        if not man.exists():
            bad.append(f'{d}: 没有 {MAN}')
            continue
        for r in rows_of(man):
            n += 1
            w = man.parent / r[2]
            if r[0] not in moods[d]:
                bad.append(f'{d}: 表情名「{r[0]}」不在该骨架的动画表 {sorted(moods[d])}')
            if not w.exists():
                bad.append(f'{d}/{r[2]}: wav 不在')
            elif w.stat().st_size < 1000:
                bad.append(f'{d}/{r[2]}: wav 只有 {w.stat().st_size} 字节')
            elif not float(r[1]) > 0:
                bad.append(f'{d}/{r[2]}: 秒数填了 {r[1]}')
    print(f'VOICE PACK CHECK {"FAIL" if bad else "OK"}: {len(moods)} 个骨架 / {n} 句, 问题 {len(bad)}')
    for x in bad[:10]:
        print('  !', x)
    sys.exit(1 if bad else 0)

for d in moods:
    out, files, cnt = SPINE / d / 'voice', [], defaultdict(int)
    for u in sorted(k for k, v in skel.items() if v == d):
        for seq, (mood, sec, txt, cn, conf, src) in enumerate(sorted(pool[u]), 1):
            files.append((mood, f'{mood}_{seq}_{src.stem}.wav', sec, txt, cn, u, conf, src))
            cnt[mood] += 1
    print(f'  {d}: {len(files)} 句 / {sum(f[2] for f in files):.0f}s 池, 表情 ' +
          ' '.join(f'{k} {v}' for k, v in sorted(cnt.items(), key=lambda x: -x[1])))
    if a.dry:
        continue
    out.mkdir(parents=True, exist_ok=True)
    for mood, fn, sec, txt, cn, u, conf, src in files:
        dst = out / fn
        if dst.exists():
            dst.unlink()
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    (out / MAN).write_text('\n'.join(['\t'.join(HDR)] +
                                      ['\t'.join([m, f'{s:.3f}', fn, t, c, u, cf])
                                       for m, fn, s, t, c, u, cf, _ in files]) + '\n',
                                     encoding='utf-8-sig')
    print(f'    -> {out / MAN}')

tot = sum(len(v) for v in pool.values())
print(f'VOICE PACK {"DRY" if a.dry else "OK"}: {a.slug} 进池 {tot} 句, 排除 ' +
      (', '.join(f'{k} {v}' for k, v in sorted(skip.items())) or '无') + f'; 骨架目录 {len(moods)} 个')
