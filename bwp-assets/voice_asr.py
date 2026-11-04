"""表情语音逐句转成文字: 一句一次喂本地 whisper, 用每句的精确时长保证「文本↔这一句」不会错位。

用法(都要用装好 faster-whisper 的那个 venv 跑):
  ~\\venvs\\asr\\Scripts\\python.exe voice_asr.py --cat emotion --per-line --limit 2   先试两个单元
  ~\\venvs\\asr\\Scripts\\python.exe voice_asr.py --cat emotion --per-line --resume      全量, 可断点续跑
  ~\\venvs\\asr\\Scripts\\python.exe voice_asr.py vo_emotion_103_buzhihuo                只跑指定单元
  公共参数: --model small|medium|base  --language ja|zh|auto  --beam 5  --limit N

产物: out/voice_lines.tsv(unit/序号/media_id/精确秒/文本/置信/段落起止/归属)
      每跑完一个单元就重写一次, --resume 认这张表里已有的单元直接跳过并原样保留其结果。

**为什么用 --per-line 而不是槽位法**: 槽位法(把整个单元拼成一条长音频再按时间戳切回每句)便宜 10 倍,
但 whisper 的时间戳有 0.2~0.5 秒系统漂移, 而表情语音一句中位才 1.07 秒 —— 同一批 wav 两种跑法对diff
过, 确实有一句被撕到邻句里。表情语音只有 1.28 小时, 逐条实测 3.6 秒/条、全量 3,835 句约 3.9 小时,
跑得完, 那就逐条: 要的是「这行字就是这句音」的绝对对应, 不省这四个小时。槽位法留在代码里做对照。
单元内每 25 句也落一次盘(最大的单元 365 句, 不然半小时看不到进度), --resume 按**句数**判单元跑没跑完,
半截的删掉重跑。

**配音是日语, 不是中文**(2026-10-28 实测): 传记旁白 vo_biography_282_liyujing 三条长句自动判定
全部 ja、置信 0.98~1.00, 转写出来是通顺日语(讲河童、头上的盘子), 按 zh 喂则一句都出不来。
所以默认 --language ja; 要转成中文意思是我在读文本时做, 不在 ASR 里做。

本机约束(2026-10-28 实测): huggingface.co 连不上(curl 返回 000), 模型走 hf-mirror.com, 且必须关掉
hf-xet(它会绕过 ENDPOINT 直连 cas-server.xethub.hf.co 拿 401); 没有 CUDA(只有 Intel Arc), CPU+int8;
素材一律本地处理, 不上传任何在线服务。
"""
import argparse
import os
import sys
import time
import wave
from collections import defaultdict
from pathlib import Path

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
# hf-xet 下载器会绕过 ENDPOINT 直连 cas-server.xethub.hf.co, 在这台机器上 401, 只能关掉走普通 HTTP
os.environ['HF_HUB_DISABLE_XET'] = '1'

import numpy as np
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parent
TSV_IN = ROOT / 'out' / 'voice_wav.tsv'
TSV_OUT = ROOT / 'out' / 'voice_lines.tsv'
SR = 16000
GAP = 0.2


def read_rows(cat):
    """out/voice_wav.tsv 按单元分组, 单元内按序号排; cat=None 表示不过滤。"""
    by = defaultdict(list)
    with open(TSV_IN, encoding='utf-8') as fh:
        head = fh.readline().rstrip('\n').split('\t')
        for line in fh:
            r = dict(zip(head, line.rstrip('\n').split('\t')))
            if cat and not r['unit'].startswith(f'vo_{cat}'):
                continue
            f = ROOT.parent / r['文件']
            if f.exists():
                by[r['unit']].append((int(r['序号'] or 0), r['media_id'], float(r['精确秒']), f))
    for u in by:
        by[u].sort()
    return by


def mono16k(path):
    """读 wav → float32 单声道 16k(线性插值降采样, 给 ASR 用够了)。"""
    with wave.open(str(path)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(np.float32) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch).mean(1).astype(np.float32)
    if sr != SR:
        idx = np.linspace(0, len(a) - 1, max(1, int(len(a) * SR / sr)))
        a = np.interp(idx, np.arange(len(a)), a).astype(np.float32)
    return a


def stitch(clips, guard=0.6, min_slot=2.4):
    """每句占一个槽位(句子本身 + 左右各 guard 秒静音), 槽位之间不相邻拼成一整条。

    为什么不直接把句子首尾相接: whisper 的词级时间戳有 0.2~0.5 秒的系统漂移, 而表情语音一句才
    1 秒上下, 相接时词会落到邻句里(实测把一句五音的词撕成「首字带长音符号 + 剩下四音」两句)。
    给每句留够静音护垫、按「槽位区间」而非句子区间来判归属, 漂移就吃在护垫里。
    代价也从逐条的 3.5 秒/条 降到约 0.35 秒/条(一次调用能装 30 秒窗口的十来个槽位)。
    """
    parts, slots, t = [], [], 0.0
    for seq, media, sec, f in clips:
        a = mono16k(f)
        slot = max(min_slot, sec + 2 * guard)
        lead = (slot - sec) / 2
        parts.append(np.concatenate([np.zeros(int(SR * lead), np.float32), a,
                                     np.zeros(int(SR * (slot - sec - lead)), np.float32)]))
        slots.append((seq, media, round(t, 3), round(t + slot, 3), round(sec, 3)))
        t += slot
    return np.concatenate(parts).astype(np.float32), slots


def assign(slots, segs, use_words=True):
    """词(或整段)落在哪个槽位就归哪句; 返回 {media: (文本, 置信, 起止, 归属)} 和掉在槽外的词数。"""
    per, loose = defaultdict(list), 0
    for s in segs:
        toks = [(w.start, w.end, w.word) for w in (s.words or [])] if (use_words and s.words) \
            else [(s.start, s.end, s.text)]
        conf = round(float(np.exp(s.avg_logprob)), 3)
        for a, b, text in toks:
            mid = (a + b) / 2
            hit = next((i for i, sl in enumerate(slots) if sl[2] <= mid < sl[3]), None)
            if hit is None:
                loose += 1
            else:
                per[hit].append((mid, text.strip(), conf))
    got = {}
    for i, items in per.items():
        items.sort()
        txt = ''.join(t for _, t, _ in items) if use_words else ' '.join(t for _, t, _ in items)
        got[slots[i][1]] = (txt.strip(), round(sum(c for _, _, c in items) / len(items), 3),
                            f'{items[0][0]:.2f}-{items[-1][0]:.2f}', '词级' if use_words else '整段')
    return got, loose


def flush(rows, extra=()):
    """落盘: 每跑完一个单元(以及单元内每 25 句)重写一次, 全量要 3 小时, 中途断了不丢已完成的。"""
    all_ = list(rows) + list(extra)
    TSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    TSV_OUT.write_text('\t'.join(HDR) + '\n' + '\n'.join('\t'.join(str(c) for c in r) for r in all_) + '\n',
                       encoding='utf-8')


HDR = ['unit', '序号', 'media_id', '精确秒', '文本', '置信', '段落起止', '归属']

ap = argparse.ArgumentParser()
ap.add_argument('units', nargs='*', help='只跑这些单元名')
ap.add_argument('--cat', help='只跑某类别, 例: emotion')
ap.add_argument('--model', default='small')
ap.add_argument('--language', default='ja', help='ja/zh/auto(按音频自己判)')
ap.add_argument('--beam', type=int, default=5)
ap.add_argument('--no-words', dest='words', action='store_false', help='退回整段归行(对照用)')
ap.add_argument('--per-line', action='store_true',
                help='一句一次调用: 归属绝对准但 2.7 秒/条, 要的就是「这行字就是这句音」')
ap.add_argument('--limit', type=int, default=0)
ap.add_argument('--resume', action='store_true', help='认 out/voice_lines.tsv, 已跑完的单元跳过')
a = ap.parse_args()

if not a.units and not a.cat:
    print(__doc__)
    sys.exit(2)

by = read_rows(a.cat if not a.units else None)
rows, done, partial = [], {}, []
if a.resume and TSV_OUT.exists():
    # 续跑认的是「这个单元已经跑完」而不是「这个单元露过脸」: 单元内部也落盘就会留半截,
    # 只按单元名跳过会永远缺一截, 所以句数对上 voice_wav.tsv 的句数才算完成, 半截的删掉重跑。
    with open(TSV_OUT, encoding='utf-8') as fh:
        fh.readline()
        for line in fh:
            if line.strip():
                r = line.rstrip('\n').split('\t')
                r = [r[i] if i < len(r) else '' for i in range(len(HDR))]
                r[1], r[3] = int(r[1] or 0), float(r[3] or 0)
                rows.append(r)
                done[r[0]] = done.get(r[0], 0) + 1
    for u, n in list(done.items()):
        want = len(by.get(u) or [])
        if not want or n < want:
            partial.append(u)
    if partial:
        rows = [r for r in rows if r[0] not in partial]
        for u in partial:
            done.pop(u, None)
    print(f'续跑: 完整 {len(done)} 个单元(跳过、原样保留), 半截或查不到句数的 {len(partial)} 个重跑'
          + (': ' + ', '.join(sorted(partial))[:200] if partial else ''))
order = [u for u in (a.units or sorted(by)) if u not in done]
if a.limit:
    order = order[:a.limit]
print(f'待跑 {len(order)} 个单元 / {sum(len(by[u]) for u in order):,} 句')

t_load = time.time()
model = WhisperModel(a.model, device='cpu', compute_type='int8')
KW = dict(language=(None if a.language == 'auto' else a.language), beam_size=a.beam,
          condition_on_previous_text=False, no_speech_threshold=0.35,
          compression_ratio_threshold=2.0)
print(f'ASR MODEL {a.model}: 加载/下载 {time.time()-t_load:.0f}s (cpu int8, language={a.language}, '
      f'beam={a.beam}, {"逐条" if a.per_line else "槽位"}法)')

PAD = np.zeros(int(SR * 0.3), np.float32)
audio_sec, wall0, loose_all, n_run, clip_run = 0.0, time.time(), 0, 0, 0
for i, unit in enumerate(order, 1):
    clips = by.get(unit)
    if not clips:
        print(f'  !{unit} 没有已解码的 wav(先跑 voice_decode.py)', flush=True)
        continue
    n_run += 1
    t0 = time.time()
    got, ur = {}, []
    if a.per_line:
        slots = []
        for k, (seq, media, sec, f) in enumerate(clips, 1):
            buf = np.concatenate([PAD, mono16k(f), PAD])
            segs, _ = model.transcribe(buf, **KW)
            segs = list(segs)
            # 逐条没有时间点可用, 置信按各段时长加权取均值, 方便后面筛幻听
            conf = round(float(np.exp(np.average([s.avg_logprob for s in segs],
                                                 weights=[max(s.end - s.start, 0.01) for s in segs]))), 3) \
                if segs else ''
            txt = ''.join(s.text.strip() for s in segs)
            got[media] = (txt, conf, '', '逐条')
            ur.append([unit, seq, media, sec, txt, conf, '', '逐条'])
            slots.append((seq, media, 0.0, 0.0, sec))
            if k % 25 == 0:  # 单元内也落盘: 一个单元最多 365 句, 盲跑半小时没法看进度
                flush(rows, ur)
                print(f'    {unit} {k}/{len(clips)} 句 ({time.time()-t0:.0f}s, '
                      f'{(time.time()-t0)/k:.2f}s/条)', flush=True)
        dur = sum(s[4] for s in slots)
    else:
        buf, slots = stitch(clips)
        segs, _ = model.transcribe(buf, word_timestamps=a.words, **KW)
        got, loose = assign(slots, list(segs), use_words=a.words)
        loose_all += loose
        dur = len(buf) / SR
        for seq, media, st, en, sec in slots:
            txt, conf, span, tag = got.get(media, ('', '', '', '没落字'))
            ur.append([unit, seq, media, sec, txt, conf, span, tag])
    audio_sec += dur
    clip_run += len(slots)
    rows += ur
    ok = sum(1 for v in got.values() if v[0])
    rate = (time.time() - t0) / len(ur)
    left = sum(len(by[u]) for u in order[i:]) / 60
    print(f'  {i:4}/{len(order)} {unit}: {len(ur)} 句 / {dur:5.1f}s -> 有字 {ok}, '
          f'掉槽外词累计 {loose_all}  ({time.time()-t0:.0f}s, {rate:.2f}s/条, '
          f'已用 {wall0 and (time.time()-wall0)/60:.0f} 分, 待跑约 {left*rate:.0f} 分)', flush=True)
    flush(rows)

flush(rows)
wall = time.time() - wall0
empty = sum(1 for r in rows if not r[4])
nohit = sum(1 for r in rows if r[7] == '没落字')
units_all = len({r[0] for r in rows})
print(f'VOICE ASR {"OK" if rows else "FAIL"}: 本次 {n_run} 个单元 -> 清单共 {units_all} 个单元 / {len(rows):,} 句, '
      f'空文本 {empty}({empty/max(len(rows),1):.0%}), 一个字都没落进来 {nohit}({nohit/max(len(rows),1):.0%}), '
      f'掉在槽外的词 {loose_all}')
if audio_sec:
    print(f'  本次音频 {audio_sec/3600:.2f} 小时, 实耗 {wall/60:.1f} 分钟 = {wall/audio_sec:.2f} 倍实时'
          + (f', {wall/max(clip_run,1):.2f}s/条' if a.per_line else ''))
print(f'  清单 {TSV_OUT}')
