"""按「耳朵听到的那一句」反查素材: 拿目标日语句和每条 wav 的转写做相似度，排出最像的几条。

用法(--phrase 给「你听到的那一句」原文，可重复给多句；原文是游戏语音转写，按裁定不进版本库，
      本机对照读未跟踪的 out/voice_lines.tsv):
  python voice_probe.py --cached --cat emotion --phrase <目标句>              已在的转写里全库找(秒出，先走这条)
  python voice_probe.py --unit vo_emotion_167_buzhihuo --phrase <目标句> --phrase <同一句的另一种听法>
  python voice_probe.py --unit vo_emotion_103_buzhihuo --only-empty          只测没转出字的那几条
  python voice_probe.py --cat emotion --phrase <目标句词干> --top 20           全表情里重跑转写(慢，一条两次调用)

产物只有 stdout 排名表(相似度 / 秒 / 无提示转写 / 带提示转写 / wav 路径)——
这是「拿已知句子找素材」的一次性比对，要落盘的结论得并进 voice_lines.tsv 才算数。
相似度只当筛子用：同一个意思各角色词尾不一样(同一形容词至少见过四种收法，跨五个角色)，
命中了要按 wav 路径去听才能定。

为什么不带 --cached 时要跑两条转写: whisper 喂 initial_prompt 会把提示词**幻听**进本来没词的音频里，
只信带提示那条就会误报。所以判据是「无提示那条自己就出了相近的词」;
无提示出空、只有带提示才出词的，一律标「可疑」，交人耳定。
相似度用 voice_norm.py 那套规范化(和规则表同一个口径)后取字符级比值。
"""
import argparse
import difflib
import os
import sys
import wave
from pathlib import Path

from voice_norm import norm

ROOT = Path(__file__).resolve().parent
WAVTSV = ROOT / 'out' / 'voice_wav.tsv'
LINESSV = ROOT / 'out' / 'voice_lines.tsv'

ap = argparse.ArgumentParser()
ap.add_argument('--unit', action='append', default=[], help='可以重复给')
ap.add_argument('--cat', help='整个类别都扫(慢)')
ap.add_argument('--phrase', action='append', default=[], help='目标日语句，可以重复给')
ap.add_argument('--only-empty', action='store_true', help='只测 voice_lines.tsv 里空文本的那些条')
ap.add_argument('--cached', action='store_true', help='不重跑 ASR，直接拿 voice_lines.tsv 里已有的转写比(快，全库扫)')
ap.add_argument('--model', default='small')
ap.add_argument('--top', type=int, default=6)
a = ap.parse_args()
if not (a.unit or a.cat) or not (a.phrase or a.only_empty):
    print(__doc__)
    sys.exit(2)

# wav 路径查表: (unit, media_id) -> (秒, 峰值, 绝对路径)
wav = {}
for i, f in enumerate((l.rstrip('\n').split('\t') for l in open(WAVTSV, encoding='utf-8'))):
    if i and len(f) >= 12:
        wav[(f[0], f[2])] = (float(f[5]), float(f[10]), ROOT.parent / f[11])

def want(unit):
    return (not a.unit or unit in a.unit) and (not a.cat or unit.startswith(f'vo_{a.cat}'))


def score(raw, text):
    return difflib.SequenceMatcher(None, norm(raw), norm(text)).ratio()


# --cached: 只比 voice_lines.tsv 里已有的转写，不加载模型——转写跑到哪就能找到哪，先筛后听。
if a.cached:
    if not a.phrase:
        sys.exit('--cached 要配 --phrase')
    hits = []
    for i, f in enumerate((l.rstrip('\n').split('\t') for l in open(LINESSV, encoding='utf-8'))):
        if i == 0 or len(f) < 8 or not f[4] or not want(f[0]):
            continue
        sec = wav.get((f[0], f[2]), (float(f[3]), 0.0, None))[0]
        hits.append((f[0], f[2], f[4], sec))
    print(f'VOICE PROBE(cached): 已转写 {len(hits):,} 句(不重跑 ASR)')
    for raw in a.phrase:
        r = sorted(((score(raw, t), u, m, t, s) for u, m, t, s in hits), reverse=True)[:a.top]
        print(f'\n=== 目标「{raw}」最像的 {len(r)} 条 ===')
        for s, u, m, t, sec in r:
            print(f'  {s:4.2f} 「{t}」 {sec:5.2f}s  {u}/{m}.wav')
    sys.exit(0)

silent = set()
if a.only_empty:
    for f in (l.rstrip('\n').split('\t') for l in open(LINESSV, encoding='utf-8')):
        if len(f) >= 5 and not f[4] and want(f[0]):
            silent.add((f[0], f[2]))

clips = [(u, m, sec, peak, p) for (u, m), (sec, peak, p) in wav.items()
         if want(u) and (not a.only_empty or (u, m) in silent) and p.exists()]
if not clips:
    sys.exit('没有要测的 wav(先跑 voice_decode.py；--only-empty 要 voice_lines.tsv 里有空文本行)')

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ['HF_HUB_DISABLE_XET'] = '1'
import numpy as np
from faster_whisper import WhisperModel

SR, model = 16000, WhisperModel(a.model, device='cpu', compute_type='int8')
PAD = np.zeros(int(SR * 0.3), np.float32)


def buf16k(path):
    """读 wav → 单声道 16k，前后各垫 0.3 秒静音(直接喂整条短句容易整段幻听)。"""
    with wave.open(str(path)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(1).astype(np.float32)
    if sr != SR:
        x = np.interp(np.linspace(0, len(x) - 1, max(1, int(len(x) * SR / sr))), np.arange(len(x)), x).astype(np.float32)
    return np.concatenate([PAD, x, PAD])


def say(buf, prompt=None):
    kw = dict(beam_size=5, condition_on_previous_text=False, no_speech_threshold=0.9)
    if prompt:
        kw['initial_prompt'] = prompt
    segs, _ = model.transcribe(buf, **kw)
    return ''.join(s.text.strip() for s in segs)


print(f'VOICE PROBE: {len(clips)} 条候选，目标 {a.phrase or "(只列无提示转写)"} (模型 {a.model}, cpu int8, 每条两次调用)')
cache = {}
for unit, media, sec, peak, path in clips:
    b = buf16k(path)
    cache[(unit, media)] = (sec, peak, say(b), path)

if not a.phrase:
    for (unit, media), (sec, peak, free, path) in sorted(cache.items()):
        print(f'  {sec:5.2f}s 峰值{peak:.2f}  {free or "(空)":<28} {unit}/{media}.wav')
else:
    for raw in a.phrase:
        scored = []
        for (unit, media), (sec, peak, free, path) in cache.items():
            biased = say(buf16k(path), prompt=raw)
            r = max(score(raw, x) for x in (free, biased) if x)
            flag = '' if free else (' 可疑:只在提示下出词' if biased else ' 两次都空')
            scored.append((r, sec, peak, free, biased, flag, unit, media))
        scored.sort(key=lambda x: (-x[0], x[1]))
        print(f'\n=== 目标「{raw}」最像的 {min(a.top, len(scored))} 条 ===')
        for r, sec, peak, free, biased, flag, unit, media in scored[:a.top]:
            print(f'  {r:4.2f}  {sec:5.2f}s 峰值{peak:.2f}  无提示={free or "(空)":<20} 带提示={biased or "-":<20}{flag}  {unit}/{media}.wav')
