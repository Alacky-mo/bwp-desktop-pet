#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""反向验 publish_gate.py 的 E 署名线（--published）—— 把「git 对象里的身份」那几处泄漏放回一次性仓库，
看它抓不抓；再把 bug 撤掉复绿。

为什么不套 reverse_red_gate.py 那套文件泄漏的写法：E 线扫的不是跟踪文件，是提交对象的两份
name+email、annotated tag 的 tagger、以及标签正文。这三格 C/D 两条线都看不见（它们只读工作树），
2026-11-04 就是在这里翻的车：两仓提交署名早就按成 noreply 了，远端那枚标签的 tagger 还是本机默认那一份。

本机那份身份**当场从 git 配置读**，脚本里一个字都不写：写死了就是自己判红（这脚本也在发布面上）。
临时目录在 _publish/identity-reverse，不推、跑完自己删。不打印泄漏内容本身，只报「哪条红了几处」。
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
TMP = os.path.join(DEV, "..", "_publish", "identity-reverse")

# 拼出来才是家目录那个形状：整串写进源码就先被 C 线判红一遍
LEAK_PATH = "/".join(["C:", "Users", "someone", "whatever"])
CLEAN = ("-c", "user.name=Release Bot", "-c", "user.email=bot@users.noreply.github.com")


def sh(*args):
    return subprocess.run(["git", "-C", TMP] + list(args), capture_output=True)


def cfg(key):
    return subprocess.run(["git", "config", "--global", key],
                          capture_output=True).stdout.decode("utf-8", errors="replace").strip()


def rmrf(path):
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            try:
                os.chmod(os.path.join(root, name), stat.S_IWRITE)
            except OSError:
                pass
    shutil.rmtree(path)


def run_gate(published=True):
    argv = [sys.executable, "-X", "utf8", GATE] + (["--published"] if published else []) + [TMP]
    r = subprocess.run(argv, capture_output=True)
    return r.returncode, r.stdout.decode("utf-8", errors="replace")


def lines_of(out, tag):
    return [l for l in out.splitlines() if tag in l]


def e_lines(out):
    # 「E 署名线查过 N 笔」那句是报数不是报红：红处的写法固定带冒号「E 署名线:」
    return [l for l in out.splitlines() if "E 署名线:" in l]


def last(out):
    return out.strip().splitlines()[-1]


def show(label, rc, out, want_red):
    e = e_lines(out)
    print("   %s rc=%d  E 线红 %d 处（期望 %s）" % (label, rc, len(e), "≥1" if want_red else "0"))
    for l in e[:2]:
        print("      " + l.strip()[:72])
    return (len(e) >= 1) == want_red and (rc == 1) == want_red


def main():
    name, mail = cfg("user.name"), cfg("user.email")
    if not name or not mail:
        print("读不到本机那份身份（全局 git 配置缺 user.name/user.email）")
        return 2
    leak = ("-c", "user.name=" + name, "-c", "user.email=" + mail)

    if os.path.exists(TMP):
        rmrf(TMP)
    os.makedirs(TMP)
    sh("init", "-q", "-b", "main", TMP)
    with open(os.path.join(TMP, "README.txt"), "w", encoding="utf-8") as fh:
        fh.write("干净仓库：文件里没东西，只有 git 对象里的身份可查\n")
    sh("add", "-A")
    sh(*(CLEAN + ("commit", "-q", "-m", "干净那一笔")))
    sh(*(CLEAN + ("tag", "-a", "v0.0.1", "-m", "干净标签：tagger 是 noreply，正文里没有路径")))

    print("① 正向对照（一笔 noreply 提交 + 一枚 noreply annotated tag）")
    rc, out = run_gate()
    counted = re.search(r"E 署名线查过 (\d+) 笔提交 \+ (\d+) 枚标签", out)
    print("   %s / %s" % (last(out), counted.group(0) if counted else "E 线没报数"))
    print("   E 线红处 %d（期望 0）" % len(e_lines(out)))
    ok1 = rc == 0 and counted and counted.groups() == ("1", "1")
    ok1b = not e_lines(out)
    clean_commit = sh("rev-parse", "HEAD").stdout.decode("utf-8").strip()

    print("② 放回 bug：tagger = 本机身份（提交照旧 noreply，文件照旧干净）")
    sh("tag", "-d", "v0.0.1")
    sh(*(leak + ("tag", "-a", "v0.0.1", "-m", "上一轮真实事故就长这样")))
    rc, out = run_gate()
    ok2 = show("tagger", rc, out, True)
    other = lines_of(out, "A 中文线") + lines_of(out, "B 日语线") + lines_of(out, "C 身份线") \
        + lines_of(out, "D 字节线")
    ok2b = not other
    print("   没串台：A/B/C/D 四条各红 %d 处（期望全 0 —— 红的是 git 对象，不是文件）" % len(other))

    print("③ 撤回 ②")
    sh("tag", "-d", "v0.0.1")
    sh(*(CLEAN + ("tag", "-a", "v0.0.1", "-m", "撤回了")))
    rc, out = run_gate()
    ok3 = show("撤回", rc, out, False)

    print("④ 放回 bug：提交署名 = 本机身份（新造一笔，不动已有的）")
    with open(os.path.join(TMP, "more.txt"), "w", encoding="utf-8") as fh:
        fh.write("第二笔\n")
    sh("add", "-A")
    sh(*(leak + ("commit", "-q", "-m", "用默认配置提交的那一笔")))
    rc, out = run_gate()
    ok4 = show("提交", rc, out, True)
    n = len([l for l in e_lines(out) if "git:提交" in l])
    print("   落点：提交那格红 %d 处（期望 4 = 作者名/作者邮箱/提交者名/提交者邮箱）" % n)

    print("⑤ 放回 bug：标签正文夹本机路径形状（署名全 noreply）")
    sh("reset", "-q", "--hard", clean_commit)      # 先抹掉 ④ 那笔，免得两处 bug 叠在一起数不清
    sh("tag", "-d", "v0.0.1")
    sh(*(CLEAN + ("tag", "-a", "v0.0.1", "-m", "复现步骤：先 cd " + LEAK_PATH + " 再双击 exe")))
    rc, out = run_gate()
    body = [l for l in e_lines(out) if "正文" in l]
    print("   标签正文这格红 %d 处（期望 1；只查 tagger 的那版实现会漏这格）" % len(body))
    print("   提交/tagger 那两格红 %d 处（期望 0 —— 证明红的是正文那一格）"
          % len([l for l in e_lines(out) if "git:提交" in l or "tagger" in l]))
    ok5 = rc == 1 and len(body) == 1 and not [l for l in e_lines(out) if "git:提交" in l or "tagger" in l]

    print("⑥ 全撤复绿")
    sh("tag", "-d", "v0.0.1")
    sh(*(CLEAN + ("tag", "-a", "v0.0.1", "-m", "只写版本号")))
    rc, out = run_gate()
    ok6 = show("复绿", rc, out, False)

    print("⑦ 开关：不加 --published 时 E 线自报「没查」（同一棵带泄漏的树）")
    sh("tag", "-d", "v0.0.1")
    sh(*(leak + ("tag", "-a", "v0.0.1", "-m", "泄漏的那枚")))
    rc, out = run_gate(published=False)
    said = [l for l in out.splitlines() if "E 署名线:没查" in l]
    print("   rc=%d（期望 0）/ 自报「没查」%d 行（期望 1）" % (rc, len(said)))
    print("   这就是 E 线开旗标而不是默认的理由：开发仓的历史本来就全是本机身份，默认开等于每次提交前红一片，"
          "红习惯了就等于没有闸 —— 代价是交班命令必须自己带 --published（§11.1 那条已经带上）")
    ok7 = len(said) == 1 and rc == 0

    try:
        rmrf(TMP)
    except OSError as e:
        print("临时目录没删干净: %s（%s）" % (TMP, getattr(e, "strerror", e)))
    gone = not os.path.exists(TMP)
    print("临时目录已删: %s" % gone)
    all_ok = all([ok1, ok1b, ok2, ok2b, ok3, ok4, ok5, ok6, ok7, gone])
    print("反向验结论: %s" % ("四处 bug 各红各的、撤得干净、开关会自报没查" if all_ok else
                          "E 线不合格（对照 %s/%s tagger %s/%s 撤回 %s 提交 %s 正文 %s 复绿 %s 开关 %s 清场 %s）"
                          % (ok1, ok1b, ok2, ok2b, ok3, ok4, ok5, ok6, ok7, gone)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
