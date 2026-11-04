#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 desk 第 27 层(包内素材首启登记)的 bug 一条条放回去，验它会不会红。

这层管五件事: 认得出可用骨架、缺 .atlas 的那只不收、已有配置的人一个字节都不许被覆盖、
包内没素材时静默、产品入口真的调了它(Seed 写得再对，没人调就等于没接)。
bug 照着这几处一条条打: a/b/c/d 在 BundledRoster.cs(UTF-8)、e 摘 Program.cs(GBK) 里那一跳;
其中 c 那条「模式写歪」(BwpHero→AzurLaneSD) 是首启登记里唯一一处「写得进去但装出来不是百闻牌那只」的错。

每条 bug: 备份字节 → 打补丁 → 单独建到 deskspine/DeskSpine/out/reverse-build/ → 跑 desk → 还原。
两道「不算红」的坑钉死在这里:
  1) 建之前把 OUT 里的产物全删掉，不然上一条 bug 留下的旧 dll 会被当成这一条的结果；
  2) 干净源码先建一份记下哈希当正对照，每条 bug 的产物必须和它不一样。
     上一轮四条全绿就栽在第 2 条上: 脚本只数了锚点命中几次、没把替换真写回文件，
     于是一路建的都是没打补丁的源码 —— 锚点对上了不等于补丁打上去了。
谁红了、整关有没有 DESK FAIL，全记进 bwp-assets/out/reverse_bundle.log。最后一步是「全部还原后复绿」。
尾巴上还有一段附件侧的: 首启那条判据有两个形状 —— 源码层(第 27 层，合成假骨架)和附件层(seed 探针，跑在
build2/fd 那份真素材上)。附件侧摆三棵临时树验它会不会红: 空包该红、骨架名对不上中文名表该红、
摘掉一只的同名 .atlas 探针该跟着少算一只(那笔账由打包脚本按 PETS 的只数兜) —— 临时树建在两个仓库外面。

跑法: python bwp-assets/reverse_red_bundle.py
"""
import hashlib
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
S = REPO / "deskspine" / "DeskSpine"
ROSTER = S / "src" / "BundledRoster.cs"      # UTF-8 BOM + CRLF
PROG = S / "src" / "Program.cs"              # GBK 无 BOM: 锚只用 ASCII
OUT = S / "out" / "reverse-build" / "Release" / "net8.0-windows" / "win-x64"
HARNESS = REPO / "bwp-assets" / "animator-test" / "bin" / "Release" / "net8.0-windows" / "bwp-animator-test.exe"
LOG = REPO / "bwp-assets" / "out" / "reverse_bundle.log"
LAYER = "包内素材首启登记"


def u(s):
    return s.encode("utf-8")


# 每条: 名字 / 期望变红的判据关键词 / [(路径, 旧字节, 新字节, 期望命中次数)]
BUGS = [
    ("a-拆掉「已有配置」那道门(包里那份会盖掉用户自己改的)",
     ["已有配置不许覆盖"],
     [(ROSTER, u('            if (File.Exists(configPath)) return 0;\r\n'), u(''), 1)]),
    ("b-不看同名 .atlas 就登记(装出来是一扇起不来的窗)",
     ["登记了几只"],
     [(ROSTER, u('                if (File.Exists(Path.ChangeExtension(skel, ".atlas")))\r\n'
                 '                    return Path.GetFullPath(skel);\r\n'),
       u('                return Path.GetFullPath(skel);\r\n'), 1)]),
    ("c-模式写成 AzurLaneSD(登记上了，但驱动它的不是百闻牌那套)",
     ["版本/模式/PMA/出场格 落对"],
     [(ROSTER, u("TinyEngine.AnimatorType.BwpHero"), u("TinyEngine.AnimatorType.AzurLaneSD"), 1)]),
    ("d-拆掉「包内没这目录」那道守卫(源码党首启直接抛)",
     ["包内没素材时静默"],
     [(ROSTER, u('            if (!Directory.Exists(bundleRoot)) return 0;\r\n'), u(''), 1)]),
    ("e-摘掉产品入口那一跳(Seed 写得再对也没人调，附件里那四只躺在 res\\spine 没人认)",
     ["首启真的会调它"],
     [(PROG, u('            BundledRoster.SeedIfFirstRun();\r\n'), u(''), 1)]),
]


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16] if p.exists() else "-"


def build():
    for f in list(OUT.glob("*")):
        if f.is_file():
            f.unlink()
    return run(["dotnet", "build", str(S / "DeskSpine.csproj"), "-c", "Release",
                "-p", "BaseOutputPath=out/reverse-build/", "-v", "q"], S)


def desk(dll):
    _, out = run([str(HARNESS), "desk", str(dll)], HARNESS.parent)
    line = next((l for l in out.splitlines() if l.strip().startswith(LAYER)), "")
    reds = [l.strip() for l in out.splitlines() if l.strip().startswith("✗")]
    mark = "否" if ": 否" in line else ("是" if ": 是" in line else "")
    tail = out.strip().splitlines()[-1] if out.strip() else "(没输出)"
    return mark, reds, tail


def say(s):
    print(s)
    lines.append(s)


lines = []
fail = 0
FILES = [ROSTER, PROG]
orig = {f: f.read_bytes() for f in FILES}
dll_path = OUT / "BwpDesktopPet.dll"


def restore():
    for f in FILES:
        f.write_bytes(orig[f])


# 正对照: 干净源码建一份，记下哈希 —— 后面每条 bug 的产物必须和它不一样，否则是补丁没进构建
rc, _ = build()
base = sha(dll_path)
say(f"正对照(干净源码): 建 {'成功' if rc == 0 else '失败'}  产物 {base}")
if rc != 0 or base == "-":
    say("干净源码这一份就建不出来，后面没法比")
    sys.exit(1)
mark, reds, tail = desk(dll_path)
say(f"正对照: 未打补丁时该层={mark} 整关 {tail}  期望=是 / DESK OK")
if mark != "是":
    fail += 1

for name, want_keys, patches in BUGS:
    data = dict(orig)
    for path, old, new, hits in patches:
        if data[path].count(old) != hits:
            say(f"{name}: ✗ 锚点没对上({path.name} 命中 {data[path].count(old)} 次)，这条根本没打进源码")
            data = None
            break
        data[path] = data[path].replace(old, new, 1)
    if data is None:
        fail += 1
        continue
    if data == orig:
        say(f"{name}: ✗ 补丁打完字节没变，这条是空操作")
        fail += 1
        continue
    for path in FILES:
        path.write_bytes(data[path])
    rc, blog = build()
    if rc != 0:
        say(f"{name}: ✗ 打了补丁建不起来，这条没验到: {blog.strip()[-180:]}")
        fail += 1
        restore()
        continue
    got = sha(dll_path)
    if got == base:
        say(f"{name}: ✗ 产物和干净那份同一哈希({got}) —— 补丁没进 dll，这条没验到(先查构建，别查判据)")
        fail += 1
        restore()
        continue
    mark, reds, tail = desk(dll_path)
    hit = [k for k in want_keys if any(k in r for r in reds)]
    ok = mark == "否" and len(hit) == len(want_keys)
    say(f"{name}: {'红得对' if ok else '没红/红错地方'}  该层={mark or '没跑到'}  产物 {got}  整关 {tail}  "
        f"期望红 {len(want_keys)} 条命中 {len(hit)} 条"
        + ("" if ok else f"  实际红: {reds[:3] or '无'}"))
    if not ok:
        fail += 1
    restore()

# 全部还原后重建正式产物(反向验会把源码 mtime 顶到 dll 之前)，再跑整关复绿
restore()
rc, _ = run(["dotnet", "build", str(REPO / "deskspine" / "DeskSpine.sln"), "-c", "Release", "-v", "q"], S)
_, out = run([str(HARNESS), "desk"], HARNESS.parent)
tail = out.strip().splitlines()[-1] if out.strip() else "(没输出)"
n_ok = sum(1 for l in out.splitlines() if l.startswith("  ") and ": 是" in l)
say(f"还原后重建 {'成功' if rc == 0 else '失败'}，整关 {tail}，打「是」的层 {n_ok} 行")
if tail != "DESK OK":
    fail += 1

# 附件侧那条判据(seed 探针)的三条负对照: 它跑在打包脚本建出来的那份产物上，不重新建
ATT = REPO.parent / "_publish" / "build2" / "fd"
NEG = REPO.parent / "_publish" / "seed-neg"          # 临时树放仓库外面，免得素材漏进发布面


def seed_probe(bundle, work):
    r = subprocess.run([str(HARNESS), "seed", str(ATT / "BwpDesktopPet.dll"), str(bundle), str(work)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       cwd=str(HARNESS.parent))
    out = (r.stdout or "") + (r.stderr or "")
    line = next((l.strip() for l in out.splitlines() if "附件真素材" in l), out.strip().splitlines()[0][:70])
    return r.returncode, line


def seed_controls():
    """把「附件里那四只真登记得上」这句话能错的三种形状摆出来，看探针红不红。"""
    import shutil
    if not (ATT / "res" / "spine").is_dir():
        say("附件侧负对照: 没找到 build2/fd（先跑 package_release_zips.py），这一轮没验到")
        return 1
    shutil.rmtree(NEG, ignore_errors=True)
    bad = 0

    def check(tag, bundle, work, want_red):
        rc, line = seed_probe(bundle, work)
        red = "✗" in line or rc != 0
        ok = red == want_red
        say(f"附件侧负对照 {tag}: {'红' if red else '绿'}（期望{'红' if want_red else '绿'}）  {line[:130]}")
        return 0 if ok else 1

    (NEG / "empty").mkdir(parents=True)
    bad += check("一·包里一棵骨架都没有", NEG / "empty", NEG / "w1", True)

    for src_name, dst_name, mutate in (("fewatlas", "w2", "atlas"), ("renamed", "w3", "skel")):
        d = NEG / src_name
        shutil.copytree(ATT / "res" / "spine" / "qianji_0552", d / "qianji_0552")
        shutil.copytree(ATT / "res" / "spine" / "xieji_0481", d / "xieji_0481")
        if mutate == "atlas":
            (d / "qianji_0552" / "qianji_0552.atlas").unlink()
        else:
            for ext in ("skel", "atlas"):
                p = d / "qianji_0552" / f"qianji_0552.{ext}"
                p.rename(d / "qianji_0552" / f"mystery_0000.{ext}")
        bad += check(f"{'二·摘掉一只的同名 .atlas' if mutate == 'atlas' else '三·把一只的骨架改名成表里没有的'}",
                     d, NEG / dst_name, mutate == "skel")

    # 第二条按设计是「绿」的：探针数的是「按产品那条规则能登记几只」，包内摘掉图集它就跟着少算一只。
    # 少一只这笔账由打包脚本那句「要 4 只、登记了 N 只」兜 —— 所以这里要看见探针确实报「回 1 只」而不是回 2 只。
    rc, line = seed_probe(NEG / "fewatlas", NEG / "w2b")
    import re
    m = re.search(r"真登记得上=回 \d+ 只\(包内可用 \d+ 只\)", line)
    say("附件侧边界: 摘图集那棵探针报「%s」（打包脚本按 PETS 的只数比这个数，少一只就红）"
        % (m.group(0).split("=", 1)[1] if m else "没读到那个数"))
    bad += 0 if "回 1 只" in line else 1
    shutil.rmtree(NEG, ignore_errors=True)
    return bad


fail += seed_controls()

LOG.parent.mkdir(parents=True, exist_ok=True)
LOG.write_text("\n".join(lines) + "\n", encoding="utf-8")
say(f"结论: {f'{len(BUGS)} 条源码 bug + 三棵附件临时树都红得对该绿的绿，还原后复绿' if fail == 0 else f'有 {fail} 条不对，先别信这层'}  日志 {LOG.relative_to(REPO)}")
sys.exit(0 if fail == 0 else 1)