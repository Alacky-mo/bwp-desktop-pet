"""NXPK (NetEase NeoX) extractor — read entries straight from the table of contents.

Layout: 'NXPK', u32 count @0x04, u32 toc_start @0x14 (== file_size - count*28).
Each 28-byte TOC record is
    u32 name_hash, u32 file_offset, u32 comp_size, u32 raw_size, u32 crc1, u32 crc2, u32 flags
Offsets are exact and cover the data region byte for byte, so nothing has to be carved or
guessed. Only the name is hashed, which is why files land as <seq>_<hash>.<ext>.

Usage: python npk_toc.py <pack.npk> <out_dir>
"""
import os, struct, sys, json, zlib
from PIL import Image
from npk_unpack import KTX_MAGIC, PNG_MAGIC, ktx_info, ktx_to_png, classify


def toc(npk_path):
    d = open(npk_path, 'rb').read()
    if d[:4] != b'NXPK':
        raise SystemExit(f'{npk_path}: not an NXPK container')
    count = struct.unpack_from('<I', d, 4)[0]
    start = struct.unpack_from('<I', d, 0x14)[0]
    if start != len(d) - count * 28:
        print(f'  warning: toc_start {start} != {len(d) - count * 28}', file=sys.stderr)
    recs = [struct.unpack_from('<7I', d, start + 28 * i) for i in range(count)]
    return d, sorted(recs, key=lambda r: r[1])


def payload(d, off, comp, raw):
    blob = d[off:off + comp]
    if comp == raw:
        return blob, 'raw'
    try:
        return zlib.decompress(blob), 'zlib'
    except zlib.error:
        return b'', 'error'


def unpack(npk_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    d, recs = toc(npk_path)
    manifest, counts = [], {}
    for seq, (h, off, comp, raw, c1, c2, fl) in enumerate(recs):
        pay, how = payload(d, off, comp, raw)
        stem = f'{seq:04d}_{h:08x}'
        e = dict(idx=seq, hash=h, name=stem, off=off, csize=comp, size=raw, kind='empty')
        if not pay:
            e['kind'] = 'error'
        elif pay[:12] == KTX_MAGIC:
            note = ktx_to_png(pay, os.path.join(out_dir, stem + '.png'))
            info = ktx_info(pay)
            e.update(name=stem + '.png', ext='.png', kind=f'{how}/ktx', w=info['w'], h=info['h'],
                     note=note)
        elif pay[:8] == PNG_MAGIC:
            w, h = struct.unpack_from('>II', pay, 16)
            with open(os.path.join(out_dir, stem + '.png'), 'wb') as f:
                f.write(pay)
            e.update(name=stem + '.png', ext='.png', kind=f'{how}/png', w=w, h=h)
        else:
            ext, kind = classify(pay)
            with open(os.path.join(out_dir, stem + ext), 'wb') as f:
                f.write(pay)
            e.update(name=stem + ext, ext=ext, kind=f'{how}/{kind}')
        counts[e.get('ext', '.bin')] = counts.get(e.get('ext', '.bin'), 0) + 1
        manifest.append(e)
        if seq and seq % 500 == 0:
            print(f'  {seq}/{len(recs)}', file=sys.stderr)
    json.dump(manifest, open(os.path.join(out_dir, '_manifest.json'), 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)
    print(f'{npk_path}: {len(recs)} entries {counts} -> {out_dir}')
    return manifest


if __name__ == '__main__':
    unpack(sys.argv[1], sys.argv[2])
