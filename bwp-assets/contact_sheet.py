"""Build labelled contact sheets from a folder of extracted PNGs so art can be picked by eye.

用法: python contact_sheet.py <图目录> <出表目录> [标签.tsv]
    标签.tsv 两列: 文件名主干<TAB>要显示在图下面第一行的中文说法。
    没给或不认识的条目只显原始名 —— 挑图靠肉眼，但名字不能由我瞎翻。
"""
import os, sys, math
from PIL import Image, ImageDraw, ImageFont

CELL = 260
LABEL = 22
COLS = 8
PER_SHEET = 8 * 12

# 项目里没有任何字体文件（渲染桌宠要的那条限制），但本机出表可以用系统字体写中文
FONTS = (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf')


def font(size):
    for p in FONTS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def board(size):
    """先铺一格棋盘再贴 —— 这批 UI 件大半是深色半透明，落在纯黑画布上等于没出图。"""
    b = Image.new('RGB', size, (205, 205, 205))
    d = ImageDraw.Draw(b)
    for y in range(0, size[1], 16):
        for x in range(0, size[0], 16):
            if (x // 16 + y // 16) % 2:
                d.rectangle((x, y, min(x + 15, size[0] - 1), min(y + 15, size[1] - 1)),
                            fill=(155, 155, 155))
    return b


def sheet(imgs, out_path, labels):
    rows = math.ceil(len(imgs) / COLS)
    W, H = COLS * CELL, rows * (CELL + LABEL * 2)
    canvas = Image.new('RGB', (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(canvas)
    big, small = font(19), font(14)
    for i, (stem, path) in enumerate(imgs):
        try:
            im = Image.open(path)
            size = f'{im.width}x{im.height}'
            box = CELL - 6
            if max(im.size) * 2 <= box:
                # 小图标按整数倍 NEAREST 放大：UI 精灵常是 10~30 px，缩略图模式下面对一张
                # 深底联系表根本看不见长什么样（第一版就被坑过一次，整页只有文件名）。
                # 用 NEAREST 不用 LANCZOS —— 要看的正是像素和硬边，糊了就看不出能不能用了。
                z = max(1, box // max(1, max(im.size)))
                im = im.resize((im.width * z, im.height * z), Image.NEAREST)
            else:
                im.thumbnail((box, box))
        except Exception:
            continue
        x = (i % COLS) * CELL + 3
        y = (i // COLS) * (CELL + LABEL * 2) + 3
        canvas.paste(board(im.size), (x, y))
        canvas.paste(im, (x, y), im if im.mode == 'RGBA' else None)
        dr.text((x, y + CELL - 4), labels.get(stem, '(未命名)'), fill=(255, 228, 132), font=big)
        dr.text((x, y - 4 + CELL + LABEL), f'{stem} {size}', fill=(200, 200, 200), font=small)
    canvas.save(out_path, optimize=True)
    print(f'  wrote {out_path} ({len(imgs)} thumbs)')


def build(src_dir, out_dir, legend=None):
    labels = {}
    if legend:
        for line in open(legend, encoding='utf-8').read().splitlines():
            if not line.strip() or '\t' not in line:
                continue
            k, v = line.split('\t', 1)
            labels[k.strip()] = v.strip()
    imgs = sorted((os.path.splitext(f)[0], os.path.join(src_dir, f))
                  for f in os.listdir(src_dir) if f.lower().endswith('.png'))
    os.makedirs(out_dir, exist_ok=True)
    for s in range(0, len(imgs), PER_SHEET):
        chunk = imgs[s:s + PER_SHEET]
        name = f'sheet_{s // PER_SHEET:02d}_{chunk[0][0]}-{chunk[-1][0]}.png'
        sheet(chunk, os.path.join(out_dir, name), labels)
    named = [n for n, _ in imgs if n not in labels]
    print(f'{len(imgs)} images -> {out_dir}' + (f'  未命名 {len(named)} 个' if named else ''))


if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
