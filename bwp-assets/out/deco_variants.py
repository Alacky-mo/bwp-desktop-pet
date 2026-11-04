"""同一批素材摆三种构图，并排看哪套不像「纸上有脏东西」。

底图还是 panelshot 那张真面板；每格下面写清楚摆了哪几件、在哪。
用法: python deco_variants.py
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "shots-border", "panel_w276_p0_idle.png")
POOL = os.path.join(HERE, "focus_ui")
OUT = os.path.join(HERE, "shots-deco")
PRE = "gui_ui_title_img_44_"

VARIANTS = [
    ("V2 只收右下角一角（落叶+枫叶+光点）", [
        ("luoyeyou6", 246, 300), ("fengye1", 240, 338), ("guangdian1", 246, 366)]),
    ("V4 右下角摆成一小景（坠子+枫叶+光点）", [
        ("zhenzi1", 246, 296), ("fengye1", 240, 332), ("guangdian1", 244, 364)]),
    ("V5 V4 + 题带那头一枚小枫叶起势", [
        ("zhenzi1", 246, 296), ("fengye1", 240, 332), ("guangdian1", 244, 364),
        ("fengye2", 250, 66)]),
    ("V6 坠子+枫叶，不撒光点", [
        ("zhenzi1", 246, 300), ("fengye1", 240, 336)]),
]


def render(bits):
    with Image.open(BASE) as src:
        panel = src.convert("RGBA")
    for stem, x, y in bits:
        with Image.open(os.path.join(POOL, PRE + stem + ".png")) as bit:
            im = bit.convert("RGBA")
        panel.alpha_composite(im, (x, y))
    return panel


def main():
    os.makedirs(OUT, exist_ok=True)
    Z, gap = 2, 16
    imgs = [(cap, render(bits), bits) for cap, bits in VARIANTS]
    w, h = imgs[0][1].width * Z, imgs[0][1].height * Z
    canvas = Image.new("RGB", (w * len(imgs) + gap * (len(imgs) + 1), h + 120), (24, 24, 26))
    d = ImageDraw.Draw(canvas)
    try:
        f = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
    except OSError:
        f = ImageFont.load_default()
    for i, (cap, img, bits) in enumerate(imgs):
        x = gap + i * (w + gap)
        canvas.paste(img.convert("RGB").resize((w, h), Image.NEAREST), (x, 60))
        d.text((x, 12), cap, fill=(230, 210, 160), font=f)
        lines = "\n".join(f"{s} @({xx},{yy})" for s, xx, yy in bits)
        d.text((x, 60 + h + 6), lines, fill=(170, 170, 170), font=f)
    canvas.save(os.path.join(OUT, "deco_variants.png"))
    print(canvas.size, "→", os.path.join(OUT, "deco_variants.png"))

    # 光点那张到底有多少墨，顺便量一下（标签里写「几乎空」，别是贴了等于没贴）
    for stem in ("guangdian1", "fengye1", "fengye2", "zhenzi1", "luoyeyou6"):
        with Image.open(os.path.join(POOL, PRE + stem + ".png")) as bit:
            size, g = bit.size, bit.convert("L")
            px = list(g.getdata())
        ink = sum(1 for v in px if v < 240)
        print(f"{stem:12} 尺寸={size} 有墨的像素={ink}")


if __name__ == "__main__":
    main()
