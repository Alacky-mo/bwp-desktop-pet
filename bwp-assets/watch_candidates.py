"""把挑框要用的候选件摊在一张图上，半透的看得清边界再决定组合。

用法: python watch_candidates.py <素材目录> <out图>
"""
import os, sys
from PIL import Image, ImageDraw

NAMES = [
    'gui_ui_scenerio_img_duihuakuang02.png',
    'gui_ui_scenerio_img_duihuakuang01.png',
    'gui_ui_scenerio_img_gualian.png',
    'gui_ui_scenerio_img_songzhen.png',
    'gui_ui_scenerio_img_qizi.png',
    'gui_ui_scenerio_img_bg_rhombus.png',
    'gui_ui_scenerio_bg_aside_frame.png',
    'gui_ui_scenerio_bg_diban_trasprt.png',
    'gui_ui_scenerio_img_title_bg.png',
    'gui_ui_scenerio_img_biaoqian_01.png',
    'gui_ui_common_bg_tips_3.png',
    'gui_ui_common_line_tips.png',
    'gui_ui_common_img_tips_shanzi_left.png',
    'gui_ui_common_img_tips_shanzi_right.png',
    'gui_ui_common_tips_xiezhan.png',
    'gui_ui_common_bg_panelbg.png',
    'gui_ui_title_img_44_fengye1.png',
    'gui_ui_title_img_44_fengye2.png',
]

ZOOM = 2
CELL_W, CELL_H = 560, 300
COLS = 3


def board(size, dark):
    b = Image.new('RGB', size, (70, 70, 78) if dark else (238, 234, 226))
    d = ImageDraw.Draw(b)
    for y in range(0, size[1], 16):
        for x in range(0, size[0], 16):
            if (x // 16 + y // 16) % 2:
                d.rectangle((x, y, min(x + 15, size[0] - 1), min(y + 15, size[1] - 1)),
                            fill=(92, 92, 100) if dark else (218, 213, 203))
    return b


def main(src, out_path):
    rows = (len(NAMES) + COLS - 1) // COLS
    img = Image.new('RGB', (COLS * CELL_W, rows * CELL_H), (255, 255, 255))
    dr = ImageDraw.Draw(img)
    for i, n in enumerate(NAMES):
        r, c = divmod(i, COLS)
        x, y = c * CELL_W, r * CELL_H
        dr.rectangle((x, y, x + CELL_W - 1, y + CELL_H - 1), outline=(120, 120, 120))
        half = CELL_W // 2
        img.paste(board((half, CELL_H), True), (x + 1, y + 1))
        img.paste(board((half - 1, CELL_H), False), (x + half + 1, y + 1))
        im = Image.open(os.path.join(src, n)).convert('RGBA')
        z = im.resize((im.width * ZOOM, im.height * ZOOM), Image.LANCZOS)
        if z.width > CELL_W - 20 or z.height > CELL_H - 40:
            z.thumbnail((CELL_W - 20, CELL_H - 40), Image.LANCZOS)
        img.paste(z, (x + (CELL_W - z.width) // 2, y + 20), z)
        dr.text((x + 8, y + 2), f'{n}  {im.width}x{im.height}', fill=(20, 20, 20))
    img.save(out_path)
    print('->', out_path)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
