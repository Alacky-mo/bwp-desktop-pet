"""从 npk_scan 出的 TSV 里挑「框」类贴图：只解码尺寸像 UI 图的条目，按透明中心 + 不透明外圈打分，出联系表。

用法: python frame_hunt.py <npk> <scan.tsv> <out_dir> [--min 90] [--max 512] [--top 60]

判据来自 UI 头像框的共同特征：中间要能放头像（透明洞），四周是装饰边。
**这是没有 plist 时的兜底路线**：`gui.npk` 里能倒出 TexturePacker 的 plist，直接按资源名裁
（见 gui_page_map.py），用不着猜形状；bigtexture/texture 这类只有图没有 plist 的包才回到这里，
按形状筛完再肉眼挑。
"""
import os, sys, json, struct, zlib, io
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texture2ddecoder
from npk_unpack import ASTC_FMTS, ETC_FMTS

KTX_MAGIC = b'\xabKTX 11\xbb'
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def to_rgba(raw):
    if raw[:8] == PNG_MAGIC:
        im = Image.open(io.BytesIO(raw)).convert('RGBA')
        return im.width, im.height, np.asarray(im)
    if raw[:12] == KTX_MAGIC:
        f = struct.unpack_from('<13I', raw, 12)
        (_, glType, _, _, internal, _, w, h, _, _, _, _, kv) = f
        if glType != 0:
            return None
        body = raw[64 + kv:]
        mip = struct.unpack_from('<I', body, 0)[0]
        data = body[4:4 + mip]
        if internal in ASTC_FMTS:
            bw, bh = ASTC_FMTS[internal]
            bgra = texture2ddecoder.decode_astc(data, w, h, bw, bh)
        elif internal in ETC_FMTS:
            kind, bpp = ETC_FMTS[internal]
            bgra = getattr(texture2ddecoder, 'decode_' + kind)(data, w, h, bpp)
        else:
            return None
        # texture2ddecoder 一律给 BGRA，按 RGBA 读会红蓝互换
        arr = np.frombuffer(bgra, dtype=np.uint8).reshape(h, w, 4)
        return w, h, arr[:, :, [2, 1, 0, 3]]
    return None


def score(a):
    """a = alpha 平面(float32 0..255)。返回 (score, 明细)。"""
    h, w = a.shape
    frac = (a > 200).mean()
    if not (0.06 < frac < 0.92):
        return 0.0, {}
    ys, xs = np.mgrid[0:h, 0:w]
    r = np.hypot((xs - w / 2) / w, (ys - h / 2) / h)     # 0=中心, ~0.7=角
    core = float(a[r < 0.20].mean()) / 255.0
    ring = float(a[(r > 0.34) & (r < 0.55)].mean()) / 255.0
    corner = float(a[r > 0.66].mean()) / 255.0
    s = ring * (1.0 - core)
    shape = '方' if corner > 0.55 else ('圆' if corner < 0.20 else '混')
    return round(s, 4), dict(cov=round(frac, 3), core=round(core, 3), ring=round(ring, 3),
                             corner=round(corner, 3), shape=shape)


def load_blob(fh, kind, off, clen):
    fh.seek(off)
    blob = fh.read(clen)
    if kind == 'zlib':
        try:
            blob = zlib.decompress(blob)
        except Exception:
            return None
    return blob


def hunt(npk, tsv, out_dir, lo, hi, top):
    os.makedirs(out_dir, exist_ok=True)
    fh = open(npk, 'rb')
    rows = []
    n = 0
    for line in open(tsv, encoding='utf-8').read().splitlines()[1:]:
        p = line.split('\t')
        if len(p) < 8:
            continue
        idx, kind, off, clen, w, h = p[0], p[1], int(p[2]), int(p[3]), int(p[4]), int(p[5])
        if w == 0 or not (lo <= w <= hi and lo <= h <= hi) or abs(w - h) > max(24, w * 0.30):
            continue
        blob = load_blob(fh, kind, off, clen)
        if not blob:
            continue
        out = to_rgba(blob)
        if out is None:
            continue
        n += 1
        _, _, rgba = out
        s, info = score(rgba[:, :, 3].astype(np.float32))
        if s < 0.05:
            continue
        rows.append(dict(idx=int(idx), w=w, h=h, score=s, **info))
        if n % 300 == 0:
            print(f'  已看 {n} 张, 候选 {len(rows)}', file=sys.stderr, flush=True)
    fh.close()
    rows.sort(key=lambda r: -r['score'])
    keep = rows[:top]
    json.dump(rows, open(os.path.join(out_dir, 'candidates.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'{n} 张方形图里 {len(rows)} 张中间是空的，出前 {len(keep)} 张联系表')
    return keep


if __name__ == '__main__':
    a = sys.argv[1:]
    lo = int(a[a.index('--min') + 1]) if '--min' in a else 90
    hi = int(a[a.index('--max') + 1]) if '--max' in a else 512
    top = int(a[a.index('--top') + 1]) if '--top' in a else 60
    hunt(a[0], a[1], a[2], lo, hi, top)
