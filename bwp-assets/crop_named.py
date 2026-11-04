"""只裁一页：给定 blob 序号 + plist，解那一张图集页然后把里面点名的 region 抠出来。

gui_page_map.py 会把整包同尺寸的 blob 全解一遍（468 张）才配出一页；已经知道配对结果时
那一步纯属浪费，这里直接按 map.log 里那行「=> page = blob#N」喂进来，一次解码出图。
配对是不是真的对，这里用同一个 content_fit 当场重算并打出来，不靠嘴说。

用法: python crop_named.py <npk> <scan.tsv> <atlas.json> <out_dir> <plist> <blob序号> [名字片段,...]
    例: python crop_named.py npk/gui.npk out/gui_scan_all.tsv out/gui_atlas.json \
            out/shots-dialog 3653.xml 4496 bg_talk_frame,bg_type2
"""
import os, sys, json, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from PIL import Image
from gui_page_map import content_fit, inset, rect_mask, dilate, decode, BLEED, PROJ_GATE


def main(npk, tsv, atlas_json, out_dir, plist, blob_idx, subs):
    db = json.load(open(atlas_json, encoding='utf-8'))
    regs = db['regions'][plist]
    page, pw, ph = db['meta'][plist]['page'], db['meta'][plist]['w'], db['meta'][plist]['h']

    rows = {r[0]: r for r in (l.split('\t') for l in open(tsv, encoding='utf-8').read().splitlines()[1:]) if len(r) >= 8}
    r = rows[blob_idx]
    with open(npk, 'rb') as fh:
        fh.seek(int(r[2]))
        blob = fh.read(int(r[3]))
    if r[1] == 'zlib':
        blob = zlib.decompress(blob)
    rgba = decode(blob)
    if rgba is None:
        print(f'blob#{blob_idx} 解不出来（格式 {r[1]}）')
        return 1
    h, w = rgba.shape[:2]
    if (w, h) != (pw, ph):
        print(f'尺寸不符: blob#{blob_idx} 是 {w}x{h}，{plist} 声明的页 {page} 是 {pw}x{ph}')
        return 1

    full = list(regs.values())
    f, over, under = content_fit(rgba[:, :, 3] > 24, dilate(rect_mask(w, h, full), BLEED), inset(full))
    verdict = '配对成立' if f >= PROJ_GATE else '配对不成立 —— 这张页不是这个 plist 的，别用'
    print(f'{plist} (页 {page}) = blob#{blob_idx}  fit={f:.4f} (溢出 {over:.4f} 空格 {under:.4f})  {verdict}')
    if f < PROJ_GATE:
        return 1

    os.makedirs(out_dir, exist_ok=True)
    keep = [n for n in regs if not subs or any(s in n.lower() for s in subs)]
    for name in sorted(keep):
        rr = regs[name]
        if rr['rot']:
            print(f'  !! {name} 是 rotated 的，方向没验过，跳过不裁')
            continue
        sub = rgba[rr['y']:rr['y'] + rr['h'], rr['x']:rr['x'] + rr['w']]
        bb = np.argwhere(sub[:, :, 3] > 16)
        box = (f'{bb[:, 1].min()},{bb[:, 0].min()}+{bb[:, 1].max() - bb[:, 1].min() + 1}'
               f'x{bb[:, 0].max() - bb[:, 0].min() + 1}') if len(bb) else '全空'
        flat = name.rsplit('.', 1)[0].replace('/', '_')
        Image.fromarray(sub).save(os.path.join(out_dir, flat + '.png'), compress_level=1)
        print(f'  {name} {rr["w"]}x{rr["h"]} 内容 {box}')
    print(f'共 {len(keep)} 张 -> {out_dir}')
    return 0


if __name__ == '__main__':
    a = sys.argv[1:]
    subs = tuple(x.strip().lower() for x in a[6].split(',') if x.strip()) if len(a) > 6 else ()
    sys.exit(main(*a[:6], subs))
