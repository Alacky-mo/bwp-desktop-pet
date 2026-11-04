# 画缺的 0 和 9: 骨架借本机毛笔字体, 上色和「分量」照真数字量出来的走。
# 实测(out/focus_digits/_color_probe.txt):
#   1..4 暖族  实心 #fefbee, 描边 #201000/#603000(带棕)
#   5..8 冷族  实心 #ffffff, 描边 #000010/#201040(带蓝紫)
#   墨迹高 84..100 px; 毛笔提按很大, 不是等宽描边
#   分量(墨/墨高) 31.3..48.8, 中位 43.0 —— 这是「像不像同一只手写的」的那把尺
# 斜穿那道笔触: 真的 1/2/3 身上没有, 4/6/8 才有 —— 它是单个字的手势, 不是整套的叠加层。
# 用户 2026-10-29 已定: 不加斜笔、色系走暖族、仿的字形可以收(但数字之间的大小以后还要调)。
import os
import random
from collections import deque

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fake")
FONT_DIR = "C:/Windows/Fonts"
INK_H = 92      # 真数字墨迹高 84..100, 取中间
SLANT = 58      # 备选斜笔的倾角

FONTS = {"行楷": "STXINGKA.TTF", "毛笔": "BRUSHSCI.TTF"}
TINTS = {
    "暖": {"fill": (254, 251, 238), "mid": (96, 48, 0), "line": (32, 16, 0)},
    "冷": {"fill": (255, 255, 255), "mid": (32, 16, 64), "line": (0, 0, 16)},
}


def ink_box(mask, thr=60):
    b = mask.point(lambda v: 255 if v >= thr else 0).getbbox()
    return b or (0, 0, mask.width, mask.height)


def ink_px(mask, thr=24):
    return sum(mask.histogram()[thr:])


def heft(img):
    """笔画「分量」= 墨像素 / 墨迹高 —— 相当于「横着扫一遍能扫出几笔」。
    为什么不用中位连续段宽: 仿的 0 是个环, 一刀下去切到两条边, 量出来和实心的 8 一样粗,
    可画出来是空心铁丝。墨量除以**外接框**也不行, 0 天生把框填满、1 天生空 —— 除以墨高才跨字可比。"""
    a = img.split()[3] if img.mode == "RGBA" else img
    box = ink_box(a, 24)
    return ink_px(a) / max(1, box[3] - box[1])


def real_heft():
    """真数字实测: 墨/墨高 31.3(那个瘦 1)..48.8, 中位 43.0"""
    ts = sorted(heft(Image.open(os.path.join(HERE, f"gui_ui_autochess_img_num_{d}.png")).convert("RGBA"))
                for d in range(1, 9))
    return ts[len(ts) // 2], ts


def glyph(ch, font_file, size=460):
    f = ImageFont.truetype(os.path.join(FONT_DIR, font_file), size)
    im = Image.new("L", (size * 2, size * 2), 0)
    ImageDraw.Draw(im).text((size // 2, size // 2), ch, font=f, fill=255)
    return im.crop(ink_box(im))


def fit_height(g, h=INK_H):
    r = h / g.height
    return g.resize((max(1, round(g.width * r)), h), Image.LANCZOS)


def dilate(mask, px):
    m = mask
    for _ in range(abs(px)):
        m = m.filter(ImageFilter.MaxFilter(3) if px > 0 else ImageFilter.MinFilter(3))
    return m


def streaks(w, h, seed, slant=SLANT):
    """飞白的丝缕: 噪声压成细条再横向放大, 就得到顺着一个方向的纹路。
    effect_noise 吃的是全局随机, 不显式播种的话每次跑出来的枯笔都不一样, 没法复验。"""
    random.seed(seed)
    n = Image.effect_noise((max(2, w // 12), max(2, h * 3)), 118).resize((w, h * 3), Image.BILINEAR)
    canvas = Image.new("L", (w * 2, h * 2), 128)
    canvas.paste(n, (w // 2, h // 2))
    canvas = canvas.rotate(slant, resample=Image.BILINEAR)
    return canvas.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))


def drybrush(mask, seed):
    """把丝缕咬进笔画, 只咬边缘, 中间留实心"""
    w, h = mask.size
    st = streaks(w, h, seed).point(lambda v: max(0, min(255, int((v - 104) * 2.4))))
    edge = Image.new("L", (w, h), 0)
    edge.paste(ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(3)), mask), (0, 0))
    bite = Image.composite(st, Image.new("L", (w, h), 0), edge.filter(ImageFilter.GaussianBlur(2)))
    return ImageChops.subtract(mask, bite).point(lambda v: 0 if v < 26 else v)


def layer(shape, color):
    im = Image.new("RGBA", shape.size, color + (0,))
    im.putalpha(shape)
    return im


def recolor(img, tint):
    """把某个字染成目标色系: 按明度在「描边→中间调→填色」三级色阶上重映射。
    真数字 1..4 暖、5..8 冷, 混排会花; 用户 2026-10-29 定了走暖族, 所以 5..8 得重染。"""
    t = TINTS[tint]
    src = img.load()
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dst = out.load()

    def mix(c1, c2, k):
        return tuple(round(a + (b - a) * k) for a, b in zip(c1, c2))

    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = src[x, y]
            if a < 8:
                continue
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
            col = mix(t["line"], t["mid"], lum * 2) if lum < 0.5 else mix(t["mid"], t["fill"], (lum - 0.5) * 2)
            dst[x, y] = col + (a,)
    return out


def compose(body, t, outline, mid=1):
    """描边 → 中间调 → 实心, 三层叠出成品"""
    out = Image.new("RGBA", body.size, (0, 0, 0, 0))
    out = Image.alpha_composite(out, layer(dilate(body, outline), t["line"]))
    out = Image.alpha_composite(out, layer(dilate(body, mid), t["mid"]))
    out = Image.alpha_composite(out, layer(body, t["fill"]))
    return out


def mount(g, seed):
    pad = 16
    canvas = Image.new("L", (g.width + pad * 2, g.height + pad * 2), 0)
    canvas.paste(g, (pad, pad))
    return drybrush(canvas, seed)


def build(ch, font_label, tint_label, seed=11, target=None, hole_floor=6):
    """补粗/缩 k 和描边宽度一起搜, 判据量**成品**:
    第一版量描边前的身子, 身子对上再描 3px 边, 成品胖了一圈没人管。
    「眼」是硬门限不是偏好: 0 和 9 的眼被描边糊死就等于画成了别的字。
    注意别为了追细把字蚀成骨架 —— 仿的 9 在 k<=-2 时碗口是「开」的, 那不是毛笔的写法,
    是我把它蚀断了; 回到正常分量它自己闭合成一个 8~16px 的眼。"""
    if target is None:
        target = real_heft()[0]
    base = fit_height(glyph(ch, FONTS[font_label]))
    t = TINTS[tint_label]
    best = None
    for k in range(-3, 4):
        body = mount(dilate(base, k), seed)
        for outline in (2, 3):
            out = compose(body, t, outline)
            alpha = out.split()[3]
            hole = largest_hole(alpha)
            if hole < hole_floor:
                continue
            d = abs(heft(out) - target)
            if best is None or d < best[0]:
                best = (d, out.crop(ink_box(alpha, 24)), heft(out), k, outline, hole)
    if best is None:
        raise SystemExit(f"{ch}·{font_label}: 搜遍了也没能保住眼宽>={hole_floor}, 别硬出图")
    _, out, hf, k, outline, hole = best
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, f"fake_{ch}_{font_label}_{tint_label}.png")
    out.save(path)
    print(f"  {os.path.basename(path):<26} 补粗 k={k:+d} 描边 {outline}px -> "
          f"墨/高={hf:.1f}(目标 {target:.1f}) 眼={hole}(门限 {hole_floor}) 尺寸={out.size}")
    return path, hf


def largest_hole(mask):
    """字中间的「眼」还剩多宽: 从外圈漫水标掉背景, 没被标到的空腔才是眼。
    描边一圈 2~3px, 0 和 9 这种带腔的字最容易被糊死 —— 糊了就等于画错了。"""
    a = mask.load()
    w, h = mask.width, mask.height
    bg = [[False] * w for _ in range(h)]
    dq = deque([(x, 0) for x in range(w)] + [(x, h - 1) for x in range(w)]
               + [(0, y) for y in range(h)] + [(w - 1, y) for y in range(h)])
    while dq:
        x, y = dq.popleft()
        if x < 0 or y < 0 or x >= w or y >= h or bg[y][x] or a[x, y] >= 24:
            continue
        bg[y][x] = True
        dq.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    best = 0
    for y in range(h):
        run = 0
        for x in range(w):
            if a[x, y] < 24 and not bg[y][x]:
                run += 1
                best = max(best, run)
            else:
                run = 0
    return best


if __name__ == "__main__":
    import sys
    target, ts = real_heft()
    print(f"真数字分量(墨/墨高) 中位={target:.1f}  各值={[round(v, 1) for v in ts]}")
    for ch in sys.argv[1:] or ["0", "9"]:
        for fl in FONTS:
            for tl in TINTS:
                build(ch, fl, tl, target=target)
