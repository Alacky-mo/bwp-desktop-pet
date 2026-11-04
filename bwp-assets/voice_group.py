"""把逐句转写按「Wwise 分组容器」摊开看, 用来验「同一个容器里的句子是不是同一情绪」。

用法:
  python voice_group.py                      全部单元, 只打汇总(每组句数分布、组内文本是否互相同义)
  python voice_group.py --unit vo_emotion_103_buzhihuo   摊开一个单元逐组看文本
  python voice_group.py --sample 6           随机摊开 6 个单元的组, 肉眼判「一组=一个表情」成不成立

结论(2026-10-29 实测, 这条假设已经死了, 留着脚本是为了别处还能摊名册):
  139 个表情单元一共只有 236 个容器组 —— 一个单元基本就一个组(vo_emotion_103_buzhihuo 的 22 句全在
  896183464 里), 容器就是「这个单元的播放列表」本身, 不区分情绪。
  能区分情绪的是**表情骨架自己的动画名**: 名册(out/voice_roster.tsv「表情动画」列)里 98 个表情单元
  对上了骨架, 动画名高度收敛在 surprise/sad/idle/thinking/happy(+smile/angry/serious) 这 5~8 个槽位。
  所以句↔表情只能靠**读转写做语义判断**, 结构上没有现成的对应。
"""
import argparse
import collections
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WAV_TSV = ROOT / 'out' / 'voice_wav.tsv'
LINE_TSV = ROOT / 'out' / 'voice_lines.tsv'

ap = argparse.ArgumentParser()
ap.add_argument('--unit', help='摊开这个单元的每一组')
ap.add_argument('--sample', type=int, default=0, help='随机摊开 N 个单元看组')
a = ap.parse_args()

if not WAV_TSV.exists():
    sys.exit('没有 out/voice_wav.tsv, 先跑 voice_decode.py --cat emotion')
if not LINE_TSV.exists():
    sys.exit('没有 out/voice_lines.tsv, 先跑 voice_asr.py')

# voice_asr.py 每跑完一个单元就整表重写, 读的时候先拷一份, 免得撞上写了一半
tmp = ROOT / 'out' / '_group_snapshot.tsv'
shutil.copyfile(LINE_TSV, tmp)

grp_of, txt_of = {}, {}
with open(WAV_TSV, encoding='utf-8') as fh:
    head = fh.readline().rstrip('\n').split('\t')
    for line in fh:
        r = dict(zip(head, line.rstrip('\n').split('\t')))
        grp_of[(r['unit'], r['media_id'])] = r['分组']
with open(tmp, encoding='utf-8') as fh:
    head = fh.readline().rstrip('\n').split('\t')
    for line in fh:
        r = dict(zip(head, line.rstrip('\n').split('\t')))
        txt_of[(r['unit'], r['media_id'])] = (int(r['序号'] or 0), r['文本'], r['置信'], r['精确秒'])
tmp.unlink()

by_unit = collections.defaultdict(lambda: collections.defaultdict(list))
for (unit, media), g in grp_of.items():
    seq, txt, conf, sec = txt_of.get((unit, media), (0, '', '', ''))
    by_unit[unit][g].append((seq, media, txt, conf, sec))

sizes = [len(v) for u in by_unit.values() for v in u.values()]
units_done = sorted(by_unit)
print(f'VOICE GROUP: {len(units_done)} 个单元 / {len(sizes)} 个容器组, '
      f'每组句数 中位 {sorted(sizes)[len(sizes)//2] if sizes else 0} / 最多 {max(sizes) if sizes else 0}, '
      f'分布 {dict(sorted(collections.Counter(sizes).items()))}')

# 组内是不是「同一句的不同演绎」: 全同文本的组占比; 以及空文本比例
same, nonempty_groups, empty = 0, 0, 0
for u in by_unit.values():
    for g in u.values():
        t = [x[2] for x in g]
        empty += sum(1 for x in t if not x)
        if any(t):
            nonempty_groups += 1
            if len({x for x in t if x}) == 1 and len(g) > 1:
                same += 1
print(f'  有字的组 {nonempty_groups} 个, 其中组内文本完全相同的 {same} 个; '
      f'空文本句 {empty}({empty/max(sum(sizes),1):.0%})')

show = [a.unit] if a.unit else (units_done[:a.sample] if a.sample else [])
if not show:
    print('  (只看汇总; --unit <单元名> 或 --sample N 摊开看组内文本)')
for unit in show:
    print(f'\n=== {unit} ({len(by_unit[unit])} 组 / {sum(len(v) for v in by_unit[unit].values())} 句) ===')
    for g, items in sorted(by_unit[unit].items(), key=lambda kv: min(r[0] for r in kv[1])):
        items.sort()
        print(f'  组 {g}({len(items)} 句): ' + ' ┃ '.join(
            f'#{sq} [{cf or "-"}] {tx or "(无字)"}' for sq, _, tx, cf, _ in items))
