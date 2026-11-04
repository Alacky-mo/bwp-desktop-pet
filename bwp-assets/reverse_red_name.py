#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 desk 第 26 层(对外名字链)的 bug 一条条放回去，验它会不会红。

这层管的是两头: 「该换的」(exe/dll 名、中文显示名、托盘 tooltip、关于窗标题、安装包字符串、工具侧的进程名)
和「不该换的」(数据目录名、单实例 Mutex 名、注册表自启值名) —— 所以 bug 也分两组打:
一组把名字改回旧的/改歪，一组把内层那半跟着界面名字改掉(裁定里明令禁止的那一半)。

每条 bug: 备份字节 → 打补丁 → 单独建到 deskspine/DeskSpine/out/reverse-build/ → 跑 desk → 还原。
建之前先把 OUT 里两个名字的产物都删掉，不然上一条 bug 留下的旧名 dll 会被当成这一条的结果(假绿)。
谁红了、整关有没有 DESK FAIL，全记进 bwp-assets/out/reverse_name.log。最后一步是「全部还原后复绿」。

跑法: python bwp-assets/reverse_red_name.py [名字前缀...]
"""
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
S = REPO / "deskspine" / "DeskSpine"
OUT = S / "out" / "reverse-build" / "Release" / "net8.0-windows" / "win-x64"
HARNESS = REPO / "bwp-assets" / "animator-test" / "bin" / "Release" / "net8.0-windows" / "bwp-animator-test.exe"
LOG = REPO / "bwp-assets" / "out" / "reverse_name.log"

PROG = S / "src" / "Program.cs"          # GBK 无 BOM: 锚只用 ASCII，中文按 gbk 编
CS = S / "src" / "ConfigForm.cs"         # 同上
DES = S / "src" / "ConfigForm.Designer.cs"
ABOUT = S / "src" / "AboutForm.cs"
CFG = S / "src" / "ConfigForm.cs"          # GBK 无 BOM
CSPROJ = S / "DeskSpine.csproj"
VDP = REPO / "deskspine" / "Setup" / "Setup.vdproj"
TOOL = REPO / "bwp-assets" / "check-pet-window.ps1"
LAYER_MARK = "对外名字链"
RED = "    ✗ "


def gbk(s):
    return s.encode("gbk")


def u(s):
    """vdproj/Designer/csproj 是 UTF-8, Program.cs / ConfigForm.cs 是 GBK —— 锚点按各自家的编码编"""
    return s.encode("utf-8")


# 每条 bug: 名字 / 期望变红的判据关键词 / [(路径, 旧, 新, 期望命中次数)]
BUGS = [
    ("a-csproj 里 AssemblyName 整条没了(根本没改名)",
     ["装配出来的就叫", "同目录那个原生壳 exe", "AssemblyName 就是它"],
     [(CSPROJ, b"        <AssemblyName>BwpDesktopPet</AssemblyName>\r\n", b"", 1)]),
    ("b-csproj 的 AssemblyName 退回旧名",
     ["装配出来的就叫", "同目录那个原生壳 exe", "AssemblyName 就是它"],
     [(CSPROJ, b"<AssemblyName>BwpDesktopPet</AssemblyName>", b"<AssemblyName>DeskSpine</AssemblyName>", 1)]),
    ("c-显示名常量改了但界面上那几个字跟着变歪",
     ["DisplayName 是那几个中文", "托盘 tooltip", "关于窗, 标题是"],
     [(PROG, gbk('DisplayName = "百闻牌桌宠";'), gbk('DisplayName = "桌宠";'), 1)]),
    ("d-托盘 tooltip 还是旧程序名(设置窗那一处没接)",
     ["托盘 tooltip"],
     [(DES, b"notifyIcon.Text = Program.DisplayName;", b"notifyIcon.Text = Program.ProgramName;", 1)]),
    ("e-关于窗标题用 ProgramName(那半没接)",
     ["关于窗, 标题是"],
     [(ABOUT, b"{Program.DisplayName}", b"{Program.ProgramName}", 1)]),
    ("f-单实例 Mutex 名跟着界面名字改了(第二个实例起得来)",
     ["「new Mutex"],
     [(PROG, b"new Mutex(true, ProgramName", b"new Mutex(true, DisplayName", 1)]),
    ("g-数据目录名跟着界面名字改了(用户已有配置就丢了)",
     ["LocalAppdataDirectory", "数据目录仍是"],
     [(PROG, b"Path.Combine(SystemValue.LocalAppdataDirectory, ProgramName)",
       b"Path.Combine(SystemValue.LocalAppdataDirectory, DisplayName)", 1)]),
    ("h-开机自启那条值名跟着界面名字改了(旧开关变孤儿)",
     ["runKey.SetValue"],
     [(PROG, b"runKey.SetValue(ProgramName", b"runKey.SetValue(DisplayName", 1)]),
    ("i-重复启动那个框的标题退回旧程序名",
     ["重复启动那个框"],
     [(PROG, b", DisplayName, MessageBoxButtons.OK", b", ProgramName, MessageBoxButtons.OK", 1)]),
    ("j-安装包 ProductName 退回旧名",
     ["四条对外字符串", "旧名清干净"],
     [(VDP, b'"ProductName" = "8:BwpDesktopPet"', b'"ProductName" = "8:DeskSpine"', 1)]),
    ("k-安装包那两条快捷方式名退回旧名",
     ["四条对外字符串", "旧名清干净"],
     [(VDP, u('"Name" = "8:百闻牌桌宠"'), b'"Name" = "8:DeskSpine"', 2)]),
    ("l-量窗那把尺子还按旧进程名找人(桌宠在跑也说没找到)",
     ["那几把尺子"],
     [(TOOL, b"Get-Process BwpDesktopPet", b"Get-Process DeskSpine", 1)]),
    ("m-设置窗那两弹错误框的标题退回旧程序名",
     ["两弹错误框"],
     [(CFG, b", Program.DisplayName, MessageBoxButtons", b", Program.ProgramName, MessageBoxButtons", 2)]),
]


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def clean_assemblies():
    """上一条 bug 留下的另一种名字的产物不许冒充这一条的结果"""
    for stem in ("BwpDesktopPet", "DeskSpine"):
        for ext in (".dll", ".exe", ".pdb", ".runtimeconfig.json"):
            f = OUT / f"{stem}{ext}"
            if f.exists():
                f.unlink()


def build():
    return run(["dotnet", "build", str(S / "DeskSpine.csproj"), "-c", "Release",
                "-p", "BaseOutputPath=out/reverse-build/", "-v", "q"], S)


def desk():
    dll = next((p for p in (OUT / "BwpDesktopPet.dll", OUT / "DeskSpine.dll") if p.exists()), None)
    assert dll is not None, "建完了却一个 dll 都没有"
    _, out = run([str(HARNESS), "desk", str(dll)], HARNESS.parent)
    lines = out.splitlines()
    at = next((i for i, l in enumerate(lines) if LAYER_MARK in l), None)
    reds = []
    if at is not None:
        for l in lines[at + 1:]:
            if l.startswith(RED):
                reds.append(l[len(RED):].strip())
            else:
                break
    marker = next((l.strip() for l in lines if l.strip() in ("DESK OK", "DESK FAIL")), "(没跑到终点)")
    return marker, reds, out


def patch(path, old, new, want):
    data = path.read_bytes()
    hits = data.count(old)
    assert hits == want, f"{path.name}: 锚点命中 {hits} 次(要 {want} 次)"
    path.write_bytes(data.replace(old, new) if new else data.replace(old, b""))


def main():
    picks = sys.argv[1:]
    bugs = [b for b in BUGS if not picks or any(b[0].startswith(p) for p in picks)]
    assert HARNESS.exists(), "先建 harness: dotnet build bwp-assets/animator-test -c Release"
    backups = {}

    def backup(p):
        backups.setdefault(p, p.read_bytes())

    def restore():
        for p, b in backups.items():
            p.write_bytes(b)
        backups.clear()

    report = []
    try:
        for name, want, patches in bugs:
            for (p, old, new, hits) in patches:
                backup(p)
                patch(p, old, new, hits)
            clean_assemblies()
            code, out = build()
            if code != 0:
                restore()
                report.append(f"{name}: ✗ 补丁没编过，这一条没法验\n{out[-1200:]}")
                continue
            marker, reds, _ = desk()
            missed = [w for w in want if not any(w in r for r in reds)]
            ok = marker == "DESK FAIL" and not missed
            report.append(
                f"{name}: {'红得对' if ok else '不对'}  整关={marker}  "
                f"想红的 {len(want)} 条里红了 {len(want) - len(missed)} 条"
                + (f"  ★没红: {missed}" if missed else "")
                + f"\n    实际红 {len(reds)} 条:\n" + "\n".join(f"      - {r}" for r in reds))
            restore()

        clean_assemblies()
        code, out = build()
        marker = reds = None
        if code == 0:
            marker, reds, _ = desk()
        report.append(f"全部还原后复跑: 建 {code}  整关={marker}  第 26 层还红 {len(reds or [])} 条"
                      + "\n".join(f"      - {r}" for r in (reds or [])))
    finally:
        restore()
        # 半途炸了也要把已经跑出来的那几条留下, 不然连「哪一条把脚本撞倒了」都看不到
        log = LOG if not picks else LOG.with_name("reverse_name_part.log")   # 挑着跑不许把整份记录冲掉
        log.write_text("\n\n".join(report) + "\n", encoding="utf-8")

    print(f"RED VERIFY DONE bugs={len(bugs)} log={LOG if not picks else LOG.with_name('reverse_name_part.log')}")
    for line in report:
        print("  " + line.splitlines()[0])


if __name__ == "__main__":
    main()
