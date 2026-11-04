# -*- coding: utf-8 -*-
"""右下角那一小景的最后一次二选一：叶子一路飘下来 vs 中间挂一枚金坠子。
金坠子在游戏里是挂在标题金底下面的，金底这轮没用上，让它单独悬在纸上就有点没着落 —— 所以两张都摆出来看一眼。
用法: python deco_drift.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "shots-border", "panel_w276_p0_idle.png")
POOL = os.path.join(HERE, "focus_ui")
OUT = os.path.join(HERE, "shots-deco")
PRE = "gui_ui_title_img_44_"

SETS = [
    ("F1 一路飘下来：枫叶·纯金 → 落叶·右飘6 → 枫叶·紫心金边",
     [("fengye2", (250, 262)), ("luoyeyou6", (246, 296)), ("fengye1", (238, 330))]),
    ("C2 中间那枚换成金坠子",
     [("luoyeyou6", (250, 268)), ("zhenzi1", (246, 300)), ("fengye1", (238, 332))]),
]

cards = []
for name, items in SETS:
    p = Image.open(BASE).convert("RGBA")
    for stem, xy in items:
        p.alpha_composite(Image.open(os.path.join(POOL, PRE + stem + ".png")).convert("RGBA"), xy)
    cards.append((name, p))

scale, lab_h, gap = 2, 26, 14
w = cards[0][1].width * scale + gap
sheet = Image.new("RGBA", (len(cards) * w, cards[0][1].height * scale + lab_h), (26, 24, 30, 255))
d = ImageDraw.Draw(sheet)
lf = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
for i, (name, p) in enumerate(cards):
    d.text((i * w + 6, 4), name, font=lf, fill=(235, 235, 235))
    sheet.paste(p.resize((p.width * scale, p.height * scale), Image.NEAREST), (i * w, lab_h))
sheet.convert("RGB").save(os.path.join(OUT, "deco_drift.png"))
print("→", os.path.join(OUT, "deco_drift.png"))
