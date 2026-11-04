"""不知火应用图标「两色剪影」处理 —— 白 + 红，细节不要，只求 16 px 认得出是她。

判「红」的走法（先在 1127@happy 上试过阈值才定下来）：R 比 G/B 里大的那个高出 30 以上，
且 max(G,B) 不到 R 的 0.66 倍。前一条管住「白发/皮肤也偏暖」—— 皮肤 (250,225,215) 的
R−G 只有 25，会被这条挡掉；后一条管住橙红和琥珀色 —— 火苗 (250,120,40)、眼睛 (200,120,60)
都进红档。剩下的实心像素一律涂白，透明底。

用法：
  python app_icon_mark.py --probe     只出 out/icon_candidates/probe_twotone.png（看分档分得对不对）
  python app_icon_mark.py             出 out/icon_candidates/sheet_mark.png（六颗处理候选）
  python app_icon_mark.py --emit=4    把第 4 颗打成 256 见方母图（挑中哪颗就填几），接 png_to_ico.py 转 ico
产物不进仓库（.gitignore 的 /bwp-assets/out/** 挡着）；挑中之后的 ico 用 png_to_ico.py 转。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "out", "icon_candidates")
THUMB = os.path.join(ROOT, "out", "emo_thumbs")
SRC = os.path.join(THUMB, "buzhihuo_1127@happy.png")

WHITE = (243, 243, 246)
RED = (206, 32, 44)
EDGE = (120, 18, 30)
GROUND_RED = (140, 22, 34)
GROUND_INK = (26, 26, 32)
ALPHA_CUT = 100


def two_tone(path):
    """墨分两档：红档按上面的判据，其余实心全涂白；alpha 二值化（细节不要，边缘要稳）"""
    a = np.asarray(Image.open(path).convert("RGBA"), dtype=np.int16)
    r, g, b, al = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    solid = al > ALPHA_CUT
    is_red = solid & ((r - np.maximum(g, b)) > 30) & (np.maximum(g, b) < 0.66 * r)
    col = np.zeros(a.shape[:2] + (3,), dtype=np.uint8)
    col[solid] = WHITE
    col[is_red] = RED
    mark = np.dstack([col, np.where(solid, 255, 0).astype(np.uint8)])
    im = Image.fromarray(mark, "RGBA")
    bb = im.getbbox()
    return im.crop(bb) if bb else im, is_red, solid


def head_crop(im, rows):
    """从墨顶起留 rows 行（切掉身子），再补成正方 —— 和 png_to_ico.square() 同走法"""
    im = im.crop((0, 0, im.width, min(rows, im.height)))
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return sq


def square(im):
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return sq


def outlined(mark, w=2):
    """沿剪影外沿描一圈深色 —— 白底（文件管理器、浅色主题托盘）上不会整颗消失"""
    al = mark.split()[3]
    ring = ImageChops.subtract(al.filter(ImageFilter.MaxFilter(2 * w + 1)), al)
    out = Image.new("RGBA", mark.size, (0, 0, 0, 0))
    out.paste(mark, (0, 0), mark)
    out.paste(Image.new("RGBA", mark.size, EDGE + (255,)), (0, 0), ring)
    return out


def badge(mark, color, shape, inset=0.12):
    size = mark.width
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shape == "disc":
        d.ellipse([0, 0, size - 1, size - 1], fill=color + (255,))
    else:
        d.rounded_rectangle([0, 0, size - 1, size - 1], radius=size * 0.22, fill=color + (255,))
    s = int(size * (1 - 2 * inset))
    m = mark.resize((s, s), Image.LANCZOS)
    im.alpha_composite(m, ((size - s) // 2, (size - s) // 2))
    return im


def variants(ss=1):
    """ss>1 = 先把硬边剪影按 NEAREST 放大 ss 倍再画地子，最后整张缩回目标尺寸 ——
    圆盘/圆角方的边和描边都是矢量级几何，不超采样就会带锯齿；放大 ss 倍只糊不掉细节，因为缩回来是均值。"""
    mark, _, _ = two_tone(SRC)
    head = head_crop(mark, int(mark.height * 0.80))
    full = square(mark)
    if ss > 1:
        head = head.resize((head.width * ss, head.height * ss), Image.NEAREST)
        full = full.resize((full.width * ss, full.height * ss), Image.NEAREST)
    return [
        ("两色平涂 · 切身子的裁法", "红档=角/火苗/额印/眼，其余全白；透明底 —— 浅底上会看不见，表里那格就是给你看这个的", head),
        ("两色平涂 · 整幅不切", "同一判据、不切身子；白块一直铺到底", full),
        ("两色平涂 + 深色描边 · 切身子的裁法", "沿外沿描 2 px 深红，白底上也有一圈边界", outlined(head, 2 * ss)),
        ("深红圆盘徽章 + 两色平涂", "整颗坐在深红圆地上，四周留 12% —— 小尺寸边界最清楚", badge(head, GROUND_RED, "disc")),
        ("深红圆角方徽章 + 两色平涂", "同上换圆角方（和系统图标同形）", badge(head, GROUND_RED, "round")),
        ("墨底圆角方徽章 + 两色平涂", "深地子，白和红都跳得出来；和现用那枚剪影同色温，对照", badge(head, GROUND_INK, "round")),
    ]


def emit(idx, size=256, ss=4):
    """把第 idx 颗处理候选打成 size 见方的母图（用户挑中的那颗走这里）"""
    name, _, src = variants(ss)[idx - 1]
    out = src if src.width == size else src.resize((size, size), Image.LANCZOS)
    p = os.path.join(OUT, "mark_%02d_%s.png" % (idx, "badge" if idx >= 4 else "flat"))
    out.save(p)
    print("母图: %s  %dx%d  %s" % (p, out.width, out.height, name))
    return p


BIG = 112
SMALL = [48, 32, 16, 16, 64]
PAD = 14
STEP = BIG + 10
CARD_W = 2 * PAD + STEP * len(SMALL) + BIG
CARD_H = BIG + 112
COLS_N = 2
GUT = 14
HEAD = 56


def read16(src):
    tiny = src.resize((16, 16), Image.LANCZOS)
    pts = [(x, y) for y in range(16) for x in range(16) if tiny.getpixel((x, y))[3] > 0]
    if not pts:
        return "16 px 全空"
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return f"16 px 墨占 {len(pts)}/256 格, 撑开 {max(xs) - min(xs) + 1}×{max(ys) - min(ys) + 1}"


def probe():
    mark, is_red, solid = two_tone(SRC)
    a = np.asarray(Image.open(SRC).convert("RGBA"))
    vis = np.zeros(a.shape[:2] + (4,), dtype=np.uint8)
    vis[solid] = (243, 243, 246, 255)
    vis[is_red] = (206, 32, 44, 255)
    im = Image.fromarray(vis, "RGBA")
    bg = Image.new("RGBA", im.size, (40, 40, 46, 255))
    bg.alpha_composite(im)
    bg.resize((768, 768), Image.LANCZOS).save(os.path.join(OUT, "probe_twotone.png"))
    n = int(solid.sum())
    print("分档: 实心 %d 格 / 红档 %d 格 = %.1f%%" % (n, int(is_red.sum()), 100.0 * is_red.sum() / max(1, n)))
    print("探针图:", os.path.join(OUT, "probe_twotone.png"))


def sheet():
    os.makedirs(OUT, exist_ok=True)
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 16)
    tiny = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 12)
    small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 13)
    vs = variants()
    rows = (len(vs) + COLS_N - 1) // COLS_N
    sheet_im = Image.new("RGBA", (COLS_N * CARD_W + GUT, rows * CARD_H + HEAD), (24, 24, 28, 255))
    d = ImageDraw.Draw(sheet_im)
    d.text((GUT, 10), "不知火 02 闭眼笑 → 白+红两色剪影的处理候选 —— 每颗一条横带：112 / 48 / 32 / 16 贴深底 / 16 贴浅底 / 16 放大 4 倍看",
           font=small, fill=(255, 228, 132))
    d.text((GUT, 30), "「16 贴浅底」那一格是白底（文件管理器、浅色主题托盘）：纯白剪影在那儿会淡掉，看这一格判要不要描边或地子。",
           font=tiny, fill=(170, 170, 180))
    for i, (name, note, src) in enumerate(vs):
        cx = (i % COLS_N) * CARD_W
        cy = HEAD + (i // COLS_N) * CARD_H
        d.rectangle([cx + 4, cy + 4, cx + CARD_W - 6, cy + CARD_H - 8], outline=(52, 52, 62))
        d.text((cx + PAD, cy + 12), f"{i + 1:02d}  {name}", font=font, fill=(255, 228, 132))
        d.text((cx + PAD, cy + 34), note, font=tiny, fill=(200, 200, 200))
        d.text((cx + PAD, cy + CARD_H - 24), read16(src), font=tiny, fill=(150, 190, 150))
        x = cx + PAD
        top = cy + 72
        for j, s in enumerate([BIG] + SMALL):
            img = src.resize((16, 16), Image.LANCZOS).resize((64, 64), Image.NEAREST) if s == 64 else src.resize((s, s), Image.LANCZOS)
            bx, by = x + (BIG - s) // 2, top + (BIG - s) // 2
            if j == 3:
                d.rectangle([bx - 5, by - 5, bx + s + 4, by + s + 4], fill=(48, 48, 54, 255))
            elif j == 4:
                d.rectangle([bx - 5, by - 5, bx + s + 4, by + s + 4], fill=(238, 238, 240, 255))
            sheet_im.alpha_composite(img, (bx, by))
            d.text((x + (BIG - s) // 2, top + BIG + 4), "16×4" if s == 64 else str(s), font=tiny, fill=(150, 150, 160))
            x += STEP
    out = os.path.join(OUT, "sheet_mark.png")
    sheet_im.save(out)
    print(f"处理候选表: {out}  {sheet_im.size[0]}x{sheet_im.size[1]}  {len(vs)} 颗")


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    emit_idx = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--emit=")), None)
    if "--probe" in sys.argv:
        probe()
    elif emit_idx:
        emit(emit_idx)
    else:
        sheet()
