"""只把 npk 里的文本条目（xml/atlas/json/txt）倒出来，用来查资源名，不动纹理。

用法: python npk_text.py <npk> [out_dir]      例: python npk_text.py npk/gui.npk t/gui_text
产物: out_dir/NNNN.xml 等 + _text_index.json + 屏幕上的类型计数。
"""
import os, struct, sys, json, collections
import npk_unpack as U


def dump_text(npk_path, out_dir):
    d = open(npk_path, 'rb').read()
    assert d[:4] == b'NXPK', 'not NXPK'
    toc_start = struct.unpack_from('<I', d, 0x14)[0]
    os.makedirs(out_dir, exist_ok=True)
    tally = collections.Counter()
    index = []
    for i, (kind, off, clen, payload) in enumerate(U.carve(d, 0x18, toc_start)):
        if kind != 'zlib':
            continue
        if payload[:12] == U.KTX_MAGIC or payload[:8] in (U.PNG_MAGIC, b'\xff\xd8\xff'):
            continue
        ext, name = U.classify(payload)
        tally[name] += 1
        if name in ('atlas', 'json', 'xml', 'text'):
            stem = f'{i:04d}'
            with open(os.path.join(out_dir, stem + ext), 'wb') as f:
                f.write(payload)
            index.append(dict(idx=i, file=stem + ext, kind=name, off=off, rawlen=len(payload)))
    json.dump(index, open(os.path.join(out_dir, '_text_index.json'), 'w'), indent=1)
    print(f'{os.path.basename(npk_path)}: {dict(tally)} -> {out_dir} ({len(index)} 个文本条目)')
    return index


if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
        't', os.path.splitext(os.path.basename(src))[0] + '_text')
    dump_text(src, dst)
