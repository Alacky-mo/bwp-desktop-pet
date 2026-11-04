#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""反向验 publish_gate.py 四条线各会不会红 —— 把泄漏放回一个一次性仓库里看它抓不抓。

第二轮走 --walk 验素材豁免那半: 原文放进 res/spine|res/dialog 放行、同样的字节搬到外面必须红、
豁免目录里夹本机路径(C/D)照样红。豁免放错了方向比没有豁免更糟，所以这三条分开钉。
不打印泄漏内容本身，只打印「第几条线红了几处」。跑完自己删临时目录。
"""
import os
import re
import shutil
import stat
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = subprocess.run(["git", "-C", HERE, "rev-parse", "--show-toplevel"],
                     capture_output=True).stdout.decode("utf-8").strip()
GATE = os.path.join(DEV, "bwp-assets", "out", "publish_gate.py")
TMP = os.path.join(DEV, "..", "_publish", "gate-reverse")

sys.path.insert(0, HERE)
from publish_gate import RUN as KANA_RE      # 假名口径只有一份：闸改了，这条反向验跟着走


def read(p):
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def pick_japanese():
    """从真实原文表里取一条 ≥4 字的假名串（不打印它）。"""
    for rel in ["bwp-assets/out/voice_lines.tsv", "bwp-assets/voice_emo_rules.tsv"]:
        for m in KANA_RE.finditer(read(os.path.join(DEV, rel))):
            if len(m.group(0)) >= 4:
                return m.group(0)
    return None


def pick_chinese():
    """从真实剧情/台词表里取一条 ≥8 字、不带假名的串。"""
    for rel in ["bwp-assets/out/scenerio_lines.log", "bwp-assets/meta/gmbridge/string.cn.json",
                "deskspine/DeskSpine/res/dialog/lines.tsv"]:
        for tok in re.split('[\t\n\r"\\\\{}]+', read(os.path.join(DEV, rel))):
            tok = tok.strip()
            if len(tok) >= 8 and re.search(r"[一-鿿]", tok) and not KANA_RE.search(tok):
                return tok
    return None


def git(*a):
    return subprocess.run(["git", "-C", TMP] + list(a), capture_output=True)


def rmrf(path):
    """git 把 object/pack 标成只读，Windows 上直接 rmtree 会撞 PermissionError，先抹掉只读位。"""
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(root, name), stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(path)


def run_gate():
    r = subprocess.run([sys.executable, "-X", "utf8", GATE, TMP], capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    return r.returncode, out


def run_gate_walk(root):
    r = subprocess.run([sys.executable, "-X", "utf8", GATE, "--walk", root], capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", errors="replace")


def exemption_check(ja, cn):
    """素材豁免那三条各验一遍: 豁免里放行、同样字节搬到豁免外要红、豁免里带本机身份还要红。

    只放行 A/B 是这轮裁定的全部风险所在 —— C/D 一旦跟着豁免，附件里那份 manifest
    写死一个开发机绝对路径就没人喊了。所以这三条必须分开钉住。
    """
    root = os.path.join(DEV, "..", "_publish", "gate-reverse-walk")
    if os.path.exists(root):
        rmrf(root)
    body = "转写一句：" + ja + "\n剧情一句：" + cn + "\n"
    home = os.path.expanduser("~").encode("utf-8", "replace")
    W = os.path.join
    for sub in (W("res", "spine", "buzhihuo_1127", "voice"), W("res", "dialog"), W("res", "image")):
        os.makedirs(W(root, sub))
    # 1) 原文照抄进豁免目录: 这一份不该红(它就是 release 附件要带的东西)
    with open(W(root, "res", "spine", "buzhihuo_1127", "voice", "lines_probe.tsv"), "w", encoding="utf-8") as fh:
        fh.write(body)
    # 2) 一模一样的字节搬到豁免外: 该红，两处都红
    with open(W(root, "stray.md"), "w", encoding="utf-8") as fh:
        fh.write(body)
    # 3) 豁免目录里夹本机身份: C、D 都不许跟着豁免走
    with open(W(root, "res", "dialog", "home_leak.tsv"), "w", encoding="utf-8") as fh:
        fh.write("cd " + LEAK_PATH + "\n")
    with open(W(root, "res", "spine", "fake.dll"), "wb") as fh:
        fh.write(b"MZ\x90\x00" + home + b"\x00")
    # 不误伤: 一张真 PNG 的开头(二进制)、一份没内容的干净文本
    with open(W(root, "res", "image", "clean.png"), "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 24)
    with open(W(root, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write("干净文本，不该红\n")

    rc, out = run_gate_walk(root)
    a, b = lines_of(out, "A 中文线"), lines_of(out, "B 日语线")
    c, d = lines_of(out, "C 身份线"), lines_of(out, "D 字节线")
    ab = a + b
    hurt = [l for l in ab + c + d
            if any(k in l for k in ("clean.png", "README.txt", "lines_probe"))
            or ("home_leak" in l and "C 身份线" not in l)]
    n_exempt = re.search(r"素材豁免 (\d+) 个文件", out)
    print("素材豁免三条:")
    print("  豁免目录里的原文: 红 %d 处（期望 0）" % len([l for l in ab if "lines_probe" in l]))
    print("  同一份字节搬到豁免外: 红 %d 处（期望 ≥2，A、B 各一处）" % len([l for l in ab if "stray.md" in l]))
    print("  豁免目录里夹本机路径: C 线红 %d 处（期望 ≥1）" % len([l for l in c if "home_leak" in l]))
    print("  豁免目录里的假产物带整条家目录: D 线红 %d 处（期望 ≥1）" % len([l for l in d if "fake.dll" in l]))
    print("  闸自己报的豁免数: %s（期望 3: lines_probe / home_leak / fake.dll 都落在 res/spine|res/dialog 下）"
          % (n_exempt.group(1) if n_exempt else "没报"))
    print("  其余文件被误伤 %d 处（期望 0）" % len(hurt))
    ok = (rc == 1 and not [l for l in ab if "lines_probe" in l]
          and len([l for l in ab if "stray.md" in l]) >= 2
          and len([l for l in c if "home_leak" in l]) >= 1
          and len([l for l in d if "fake.dll" in l]) >= 1
          and not hurt and n_exempt and n_exempt.group(1) == "3")
    rmrf(root)
    return ok


def lines_of(out, tag):
    return [l for l in out.splitlines() if tag in l]


# 拼出来才是家目录那个形状：这脚本自己也在发布面上，写成一整串就先被自己的 C 线判红
LEAK_PATH = "/".join(["C:", "Users", "someone", "whatever"])


def main():
    ja, cn = pick_japanese(), pick_chinese()
    if not ja or not cn:
        print("取不到原文样本（表不在？）: ja=%s cn=%s" % (bool(ja), bool(cn)))
        return 2
    if os.path.exists(TMP):
        rmrf(TMP)
    os.makedirs(TMP)
    git("init", "-q", "-b", "main", TMP)
    with open(os.path.join(TMP, "leak_ja.md"), "w", encoding="utf-8") as fh:
        fh.write("注释里贴了一句转写：" + ja + "\n")
    with open(os.path.join(TMP, "leak_cn.md"), "w", encoding="utf-8") as fh:
        fh.write("注释里贴了一句剧情：" + cn + "\n")
    with open(os.path.join(TMP, "leak_path.md"), "w", encoding="utf-8") as fh:
        fh.write("cd " + LEAK_PATH + "\n")   # 闸抓的是形状，不靠具体用户名
    drag = "あ" + "\u30fc" + "う"      # 合成的拖音词：表序里不相邻，只有把长音符算进假名范围才抓得到
    with open(os.path.join(TMP, "leak_drag.md"), "w", encoding="utf-8") as fh:
        fh.write("合成拖音词：" + drag + "\n")
    # D 字节线：假产物里塞两条本机路径 —— 原样那条（dll 的 RSDS 就长这样）和点号归一化那条（pdb 长这样）
    home = os.path.expanduser("~").encode("utf-8", "replace")
    with open(os.path.join(TMP, "leak_fakedll.dat"), "wb") as fh:
        fh.write(b"MZ\x90\x00" + home + b"\x00" + home.replace(b"\\", b".") + b"\x00\x00")
    with open(os.path.join(TMP, "control.dat"), "wb") as fh:
        fh.write(b"MZ\x90\x00Users\x00home\x00" + b"\x01\x02\x03" * 8)   # 只有 Users 这个词，不该红
    with open(os.path.join(TMP, "control.md"), "w", encoding="utf-8") as fh:
        fh.write("放行样本：あいうえおかきくけこ / アイウエオカキクケコ / 促音 っ 单独一个 / 长音 ー\n")
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x")

    rc, out = run_gate()
    b = lines_of(out, "B 日语线")
    a = lines_of(out, "A 中文线")
    c = lines_of(out, "C 身份线")
    d = lines_of(out, "D 字节线")
    ctl = [l for l in b + a + c + d if "control." in l]
    print("放回五条泄漏：")
    print("  B 日语线红 %d 处（期望 ≥2：一条转写 + 一条合成拖音，都该有）" % len(b))
    print("  A 中文线红 %d 处（期望 ≥1，且落在 leak_cn.md）" % len(a))
    print("  C 身份线红 %d 处（期望 ≥1，且落在 leak_path.md）" % len(c))
    print("  D 字节线红 %d 处（期望 ≥1，且落在 leak_fakedll.dat；光有 Users 这个词不该红）" % len(d))
    print("  放行样本（含那个假二进制）被误伤 %d 处（期望 0）" % len(ctl))
    ok1 = rc == 1 and len(b) >= 2 and len(a) >= 1 and len(c) >= 1 and len(d) >= 1 and not ctl

    for f in ("leak_ja.md", "leak_cn.md", "leak_path.md", "leak_drag.md", "leak_fakedll.dat"):
        os.remove(os.path.join(TMP, f))
    git("add", "-A")
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "unleak")
    rc2, out2 = run_gate()
    print("撤掉五条之后复跑：rc=%d %s" % (rc2, out2.strip().splitlines()[-1]))
    ok2 = rc2 == 0
    ok3 = exemption_check(ja, cn)
    try:
        rmrf(TMP)
    except OSError as e:
        print("临时目录没删干净: %s（%s）" % (TMP, e.strerror))
    print("反向验结论: %s" % ("红得对、撤得干净、豁免只放对的那一半" if ok1 and ok2 and ok3
                          else "这条判据不合格（红 %s / 撤 %s / 豁免 %s）" % (ok1, ok2, ok3)))
    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    sys.exit(main())
