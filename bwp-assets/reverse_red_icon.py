#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 desk 第 25 层(应用图标链)的 bug 一条条放回去，验它会不会红。

每条 bug 都: 备份字节 → 打补丁 → 单独建到 deskspine/DeskSpine/out/reverse-build/ → 跑 desk → 还原。
产物那一侧(装机那张 ico)不动源码，直接把文件挪走/改坏，跑完从源图拷回来。
谁红了、整关有没有 DESK FAIL，全记进 bwp-assets/out/reverse_icon.log。
最后一步是「全部还原之后复绿」—— 只红不绿等于脚本把仓库弄坏了。

跑法: python bwp-assets/reverse_red_icon.py
"""
import base64
import pathlib
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
S = REPO / "deskspine" / "DeskSpine"
OUT = S / "out" / "reverse-build" / "Release" / "net8.0-windows" / "win-x64"
HARNESS = REPO / "bwp-assets" / "animator-test" / "bin" / "Debug" / "net8.0-windows" / "bwp-animator-test.exe"
LOG = REPO / "bwp-assets" / "out" / "reverse_icon.log"

SRC_ICO = S / "res" / "image" / "appicon_buzhihuo.ico"
INSTALLED = OUT / "res" / "image" / "appicon_buzhihuo.ico"
CHIME = OUT / "res" / "image" / "hourlychime.ico"
LAYER_MARK = "应用图标链"
RED = "    ✗ "

CSPATH = S / "src" / "Config.cs"
APATH = S / "src" / "AppIcon.cs"

# SystemConfig 那三行(用 HourlyChime 收尾是为了和 PomodoroConfig 里同形状的那块区分开)
DAMO_DEFAULT = (b'public string? BalloonIconPath { get; set; } =\r\n'
                b'            Path.Combine(Program.ProgramResourceDirectory, @"image\\focus_damo.ico");\r\n'
                b'        public bool HourlyChime = true;')
# Config() 构造函数开头两行。上游那三组演示骨骼删掉之后名册默认值就没人了，
# 所以这一条锚点从「那行 SkelPath0 默认值」改成构造函数本身 —— bug j 要的还是「把默认值搬进构造函数」那个形状。
CTOR_ANCHOR = (b'public Config()\r\n'
               b'        {\r\n')

# 每条 bug: 名字 / 期望变红的判据关键词 / 源码补丁[ kinds: bytes|resx ] / 产物补丁[ rm|append ]
BUGS = [
    ("a-装机那张整个没了",
     ["在且六帧齐", "逐字节同一张", "真被取上", "exe 文件图标抠出来"],
     [], ("rm", INSTALLED)),
    ("b-装机那张尾巴多了一个字节",
     ["逐字节同一张"],
     [], ("append", INSTALLED)),
    ("c-探到文件也不装",
     ["真被取上"],
     [("bytes", APATH, b"if (File.Exists(path)) derived = new Icon(path);",
       b'if (File.Exists(path) && System.IO.File.Exists(@"q:\\no-such-file-xyz.ico")) derived = new Icon(path);')], None),
    ("d-没有占位兜底(干净克隆上就一枚都不挂)",
     ["退回占位"],
     [("bytes", APATH, b"return derived ?? placeholder;", b"return derived;")], None),
    ("e-标题栏那一处没接(只有托盘换了)",
     ["ConfigForm.cs 里"],
     [("bytes", S / "src" / "ConfigForm.cs",
       b'Icon = AppIcon.Resolve((Icon?)resources.GetObject("$this.Icon"));',
       b'Icon = (Icon?)resources.GetObject("$this.Icon");')], None),
    ("f-衍生图塞进了 resx(版权件进仓库)",
     ["没有任何一枚 icon", "占位就是上游"],
     [("resx", S / "src" / "ConfigForm.resx")], None),
    ("g-gitignore 那一行没了",
     ["gitignore 挡着"],
     [("bytes", REPO / "deskspine" / ".gitignore",
       b"DeskSpine/res/image/appicon_buzhihuo.ico\r\n", b"")], None),
    ("h-exe 图标退回上游那张(条件 ApplicationIcon 没了)",
     ["两条条件 ApplicationIcon", "exe 文件图标抠出来"],
     [("bytes", S / "DeskSpine.csproj",
       b"""        <ApplicationIcon Condition="Exists('res\\image\\appicon_buzhihuo.ico')">res\\image\\appicon_buzhihuo.ico</ApplicationIcon>\r\n"""
       b"""        <ApplicationIcon Condition="!Exists('res\\image\\appicon_buzhihuo.ico')">appicon_dark.ico</ApplicationIcon>""",
       b"""        <ApplicationIcon>appicon_dark.ico</ApplicationIcon>""")], None),
    ("i-报时默认还是旧的那颗钟",
     ["报时那颗默认"],
     [("bytes", CSPATH, DAMO_DEFAULT,
       DAMO_DEFAULT.replace(b"focus_damo.ico", b"hourlychime.ico"))], None),
    ("j-默认值搬回 Config() 构造函数(Load 整段换掉就冲没)",
     ["报时那颗默认", "Config.cs 里"],
     [("bytes", CSPATH, DAMO_DEFAULT,
       b'public string? BalloonIconPath { get; set; }\r\n'
       b'        public bool HourlyChime = true;'),
      ("bytes", CSPATH, CTOR_ANCHOR,
       CTOR_ANCHOR + b'\r\n            SystemConfig.BalloonIconPath = Path.Combine(Program.ProgramResourceDirectory,'
                     b' @"image\\focus_damo.ico");')], None),
    ("k-hourlychime.ico 不装机了(用户手动选不回去)",
     ["旧的 hourlychime.ico"],
     [], ("rm", CHIME)),
    ("l-报时那颗读不到就弹窗(门控拆掉，干净克隆上启动卡在模态框里)",
     ["不许弹窗"],
     [("bytes", S / "src" / "ConfigForm.cs",
       b'                        if (Visible && File.Exists(value))\r\n                            MessageBox.Show(',
       b'                        MessageBox.Show(')], None),
]


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def build():
    return run(["dotnet", "build", str(S / "DeskSpine.csproj"), "-c", "Release",
                "-p", "BaseOutputPath=out/reverse-build/", "-v", "q"], S)


def desk():
    _, out = run([str(HARNESS), "desk", str(OUT / "BwpDesktopPet.dll")], HARNESS.parent)
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


def patch_bytes(path, old, new):
    data = path.read_bytes()
    hits = data.count(old)
    assert hits == 1, f"{path.name}: 锚点命中 {hits} 次(要 1 次)"
    path.write_bytes(data.replace(old, new))


def patch_resx(path):
    """把 ConfigForm.resx 的 $this.Icon 换成衍生那张的 base64 —— 「版权件偷偷进仓库」的形状"""
    text = path.read_text(encoding="utf-8")
    b64 = base64.b64encode(SRC_ICO.read_bytes()).decode()
    at = text.index('<data name="$this.Icon"')
    open_at = text.index("<value>", at) + len("<value>")
    close_at = text.index("</value>", open_at)
    path.write_text(text[:open_at] + "\n        " + b64 + "\n    " + text[close_at:], encoding="utf-8")


def main():
    # 只跑某几条: python bwp-assets/reverse_red_icon.py a b   (按名字前缀挑)
    picks = sys.argv[1:]
    bugs = [b for b in BUGS if not picks or any(b[0].startswith(p) for p in picks)]
    assert HARNESS.exists(), "先建 harness: dotnet build bwp-assets/animator-test"
    assert SRC_ICO.exists(), "源图不在，验不了"
    backups = {}

    def backup(p):
        backups.setdefault(p, p.read_bytes())

    def restore():
        for p, b in backups.items():
            p.write_bytes(b)
        backups.clear()

    def artifact(kind, target):
        if kind == "rm" and target.exists():
            target.rename(target.with_name(target.name + ".gone"))
        elif kind == "append" and target.exists():
            target.write_bytes(target.read_bytes() + b"\x00")

    def artifact_back(target):
        # 装机那一份本来就是源图的拷贝，直接从源图拷回来最干净
        if target.with_name(target.name + ".gone").exists():
            target.with_name(target.name + ".gone").rename(target)
        elif target.name == SRC_ICO.name:
            shutil.copyfile(SRC_ICO, target)

    report = []
    try:
        for name, want, patches, art in bugs:
            for p in patches:
                backup(p[1])
                if p[0] == "bytes":
                    patch_bytes(p[1], p[2], p[3])
                else:
                    patch_resx(p[1])
            code, out = build()
            if code != 0:
                restore()
                report.append(f"{name}: ✗ 补丁没编过，这一条没法验\n{out[-1200:]}")
                continue
            if art:
                artifact(art[0], art[1])
            marker, reds, _ = desk()
            if art:
                artifact_back(art[1])
            missed = [w for w in want if not any(w in r for r in reds)]
            ok = marker == "DESK FAIL" and not missed
            report.append(
                f"{name}: {'红得对' if ok else '不对'}  整关={marker}  "
                f"想红的 {len(want)} 条里红了 {len(want) - len(missed)} 条"
                + (f"  ★没红: {missed}" if missed else "")
                + f"\n    实际红 {len(reds)} 条:\n" + "\n".join(f"      - {r}" for r in reds))
            restore()

        code, out = build()
        marker = reds = None
        if code == 0:
            marker, reds, _ = desk()
        report.append(f"全部还原后复跑: 建 {code}  整关={marker}  第 25 层还红 {len(reds or [])} 条"
                      + "\n".join(f"      - {r}" for r in (reds or [])))
    finally:
        restore()

    log = LOG if not picks else LOG.with_name("reverse_icon_part.log")   # 挑着跑不许把整份记录冲掉
    log.write_text("\n\n".join(report) + "\n", encoding="utf-8")
    print(f"RED VERIFY DONE bugs={len(bugs)} log={log}")
    for line in report:
        print("  " + line.splitlines()[0])


if __name__ == "__main__":
    main()
