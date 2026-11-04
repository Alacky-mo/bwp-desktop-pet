"""把逐句转写按语义规则归到表情骨架实际有的动画上，出联系表和能双击的试听目录。

用法:
  python voice_emo_map.py                    出 out/voice_emo_sheet.tsv + 终端汇总
  python voice_emo_map.py --audition         再把每句 wav 硬链成 <角色>/<表情>_<序号>_<原文>.wav 好试听
  python voice_emo_map.py --unit vo_emotion_103_buzhihuo   只看一个角色

输入: out/voice_lines.tsv(转写) + out/voice_roster.tsv(角色↔骨架↔动画名单) + voice_emo_rules.tsv(判断)
产物: out/voice_emo_sheet.tsv(中文名/拼音/单元/序号/秒/原文/中文意思/规则表情/实际动画/有无/置信/wav)

为什么长这样: 包里读不出「这句属于哪个表情」(见 docs/理解地图.md)，唯一的判断来源是**读懂这句日语**，
所以判断写在 voice_emo_rules.tsv 里、脚本只负责套用和验收 —— 改规则重跑就行，不是一次性手抄。
表情标签不许自创：只能用该角色骨架真有的那些动画名，规则给了它没有的就按 FALLBACK 退，退到 idle 为止。
"""
import argparse
import collections
import os
import re
import shutil
import sys
from pathlib import Path

from voice_norm import norm

ROOT = Path(__file__).resolve().parent
LINES = ROOT / 'out' / 'voice_lines.tsv'
ROSTER = ROOT / 'out' / 'voice_roster.tsv'
RULES = ROOT / 'voice_emo_rules.tsv'
WAVTSV = ROOT / 'out' / 'voice_wav.tsv'
OUT = ROOT / 'out' / 'voice_emo_sheet.tsv'
AUDITION = ROOT / 'voice' / 'audition'

# 规则给的动画该角色没有时往哪儿退，最后一档必须是所有骨架都有的 idle。
# angry 只许退 serious 或 idle —— 早先让它退 surprise，把「哼」那一类配成了惊讶，语义直接反了。
FALLBACK = {'surprise': ['thinking', 'idle'], 'sad': ['idle'], 'happy': ['smile', 'idle'],
            'smile': ['happy', 'idle'], 'angry': ['serious', 'idle'],
            'serious': ['thinking', 'idle'], 'thinking': ['idle'], 'idle': ['idle']}

def tsv(path, need):
    with open(path, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        miss = [c for c in need if c not in head]
        if miss:
            sys.exit(f'{path.name} 少了列 {miss}')
        rows = [dict(zip(head, line.rstrip('\n').split('\t'))) for line in fh if line.strip()]
    return rows


def load_rules():
    out = []
    for f in (l.rstrip('\n').split('\t') for l in open(RULES, encoding='utf-8')
              if l.strip() and not l.startswith('#')):
        if len(f) < 4:
            sys.exit(f'voice_emo_rules.tsv 这一行列数不对(要 匹配方式/模式/表情/中文意思): {f}')
        if f[0] not in ('exact', 'contains'):
            sys.exit(f'匹配方式只认 exact/contains，写了 {f[0]!r}')
        out.append((f[0], norm(f[1]), f[2], f[3]))
    if not out:
        sys.exit('voice_emo_rules.tsv 是空的，没法配')
    return out


ap = argparse.ArgumentParser()
ap.add_argument('--audition', action='store_true', help='硬链 wav 出可试听目录')
ap.add_argument('--unit', help='只看这个单元')
a = ap.parse_args()
for p in (LINES, ROSTER, RULES, WAVTSV):
    if not p.exists():
        sys.exit(f'缺 {p.name}，先跑对应的上游脚本')

rules = load_rules()
wav_of = {f'{r["unit"]}/{r["media_id"]}': r['文件'] for r in tsv(WAVTSV, ['unit', 'media_id', '文件'])}
cast = {}
for r in tsv(ROSTER, ['unit', 'slug', '中文名', '表情动画', '对上方式']):
    cast[r['unit']] = (r['中文名'], r['slug'], [x for x in r['表情动画'].split(',') if x], r['对上方式'])

lines = [r for r in tsv(LINES, ['unit', '序号', 'media_id', '精确秒', '文本', '置信'])
         if not a.unit or r['unit'] == a.unit]
if not lines:
    sys.exit('转写表是空的(voice_asr.py 还在跑就先等它落几个单元)')

rows, unmatched = [], collections.Counter()
for r in sorted(lines, key=lambda x: (x['unit'], int(x['序号'] or 0))):
    key, txt = norm(r['文本']), r['文本']
    cn, slug, anims, _ = cast.get(r['unit'], ('', r['unit'], [], ''))
    rel = wav_of.get(f'{r["unit"]}/{r["media_id"]}', '')
    if not txt:
        # 没转出字的也留在表里: 表情语音里 26% 是笑/气声这类非台词短句,
        # 悄悄丢掉等于素材凭空少一层, 该不该用要用户听了算
        rows.append(dict(who=cn or '待确认', slug=slug, unit=r['unit'], seq=r['序号'], sec=r['精确秒'],
                         txt='(没出字)', mean='', want='', pick='要听', fell='', how='无原文', conf=r['置信'],
                         rel=rel))
        continue
    hit = next((x for x in rules if (x[0] == 'exact' and x[1] == key) or (x[0] == 'contains' and x[1] in key)), None)
    if not hit:
        unmatched[key] += 1
        rows.append(dict(who=cn or '待确认', slug=slug, unit=r['unit'], seq=r['序号'], sec=r['精确秒'],
                         txt=txt, mean='', want='', pick='', fell='', how='没规则', conf=r['置信'], rel=rel))
        continue
    want, mean = hit[2], hit[3]
    if not anims:
        # 共享池(vo_emotion / vo_emotion_2, 名字里没拼音)没有对应骨架, 给个标签当参考, 不硬退到 idle
        pick, fell = want, '共享池无骨架'
    elif want in anims:
        pick, fell = want, ''
    else:
        pick = next((x for x in FALLBACK.get(want, ['idle']) if x in anims), '')
        fell = '退让' if pick else '退不动'
    rows.append(dict(who=cn or '待确认', slug=slug, unit=r['unit'], seq=r['序号'], sec=r['精确秒'], txt=txt,
                     mean=mean, want=want, pick=pick or '无', fell=fell, how=hit[0], conf=r['置信'], rel=rel))

hdr = ['中文名', '拼音', 'unit', '序号', 'media_id', '秒', '日语原文', '中文意思', '规则表情',
       '实际动画', '退让', '命中方式', '置信', 'wav']
keyed = sorted(lines, key=lambda x: (x['unit'], int(x['序号'] or 0)))
body = [[r['who'], r['slug'], r['unit'], r['seq'], k['media_id'], r['sec'], r['txt'], r['mean'],
         r['want'], r['pick'], r['fell'], r['how'], r['conf'], r['rel']] for r, k in zip(rows, keyed)]
OUT.write_text('\t'.join(hdr) + '\n' + '\n'.join('\t'.join(str(c) for c in b) for b in body) + '\n',
               encoding='utf-8')

got = [r for r in rows if r['want']]
silent = [r for r in rows if r['how'] == '无原文']
said = len(rows) - len(silent)
print(f'VOICE EMO MAP: {len(rows):,} 句(转出字 {said:,}, 没出字 {len(silent):,}={len(silent)/max(len(rows),1):.0%}) '
      f'-> 有规则 {len(got):,}({len(got)/max(said,1):.0%} 的有字句), 没规则 {said-len(got):,}, 规则表 {len(rules)} 条')
print('  实际动画分布: ' + ', '.join(f'{k} {v}' for k, v in sorted(
      collections.Counter(r['pick'] for r in got).items(), key=lambda x: -x[1])))
fell = collections.Counter(r['fell'] for r in got if r['fell'])
print('  退让/没动画: ' + (', '.join(f'{k} {v}' for k, v in fell.most_common()) or '没有'))
print(f'  中文名已确认的角色 {len({r["who"] for r in rows}) - (1 if any(r["who"]=="待确认" for r in rows) else 0)} 个; '
      f'待确认(只显示拼音) {sum(1 for r in rows if r["who"]=="待确认"):,} 句')
if unmatched:
    print('  没规则的高频原文(照这几个补规则):')
    for k, v in unmatched.most_common(15):
        print(f'    {v:3} × {k}')

if a.audition:
    n = miss = 0
    for r in rows:
        if not r['rel'] or not (ROOT.parent / r['rel']).exists():
            miss += 1
            continue
        d = AUDITION / r['who']
        d.mkdir(parents=True, exist_ok=True)
        tag = re.sub(r'[\\/:*?"<>|]', '', f'{r["pick"] or "无表情"}_{int(r["seq"]):02d}_{r["txt"]}')[:70]
        dst = d / f'{tag}.wav'
        if dst.exists():
            dst.unlink()
        try:
            os.link(ROOT.parent / r['rel'], dst)
        except OSError:
            shutil.copyfile(ROOT.parent / r['rel'], dst)
        n += 1
    print(f'  试听目录 {AUDITION}: 硬链 {n} 个 wav(找不到 wav 的 {miss} 个)，只本机听')
print(f'  联系表 {OUT}')
