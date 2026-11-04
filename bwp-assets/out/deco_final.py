# -*- coding: utf-8 -*-
"""装饰件定稿对比：几套构图都贴在 panelshot 出的真面板图上看，名字用 focus_ui_labels.tsv 里那条。
坐标就是将来 Compose 里要用的坐标；每张旁边标出它压到哪个打靶框、有没有出纸界。
用法: python deco_final.py
"""
import io, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "shots-border", "panel_w276_p0_idle.png")
POOL = os.path.join(HERE, "focus_ui")
OUT = os.path.join(HERE, "shots-deco")
PRE = "gui_ui_title_img_44_"
PAPER_L, PAPER_R = 21, 272          # 纸自己的左右边线，出这条就是贴到纸外面了

SPOTS = {"Title": (26, 12, 186, 44), "Close": (220, 12, 44, 44),
         "Row0": (65, 64, 166, 54), "Row1": (65, 118, 166, 54), "Row2": (65, 172, 166, 54),
         "Summary": (26, 234, 224, 24), "Switch": (65, 266, 166, 54), "Start": (73, 328, 150, 66)}

lab = {}
for ln in io.open(os.path.join(HERE, os.pardir, "focus_ui_labels.tsv"), encoding="utf-8"):
    a = ln.rstrip("\n").split("\t")
    if len(a) >= 2:
        lab[a[0]] = a[1]

CORNER = [("zhenzi1", (246, 296)), ("fengye1", (240, 332))]
VARIANTS = [
    ("C1 右下角一小景：金坠子 + 枫叶", CORNER),
    ("C2 C1 + 上面一枚落叶·右飘6", CORNER + [("luoyeyou6", (250, 268))]),
    ("C3 C1 + 标题金纹横底原尺寸压在标题后", [("diban", (26, 12))] + CORNER),
    ("C4 只换纸人：右下角一枚纸人", [("zhiren", (234, 300))]),
    ("C5 C1 + 顶部右角一枚枫叶·纯金", CORNER + [("fengye2", (252, 62))]),
]


def overlap(a, b):
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or
                a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


def build(items):
    panel = Image.open(BASE).convert("RGBA")
    notes = []
    for stem, (x, y) in items:
        im = Image.open(os.path.join(POOL, PRE + stem + ".png")).convert("RGBA")
        box = (x, y, im.width, im.height)
        hits = [n for n, r in SPOTS.items() if overlap(box, r)]
        off = x < PAPER_L or x + im.width > PAPER_R or y < 0 or y + im.height > panel.height
        notes.append(f"{lab.get(PRE + stem, stem)} {im.width}x{im.height}@({x},{y}) "
                     f"压={hits or '无'} 出纸界={'是' if off else '否'}")
        panel.alpha_composite(im, (x, y))
    return panel, notes


report = io.StringIO()
cols = 3
scale = 2
cards = []
for name, items in VARIANTS:
    p, notes = build(items)
    report.write(name + "\n  " + "\n  ".join(notes) + "\n\n")
    cards.append((name, p))

gap, lab_h = 16, 26
w = cards[0][1].width * scale + gap
h = cards[0][1].height * scale + lab_h
rows = (len(cards) + cols - 1) // cols
sheet = Image.new("RGBA", (cols * w, rows * h), (26, 24, 30, 255))
d = ImageDraw.Draw(sheet)
lf = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
for i, (name, p) in enumerate(cards):
    cx, cy = (i % cols) * w, (i // cols) * h
    d.text((cx + 6, cy + 4), name, font=lf, fill=(235, 235, 235))
    big = p.resize((p.width * scale, p.height * scale), Image.NEAREST)
    sheet.paste(big, (cx, cy + lab_h))
os.makedirs(OUT, exist_ok=True)
sheet.convert("RGB").save(os.path.join(OUT, "deco_final.png"))
io.open(os.path.join(OUT, "deco-final-report.txt"), "w", encoding="utf-8").write(report.getvalue())
print(report.getvalue())
print("→", os.path.join(OUT, "deco_final.png"), sheet.size)
