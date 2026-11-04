# 把 warm/ 那套数字**重新配平大小**再出一套 balanced/（用户 2026-10-31：「5 那颗不协调，把各个数字的大小再调调」）
#
# 现场量出来的两件事，决定了这里为什么不是「再缩一缩 5」那么简单：
#   1) warm/ 里 5 的画布是 82x103，可**本体只有 66x96** —— 右下角挂着一颗 76 px 的墨点；
#      6 也一样，左上角一颗 216 px 的斜杠把框撑到 63x102，本体 57x95。
#      FocusArt.DigitStrip 是「整图缩到 36 高」，所以那颗点既占位又把本体压小了一档。
#   2) 十个字的本体墨迹高本来就差 88..98（极差 10%），等高等比放大后，
#      宽字（4/7 宽高比 .82）显得胖、窄字（1 是 .55）显得细，一排看过去不齐。
#
# 所以这一步做三件事：把不属于本体的墨**抹掉**（不能只裁框 —— 6 那截斜杠有一截正好落在本体的框里）
# → 按「宽高比惩罚」给每颗字配一个目标高 → 全部贴到同一张 100 高画布、底边坐在同一条基线上。
# 这样 DigitStrip 那句「整图缩到 36 高」不用改一行，出来的就是一排共基线、宽窄有节的字。
#
# 装好的那 11 张由 desk 判据第 19 条量（同一张画布高 / 底边留白全等 / 墨迹高极差 ≤ 8%）；
# 杂点这一类它管不了，只有下面那张对拍图看得出。
#
# 用法: python make_balanced.py            （改完记得 python ../../install_focus_ui.py）
import os
from collections import deque

from PIL import Image, ImageDraw, ImageFont

import make_sheet as ms

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "warm")
OUT = os.path.join(HERE, "balanced")
THR = 24            # 判墨门槛，和 make_fake 的 heft / ink_box 同一档
CANVAS_H = 100      # 统一画布高
BASELINE = 98       # 底边坐这条线上（数字没有下伸部，底边即基线）
SIDE = 2            # 左右各留一点，避免缩放时贴边糊掉
LAMBDA = 0.35       # 宽高比惩罚：比中位宽的往小调、比中位窄的往大调，±5% 那一档


def components(im):
    """4-邻接连通块，返回 [(面积, 框, 像素)]，按面积从大到小"""
    a = im.split()[3]
    w, h = a.size
    px = a.load()
    seen = [[False] * w for _ in range(h)]
    out = []
    for y in range(h):
        for x in range(w):
            if px[x, y] < THR or seen[y][x]:
                continue
            q = deque([(x, y)])
            seen[y][x] = True
            box = [x, y, x + 1, y + 1]
            pts = []
            while q:
                cx, cy = q.popleft()
                pts.append((cx, cy))
                box[0] = min(box[0], cx)
                box[1] = min(box[1], cy)
                box[2] = max(box[2], cx + 1)
                box[3] = max(box[3], cy + 1)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and px[nx, ny] >= THR:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            out.append((len(pts), tuple(box), pts))
    return sorted(out, reverse=True)


def body(ch):
    """只留最大那块（>= 主块 20% 面积的算同一颗字，别把笔画切丢），再裁到本体。
    丢掉的块要真抹掉，不能只靠裁框 —— 6 那颗斜杠有一截正好落在本体的框里"""
    im = Image.open(os.path.join(SRC, f"{ch}.png")).convert("RGBA")
    cs = components(im)
    main_n = cs[0][0]
    keep = [(n, b, p) for n, b, p in cs if n >= main_n * 0.2]
    x0 = min(b[0] for _, b, _ in keep)
    y0 = min(b[1] for _, b, _ in keep)
    x1 = max(b[2] for _, b, _ in keep)
    y1 = max(b[3] for _, b, _ in keep)
    mask = Image.new("1", im.size, 0)
    for _, _, pts in keep:
        for p in pts:
            mask.putpixel(p, 1)
    kept = Image.new("RGBA", im.size, (0, 0, 0, 0))
    kept.paste(im, (0, 0), mask)
    # 只在左右留边（缩放时别贴边糊掉）；上下必须贴墨裁，不然每张的留白不一样，
    # 「贴到基线上」就贴不准 —— 判据 desk 第 19 条量的就是这个
    crop = kept.crop((max(0, x0 - SIDE), y0, min(im.width, x1 + SIDE), y1))
    return crop, cs, (x1 - x0, y1 - y0)


def main():
    os.makedirs(OUT, exist_ok=True)
    bodies = {}
    for ch in "0123456789":
        crop, cs, (bw, bh) = body(ch)
        bodies[ch] = (crop, bw, bh, cs)
    aspects = sorted(bw / bh for crop, bw, bh, cs in bodies.values())
    med_a = (aspects[4] + aspects[5]) / 2
    med_h = sorted(bh for crop, bw, bh, cs in bodies.values())[5]

    print(f"本体中位：高={med_h} 宽高比={med_a:.3f}   惩罚 λ={LAMBDA}（比中位宽的往小、窄的往大）")
    print(f"{'字':>3} {'原画布':>9} {'本体':>9} {'丢掉':>7} {'宽高比':>7} {'目标高':>7} {'导出':>9}")
    for ch in "0123456789":
        crop, bw, bh, cs = bodies[ch]
        src = Image.open(os.path.join(SRC, f"{ch}.png"))
        a = bw / bh
        target = round(med_h / (1 + LAMBDA * (a - med_a)))
        target = min(target, BASELINE)
        w = max(1, round(crop.width * target / bh))
        h = target
        big = crop.resize((w, h), Image.LANCZOS)
        tile = Image.new("RGBA", (w + 2 * SIDE, CANVAS_H), (0, 0, 0, 0))
        # 底是空的，直接整张盖上去就行。别写成 paste(big, pos, big)：拿 RGBA 自己当蒙版
        # 等于把 alpha 平方一遍，边缘那几排淡墨会掉到门槛以下，字就凭空缩一圈
        tile.paste(big, (SIDE, BASELINE - h))
        tile.save(os.path.join(OUT, f"{ch}.png"))
        dropped = sum(n for n, _, _ in cs[1:] if n < cs[0][0] * 0.2)
        print(f"{ch:>3} {src.width:>4}x{src.height:<4} {bw:>4}x{bh:<4} {dropped:>7} {a:>7.3f} {target:>7} "
              f"{tile.width:>4}x{tile.height}")

    # 冒号跟着配：同一张画布、两点坐在数字的腰上（原来按中位高 98 画的，现在按本体中位高）
    t = ms.colon_tile("暖", med_h)
    colon = Image.new("RGBA", (t.width + 2 * SIDE, CANVAS_H), (0, 0, 0, 0))
    colon.paste(t, (SIDE, BASELINE - med_h))
    colon.save(os.path.join(OUT, "colon.png"))
    print(f"冒号 {t.width + 2 * SIDE}x{CANVAS_H}（点画在腰上，底边同一条基线）→ {os.path.join(OUT, 'colon.png')}")

    sheet(med_h)


def strip(paths, h=36, gap=4, pad=8):
    """照 FocusArt.DigitStrip 的走法：整图缩到 h 高、贴 y=0、字间 gap"""
    tiles = []
    for p in paths:
        im = Image.open(p).convert("RGBA")
        tiles.append(im.resize((max(1, round(im.width * (h / im.height))), h), Image.LANCZOS))
    w = sum(t.width for t in tiles) + gap * (len(tiles) - 1) + 2 * pad
    canvas = Image.new("RGBA", (w, h + 2 * pad), (24, 24, 26, 255))
    x = pad
    for t in tiles:
        canvas.paste(t, (x, pad), t)
        x += t.width + gap
    return canvas


def sheet(med_h):
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    combos = ["25:09", "11:11", "38:46", "08:05", "17:59", "0123456789"]
    rows = []
    for name in combos:
        old = [os.path.join(SRC, "colon.png" if c == ":" else f"{c}.png") for c in name]
        new = [os.path.join(OUT, "colon.png" if c == ":" else f"{c}.png") for c in name]
        rows.append((f"{name}  改前（画布被杂点撑大、等高等比）", strip(old)))
        rows.append((f"{name}  改后（去杂点 + 宽高比惩罚 + 共基线）", strip(new)))
    pad, label_h = 10, 24
    w = max(r.width for _, r in rows) + 2 * pad
    h = sum(r.height + label_h for _, r in rows) + pad * (len(rows) + 1)
    canvas = Image.new("RGBA", (w, h), (18, 18, 20, 255))
    d = ImageDraw.Draw(canvas)
    y = pad
    for name, r in rows:
        d.text((pad, y), name, font=font, fill=(226, 214, 190, 255))
        y += label_h
        canvas.paste(r, (pad, y), r)
        y += r.height + pad
    out = os.path.join(HERE, "_balanced_sheet.png")
    canvas.save(out)
    print("对拍图（深浅底看观感，尺寸是浮窗真会用的 36 高）:", out, canvas.size)


if __name__ == "__main__":
    main()
