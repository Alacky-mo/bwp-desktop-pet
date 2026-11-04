"""扫 npk 里的纹理条目，只记尺寸/格式不解码，用来决定哪几条值得解成 PNG。

用法: python npk_scan.py <npk> [out.tsv]
产物: TSV 每行 idx  kind  off  comp_len  w  h  fmt  以及最后一段汇总。
"""
import os, struct, sys, json
import npk_unpack as U


def scan(npk_path, out_tsv):
    d = open(npk_path, 'rb').read()
    assert d[:4] == b'NXPK', 'not NXPK'
    count = struct.unpack_from('<I', d, 4)[0]
    # 0x14 那个字段不能当数据区结尾用：gui.npk 在它之后还有 44 张 2048x2048 的 atlas 页。
    # carve 靠 magic + 结构自校验，扫到文件尾只会多出几次失败的 zlib 尝试，不会认错块。
    rows = []
    for i, (kind, off, clen, payload) in enumerate(U.carve(d, 0x18, len(d))):
        w = h = 0
        fmt = ''
        if kind == 'ktx' or (kind == 'zlib' and payload[:12] == U.KTX_MAGIC):
            raw = payload if kind == 'ktx' else payload
            info = U.ktx_info(raw)
            w, h, fmt = info['w'], info['h'], hex(info['internal'])
        elif kind == 'zlib' and payload[:8] == U.PNG_MAGIC:
            w, h = struct.unpack_from('>II', payload, 16)
            fmt = 'png'
        elif kind == 'png':
            w, h = struct.unpack_from('>II', payload, 16)
            fmt = 'png'
        elif kind == 'jpg':
            fmt = 'jpg'
        elif kind == 'zlib':
            ext, kind_name = U.classify(payload)
            fmt = kind_name
        rows.append((i, kind, off, clen, w, h, fmt, len(payload)))
    with open(out_tsv, 'w', encoding='utf-8', newline='') as f:
        f.write('idx\tkind\toff\tclen\tw\th\tfmt\trawlen\n')
        for r in rows:
            f.write('\t'.join(str(x) for x in r) + '\n')

    tex = [r for r in rows if r[4] and r[5]]
    print(f'{os.path.basename(npk_path)}: toc 声明 {count} 条, 切出 {len(rows)} 块, 其中带尺寸 {len(tex)}')
    big = sorted(tex, key=lambda r: -r[4] * r[5])[:8]
    for r in big:
        print(f'   最大 #{r[0]:04d} {r[1]} {r[4]}x{r[5]} {r[6]} raw={r[7]:,}')
    sq = [r for r in tex if abs(r[4] - r[5]) <= 2 and 128 <= r[4] <= 640]
    print(f'   接近正方且边长 128~640 的页/件: {len(sq)} 条')
    print(f'   -> {out_tsv}')
    return rows


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'out',
        os.path.splitext(os.path.basename(src))[0] + '_scan.tsv')
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    scan(src, dst)
