# -*- coding: utf-8 -*-
# 上一轮字体表的错：只验了「家族名解析得出来」，没验「这一款自己有没有这些字形」。
# 「素晴字体」解析成功了，可它的 cmap 里一个「番茄钟」都没有 —— GDI+ 缺字时静默借宋体代笔，
# PIL 缺字画豆腐块。所以那张候选表里「素晴字体」那一格，其实是宋体写的。
# 这张表按「小窗真会画出来的那些字」逐款数覆盖，缺一个就标出来，并把缺哪些列出来。
#
# 两种跑法：
#   python font_cover.py          出候选表 cover-report.txt（哪些款全套都有、哪些缺字）
#   python font_cover.py --check  对着产品代码验字形覆盖：从小窗那几份源码里抠出 TitleFamily
#                                 和所有画上去的字串，缺一个字就退出码 1（判据用，不是给人看的表）
# 为什么这一半不能在 C# 那侧验：GDI+ 借笔之后量尺寸、比像素都照常通过，FamilyName 也照样回得来，
# 只有直接读字体文件自己的 cmap 才看得到「这一款到底带不带这些字」。
import io, os, re, sys
from fontTools.ttLib import TTFont

NEED = "番茄钟短休长假连做段现在这几分钟没对上任何档分歧换弹气泡开始专注继停0123456789·"
HERE = os.path.dirname(os.path.abspath(__file__))
# 凡是往板上画字的那几扇都读一遍 —— 只盯 FocusPresetForm.cs 的话，天气卡上「雷阵雨伴小冰雹」
# 和「读取中…」这类新词就没人管了（GDI+ 缺字是静默借笔，量尺寸和比像素照旧全绿）
SRC_DIR = os.path.normpath(os.path.join(HERE, os.pardir, os.pardir,
                                        "deskspine", "DeskSpine", "src"))
SRCS = [os.path.join(SRC_DIR, n) for n in
        ("FocusPresetForm.cs", "WeatherService.cs", "PetMenuForm.cs", "WeatherForm.cs")]
# 正文和摘要那两支笔跟着系统消息字体走，产品里写的是 SystemFonts.MessageBoxFont
BODY_FAMILY = "Microsoft YaHei UI"

def names(f):
    """取这张字体自己声明的中英文名 —— 标签用它自己的名字，不自己翻译"""
    zh = en = None
    for rec in f["name"].names:
        if rec.platformID != 3:
            continue
        try:
            v = rec.toUnicode()
        except Exception:
            continue
        if rec.langID == 0x409:
            if rec.nameID in (1, 16): en = en or v
        elif rec.langID in (0x804, 0x404):
            if rec.nameID in (1, 16): zh = zh or v
    return zh, en

def tables(path):
    try:
        f = TTFont(path, fontNumber=0, lazy=True)
    except Exception:
        return []
    out = []
    try:
        n = f["maxp"].numGlyphs  # 只为触发解析
        cm = f.getBestCmap() or {}
        out.append(names(f) + (set(cm.keys()),))
        # .ttc 里后面还有脸，一并数（雅黑/宋体的 Bold 就在同一文件的下一张）
        from fontTools.ttLib import TTCollection
        if path.lower().endswith(".ttc"):
            f.close()
            c = TTCollection(path, lazy=True)
            for g in c.fonts:
                cm = g.getBestCmap() or {}
                out.append(names(g) + (set(cm.keys()),))
    except Exception:
        pass
    else:
        pass
    return out

def scan():
    """本机装着的每一款字体: (中文名, 英文名, 文件名, 码点数, 缺的字)"""
    dirs = [r"C:\Windows\Fonts", os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Fonts")]
    seen, rows = set(), []
    for d in dirs:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith((".ttf", ".ttc", ".otf")):
                continue
            p = os.path.join(d, fn)
            try:
                got = tables(p)
            except Exception:
                got = []
            for zh, en, codes in got:
                lab = zh or en or fn
                key = (lab.lower(), fn.lower())
                if key in seen:
                    continue
                seen.add(key)
                lack = [c for c in NEED if ord(c) not in codes]
                rows.append((lab, en, fn, len(codes), "".join(lack), codes))
    return rows


def report(rows):
    full = [r for r in rows if not r[4]]
    part = [r for r in rows if r[4]]
    o = io.open(os.path.join(HERE, "shots-fonts", "cover-report.txt"), "w", encoding="utf-8")
    o.write("要覆盖的字：%s\n\n自己就带全套字形（%d 款）：\n" % (NEED, len(full)))
    for lab, en, fn, n, _, _ in sorted(full, key=lambda r: r[:3]):
        o.write("  %-18s %-34s %-22s 码点 %d\n" % (lab, en, fn, n))
    o.write("\n缺字（用了就是借别人的笔，%d 款）：\n" % len(part))
    for lab, en, fn, n, lack, _ in sorted(part, key=lambda r: r[:3]):
        o.write("  %-18s %-34s %-22s 码点 %-6d 缺 %s\n" % (lab, en, fn, n, lack))
    o.close()
    print("full=%d part=%d -> shots-fonts/cover-report.txt" % (len(full), len(part)))
    return 0


def pool(rows, family):
    """同名一家可能散在好几个文件里（雅黑的 Regular/Bold/Light 是三张 ttc），并起来才是这一家真正带得动的字"""
    codes, files = set(), []
    for lab, en, fn, _, _, c in rows:
        if family.lower() in (lab.lower(), (en or "").lower()):
            codes |= c
            files.append(fn)
    return codes, files


def check(rows):
    """产品里写了哪一家、画了哪些字，就从代码里读，别在这儿抄一份 —— 抄的那份会和代码不同步"""
    texts = [(p, io.open(p, encoding="utf-8-sig").read()) for p in SRCS]
    title_family = None
    for p, src in texts:
        m = re.search(r'const string TitleFamily\s*=\s*"([^"]+)"', src)
        if m:
            title_family = m.group(1)
    if title_family is None:
        print("CHECK FAIL: 这几份里找不到 TitleFamily: %s" % ", ".join(os.path.basename(p) for p, _ in texts))
        return 2
    # 每一个 DrawString/PrimaryLabel/摘要模板/现象词表里出现的中文和数字，一个都不放过：
    # 拿全串里所有引号内的中文/数字/标点 求并集，宁可多验几个字，也不能漏
    chars = set()
    for _, src in texts:
        lits = re.findall(r'@"[^"]*"|\$?"(?:[^"\\]|\\.)*"', src)
        for lit in lits:
            body = lit.lstrip("$@").strip('"')
            if "{" in body:                       # 插值段 {preset.Work} 里只有键名, 取它外面的字面
                body = re.sub(r"\{[^{}]*\}", "", body)
            for ch in body:
                # ° 和 ~ 是天气卡上真的画出来的（「20° 阴」「今日 13° ~ 20°」），
                # 它们都掉在 0x2000 以下, 光靠「中文或数字」那一档抓不住
                if ord(ch) > 0x2000 or ch.isdigit() or ch in "·°~—":
                    chars.add(ch)
    need = "".join(sorted(chars))
    title_need = "".join(c for c in need if not c.isdigit())
    lines = ["代码 " + "  ".join(os.path.basename(p) for p, _ in texts),
             "标题那一族 = %s" % title_family, "正文/摘要那一族 = %s" % BODY_FAMILY,
             "从代码里抠出来要画的字（%d 个）= %s" % (len(need), need)]
    bad = []
    for family, subset in ((title_family, need), (BODY_FAMILY, need)):
        codes, files = pool(rows, family)
        if not files:
            bad.append("%s: 本机没有这一家(装了也不认)" % family)
            continue
        lack = [c for c in subset if ord(c) not in codes]
        if lack:
            bad.append("%s: 缺 %s（用的那几个字 %s 里都没有，画出来就是借笔）"
                       % (family, "".join(lack), "/".join(files)))
    lines += [""] + (bad if bad else ["每个字都在自己家名下, 没借笔"])
    io.open(os.path.join(HERE, "shots-fonts", "check.txt"), "w", encoding="utf-8").write(
        "\n".join(lines) + "\n")
    print("CHECK OK" if not bad else "CHECK FAIL")
    for l in lines:
        sys.stdout.buffer.write((l + "\n").encode("utf-8", "replace"))
    sys.stdout.flush()
    return 0 if not bad else 1


rows = scan()
sys.exit(check(rows) if "--check" in sys.argv[1:] else report(rows))
