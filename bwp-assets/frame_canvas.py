"""把 plist 裁出来的头像框补回游戏自己的画布，并量出每张框「放头像的那个洞」。

TexturePacker 存盘时把四周透明像素裁掉了，还记了 spriteOffset 说「裁片中心相对画布中心偏了多少」。
直接用裁片渲染，等于把偏心当成正中——十张框的裁片尺寸从 115x102 到 128x118 各不相同，
同一个贴合系数套上去就会看出「每个框大小位置都不一样」。这里按 spriteSourceSize 补回画布，
十张框就共用一套坐标了。

用法: python frame_canvas.py <plist.xml> <裁片目录> <输出目录> [几何.tsv]
"""
import os, re, sys, plistlib
from collections import deque
import numpy as np
from PIL import Image

NUM = lambda s: [float(x) for x in re.findall(r'-?\d+\.?\d*', str(s))]


def hole_of(alpha):
    """裁片上「放头像的那个洞」：先排掉与图边连成一片的透明（=框外），再取剩下的最大空洞。

    返回 (心x, 心y, 直径, 圆度)。直径取宽高均值——游戏这些框的洞不是正圆，
    有的被浪花/花枝探进来一点，但整体就是个能塞住一颗头的圆。
    只用内切圆会挑到装饰件挤不进去的那一小块，量出来比实际开口小一截。
    """
    h, w = alpha.shape
    solid = alpha > 8
    outside = np.zeros((h, w), dtype=bool)
    q = deque((y, x) for y, x in zip(*np.where(~solid)) if y in (0, h - 1) or x in (0, w - 1))
    for y, x in q:
        outside[y, x] = True
    while q:
        y, x = q.popleft()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < h and 0 <= nx < w and not solid[ny, nx] and not outside[ny, nx]:
                outside[ny, nx] = True
                q.append((ny, nx))
    seen = np.zeros((h, w), dtype=bool)
    best = None
    for sy, sx in zip(*np.where(~solid & ~outside)):
        if seen[sy, sx]:
            continue
        comp, stack = [], [(sy, sx)]
        seen[sy, sx] = True
        while stack:
            y, x = stack.pop()
            comp.append((y, x))
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and not solid[ny, nx] and not outside[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        if best is None or len(comp) > len(best):
            best = comp
    if best is None:
        return None
    ys = np.array([p[0] for p in best]); xs = np.array([p[1] for p in best])
    bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1 + 1
    return (float(xs.mean()), float(ys.mean()), (bw + bh) / 2.0, len(best) / (bw * bh))


def main(plist, src, dst, tsv=None):
    frames = plistlib.load(open(plist, 'rb'))['frames']
    os.makedirs(dst, exist_ok=True)
    rows = []
    for key, d in sorted(frames.items()):
        name = os.path.basename(key)
        stem = name.rsplit('.', 1)[0]
        crop = os.path.join(src, f'gui_ui_charframe_{stem}.png')
        if not os.path.isfile(crop):
            print(f'跳过 {key}: 找不到裁片 {crop}')
            continue
        ox, oy = NUM(d['spriteOffset'])
        tw, th = [int(x) for x in NUM(d['spriteSize'])]
        cw, ch = [int(x) for x in NUM(d['spriteSourceSize'])]
        if d['textureRotated']:
            print(f'跳过 {key}: rotated 的朝向没实测过，不猜')
            continue
        im = Image.open(crop).convert('RGBA')
        # spriteOffset 的 Y 向上为正（TexturePacker 约定），图像行号向下，所以画布 y = 中心 - oy
        x0 = int(round(ox + (cw - 1) / 2 - (tw - 1) / 2))
        y0 = int(round(-oy + (ch - 1) / 2 - (th - 1) / 2))
        canvas = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
        canvas.paste(im, (x0, y0), im)
        canvas.save(os.path.join(dst, os.path.basename(crop)))

        a = np.asarray(im)[..., 3]
        hole = hole_of(a)
        if hole is None:
            print(f'警告 {key}: 裁片里找不到封闭的洞')
            continue
        hx, hy, dia, fill = hole
        cx, cy = hx + x0, hy + y0
        ys, xs = np.where(a > 8)
        rows.append([key, cw, ch, ox, oy, tw, th, x0, y0,
                     round(dia, 1), round(dia / cw, 4), round(cx / cw, 4), round(cy / ch, 4),
                     round(fill, 3),
                     f'{xs.min()},{ys.min()},{xs.max()-xs.min()+1},{ys.max()-ys.min()+1}'])
        print(f'{key} 画布{cw}x{ch} 洞径{dia:.1f}({dia/cw:.3f}) 心({cx:.1f},{cy:.1f}) 相对画布中心'
              f'({cx-(cw-1)/2:+.1f},{cy-(ch-1)/2:+.1f}) 圆度{fill:.2f} '
              f'内容占画布{(xs.max()-xs.min()+1)/cw:.2f}x{(ys.max()-ys.min()+1)/ch:.2f}')
    if tsv:
        with open(tsv, 'w', encoding='utf-8') as fh:
            fh.write('region\tcw\tch\toffsetX\toffsetY\ttrimW\ttrimH\tx0\ty0\t'
                     'holeDia\tholeOverCanvas\tholeCx\tholeCy\tholeFill\tcontentRect\n')
            for r in rows:
                fh.write('\t'.join(str(x) for x in r) + '\n')
        print(f'几何表 -> {tsv}')
    print(f'{len(rows)} 张框补回画布 -> {dst}')


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 3:
        print(__doc__)
        sys.exit(2)
    main(a[0], a[1], a[2], a[3] if len(a) > 3 else None)
