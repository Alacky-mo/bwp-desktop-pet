"""用 vgmstream 把语音单元解成能双击的 wav, 并记下每句的精确时长和有没有声。

用法:
  python voice_decode.py --cat emotion                解某一类别的全部单元
  python voice_decode.py one <单元名> [<单元名>...]   只解指定单元
  python voice_decode.py --cat emotion --check        不重解, 只核对已有 wav(算时长/查静音/对估时)

产物: voice/wav/<单元>/<media id>.wav + out/voice_wav.tsv
      (unit/序号/media/声部分组/采样率/精确秒/估秒/误差/RMS/有声帧占比/文件)

现场事实(2026-10-28 实测): vgmstream r2168 能直接开 Wwise 一代 bank —— `-s 1 -S 0` 把包里每条
media 解成一个 wav, `?n` 通配符给出的是 media id(和包外散装 .wem 同名), 编码报 "Custom Vorbis"。
所以不再需要先把 media 从 DATA 段里搬出来。
"""
import subprocess
import sys
import wave
from pathlib import Path
from statistics import median

import numpy as np

from voice_bnk import Bank, unit_parts

ROOT = Path(__file__).resolve().parent
RAW = ROOT / 'voice' / 'raw'
WAV = ROOT / 'voice' / 'wav'
TSV = ROOT / 'out' / 'voice_wav.tsv'
VGS = Path.home() / 'AppData' / 'Local' / 'Tools' / 'vgmstream' / 'ex' / 'vgmstream-cli.exe'


def banks(argv):
    """按 --cat / one <单元名> 选出要处理的单元包(共享包 vo_emotion 之类不算单元, 跳过)。"""
    if argv[:1] == ['one']:
        want = {a if a.endswith('.bnk') else a + '.bnk' for a in argv[1:]}
        miss = sorted(a for a in want if not (RAW / a).exists())
        if miss:
            sys.exit(f"voice/raw 里没有这些单元: {', '.join(miss)[:300]}")
        return sorted(RAW / a for a in want)
    cat = argv[argv.index('--cat') + 1] if '--cat' in argv else None
    got = sorted(p for p in RAW.glob('*.bnk') if unit_parts(p.stem))
    return [p for p in got if not cat or p.stem.startswith(f'vo_{cat}')]


def decode(bank, dst):
    """一个包解成每 media 一个 wav; 包里指到外部 media 的, 改解 raw/<media id>.wem。"""
    dst.mkdir(parents=True, exist_ok=True)
    bk = Bank(bank)
    got = set()
    if bk.media:
        r = subprocess.run([str(VGS), '-i', '-s', '1', '-S', '0', '-o', f'{dst}/?n.wav', str(bank)],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        got = {int(p.stem) for p in dst.glob('*.wav') if p.stem.isdigit()}
        if not got:
            print(f'  !{bank.stem} 没解出任何 wav rc={r.returncode} :: {(r.stdout or r.stderr).strip()[-160:]}')
            return []
    want = set(bk.media) | {c['media'] for c in bk.clips() if not c['media_in_bank']}
    for mid in sorted(want - got):
        src = RAW / f'{mid}.wem'
        if not src.exists():
            continue
        subprocess.run([str(VGS), '-i', '-o', f'{dst}/{mid}.wav', str(src)],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return bk.clips()


def measure(path):
    """读 wav 拿精确时长, 再用能量判断是不是真有声音。

    表情语音中位只有 1.07 秒、最短 0.17 秒, 喊完就剩静音尾巴, 所以「有声帧占比」不能单独当判据
    (实测有 19 条占比<15% 但峰值 0.15~0.97, 是真声音); 判「解空了」要看峰值。
    """
    with wave.open(str(path)) as w:
        sr, n = w.getframerate(), w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype='<i2').astype(np.float32) / 32768.0
    win = max(1, int(sr * 0.05))
    grid = a[:len(a) // win * win].reshape(-1, win)
    speech = float((np.sqrt((grid * grid).mean(1)) > 0.01).mean()) if len(grid) else 0.0
    return sr, n / sr, float(np.sqrt((a * a).mean())), speech, float(np.abs(a).max())


def est_seconds(bk, mid):
    for c in bk.clips():
        if c['media'] == mid and c['info']:
            return c['info']['data'] / c['info']['byterate']
    return None


rows, problems = [], []
argv = [a for a in sys.argv[1:]]
paths = banks(argv)
if not paths:
    print(__doc__)
    sys.exit(2)
check_only = '--check' in argv

for i, bank in enumerate(paths, 1):
    dst = WAV / bank.stem
    bk = Bank(bank)
    if not check_only:
        decode(bank, dst)
    order = {}
    for c in bk.clips():
        order.setdefault(c['media'], (len(order) + 1, c['parent']))
    files = sorted(p for p in dst.glob('*.wav')) if dst.exists() else []
    for f in files:
        mid = int(f.stem) if f.stem.isdigit() else 0
        sr, sec, rms, speech, peak = measure(f)
        e = est_seconds(bk, mid)
        err = abs(sec - e) / sec if e else None
        seq, parent = order.get(mid, ('', ''))
        rows.append([bank.stem, seq, mid, parent, sr, round(sec, 3), round(e or 0, 3),
                     '' if err is None else round(err, 3), round(rms, 4), round(speech, 3),
                     round(peak, 3), str(f.relative_to(ROOT.parent))])
        if peak < 0.05:
            problems.append(f'{bank.stem}/{f.name} 峰值只有 {peak:.3f}, 疑似解空/纯静音')
        if err is not None and err > 0.2:
            problems.append(f'{bank.stem}/{f.name} 估时偏差 {err:.0%}(估 {e:.2f}s 实 {sec:.2f}s)')
    want = set(order)
    if len(files) != len(want):
        problems.append(f'{bank.stem}: 该有 {len(want)} 条 media, 解出 {len(files)} 个 wav '
                        f'(缺 {sorted(want - {int(p.stem) for p in files if p.stem.isdigit()})[:5]})')
    if i % 20 == 0 or i == len(paths):
        print(f'  {i:4}/{len(paths)} {bank.stem}')

TSV.parent.mkdir(parents=True, exist_ok=True)
hdr = ['unit', '序号', 'media_id', '分组', '采样率', '精确秒', '估秒', '估时误差', 'RMS', '有声帧占比', '峰值', '文件']
TSV.write_text('\t'.join(hdr) + '\n' + '\n'.join('\t'.join(str(c) for c in r) for r in rows) + '\n',
               encoding='utf-8')
tot = sum(r[5] for r in rows)
errs = [r[7] for r in rows if r[7] != '']
dead = sum(1 for r in rows if r[10] < 0.05)
print(f'VOICE DECODE {"OK" if not problems else f"注意 {len(problems)} 项"}: {len(paths)} 个单元 -> '
      f'{len(rows):,} 个 wav, 合计 {tot/3600:.2f} 小时(估 {sum(r[6] for r in rows)/3600:.2f} 小时)')
if errs:
    print(f'  估时误差 中位 {median(errs):.1%} / 最大 {max(errs):.1%}(超过 20% 的 {sum(1 for e in errs if e > 0.2)} 条)')
print(f'  疑似解空的(峰值<0.05): {dead} 条')
for p in problems[:15]:
    print('  !', p)
print(f'  清单 {TSV}')
