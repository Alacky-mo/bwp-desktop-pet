# 一次性量尺：把 bg_tips_3（和风纸面板）的每一列/每一行「有没有东西、有多亮」打出来，
# 定位左边那半截素材到底占哪几列，以及纸自己的边框线在第几列/第几行。
import sys
from PIL import Image

path = sys.argv[1]
im = Image.open(path).convert("RGBA")
w, h = im.size
px = im.load()

print(f"{path}  {w}x{h}")


def col_stats(x):
    a = 0
    lum = 0
    n = 0
    for y in range(h):
        r, g, b, al = px[x, y]
        a += al
        lum += (r + g + b) // 3 * (al / 255.0)
        n += 1
    return a / n, (lum / n)


def row_stats(y):
    a = 0
    n = 0
    for x in range(w):
        r, g, b, al = px[x, y]
        a += al
        n += 1
    return a / n


print("\n-- 列均 alpha（每 1 列，前 60 + 后 60）--")
for x in list(range(0, 60)) + list(range(w - 60, w)):
    a, l = col_stats(x)
    bar = "#" * int(a / 255 * 40)
    print(f"x={x:3d} a={a:6.1f} lum={l:6.1f} {bar}")

print("\n-- 行均 alpha（全表）--")
for y in range(0, h):
    a = row_stats(y)
    bar = "#" * int(a / 255 * 40)
    print(f"y={y:3d} a={a:6.1f} {bar}")
