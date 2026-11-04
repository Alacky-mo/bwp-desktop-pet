# -*- coding: utf-8 -*-
"""标题金纹横底到底能不能压在标题那一行底下用 —— 关键是**先后顺序**：先摆金底，再写字。
deco_final.py 那张是把装饰件盖在已画好的面板上，所以标题被底吃掉了，那张不能用来判这条。
这里按将来 Compose 的顺序重画一遍：纸 → 金底 → 角上那两枚 → 标题字 → 摘要字。
用法: python deco_zorder.py
"""
import io, os
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "shots-border", "panel_w276_p0_idle.png")
POOL = os.path.join(HERE, "focus_ui")
OUT = os.path.join(HERE, "shots-deco")
PRE = "gui_ui_title_img_44_"
INK = (43, 43, 43)
TITLE_AT = (26, 12, 186, 44)          # FocusPresetForm.Arrange 在 276 宽下量出来的标题盒
SUM_AT = (26, 234, 224, 24)
SENT = "短休 5 · 长假 15 · 连做 4 段"


def bit(name):
    return Image.open(os.path.join(POOL, PRE + name + ".png")).convert("RGBA")


def vcentre(box, h):
    return box[0], box[1] + (box[3] - h) // 2


def build(with_band, title_path, title_size, title_bold_stroke):
    p = Image.open(BASE).convert("RGBA")
    # 先把原来那行字抹了：金底不铺满整行，剩下的旧字会和新字叠成重影
    if not with_band:
        d = ImageDraw.Draw(p)
        d.rectangle([TITLE_AT[0], TITLE_AT[1], TITLE_AT[0] + TITLE_AT[2], TITLE_AT[1] + TITLE_AT[3]],
                    fill=(0, 0, 0, 0))
    if with_band:
        b = bit("diban")
        p.alpha_composite(b, (TITLE_AT[0], 11))
    for stem, xy in [("zhenzi1", (246, 296)), ("fengye1", (240, 332))]:
        p.alpha_composite(bit(stem), xy)
    d = ImageDraw.Draw(p)
    f = ImageFont.truetype(title_path, title_size)
    d.text(vcentre(TITLE_AT, title_size) , "番茄钟", font=f, fill=INK,
           stroke_width=title_bold_stroke, stroke_fill=INK)
    fs = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 17)
    w = d.textlength(SENT, font=fs)
    d.text((SUM_AT[0] + (SUM_AT[2] - w) / 2, SUM_AT[1] + 2), SENT, font=fs, fill=INK)
    return p


CARDS = [
    ("D1 金底 + 华文中宋 28 写在底上", build(True, r"C:\Windows\Fonts\STZHONGS.TTF", 28, 0)),
    ("D2 不要金底，华文中宋 28", build(False, r"C:\Windows\Fonts\STZHONGS.TTF", 28, 0)),
    ("D3 金底 + 华文行楷 28", build(True, r"C:\Windows\Fonts\STXINGKA.TTF", 28, 0)),
]
gap, scale = 14, 2
w = CARDS[0][1].width * scale + gap
h = CARDS[0][1].height * scale + 26
sheet = Image.new("RGBA", (len(CARDS) * w, h), (26, 24, 30, 255))
d = ImageDraw.Draw(sheet)
lf = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
for i, (name, p) in enumerate(CARDS):
    d.text((i * w + 6, 4), name, font=lf, fill=(235, 235, 235))
    sheet.paste(p.resize((p.width * scale, p.height * scale), Image.NEAREST), (i * w, 26))
os.makedirs(OUT, exist_ok=True)
sheet.convert("RGB").save(os.path.join(OUT, "deco_zorder.png"))
print("→", os.path.join(OUT, "deco_zorder.png"), sheet.size)
