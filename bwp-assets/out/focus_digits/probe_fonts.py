# 挑一支和「自走棋数字」最像的字体: 拿候选字体的 1..8 和真数字 1..8 对轮廓重合度,
# 谁最像就用谁的骨架去画缺的 0 和 9。判据只看形状, 不看颜色(颜色是后期刷上去的)。
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REAL = HERE
FONT_DIR = "C:/Windows/Fonts"
CANDIDATES = [
    "STXINGKA.TTF",  # 华文行楷
    "STKAITI.TTF",   # 华文楷体
    "FZSTK.TTF",     # 方正舒体
    "STXINWEI.TTF",  # 华文新魏
    "SIMLI.TTF",     # 隶书
    "STLITI.TTF",    # 华文隶书
    "BRUSHSCI.TTF",
    "CASTELAR.TTF",
    "ITCKRIST.TTF",
    "LCALLIG.TTF",
    "MISTRAL.TTF",
    "PRISTINA.TTF",
    "FELIXTI.TTF",
    "BELLI.TTF",
    "KUNSTLER.TTF",
]
SIDE = 200  # 归一化到同一方格再比, 免得字号不同的字体白占便宜


def ink(mask):
    xs = [x for x in range(mask.width) if any(mask.getpixel((x, y)) for y in range(mask.height))]
    ys = [y for y in range(mask.height) if any(mask.getpixel((x, y)) for x in range(mask.width))]
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs) + 1, max(ys) + 1


def norm(img, side=SIDE):
    """裁到墨迹, 等比塞进 side x side 的方格(保持长宽比, 居中)"""
    m = img.split()[3] if img.mode == "RGBA" else img
    box = ink(m)
    if box is None:
        return None
    c = img.crop(box)
    r = min(side / c.width, side / c.height)
    c = c.resize((max(1, round(c.width * r)), max(1, round(c.height * r))), Image.LANCZOS)
    out = Image.new("L", (side, side), 0) if c.mode in ("L",) else Image.new("RGBA", (side, side), (0, 0, 0, 0))
    out.paste(c, ((side - c.width) // 2, (side - c.height) // 2))
    return out


def real_mask(path):
    im = Image.open(path).convert("RGBA")
    a = im.split()[3].point(lambda v: 255 if v > 60 else 0)
    return norm(a)


def font_mask(path, ch, size=420):
    f = ImageFont.truetype(path, size)
    im = Image.new("L", (size * 2, size * 2), 0)
    d = ImageDraw.Draw(im)
    d.text((size // 2, size // 2), ch, font=f, fill=255)
    return norm(im)


def iou(a, b):
    pa, pb = a.load(), b.load()
    hit = both = 0
    for y in range(a.height):
        for x in range(a.width):
            va, vb = pa[x, y] > 128, pb[x, y] > 128
            if va or vb:
                both += 1
                if va and vb:
                    hit += 1
    return hit / both if both else 0.0


def main():
    reals = {}
    for p in sorted(glob.glob(os.path.join(REAL, "gui_ui_autochess_img_num_*.png"))):
        d = os.path.basename(p).rsplit("_", 1)[-1].split(".")[0]
        if d.isdigit():
            reals[int(d)] = real_mask(p)
    print("真数字:", sorted(reals), file=sys.stderr)
    rows = []
    for fname in CANDIDATES:
        fp = os.path.join(FONT_DIR, fname)
        if not os.path.exists(fp):
            continue
        try:
            scores = []
            for d, rm in sorted(reals.items()):
                fm = font_mask(fp, str(d))
                if fm is None:
                    continue
                scores.append(iou(fm, rm))
        except Exception as exc:  # 有的字体不认数字, 跳过就行
            print(f"跳过 {fname}: {exc}", file=sys.stderr)
            continue
        if not scores:
            continue
        label = {
            "STXINGKA.TTF": "华文行楷", "STKAITI.TTF": "华文楷体", "FZSTK.TTF": "方正舒体",
            "STXINWEI.TTF": "华文新魏", "SIMLI.TTF": "隶书", "STLITI.TTF": "华文隶书",
            "BRUSHSCI.TTF": "BrushSci(西文毛笔)", "CASTELAR.TTF": "Castelar(西文花体)",
            "ITCKRIST.TTF": "ITC Krister", "LCALLIG.TTF": "Lucida Calligraphy",
            "MISTRAL.TTF": "Mistral", "PRISTINA.TTF": "Pristina",
            "FELIXTI.TTF": "Felix Titling", "BELLI.TTF": "Belli", "KUNSTLER.TTF": "Kunstler",
        }.get(fname, fname)
        rows.append((sum(scores) / len(scores), label, fname, len(scores)))
    rows.sort(reverse=True)
    print("轮廓重合度(1..8 平均 IoU, 越高越像):")
    for s, label, fname, n in rows:
        print(f"  {s:.3f}  {label:<18} {fname}  (比了 {n} 个)")
    if rows:
        print("最佳:", rows[0][1], rows[0][2])


if __name__ == "__main__":
    main()
