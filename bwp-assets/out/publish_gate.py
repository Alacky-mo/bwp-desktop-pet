#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""发布门面闸：往外推之前，一条仓库里不能出现 ①游戏文本（中文剧情串 / 日语语音转写）②本机用户名。

用法:  python bwp-assets/out/publish_gate.py [要扫的仓库根]        扫这个 git 仓库的跟踪文件
       python bwp-assets/out/publish_gate.py --published [快照仓库根]  外加 E 署名线（要推出去的那份才加）
       python bwp-assets/out/publish_gate.py --walk [要扫的目录]    扫这个目录树里的每一个文件
                                                          （给 build 产物 / release 附件用 —— 它们不在 git 里）
退出码 0 = 干净；非 0 = 有泄漏，stdout 逐条列 文件:行 + 为什么（不打印命中的原文）。

规则五条：
  A 中文线：命中本机原文池里 ≥8 字、且整串不带假名的串（剧情/提示框那类中文）→ 红。
    短于 8 字的中文串不开这条 —— 池子里混着我们自己的中文注释列，≥8 才是「照抄了一句」的形状。
  B 日语线：任何 ≥2 个连续假名的串 → 红，**除非**它是假名表里连着的一段（あいう… / アイウ…）
    那种「字母表样本」—— 字体覆盖面探针要的是假名本身，不是某句台词。
    单个假名（规范化代码里的促音、长音符）不算串，照旧放行。这条不依赖池子，换机器照样有牙。
  C 身份线：本机用户名、私人邮箱域 → 红。
  D 字节线：C 那套形状**按字节**查，连二进制一起查 —— 上一轮就是在这里翻车：
    建出来的每个 dll 里那条 RSDS 记录写着 pdb 的**绝对路径**（整条家目录），pdb 自己把路径按
    长度前缀切成一段段（`Users` 和登录名中间夹的是 0x05 那种字节，不是斜杠也不是点），
    两头都不是「带反斜杠的整串」，只扫文本等于没扫。产物不带 pdb 和调试目录就不红（见 --walk）。
  E 署名线（要 --published 才开）：**git 对象**里的身份。仓库推出去之后，公开的不只是文件内容 ——
    每笔提交揣着作者/提交者两份 name+email，annotated tag 还**另外**揣一份 tagger。
    2026-11-04 实测：两仓提交署名早就按成 noreply 了，远端那枚标签的 tagger 却还是本机默认那一份 ——
    `git log --format='%ae %ce'` 看不见它，C/D 两条也看不见（它们扫的是文件）。这条就是补那一格。
    为什么开旗标而不是默认：开发仓库的历史**本来**就全是本机那份身份（那是给内部留的账），
    默认开等于每次提交前都红一片，红习惯了就等于没有闸。不加旗标时 stdout 明写「没查」。

C/D 两线用的家目录形状是**运行时**从 expanduser 取的，源文本里一个字节都不留 —— 留着就是自己判红。
A 线的池子永远从「本脚本所在的开发树」取（要扫的快照里本来就没有那些表）；表不在就打印降级，
那时只有 B/C/D 有牙 —— 日语那一半照样拦得住，中文剧情串就得靠人。

素材豁免（只在 --walk 生效）: res/spine/ 与 res/dialog/ 底下的文件不查 A、B 两条 ——
2026-11-04 用户裁定 release 附件就是一份百闻牌素材包，骨骼、语音转写、那 22 条台词本来就是要带给用户的。
git 侧不豁免（两个仓里素材仍 0 字节），豁免的那一半也只豁免「文本内容」:
C 身份线、D 字节线、编码线一条都不松 —— 素材里夹本机路径照样红（manifest 那种表最容易带绝对路径）。
"""
import os
import re
import subprocess
import sys

# 假名区间用 chr() 拼：直接把端点写出来就是两个连续假名，闸会把自己判红（而且确实该判红）。
KANA = "[" + chr(0x3040) + "-" + chr(0x309F) + chr(0x30A0) + "-" + chr(0x30FF) + "]"
RUN = re.compile("(" + KANA + "{2,})")
TEXTY = re.compile("[一-鿿" + chr(0x3040) + "-" + chr(0x30FF) + "]")
SPLIT = re.compile('[\t\n\r"\\\\{}]+')
# 身份线抓的是「家目录被写死进仓库」这个形状，不写某个具体用户名 —— 那个字面量一进来就先被自己抓一遍。
IDENT = re.compile(r"[A-Za-z]:[\\/](?:Users|home)[\\/]|/c/(?:Users|home)/|qq\.com")
GOJUON_HIRA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわん"
GOJUON_KATA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン"

HOME = os.path.expanduser("~")
LOGIN = re.split(r"[\\/]", HOME)[-1]
# 同一条家目录的两种写法：原样（dll 的 RSDS 记录）和正斜杠（json / msys 那一类）
HOME_BYTES = [("整条家目录", HOME.encode("utf-8", "replace")),
              ("正斜杠写法", HOME.replace("\\", "/").encode("utf-8", "replace"))]
# 兜住「Users 紧跟登录名」的其它写法：pdb 的字符串堆里两者之间夹的是**长度前缀字节**（实测是 0x05），
# 不是斜杠也不是点 —— 所以中间允许任意几个字节，只按「家目录段后面马上是本机登录名」判。
USER_LOGIN = re.compile(rb"(?:Users|home).{0,4}" + re.escape(LOGIN.encode("utf-8", "replace")),
                        re.DOTALL)


LOCAL_POOL = [
    "bwp-assets/out/voice_lines.tsv",
    "bwp-assets/voice_emo_rules.tsv",
    "bwp-assets/t/spine_emotion/buzhihuo_1127/voice/_manifest.tsv",
    "bwp-assets/out/scenerio_lines.log",
    "bwp-assets/meta/gmbridge/string.cn.json",
    "deskspine/DeskSpine/res/dialog/lines.tsv",
]

# 产物模式下的素材豁免前缀: 这两底下的游戏文本是 release 附件要带的东西，不是泄漏
ASSET_PREFIX = ("res/spine/", "res/dialog/")


def dev_root():
    here = os.path.dirname(os.path.abspath(__file__))
    out = subprocess.run(["git", "-C", here, "rev-parse", "--show-toplevel"],
                         capture_output=True)
    return out.stdout.decode("utf-8", errors="replace").strip() or here


def pool_strings(root):
    got, missing = set(), []
    for rel in LOCAL_POOL:
        p = os.path.join(root, rel)
        if not os.path.exists(p):
            missing.append(rel)
            continue
        with open(p, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        for tok in SPLIT.split(raw):
            tok = tok.strip()
            if len(tok) >= 8 and TEXTY.search(tok) and not re.search(KANA, tok):
                got.add(tok)
    return got, missing


def base_seq(s):
    """浊点/半浊点拆回基础假名（ば→は），再比是不是假名表里连着的一段。"""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c)[0] != "M")


def is_syllabary_run(run):
    """放行的是「五十音表里连着的一段」，不是任意假名串 —— 真台词几乎不会按表序走。"""
    base = base_seq(run)
    return bool(base) and (base in GOJUON_HIRA or base in GOJUON_KATA)


def tracked_files(root):
    out = subprocess.run(["git", "-C", root, "ls-files", "-z"],
                         capture_output=True).stdout
    if out == b"":
        raise SystemExit("不是个 git 仓库或没有跟踪文件: " + root)
    return [p for p in out.decode("utf-8").split(chr(0)) if p]


def walk_files(root):
    got = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for nm in names:
            got.append(os.path.relpath(os.path.join(base, nm), root).replace("\\", "/"))
    if not got:
        raise SystemExit("这目录里一个文件都没有: " + root)
    return sorted(got)


def byte_leaks(data):
    """D 字节线：二进制里有没有本机的路径形状（dll 的 RSDS、pdb 的归一化都在这儿露）。"""
    why = []
    for label, pat in HOME_BYTES:
        if pat in data:
            why.append("D 字节线:%s（整条本机路径写进了产物，不打印它）" % label)
    m = USER_LOGIN.search(data)
    if m and not why:
        why.append("D 字节线:Users/home 紧跟本机登录名（不打印它）")
    return why


US = chr(0x1f)


def sh(root, *args):
    return subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True).stdout.decode("utf-8", errors="replace")


def local_identity(root):
    """本机那份身份**当场从 git 配置读** —— 写死进源码就是自己判红。"""
    return {v for v in (sh(root, "config", "--global", "user.name").strip(),
                        sh(root, "config", "--global", "user.email").strip()) if v}


def id_why(field, val, local):
    if not val or not val.strip():
        return []
    if val in local:
        return ["E 署名线:%s 就是本机 git 配置里那一份（不打印它）" % field]
    m = IDENT.search(val)
    if m:
        return ["E 署名线:%s 命中 %s" % (field, m.group(0))]
    if LOGIN in val:
        return ["E 署名线:%s 里有本机登录名（不打印它）" % field]
    return []


def identity_scan(root):
    """E 署名线：提交对象两份身份 + annotated tag 的 tagger + 标签正文。返回 (红处, 笔数, 枚数)。"""
    bad = []
    local = local_identity(root)
    rows = [r for r in sh(root, "log", "--all",
                          "--format=%h" + US + "%an" + US + "%ae" + US + "%cn" + US + "%ce").splitlines() if r]
    ncommit = len(rows)
    for row in rows:
        cells = row.split(US)
        for field, val in zip(("作者名", "作者邮箱", "提交者名", "提交者邮箱"), cells[1:]):
            for why in id_why(field, val, local):
                bad.append(("git:提交 " + cells[0], 0, why))
    trows = [r for r in sh(root, "for-each-ref", "refs/tags",
                           "--format=%(refname:short)" + US + "%(taggername)" + US +
                           "%(taggeremail)").splitlines() if r]
    tagnames = [r.split(US)[0] for r in trows]
    for row in trows:
        nm, tn, te = (row.split(US) + ["", ""])[:3]
        for field, val in (("tagger 名", tn), ("tagger 邮箱", te)):
            for why in id_why(field, val, local):
                bad.append(("git:标签 %s" % nm, 0, why))
    for nm in tagnames:
        body = sh(root, "for-each-ref", "--format=%(contents)", "refs/tags/" + nm)
        for line_no, line in enumerate(body.splitlines(), 1):
            m = IDENT.search(line)
            if m:
                bad.append(("git:标签 %s 正文" % nm, line_no,
                            "E 署名线:标签正文命中 %s（不打印整行）" % m.group(0)))
            elif LOGIN in line:
                bad.append(("git:标签 %s 正文" % nm, line_no,
                            "E 署名线:标签正文里有本机登录名（不打印整行）"))
    return bad, ncommit, len(tagnames)


def main():
    argv = [a for a in sys.argv[1:]]
    walk = "--walk" in argv
    published = "--published" in argv
    argv = [a for a in argv if a not in ("--walk", "--published")]
    target = os.path.abspath(argv[0] if argv else ".")
    pool, missing = pool_strings(dev_root())
    bad = []
    n = nb = 0
    files = walk_files(target) if walk else tracked_files(target)
    nexempt = 0
    for rel in files:
        p = os.path.join(target, rel)
        if not os.path.isfile(p):
            continue
        # 豁免只给产物模式: 附件里那几只是要发给用户的游戏素材；git 侧一条不松(两个仓里素材仍 0 字节)
        asset = walk and rel.startswith(ASSET_PREFIX)
        nexempt += 1 if asset else 0
        data = open(p, "rb").read()
        for why in byte_leaks(data):
            bad.append((rel, 0, why))
        if b"\x00" in data[:4096]:
            nb += 1
            continue          # 二进制没有「行」可扫，上面那趟字节级已经查过身份
        text = None
        for enc in ("utf-8", "gbk"):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            print("读不动(既不是 UTF-8 也不是 GBK): " + rel)
            bad.append((rel, 0, "编码线:没法读就没法验，当红处理"))
            continue
        n += 1
        for i, line in enumerate(text.splitlines(), 1):
            for m in IDENT.finditer(line):
                bad.append((rel, i, "C 身份线:命中 " + m.group(0))
                           )
            if asset:
                continue      # A/B 放行(素材本身就是游戏文本)，C 那一跳在上面已经查过
            for s in pool:
                if s in line:
                    bad.append((rel, i, "A 中文线:照抄了 %d 字剧情/文案串" % len(s)))
                    break
            for m in RUN.finditer(line):
                if not is_syllabary_run(m.group(1)):
                    bad.append((rel, i, "B 日语线:%d 个连续假名(不是假名表样本)" % len(m.group(1))))

    print("闸跑在 " + target + ("（产物模式：逐个文件都查）" if walk else ""))
    if not walk:
        if published:
            more, ncommit, ntag = identity_scan(target)
            bad += more
            print("E 署名线查过 %d 笔提交 + %d 枚标签（含标签正文）" % (ncommit, ntag))
        else:
            print("E 署名线:没查（要推出去的快照请加 --published —— 提交/标签对象里的身份 C、D 两条看不见）")
    if missing:
        print("降级:开发树里缺原文表 " + ", ".join(missing) + " —— A 线空转，只有 B/C/D 有牙")
    else:
        print("A 线池子: %d 条(本机未跟踪，不打印内容)" % len(pool))
    if walk:
        print("素材豁免 %d 个文件(A/B 放行，C/D/编码线照查)" % nexempt)
    print("扫过 %d 个文本文件 + %d 个二进制（合计 %d 个%s）"
          % (n, nb, len(files), "，目录树里的全部文件" if walk else "，即这个仓库的跟踪清单"))

    if bad:
        print("红 %d 处:" % len(bad))
        for rel, i, why in bad:
            print("  %s:%d  %s" % (rel, i, why))
        return 1
    print("GATE OK 发布面上没有游戏文本、没有本机用户名"
          + ("，提交与标签里的署名也不是本机那一份" if published and not walk else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
