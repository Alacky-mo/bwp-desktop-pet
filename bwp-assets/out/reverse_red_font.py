# -*- coding: utf-8 -*-
# 反向验新判据: 把这一轮引入的每一类 bug 挨个放回去, 看它红不红。
# 每步都改完就还原; 产物只写一份报告 out/shots-fonts/reverse-red.txt
import io, os, re, shutil, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
PET = ROOT
SRC = os.path.join(PET, "deskspine", "DeskSpine", "src", "FocusPresetForm.cs")
OUTBASE = os.path.join(PET, "deskspine", "out-side")
SIDE = os.path.join(OUTBASE, "x64", "Release", "net8.0-windows", "win-x64")
DECO = os.path.join(SIDE, "res", "image", "focus_ui", "deco")
EXE = os.path.join(PET, "bwp-assets", "animator-test", "bin", "Release", "net8.0-windows", "bwp-animator-test.exe")
log = []

def patch(old, new, n=1):
    s = io.open(SRC, encoding="utf-8").read()
    assert s.count(old) == n, "锚点对不上: %r 出现 %d 次" % (old[:24], s.count(old))
    io.open(SRC, "w", encoding="utf-8", newline="").write(s.replace(old, new))
    return s

def restore(s):
    io.open(SRC, "w", encoding="utf-8", newline="").write(s)

def sh(cmd):
    # 超时兜底: 这条线上一栽过一次「管道被活着的子进程锁死」, 宁可报错也不要挂住
    p = subprocess.run(cmd, cwd=PET, capture_output=True, shell=False, timeout=600)
    return p.returncode, (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")

def build():
    return sh(["dotnet", "build", "deskspine/DeskSpine.sln", "-c", "Release",
               "-p:BaseOutputPath=%s\\" % OUTBASE, "-v", "q", "--nologo"])

def desk():
    return sh([EXE, "desk", os.path.join(SIDE, "DeskSpine.dll")])

def record(what, want_red, rc, out, needle):
    # 光看退出码只能证明「这一大条红了」, 证不了红在哪一小条 —— 把 ✗ 那几行一并抓进报告
    hit = [l.strip() for l in out.splitlines() if needle in l or l.strip().startswith("✗")]
    got_red = rc == 1
    line = "%-40s 期望%s 实际%s -> %s\n    %s" % (
        what, "红" if want_red else "绿", "红" if got_red else "绿",
        "符合" if got_red == want_red else "★不符合★", "\n    ".join(hit[:4])[:900])
    log.append(line)
    print(("| " + line.replace("\n", "\n  | ")).encode("ascii", "backslashreplace").decode()[:700])

# ① 标题换成那个「认得出名字却没有字形」的素晴字体: GDI+ 侧照旧全绿, 只有 cmap 那一半会红
s = patch('"华文中宋"', '"素晴字体"')
rc, out = sh(["python", "bwp-assets/out/font_cover.py", "--check"])
record("① TitleFamily=素晴字体 → font_cover --check", True, rc, out, "缺")
build(); rc2, out2 = desk()
record("① 同一改动 → desk(证明 C# 那条看不见借笔)", False, rc2, out2, "版面里的字与右下角装饰件")
restore(s)

# ② 小字退回 15 常规
s = patch("smallFont = new(SystemFonts.MessageBoxFont!.FontFamily, 17f, FontStyle.Bold",
          "smallFont = new(SystemFonts.MessageBoxFont!.FontFamily, 15f, FontStyle.Regular")
build(); rc, out = desk(); record("② smallFont 退回 15 常规", True, rc, out, "小字真的又粗"); restore(s)

# ③ 摘要盒退回 PadX(就是上一轮真发生过的那次溢出: 盒子只有 224 宽, 最宽那句 227 顶出去)
s = patch("var summaryW = panelWidth - 2 * PaperMargin;\n            var summary = new Rectangle(CentreX(panelWidth, summaryW), y, summaryW, SummaryH);",
          "var summaryW = panelWidth - 2 * PadX;\n            var summary = new Rectangle(PadX, y, summaryW, SummaryH);")
build(); rc, out = desk(); record("③ 摘要盒退回 PadX 224 宽", True, rc, out, "放进 摘要"); restore(s)

# ④ 叶子挪到主按钮那一块上
s = patch('(@"deco\\fengye2.png", 11, 312)', '(@"deco\\fengye2.png", 90, 352)')
build(); rc, out = desk(); record("④ 枫叶压到主按钮", True, rc, out, "fengye2 不压文字"); restore(s)

# ⑤ 装机那张图不见了(DrawDeco 会一声不响地一枚都不画)
gone = os.path.join(DECO, "fengye2.png")
shutil.move(gone, gone + ".bak")
rc, out = desk(); record("⑤ deco/fengye2.png 没装机", True, rc, out, "装饰件表里有人")
shutil.move(gone + ".bak", gone)

# ⑥ 标题字号涨到盖过标题盒
s = patch("TitleSize = 28", "TitleSize = 46")
build(); rc, out = desk(); record("⑥ 标题 28 → 46", True, rc, out, "放进 标题"); restore(s)

# ⑦ 标题退回坐在 PadY 那一档(就是用户这次报的「被上面斜斜的装饰物挡住」)
s = patch("private const int TitleY = 24;", "private const int TitleY = 12;")
build(); rc, out = desk(); record("⑦ TitleY 24 → 12", True, rc, out, "标题的墨不压顶栏那两笔墨痕"); restore(s)

# ⑧ 摘要盒退回照 PaperMargin 起(盒子中线 138 = 整幅宽的一半, 比选项组左 10 格)
s = patch("new Rectangle(CentreX(panelWidth, summaryW), y, summaryW, SummaryH)",
          "new Rectangle(PaperMargin, y, summaryW, SummaryH)")
build(); rc, out = desk(); record("⑧ 摘要盒退回左边照纸边起", True, rc, out, "摘要和选项组坐在同一条纸面中线上"); restore(s)

# 全还原后必须复绿
build(); rc, out = desk()
log.append("还原后复跑 desk: 退出码 %d (%s)" % (rc, "DESK OK" if rc == 0 else "还红着"))
rc, out = sh(["python", "bwp-assets/out/font_cover.py", "--check"])
log.append("还原后复跑 font_cover --check: 退出码 %d (%s)" % (rc, "CHECK OK" if rc == 0 else "还红着"))

io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots-fonts", "reverse-red.txt"),
        "w", encoding="utf-8").write("\n\n".join(log) + "\n")
print("REVERSE RED DONE rc_last=%d" % rc)
