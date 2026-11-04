# -*- coding: utf-8 -*-
"""装饰件候选：把库里这几枚各自摆到和风纸上看一眼，名字一律用 focus_ui_labels.tsv 里那条，不自己翻译。"""
import io, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
POOL = os.path.join(HERE, "focus_ui")
OUT = os.path.join(HERE, "shots-deco")
PRE = "gui_ui_title_img_44_"
PAPER = os.path.join(HERE, os.pardir, os.pardir, "deskspine", "out", "x64", "Release",
                     "net8.0-windows", "win-x64", "res", "image", "focus_ui", "bg_tips_3.png")
BITS = ["diban", "yuanquan", "zhenzi1", "zhenzi2", "fengye1", "fengye2",
        "luoyeyou6", "luoyezuo3", "zhiren", "nangua", "shuzi", "shoubi", "guangdian1"]

lab = {}
for ln in io.open(os.path.join(HERE, os.pardir, "focus_ui_labels.tsv"), encoding="utf-8"):
    a = ln.rstrip("\n").split("\t")
    if len(a) >= 2:
        lab[a[0]] = a[1]

paper = Image.open(PAPER).convert("RGBA")
cell_w, cell_h = 230, 110
lf = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 14)
cols = 3
rows = (len(BITS) + cols - 1) // cols
sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (26, 24, 30, 255))
d = ImageDraw.Draw(sheet)
for i, s in enumerate(BITS):
    im = Image.open(os.path.join(POOL, PRE + s + ".png")).convert("RGBA")
    cx, cy = (i % cols) * cell_w, (i // cols) * cell_h
    d.rectangle([cx, cy, cx + cell_w - 1, cy + cell_h - 1], outline=(70, 70, 80))
    # 底用真纸的一小块，浅底深底一眼能看出来
    sw = min(170, im.width + 40)
    sheet.paste(paper.crop((20, 60, 20 + sw, 60 + 70)), (cx + 20, cy + 18))
    scale = 2 if im.width <= 40 else 1
    big = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    sheet.paste(big, (cx + (cell_w - big.width) // 2, cy + 18 + (70 - big.height) // 2), big)
    d.text((cx + 8, cy + 92), f"{s}｜{lab.get(PRE + s, '?')} {im.width}x{im.height}", font=lf, fill=(230, 230, 230))
sheet.convert("RGB").save(os.path.join(OUT, "deco_bits.png"))
print("→", os.path.join(OUT, "deco_bits.png"), sheet.size)
