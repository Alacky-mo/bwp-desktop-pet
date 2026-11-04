"""按游戏自己的比例，把头像框套到桌宠头上，出对照表肉眼过。

游戏侧量出来的两条事实（`frame_canvas.py`）：十张框全画在 128x128 画布里，
放头像的洞圆心就在画布中心（±5px），洞径占画布 0.52~0.57。
也就是游戏的规矩是「头像方框 = 环的画布，洞是方框里 0.54 见方的窗」。

两种候选规则：
  box  —— 环画布 == 桌宠剪影方框，同心。纯几何，不需要量头。
  head —— 先量「头团」（剪影里最厚的实心圆 = 头），让洞正好套住它。
实测三个桌宠的头团直径是剪影高的 0.54~0.68，和游戏洞径占比 0.544 撞在一起，
所以两条规则算出来的环几乎一样大——box 更简单，head 用来当交叉验证。

用法: python frame_fit.py <几何.tsv> <框画布目录> <桌宠渲染.png> [...] [--mode box|head] [-o 目录]
"""
import os, sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


def measure(path):
    """返回 (剪影框, 头心, 头半径)。头团 = 剪影里离边界最远的实心点，
    发冠飘带猫耳这些细长件会被自然排除；渲染被画布裁到时头团不可信，返回 None。"""
    a = np.asarray(Image.open(path).convert('RGBA'))[..., 3]
    solid = a > 8
    ys, xs = np.where(solid)
    box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
    dist = ndimage.distance_transform_edt(solid)
    y, x = np.unravel_index(int(np.argmax(dist)), dist.shape)
    clipped = box[0] == 0 or box[1] == 0 or box[2] >= a.shape[1] or box[3] >= a.shape[0]
    return box, (float(x), float(y)), (None if clipped else float(dist[y, x]))


def main(geom_tsv, frame_dir, pets, mode, out_dir, scale=0.5):
    os.makedirs(out_dir, exist_ok=True)
    rows = [l.split('\t') for l in open(geom_tsv, encoding='utf-8').read().splitlines()[1:]]
    tiles = []
    for pet in pets:
        name = os.path.splitext(os.path.basename(pet))[0]
        im = Image.open(pet).convert('RGBA')
        (x0, y0, x1, y1), (hx, hy), hr = measure(pet)
        bw, bh = x1 - x0, y1 - y0
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0        # 剪影方框中心
        print(f'{name}: 剪影 {bw}x{bh} 中心({cx:.0f},{cy:.0f})',
              f'头团 r={hr:.1f}@({hx:.0f},{hy:.0f}) 占剪影高 {2*hr/bh:.2f}' if hr else '头团不可信(渲染被裁)')
        for r in rows:
            stem = os.path.basename(r[0]).rsplit('.', 1)[0].replace('/', '_')
            ratio, hcx, hcy = float(r[10]), float(r[11]), float(r[12])
            if mode == 'head' and hr:
                side = (2 * hr) / ratio                   # 洞正好套住头团
                ax, ay = hx, hy                           # 洞心对齐头团
            else:
                side = bh                                 # 环画布 == 剪影方框
                ax, ay = cx, cy                           # 同心
            art = Image.open(os.path.join(frame_dir, f'gui_ui_charframe_{stem[-4:]}.png')).convert('RGBA')
            s = max(8, int(round(side * scale)))
            art = art.resize((s, s), Image.LANCZOS)
            canvas = im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS).convert('RGBA')
            layer = Image.new('RGBA', canvas.size, (0, 0, 0, 0))
            # 洞心落在锚点上: 落点 = 锚点 - 洞心在环内的位置
            layer.paste(art, (int(round(ax * scale - hcx * s)), int(round(ay * scale - hcy * s))), art)
            shot = Image.alpha_composite(canvas, layer).convert('RGB')
            d = ImageDraw.Draw(shot)
            if hr:
                d.ellipse([hx*scale-hr*scale, hy*scale-hr*scale, hx*scale+hr*scale, hy*scale+hr*scale],
                          outline=(0, 255, 0), width=1)
            d.text((3, 3), f'#{stem[-4:]} 环{side:.0f}px', fill=(255, 255, 0))
            tiles.append((f'{name}__{stem[-4:]}.png', shot))
    W = max(t.width for _, t in tiles); H = max(t.height for _, t in tiles)
    cols = 5
    sheet = Image.new('RGB', (cols*(W+4), (len(tiles)//cols + 1)*(H+4)), (24, 24, 24))
    for i, (n, t) in enumerate(tiles):
        sheet.paste(t, ((i % cols)*(W+4), (i//cols)*(H+4)))
        t.save(os.path.join(out_dir, n))
    sheet.save(os.path.join(out_dir, f'sheet_{mode}.png'))
    print(f'{len(tiles)} 张 -> {out_dir}/sheet_{mode}.png')


if __name__ == '__main__':
    a = sys.argv[1:]
    mode = a[a.index('--mode') + 1] if '--mode' in a else 'box'
    a = [x for x in a if x != '--mode' and x != mode]
    o = a[a.index('-o') + 1] if '-o' in a else 'out/diag/fit'
    a = a[:a.index('-o')] if '-o' in a else a
    main(a[0], a[1], a[2:], mode, o)
