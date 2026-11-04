# 出「成套暖族 0..9」: 用户 2026-10-29 定了 —— 仿形可收、走暖族、不加斜笔、大小以后还要调。
# 所以这里做三件事:
#   1) 真的 1..8 全部过同一套暖色阶重染(不是一半染一半不染, 那样两半的色阶对不上)
#   2) 0 和 9 用行楷骨架那份仿的(两个骨架肉眼分不出, 挑个来路正的 CJK 字体记账清楚)
#   3) 量出每个字的墨迹高/宽/分量(墨/墨高), 给「大小要调」留一张有基线的表, 别到时候凭感觉
import os

from PIL import Image, ImageDraw, ImageFont

import make_fake as mf
import make_sheet as ms

HERE = os.path.dirname(os.path.abspath(__file__))
SET_DIR = os.path.join(HERE, "warm")
TINT = "暖"
SKELETON = "行楷"
LABEL_FONT = "C:/Windows/Fonts/msyh.ttc"


def source(ch):
    """0/9 是仿的, 1..8 是库里的真图; 真图一律重染到暖色阶, 保证十个字同一套色"""
    if ch in ("0", "9"):
        return Image.open(os.path.join(mf.OUT, f"fake_{ch}_{SKELETON}_{TINT}.png")).convert("RGBA")
    im = ms.to_ink(Image.open(os.path.join(HERE, f"gui_ui_autochess_img_num_{ch}.png")).convert("RGBA"))
    return mf.recolor(im, TINT)


def main():
    os.makedirs(SET_DIR, exist_ok=True)
    reals = {str(d): ms.to_ink(Image.open(os.path.join(HERE, f"gui_ui_autochess_img_num_{d}.png")).convert("RGBA"))
             for d in range(1, 9)}
    half = {}          # 只染 5..8、1..4 保持原样 —— 另一种做法, 拿来对比用
    for d in range(1, 9):
        half[str(d)] = reals[str(d)] if d <= 4 else mf.recolor(reals[str(d)], TINT)
    for d in ("0", "9"):
        half[d] = Image.open(os.path.join(mf.OUT, f"fake_{d}_{SKELETON}_{TINT}.png")).convert("RGBA")

    hs, ws, ths = [], [], []
    for d in "0123456789":
        im = source(d)
        im.save(os.path.join(SET_DIR, f"{d}.png"))
        a = im.split()[3]
        box = mf.ink_box(a, 24)
        hs.append(box[3] - box[1])
        ws.append(box[2] - box[0])
        ths.append(mf.heft(im))
    mh = sorted(hs)[len(hs) // 2]
    print("成套暖族 0..9 实测（墨迹高/宽、分量=墨/墨高；高差就是「大小要调」的量）")
    for i, d in enumerate("0123456789"):
        src = "仿" if d in ("0", "9") else "真"
        print(f"  {d}  {src}  高={hs[i]:>3} ({hs[i] - mh:+3})  宽={ws[i]:>3}  分量={ths[i]:.1f}")
    print(f"  中位高={mh}  最高/最矮={max(hs)}/{min(hs)}  极差={max(hs) - min(hs)} px"
          f"  = {100 * (max(hs) - min(hs)) / mh:.0f}%")

    # 冒号跟着成套一起出：库里根本没有这个字形，而浮窗拼的是 mm:ss，少它就得回去用系统字体画字
    ms.colon_tile(TINT, mh).save(os.path.join(SET_DIR, "colon.png"))
    print(f"  冒号 高={mh}（点画在中位高的 ±14）→ {os.path.join(SET_DIR, 'colon.png')}")

    # 联系表: 1:1 一套 + 半染一套 + 浮窗里真会用的 40px 实景
    lf = ImageFont.truetype(LABEL_FONT, 14)
    cell, pad = 118, 10
    w = cell * 10 + pad
    canvas = Image.new("RGB", (w, 3 * (cell + 34) + 16), (24, 24, 26))
    d = ImageDraw.Draw(canvas)
    for row, (name, imgs) in enumerate([
            ("成套（1..8 全重染）", [source(c) for c in "0123456789"]),
            ("对比（只染 5..8，1..4 原样）", [half[c] for c in "0123456789"]),
    ]):
        y = 12 + row * (cell + 34)
        d.text((pad, y), name, font=ImageFont.truetype(LABEL_FONT, 17), fill=(226, 214, 190))
        for i, im in enumerate(imgs):
            r = min((cell - 12) / im.height, (cell - 6) / im.width)
            small = im.resize((max(1, round(im.width * r)), max(1, round(im.height * r))), Image.LANCZOS)
            x = pad + i * cell
            canvas.paste(small, (int(x + (cell - small.width) / 2), int(y + 24 + (cell - 24 - small.height) / 2)), small)
            d.text((x + 4, y + cell + 12), "0123456789"[i], font=lf, fill=(205, 205, 205))
    y = 12 + 2 * (cell + 34)
    d.text((pad, y), "实景 40px（浮窗真会用的字高）", font=ImageFont.truetype(LABEL_FONT, 17), fill=(226, 214, 190))
    seq = [source(c) for c in "2509"]
    x = pad
    for i, im in enumerate(seq):
        r = 40 / im.height
        small = im.resize((max(1, round(im.width * r)), 40), Image.LANCZOS)
        canvas.paste(small, (x, y + 30), small)
        x += small.width + 4
        if i == 1:
            c = ms.colon_tile(TINT, 40).resize((16, 40), Image.LANCZOS)
            canvas.paste(c, (x, y + 30), c)
            x += 20
    path = os.path.join(HERE, "_set_warm.png")
    canvas.save(path)
    print("联系表:", path)


if __name__ == "__main__":
    main()
