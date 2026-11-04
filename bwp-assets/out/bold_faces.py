# -*- coding: utf-8 -*-
# 「这一家的粗是自己带的，还是 GDI+ 拿常规面描边描出来的」—— 这条不能问 GDI+。
# FontFamily.IsStyleAvailable(Bold) 对宋体回 True，可 simsun.ttc 里压根没有 Bold 面，
# 那一版字体候选表就是被它骗过一次。所以只能去问字体文件自己的命名表（nameID=2 那一栏）。
# 产出 shots-fonts/bold-faces.txt：一行一个「带真粗面」的家族名（中英文都写），panelshot 读它打标签。
import io, os
from fontTools.ttLib import TTFont, TTCollection

HERE = os.path.dirname(os.path.abspath(__file__))
DIRS = [r"C:\Windows\Fonts", os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Fonts")]
BOLD = ("bold", "black", "heavy", "粗体")   # 只看子脸那一栏；「黑体」是家族名不是字重，写进来会误判

def face_names(f):
    fam = set()
    sub = set()
    for rec in f["name"].names:
        if rec.platformID not in (3, 1):
            continue
        try:
            v = rec.toUnicode()
        except Exception:
            continue
        if rec.nameID in (1, 16):
            fam.add(v)
        elif rec.nameID in (2, 17):
            sub.add(v)
    return fam, sub

bold_families = set()
for d in DIRS:
    if not os.path.isdir(d):
        continue
    for fn in sorted(os.listdir(d)):
        if not fn.lower().endswith((".ttf", ".ttc", ".otf")):
            continue
        p = os.path.join(d, fn)
        try:
            faces = TTCollection(p, lazy=True).fonts if fn.lower().endswith(".ttc") else [TTFont(p, fontNumber=0, lazy=True)]
        except Exception:
            continue
        for f in faces:
            try:
                fam, sub = face_names(f)
            except Exception:
                continue
            if any(any(k in s.lower() for k in BOLD) for s in sub):
                bold_families |= fam

out = io.open(os.path.join(HERE, "shots-fonts", "bold-faces.txt"), "w", encoding="utf-8")
out.write("# 这些家族里至少有一张脸自己声明是粗体（nameID=2 里带 Bold/粗体），不是电脑描边仿的\n")
for name in sorted(bold_families):
    out.write(name + "\n")
out.close()
print("bold faces = %d -> shots-fonts/bold-faces.txt" % len(bold_families))
for probe in ("宋体", "SimSun", "华文中宋", "Microsoft YaHei UI", "Noto Serif SC", "等线", "黑体"):
    print("%-22s %s" % (probe, "有真粗面" if probe in bold_families else "没有(要粗就是仿的)"))
