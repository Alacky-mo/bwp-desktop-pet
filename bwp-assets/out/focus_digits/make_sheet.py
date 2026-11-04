# 出对比表交用户判断。三块:
#   1) 真数字 1..8 —— 基准
#   2) 仿的 0 / 9 —— 骨架(行楷/毛笔) × 色系(暖/冷)
#   3) 实景 25:09 —— 仿的字和真的字混排, 1:1 尺寸下看眼睛能不能挑出来
# 所有格子都先裁到墨迹外接框、再按同一个墨迹高画, 不然「看起来更小」只是留白不同。
import os

from PIL import Image, ImageDraw, ImageFont

import make_fake as mf

HERE = os.path.dirname(os.path.abspath(__file__))
BG = (43, 43, 43)          # 本机深色主题实测的任务栏/提示底色
LABEL_FONT = "C:/Windows/Fonts/msyh.ttc"
DRAW_H = 100               # 每个格子里统一画这么高的墨迹
CELL_W, CELL_H, GAP = 158, 152, 8
TITLE_H, ROW_LABEL_W = 48, 118


def to_ink(img):
    return img.crop(mf.ink_box(img.split()[3], 24))


def real_row():
    return [(str(d), to_ink(Image.open(os.path.join(HERE, f"gui_ui_autochess_img_num_{d}.png")).convert("RGBA")))
            for d in range(1, 9)]


def fake_row(ch):
    cells = []
    for fl in mf.FONTS:
        for tl in mf.TINTS:
            p = os.path.join(mf.OUT, f"fake_{ch}_{fl}_{tl}.png")
            cells.append((f"{ch}｜{fl}·{tl}", to_ink(Image.open(p).convert("RGBA"))))
    return cells


def colon_tile(tint, h):
    fill, line = mf.TINTS[tint]["fill"], mf.TINTS[tint]["line"]
    t = Image.new("RGBA", (26, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    for cy in (h // 2 - 14, h // 2 + 14):
        d.ellipse((5, cy - 8, 21, cy + 8), fill=line)
        d.ellipse((7, cy - 6, 19, cy + 6), fill=fill)
    return t


def countdown(tint, fl="行楷"):
    """25:09 —— 真的 2/5 也过同一套色阶, 和仿的 0/9 混排; 不重染的话这里就是「混排会花」本身的现场照"""
    reals = {d: mf.recolor(to_ink(Image.open(os.path.join(HERE, f"gui_ui_autochess_img_num_{d}.png")).convert("RGBA")), tint)
             for d in (2, 5)}
    fakes = {c: to_ink(Image.open(os.path.join(mf.OUT, f"fake_{c}_{fl}_{tint}.png")).convert("RGBA"))
             for c in ("0", "9")}
    seq = [reals[2], reals[5], colon_tile(tint, DRAW_H), fakes["0"], fakes["9"]]
    gap = 7
    w = sum(s.width for s in seq) + gap * (len(seq) - 1) + 24
    tile = Image.new("RGBA", (w, DRAW_H + 24), (0, 0, 0, 0))
    x = 12
    for s in seq:
        r = DRAW_H / s.height
        im = s.resize((max(1, round(s.width * r)), DRAW_H), Image.LANCZOS)
        tile.paste(im, (x, (DRAW_H + 24 - im.height) // 2), im)
        x += im.width + gap
    return tile


def cell(canvas, x, y, label, img, lf):
    d = ImageDraw.Draw(canvas)
    d.rectangle((x, y, x + CELL_W, y + CELL_H), fill=BG)
    r = min(DRAW_H / img.height, (CELL_W - 18) / img.width)
    im = img.resize((max(1, round(img.width * r)), max(1, round(img.height * r))), Image.LANCZOS)
    canvas.paste(im, (x + (CELL_W - im.width) // 2, y + 6 + (DRAW_H - im.height) // 2 + 4), im)
    d.text((x + 7, y + CELL_H - 24), label, font=lf, fill=(205, 205, 205, 255))


def full_set(tint):
    """成套的 0..9: 仿的 0/9 + 真的 1..8 一起染到同一个色系"""
    cells = [(f"0｜仿", to_ink(Image.open(os.path.join(mf.OUT, f"fake_0_行楷_{tint}.png")).convert("RGBA")))]
    for d in range(1, 9):
        im = to_ink(Image.open(os.path.join(HERE, f"gui_ui_autochess_img_num_{d}.png")).convert("RGBA"))
        cells.append((f"{d}｜真", mf.recolor(im, tint)))
    cells.append((f"9｜仿", to_ink(Image.open(os.path.join(mf.OUT, f"fake_9_行楷_{tint}.png")).convert("RGBA"))))
    return cells


def main():
    lf = ImageFont.truetype(LABEL_FONT, 15)
    tf = ImageFont.truetype(LABEL_FONT, 21)
    rows = [("真数字\n库里现成\n(注意冷暖\n不是一族)", real_row()),
            ("仿的 0\n骨架×色系", fake_row("0")),
            ("仿的 9\n骨架×色系", fake_row("9")),
            ("成套 0..9\n全染暖族\n(已选)", full_set("暖")),
            ("成套 0..9\n全染冷族", full_set("冷"))]
    shots = [("实景\n成套·暖", countdown("暖")), ("实景\n成套·冷", countdown("冷")),
             ("实景\n暖·毛笔骨架", countdown("暖", "毛笔"))]
    cols = 10
    body_h = len(rows) * (CELL_H + 8) + len(shots) * (CELL_H + 8)
    canvas = Image.new("RGB", (ROW_LABEL_W + cols * (CELL_W + GAP) + 16, TITLE_H + body_h + 16),
                       (24, 24, 26))
    d = ImageDraw.Draw(canvas)
    d.text((16, 13), "番茄钟数字 · 仿 0/9 对比（百闻牌素材为网易/画师版权，仅本机个人使用，不随任何产物分发）",
           font=tf, fill=(240, 232, 214))
    y = TITLE_H
    for name, cells_ in rows:
        d.text((12, y + 34), name, font=lf, fill=(226, 214, 190))
        for i, (lbl, im) in enumerate(cells_):
            cell(canvas, ROW_LABEL_W + i * (CELL_W + GAP), y, lbl, im, lf)
        y += CELL_H + 8
    for lbl, tile in shots:
        d.text((12, y + 34), lbl, font=lf, fill=(226, 214, 190))
        canvas.paste(tile, (ROW_LABEL_W + 14, y + 20), tile)
        d.rectangle((ROW_LABEL_W, y, ROW_LABEL_W + cols * (CELL_W + GAP), y + CELL_H), outline=(72, 72, 78))
        y += CELL_H + 8
    path = os.path.join(HERE, "_compare_fake.png")
    canvas.save(path)
    print(path)


if __name__ == "__main__":
    main()
