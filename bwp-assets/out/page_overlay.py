"""把某个 blob 解出来，并把某个 plist 的 region 框画在上面，用来肉眼确认配对对不对。

用法: python out/page_overlay.py <npk> <scan.tsv> <atlas.json> <blob号> <plist文件> <out.png>
"""
import sys, json, zlib, os
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gui_page_map import decode, rect_mask


def main(npk, tsv, atlas, idx, plist, out):
    rows = {}
    for l in open(tsv, encoding='utf-8').read().splitlines()[1:]:
        r = l.split('\t')
        if len(r) >= 8:
            rows[r[0]] = r
    r = rows[idx]
    fh = open(npk, 'rb')
    fh.seek(int(r[2]))
    blob = fh.read(int(r[3]))
    if r[1] == 'zlib':
        blob = zlib.decompress(blob)
    rgba = decode(blob)
    if rgba is None:
        sys.exit(f'blob#{idx} 解不开')
    regs = json.load(open(atlas, encoding='utf-8'))['regions'][plist]
    w, h = rgba.shape[1], rgba.shape[0]
    base = Image.fromarray(rgba).convert('RGBA')
    ov = Image.new('RGBA', base.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for n, q in regs.items():
        d.rectangle([q['x'], q['y'], q['x'] + q['w'] - 1, q['y'] + q['h'] - 1], outline=(255, 40, 40, 255))
        d.text((q['x'] + 2, q['y'] + 2), os.path.basename(n)[:12], fill=(255, 255, 0, 255))
    comp = Image.alpha_composite(base, ov)
    # 右侧再放一张「内容但不在任何声明格子里」的红图，溢出到底在哪一眼看到
    content = rgba[:, :, 3] > 24
    spill = content & ~rect_mask(w, h, list(regs.values()))
    spill_img = np.zeros((h, w, 4), dtype=np.uint8)
    spill_img[~content] = (30, 30, 30, 255)
    spill_img[spill] = (255, 0, 0, 255)
    canvas = Image.new('RGBA', (w * 2 + 8, h), (0, 0, 0, 255))
    canvas.paste(comp, (0, 0))
    canvas.paste(Image.fromarray(spill_img), (w + 8, 0))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    canvas.save(out)
    print(f'{out}  左=叠了 region 框，右=灰是透明/红是溢出，溢出像素 {int(spill.sum()):,} '
          f'占内容 {100*int(spill.sum())/max(1,int(content.sum())):.1f}%')


if __name__ == '__main__':
    main(*sys.argv[1:7])
