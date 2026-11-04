"""从 MuMu 里只读拉 npk 包: 先看远端尺寸, 再 pull, 再核对本地字节数。

用法: python pull_npk.py <包名.npk> [...]        例: python pull_npk.py gui.npk bigtexture.npk
产物: bwp-assets/npk/<包名.npk> + 屏幕上每包一行「远端/本地/是否一致」。
只读设备, 不写不删不改游戏数据。
"""
import os, subprocess, sys, tempfile, time, contextlib
from pathlib import Path

MGR = r"C:\Program Files\Netease\MuMu\nx_main\MuMuManager.exe"
RES = "/sdcard/Android/data/com.netease.yysbwp.m4399/files/netease/g97/Documents/res"
LOCAL = Path(__file__).resolve().parent / "npk"
TMP = Path(__file__).resolve().parent / "out" / "pull_tmp"


def adb(cmd, timeout=900):
    """跑一次 adb, 输出走文件而不是管道 —— adb server 是孙子进程, 会锁死管道捕获。
    MuMu 的包装器只吃 `--cmd "<整条 adb 参数>"`, 设备号它自己插。"""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f"adb_{int(time.time()*1000)}.log"
    with open(out, "wb") as fh:
        p = subprocess.run([MGR, "adb", "-v", "0", "--cmd", cmd], stdout=fh,
                           stderr=subprocess.STDOUT, timeout=timeout)
    text = out.read_text(encoding="utf-8", errors="replace")
    # adb server 是孙子进程, 日志文件可能还被它攥着 —— 删不掉就别管, 下次换个时间戳文件名
    with contextlib.suppress(OSError):
        out.unlink(missing_ok=True)
    return p.returncode, text


def remote_size(name):
    rc, text = adb(f"shell stat -c %s {RES}/{name}")
    for token in text.split():
        if token.isdigit():
            return int(token)
    print(f"   读不到 {name} 的远端尺寸 (rc={rc}): {text.strip()[:200]}")
    return None


LOCAL.mkdir(parents=True, exist_ok=True)
names = sys.argv[1:] or ["gui.npk"]
for name in names:
    dst = LOCAL / name
    if dst.exists():
        print(f"={name} 本地已有 {dst.stat().st_size:,} 字节, 跳过拉取")
        continue
    size = remote_size(name)
    if size is None:
        print(f"={name} 设备上找不到, 跳过")
        continue
    print(f"={name} 远端 {size:,} 字节 ({size/2**20:.0f} MB), 开始拉取...")
    t0 = time.time()
    rc, text = adb(f"pull {RES}/{name} {dst}.part", timeout=7200)
    part = Path(str(dst) + ".part")
    if rc != 0 or not part.exists():
        print(f"   拉取失败 rc={rc}: {text.strip()[-300:]}")
        part.unlink(missing_ok=True)
        continue
    got = part.stat().st_size
    if got != size:
        print(f"   尺寸不符: 远端 {size:,} 本地 {got:,}, 保留 .part 供人工看")
        continue
    part.rename(dst)
    print(f"   OK {dst.name} {got:,} 字节, 用时 {time.time()-t0:.0f}s -> {dst}")
