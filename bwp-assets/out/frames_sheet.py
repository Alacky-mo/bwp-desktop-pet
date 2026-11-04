"""给 crops/gui_frames 出带编号的联系表和中文图例，方便肉眼挑头像框。

用法: python out/frames_sheet.py [crops目录] [输出前缀]
"""
import os, sys, math, re
from PIL import Image, ImageDraw

CELL, LABEL, COLS = 300, 34, 6

# 只翻这些结构词，角色/活动名不猜；拿不准的留着原名让用户自己认
GLOSS = {
    'touxiang': '头像', 'touxiangkuang': '头像框', 'kuang': '框', 'dikuang': '底框',
    'biankuang': '边框', 'neikuang': '内框', 'paimingkuang': '排名框', 'renwukuang': '任务框',
    'xuanrenkuang': '选人框', 'tubiaokuang': '图标框', 'shurukuang': '输入框',
    'wupingkuang': '物品框', 'wuqinkuang': '武器框', 'tishidikuang': '提示底框',
    'jinengkuang': '技能框', 'guanzhankuang': '观战框', 'paikuang': '排框',
    'head': '头像', 'avatar': '头像', 'portrait': '头像', 'charframe': '角色框',
    'select': '选中', 'xuanzhong': '选中', 'normal': '常态', 'gray': '灰',
    'mask': '遮罩', 'shade': '阴影', 'di': '底', 'diwen': '底纹', 'bg': '背景',
    'yuan': '圆', 'yigoumai': '已购买', 'info': '详情', 'frame': '框',
}


def gloss(name):
    stem = re.sub(r'\.(png|jpg)$', '', name).lower()
    # 只认最长的那一个词，别把「底框·框·底」这种重复堆出来
    for k, v in sorted(GLOSS.items(), key=lambda kv: -len(kv[0])):
        if k in stem:
            return v
    return ''


def main(src='crops/gui_frames', out_prefix='out/frames_gui/sheet'):
    files = sorted(f for f in os.listdir(src) if f.endswith('.png'))
    imgs = [(i + 1, f) for i, f in enumerate(files)]
    os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
    sheets = math.ceil(len(imgs) / (COLS * 10))
    for s in range(sheets):
        part = imgs[s * COLS * 10:(s + 1) * COLS * 10]
        rows = math.ceil(len(part) / COLS)
        canvas = Image.new('RGB', (COLS * CELL, rows * (CELL + LABEL)), (26, 26, 30))
        dr = ImageDraw.Draw(canvas)
        for i, (num, f) in enumerate(part):
            im = Image.open(os.path.join(src, f))
            thumb = im.copy()
            thumb.thumbnail((CELL - 8, CELL - 8))
            x, y = (i % COLS) * CELL + 4, (i // COLS) * (CELL + LABEL)
            base = f.replace('gui_ui_', '').replace('gui_', '')
            # 标签贴在每格顶部，图在下方：缩略图普遍比格子小很多，标签放格底会看着像别人的
            dr.text((x, y + 2), f'#{num:02d} {im.width}x{im.height}', fill=(255, 230, 120))
            dr.text((x, y + 14), base[:44], fill=(220, 220, 220))
            canvas.paste(thumb, (x, y + LABEL), thumb if thumb.mode == 'RGBA' else None)
        p = f'{out_prefix}_{s}.png' if sheets > 1 else f'{out_prefix}.png'
        canvas.save(p, optimize=True)
        print(f'  {p}  {len(part)} 格')
    legend = os.path.dirname(out_prefix) + '/图例.txt'
    with open(legend, 'w', encoding='utf-8') as fh:
        for num, f in imgs:
            fh.write(f'#{num:02d}  {f}\n      {gloss(f)}\n')
    print(f'  图例 {legend}  共 {len(imgs)} 张')


if __name__ == '__main__':
    main(*(sys.argv[1:3] if len(sys.argv) > 2 else []))
