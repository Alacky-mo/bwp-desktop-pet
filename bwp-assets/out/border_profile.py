"""量 bg_tips_3 那圈边框线的真实粗细 —— 逐行/逐列数「不透明且算墨」的连续段。

两条对照：装机那张（逐行贴线抹过左边）和素材池里那张原图 —— 两边四个分布必须一模一样，
不一样就是装机侧把纸自己的线动过了。
左边线、右边线各逐行量厚度；顶线、底线各逐列量厚度。
用法: python border_profile.py
"""
import os
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
TRIMMED = os.path.join(HERE, "..", "..", "deskspine", "DeskSpine", "res", "image", "focus_ui", "bg_tips_3.png")
PRISTINE = os.path.join(HERE, "focus_ui", "gui_ui_common_bg_tips_3.png")
A = 120          # 算「有线」的最小 alpha
INK = 170        # 算「墨色」的最大亮度：边框那圈是深褐墨线，纸面是奶白


def runs(im, fixed, lo, hi, horizontal):
    """返回这条切线里所有「墨」连续段的 (起点, 厚度)。horizontal=True 表示沿 x 扫(量竖线的粗细)"""
    out = []
    cur = None
    for p in range(lo, hi):
        x, y = (p, fixed) if horizontal else (fixed, p)
        if x >= im.width or y >= im.height:
            break
        r, g, b, a = im.getpixel((x, y))
        dark = a >= A and (r + g + b) / 3 < INK
        if dark and cur is None:
            cur = [p, 1]
        elif dark:
            cur[1] += 1
        elif cur:
            out.append(tuple(cur))
            cur = None
    if cur:
        out.append(tuple(cur))
    return out


def profile(path, tag):
    with Image.open(path) as src:
        im = src.convert("RGBA")
    W, H = im.size
    print(f"\n=== {tag}  {W}x{H} ===")
    for name, fn in (
        ("左边线(逐行, 在 x=14..34 里找墨段)", lambda y: runs(im, y, 14, 34, True)),
        ("右边线(逐行, 在 x=W-34..W 里找墨段)", lambda y: runs(im, y, W - 34, W, True)),
    ):
        print(f"-- {name}")
        buckets = {}
        firsts = {}
        for y in range(40, 195, 5):
            segs = fn(y)
            for i, (s, t) in enumerate(segs):
                buckets.setdefault(t, 0)
                buckets[t] += 1
                if i == 0:
                    firsts.setdefault(s, 0)
                    firsts[s] += 1
        print("   厚度分布(厚度:出现次数):", dict(sorted(buckets.items())))
        print("   第一段起点分布(起点:次数):", dict(sorted(firsts.items())))
    for name, rng in (("顶线(逐列, 在 y=0..20)", range(0, 20)), ("底线(逐列, 在 y=H-20..H)", range(H - 20, H))):
        print(f"-- {name}")
        buckets = {}
        for x in range(40, W - 40, 5):
            for i, (s, t) in enumerate(runs(im, x, rng[0], rng[-1] + 1, False)):
                buckets[t] = buckets.get(t, 0) + 1
        print("   厚度分布:", dict(sorted(buckets.items())))


for p, t in ((TRIMMED, "装机那张(逐行贴线抹)"), (PRISTINE, "素材池原图")):
    if os.path.exists(p):
        profile(p, t)
    else:
        print("读不到", p)
