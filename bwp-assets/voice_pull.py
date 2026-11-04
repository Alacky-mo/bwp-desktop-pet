"""语音素材在设备上的落地形态是 Wwise bank: Documents/res/wwise/<单元名>.bnk。

这个脚本只读设备, 三件事:
  python voice_pull.py ls                 列 res/wwise, 出 out/voice_wwise.tsv + 按类别统计
  python voice_pull.py pull [前缀]        把匹配的 .bnk 拉到 voice/raw/, 逐个核对字节数(默认 vo_emotion)
  python voice_pull.py wem               按 out/voice_clips_external.tsv 的 media id 拉同名 <id>.wem
                                         (传记语音的包只有 id, 音频在散装 .wem 里)

为什么语音不在 npk 里: meta/subpack_version.json 里 vo_* 全是 type=discrete,
每个单元就是 wwise 目录下的一个散装 .bnk(游戏按需下载), 所以只能从设备文件里拿。
"""
import contextlib, re, subprocess, sys, time
from pathlib import Path

MGR = r"C:\Program Files\Netease\MuMu\nx_main\MuMuManager.exe"
DOC = "/sdcard/Android/data/com.netease.yysbwp.m4399/files/netease/g97/Documents"
WWISE = f"{DOC}/res/wwise"
ROOT = Path(__file__).resolve().parent
RAW = ROOT / "voice" / "raw"
TSV = ROOT / "out" / "voice_wwise.tsv"
TMP = ROOT / "out" / "pull_tmp"


def adb(args, timeout=1800):
    """跑一次 adb。输出必须走文件: adb server 是孙子进程, 管道捕获会被它锁死(踩过 12 小时的坑)。"""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f"voice_adb_{int(time.time() * 1000)}.log"
    with open(out, "wb") as fh:
        p = subprocess.run([MGR, "adb", "-v", "0", "--cmd", args], stdout=fh,
                           stderr=subprocess.STDOUT, timeout=timeout)
    text = out.read_text(encoding="utf-8", errors="replace")
    with contextlib.suppress(OSError):   # 日志可能还被孙子攥着, 删不掉就算了
        out.unlink(missing_ok=True)
    return p.returncode, text


def listing():
    """返回 {文件名: 字节数}, 从 ls -l 的常规文件行来(目录行不算)。"""
    rc, text = adb(f"shell ls -l {WWISE}")
    if rc != 0 and not text.strip():
        sys.exit(f"adb 调用失败 rc={rc}: {text.strip()[:200]}")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"^-\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+\S+\s+\S+\s+(\S+)$", line)
        if m:
            rows[m.group(2)] = int(m.group(1))
    if not rows:
        sys.exit(f"没解析出任何文件, 检查模拟器是否开着:\n{text[:300]}")
    return rows


def category(name):
    m = re.match(r"vo_(battle|biography|emotion|street)", name)
    return m.group(1) if m else "(非语音)"


if sys.argv[1:2] == ["ls"]:
    rows = listing()
    TSV.parent.mkdir(parents=True, exist_ok=True)
    TSV.write_text("\n".join(f"{n}\t{s}" for n, s in sorted(rows.items())) + "\n", encoding="utf-8")
    vo = {n: s for n, s in rows.items() if n.startswith("vo_")}
    print(f"res/wwise 共 {len(rows)} 个文件 {sum(rows.values()):,} 字节, 其中 vo_* {len(vo)} 个 "
          f"{sum(vo.values()) / 2 ** 20:.0f} MB -> {TSV}")
    tally = {}
    for n, s in vo.items():
        c = category(n)
        t = tally.setdefault(c, [0, 0])
        t[0] += 1
        t[1] += s
    for c, (n, s) in sorted(tally.items(), key=lambda kv: -kv[1][1]):
        print(f"  {c:10} {n:4} 个  {s / 2 ** 20:7.1f} MB")
    sys.exit(0)

if sys.argv[1:2] == ["wem"]:
    ext = ROOT / "out" / "voice_clips_external.tsv"
    if not ext.exists():
        sys.exit(f"先跑 python voice_bnk.py parse voice/raw -o out/voice_clips.tsv 生成 {ext}")
    ids = sorted({r[4] for r in (l.split("\t") for l in ext.read_text(encoding="utf-8").splitlines()[1:])
                  if len(r) == 5})
    rows = listing()
    have = [f"{i}.wem" for i in ids if f"{i}.wem" in rows]
    gone = [i for i in ids if f"{i}.wem" not in rows]
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"外部 media {len(ids)} 个: 设备上有 {len(have)} 个({sum(rows[n] for n in have) / 2 ** 20:.0f} MB), "
          f"设备上找不到 {len(gone)} 个")
    bad = []
    for i, name in enumerate(have, 1):
        dst = RAW / name
        if dst.exists() and dst.stat().st_size == rows[name]:
            continue
        rc, text = adb(f"pull {WWISE}/{name} {dst}")
        got = dst.stat().st_size if dst.exists() else -1
        if rc != 0 or got != rows[name]:
            bad.append(name)
        elif i % 40 == 0 or i == len(have):
            print(f"  {i:4}/{len(have)} ={name} {got:,} OK")
    print(f"VOICE WEM {'OK' if not bad else f'FAIL({len(bad)})'}: {len(have) - len(bad)}/{len(have)} 个字节数对上 -> {RAW}")
    if gone:
        print("  设备上没有的 media id(对应那句语音没被下载过):", ", ".join(gone[:10]))
    sys.exit(0 if not bad else 1)

prefix = sys.argv[2] if sys.argv[1:2] == ["pull"] else "vo_emotion"
if sys.argv[1:2] != ["pull"]:
    print(__doc__)
    sys.exit(2)

rows = listing()
want = sorted(n for n in rows if n.startswith(prefix))
RAW.mkdir(parents=True, exist_ok=True)
print(f"拉 {len(want)} 个 {prefix}* (共 {sum(rows[n] for n in want) / 2 ** 20:.0f} MB)")
bad = []
for i, name in enumerate(want, 1):
    dst = RAW / name
    if dst.exists() and dst.stat().st_size == rows[name]:
        print(f"  {i:3}/{len(want)} ={name} 本地已有 {rows[name]:,} 字节, 跳过")
        continue
    rc, text = adb(f"pull {WWISE}/{name} {dst}")
    got = dst.stat().st_size if dst.exists() else -1
    if rc != 0 or got != rows[name]:
        bad.append(name)
        print(f"  {i:3}/{len(want)} !{name} rc={rc} 远端 {rows[name]:,} 本地 {got:,} :: {text.strip()[-120:]}")
    elif i % 20 == 0 or i == len(want):
        print(f"  {i:3}/{len(want)} ={name} {got:,} OK")
print(f"VOICE PULL {'OK' if not bad else f'FAIL({len(bad)})'}: {len(want) - len(bad)}/{len(want)} 个字节数对上 -> {RAW}")
if bad:
    print("  失败:", ", ".join(bad[:10]))
