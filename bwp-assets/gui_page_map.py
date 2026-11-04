"""把 gui.npk 里无名的 atlas 页（图片 blob）和有名的 plist（region 表）配上，再按资源名裁图。

TOC 加密，blob 没有名字；但 plist 写了 realTextureFileName 和每个 region 的 rect。
配对分两步：**粗网格占位 IoU 只用来提名**（2048 的密页上并集几乎铺满，IoU 分不开同尺寸的
不同页，直接拿它判决会配出离谱的组合）；判决用整分辨率的 content_fit —— 内容不许跑到声明
格子（放宽 BLEED 像素）之外，声明的格子也不许是空的，最后按 fit 从高到低**一对一**认领。

用法: python gui_page_map.py <npk> <scan.tsv> <atlas.json> <out_dir> [资源前缀,...] [关键词,...]
    例: python npk_scan.py npk/gui.npk out/gui_scan_all.tsv
        python gui_plist_index.py t/gui_text out/gui_atlas.json
        python gui_page_map.py npk/gui.npk out/gui_scan_all.tsv out/gui_atlas.json crops/gui_frames
"""
import os, sys, json, zlib, struct, io

TOP = 10        # 每张图按 IoU 提名几个 plist 去做整分辨率判决
PROJ_GATE = 0.995  # 溢出 x 空格 的乘积门槛，低于它宁可不出图
BLEED = 5          # ASTC 块渗色的放宽半径，判决时给声明格子长这么多余量
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texture2ddecoder
from npk_unpack import ASTC_FMTS, ETC_FMTS, KTX_MAGIC

PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
GRID = 256      # 占位格边数；2048 页切成 8px 的格，够把同尺寸的不同页分开

DEFAULT_PREFIX = ('gui/ui/',)
DEFAULT_KEYWORDS = ('kuang', 'head', 'touxiang')


def decode(raw):
    """bytes -> RGBA ndarray (h,w,4)，认不出的格式返回 None。"""
    if raw[:8] == PNG_MAGIC:
        return np.asarray(Image.open(io.BytesIO(raw)).convert('RGBA'))
    if raw[:12] != KTX_MAGIC:
        return None
    f = struct.unpack_from('<13I', raw, 12)
    (_, glType, _, _, internal, _, w, h, _, _, _, _, kv) = f
    if glType != 0:
        return None
    body = raw[64 + kv:]
    data = body[4:4 + struct.unpack_from('<I', body, 0)[0]]
    if internal in ASTC_FMTS:
        bw, bh = ASTC_FMTS[internal]
        bgra = texture2ddecoder.decode_astc(data, w, h, bw, bh)
    elif internal in ETC_FMTS:
        # decode_etc2a8(data, w, h) —— npk_unpack 里多传的那个 bpp 参数是错的，这里不抄
        bgra = getattr(texture2ddecoder, 'decode_' + ETC_FMTS[internal][0])(data, w, h)
    else:
        return None
    arr = np.frombuffer(bgra, dtype=np.uint8).reshape(h, w, 4)
    return arr[:, :, [2, 1, 0, 3]]      # texture2ddecoder 给的是 BGRA，读成 RGBA 会红蓝互换


def sample(mask):
    """布尔图 -> GRID x GRID 布尔（左上最近邻）。"""
    h, w = mask.shape
    yy = (np.arange(GRID) * h // GRID)[:, None]
    xx = (np.arange(GRID) * w // GRID)[None, :]
    return mask[yy, xx]


def rect_mask(w, h, rects):
    m = np.zeros((h, w), dtype=bool)
    for r in rects:
        # rotated 的 region 在页里占的是宽高互换的那块（plist 里 rect 写的是原图尺寸）
        rw, rh = (r['h'], r['w']) if r['rot'] else (r['w'], r['h'])
        m[r['y']:r['y'] + rh, r['x']:r['x'] + rw] = True
    return m


def dilate(m, k):
    """布尔图向外长 k 像素（方核，行列各一遍）。ASTC 4x4 会让透明区渗出内容，判决要留出这点余量。"""
    out = m
    for ax in (0, 1):
        acc = out.copy()
        for i in range(1, k + 1):
            sl = [slice(None)] * 2
            if ax == 0:
                acc[i:] |= out[:-i]; acc[:-i] |= out[i:]
            else:
                acc[:, i:] |= out[:, :-i]; acc[:, :-i] |= out[:, i:]
        out = acc
    return out


def inset(rects, pad=3, limit=300):
    """格子里必须真有图：把 rect 内缩 pad 再查，边缘渗色不算数。"""
    r = [q for q in rects if q['w'] >= pad * 2 + 4 and q['h'] >= pad * 2 + 4]
    step = max(1, len(r) // limit)
    out = []
    for q in r[::step][:limit]:
        rh, rw = (q['w'], q['h']) if q['rot'] else (q['h'], q['w'])   # 页上的实际宽高
        out.append((q['y'] + pad, q['y'] + rh - pad, q['x'] + pad, q['x'] + rw - pad))
    return out


def content_fit(content, dmask, ins):
    """(1-溢出)(1-空格)。溢出=内容跑到声明格子(放宽后)之外；空格=声明了格子却是空的。"""
    cp = int(content.sum())
    over = int((content & ~dmask).sum()) / max(1, cp)
    empty = sum(1 for y0, y1, x0, x1 in ins if not content[y0:y1, x0:x1].any())
    under = empty / max(1, len(ins))
    return (1.0 - over) * (1.0 - under), over, under


def main(npk, tsv, atlas_json, out_dir, prefixes, keywords=()):
    os.makedirs(out_dir, exist_ok=True)      # 输出目录不给就先建：配对跑完才在存图那步撞死最亏
    db = json.load(open(atlas_json, encoding='utf-8'))
    meta, regions = db['meta'], db['regions']
    cands = {}
    for fn, regs in regions.items():
        names = [n for n in regs if n.startswith(prefixes)
                 and (not keywords or any(k in n.lower() for k in keywords))]
        if not names:
            continue
        w, h = meta[fn]['w'], meta[fn]['h']
        full = list(regs.values())
        cands[fn] = dict(page=meta[fn]['page'], w=w, h=h, names=names,
                         sig=sample(rect_mask(w, h, full)),
                         dmask=dilate(rect_mask(w, h, full), BLEED), ins=inset(full))
    sizes = {(c['w'], c['h']) for c in cands.values()}
    print(f'目标资源 {sum(len(c["names"]) for c in cands.values())} 个，'
          f'落在 {len(cands)} 个 plist 版本上，页尺寸 {sorted(sizes)}')

    rows = {r[0]: r for r in (l.split('	') for l in open(tsv, encoding='utf-8').read().splitlines()[1:]) if len(r) >= 8}
    todo = [k for k, r in rows.items() if r[4] and (int(r[4]), int(r[5])) in sizes]
    print(f'尺寸对得上的 blob: {len(todo)}')

    fh = open(npk, 'rb')

    def load(idx):
        r = rows[str(idx)]
        fh.seek(int(r[2]))
        blob = fh.read(int(r[3]))
        if r[1] == 'zlib':
            try:
                blob = zlib.decompress(blob)
            except Exception:
                return None
        return decode(blob)

    # 第一轮：IoU 提名。每张图只留 TOP 个 plist，每个 plist 也只在被提名时进入判决
    nom = []            # (iou, plist, blob)
    n = 0
    for idx in todo:
        rgba = load(idx)
        if rgba is None:
            continue
        n += 1
        h, w = rgba.shape[0], rgba.shape[1]
        g = sample(rgba[:, :, 3] > 24)
        hits = []
        for fn, c in cands.items():
            if (c['w'], c['h']) != (w, h):
                continue
            iou = float((g & c['sig']).sum()) / max(1.0, float((g | c['sig']).sum()))
            hits.append((iou, fn))
        hits.sort(reverse=True)
        nom.extend((iou, fn, int(idx)) for iou, fn in hits[:TOP])
    print(f'实际解码 {n} 张，提名 {len(nom)} 对')

    # 第二轮：整分辨率判决。按 blob 分组，每张图只解一次
    by_blob = {}
    for iou, fn, idx in nom:
        by_blob.setdefault(idx, []).append((iou, fn))
    rated = []
    for idx, lst in by_blob.items():
        rgba = load(idx)
        if rgba is None:
            continue
        h, w = rgba.shape[0], rgba.shape[1]
        content = rgba[:, :, 3] > 24
        for iou, fn in lst:
            c = cands[fn]
            f, over, under = content_fit(content, c['dmask'], c['ins'])
            rated.append((f, over, under, iou, fn, idx, rgba))
    rated.sort(key=lambda t: (-t[0], -t[3]))
    used_p, used_b, pairs = set(), set(), {}
    for f, over, under, iou, fn, idx, rgba in rated:
        if fn in used_p or idx in used_b:
            continue
        used_p.add(fn); used_b.add(idx)
        pairs[fn] = (f, over, under, iou, idx, rgba)
        if len(used_p) == len(cands):
            break
    fh.close()

    hit = miss = 0
    for fn in sorted(cands, key=lambda f: -pairs.get(f, (0.0,))[0]):
        c = cands[fn]
        if fn not in pairs or pairs[fn][0] < PROJ_GATE:
            got = f' 最好 fit={pairs[fn][0]:.4f}' if fn in pairs else ''
            print(f'  {c["page"]} ({c["w"]}x{c["h"]}, {fn}): 配不上{got}')
            miss += 1
            continue
        f, over, under, iou, idx, rgba = pairs[fn]
        hit += 1
        print(f'  => {c["page"]} = blob#{idx}  fit={f:.4f} (溢出 {over:.4f} 空格 {under:.4f}, IoU 提名 {iou:.3f})')
        for name in c['names']:
            r = regions[fn][name]
            if r['rot']:
                print(f'     !! {name} 是 rotated 的，方向没验过，跳过不裁')
                continue
            sub = rgba[r['y']:r['y'] + r['h'], r['x']:r['x'] + r['w']]
            bb = np.argwhere(sub[:, :, 3] > 16)
            box = f'{bb[:,1].min()},{bb[:,0].min()}+{bb[:,1].max()-bb[:,1].min()+1}x{bb[:,0].max()-bb[:,0].min()+1}' if len(bb) else '空'
            flat = name.rsplit('.', 1)[0].replace('/', '_')   # 资源名自带 .png，别再叠一层后缀
            Image.fromarray(sub).save(os.path.join(out_dir, flat + '.png'), compress_level=1)
            print(f'     {name} {r["w"]}x{r["h"]} 内容 {box}')
    print(f'配上 {hit} 页 / 配不上 {miss} 页，图在 {out_dir}')


if __name__ == '__main__':
    a = sys.argv[1:]
    pre = tuple(a[4].split(',')) if len(a) > 4 else DEFAULT_PREFIX
    # 只给到第 4 个参数才用默认关键词；自己指定了前缀就说明要整目录，别再拿关键词筛
    kw = tuple(x for x in a[5].split(',') if x) if len(a) > 5 else (DEFAULT_KEYWORDS if len(a) == 4 else ())
    main(a[0], a[1], a[2], a[3], pre, kw)
