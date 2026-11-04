"""NXPK (NetEase NeoX) unpacker — carve blobs from the data region and convert textures to PNG."""
import struct, zlib, io, json, os, sys, re
from PIL import Image
import texture2ddecoder

PNG_MAGIC = b'\x89PNG\r\n\x1a\n'
KTX_MAGIC = b'\xabKTX 11\xbb\r\n\x1a\n'
# KTX glInternalFormat -> ASTC block size (Khronos GL_COMPRESSED_RGBA_ASTC_*)
ASTC_FMTS = {
    0x93B0: (4, 4), 0x93B1: (5, 4), 0x93B2: (6, 5), 0x93B3: (8, 5),
    0x93B4: (8, 6), 0x93B5: (10, 5), 0x93B6: (10, 6), 0x93B7: (8, 8),
    0x93B8: (12, 10), 0x93B9: (10, 10), 0x93BA: (12, 12), 0x93BB: (3, 3),
    0x809A: (4, 4), 0x809B: (5, 4), 0x809C: (6, 5), 0x809D: (8, 5),
    0x809E: (8, 6), 0x809F: (10, 5), 0x80A0: (10, 6), 0x80A1: (8, 8),
    0x80A2: (12, 10), 0x80A3: (10, 10), 0x80A4: (12, 12),
}
ETC_FMTS = {0x8D64: ('etc2', 3), 0x8D65: ('etc2a1', 4), 0x9275: ('etc2a8', 4),
            0x9274: ('etc2a8', 4), 0x8D67: ('etc1', 3),
            0x9278: ('etc2a8', 4), 0x9279: ('etc2a8', 4)}   # RGBA8_ETC2_EAC，gui.npk 的 atlas 页在用


MAX_BLOB = 1 << 26  # 64 MiB; also keeps false-positive magic scans O(1)


def png_len(d, o):
    p = o + 8
    while p + 8 <= len(d) and p - o < MAX_BLOB:
        ln = struct.unpack_from('>I', d, p)[0]
        typ = d[p + 4:p + 8]
        if typ == b'IEND':
            return p + 12 - o
        if ln > MAX_BLOB or not typ or not all(65 <= c < 91 or 97 <= c < 123 for c in typ):
            return None
        p += 12 + ln
    return None


def jpg_len(d, o):
    eoi = d.find(b'\xff\xd9', o + 2, o + MAX_BLOB)
    return None if eoi < 0 else eoi + 2 - o


def ktx_info(raw):
    f = struct.unpack_from('<13I', raw, 12)
    (endian, glType, glTypeSize, glFormat, internal, base, w, h, depth,
     arr, faces, mips, kv) = f
    return dict(internal=internal, w=w, h=h, mips=mips, faces=faces, arr=arr, kv=kv,
                compressed=(glType == 0))


def ktx_to_png(raw, out_path):
    info = ktx_info(raw)
    w, h = info['w'], info['h']
    body = raw[64 + info['kv']:]
    mip_size = struct.unpack_from('<I', body, 0)[0]
    data = body[4:4 + mip_size]
    fmt = info['internal']
    # texture2ddecoder hands back BGRA for every format; reading it as RGBA silently swaps the
    # red and blue channels, which is what made the exported art read cold and blue-violet.
    if fmt in ASTC_FMTS:
        bw, bh = ASTC_FMTS[fmt]
        bgra = texture2ddecoder.decode_astc(data, w, h, bw, bh)
        Image.frombytes('RGBA', (w, h), bgra, 'raw', 'BGRA').save(out_path, compress_level=1)
        return f'ASTC {bw}x{bh} {w}x{h}'
    if fmt in ETC_FMTS:
        kind = ETC_FMTS[fmt][0]
        fn = getattr(texture2ddecoder, 'decode_' + kind)
        bgra = fn(data, w, h)     # ETC 的解码函数只收 (data, w, h)，多传 bpp 会 TypeError
        Image.frombytes('RGBA', (w, h), bgra, 'raw', 'BGRA').save(out_path, compress_level=1)
        return f'{kind} {w}x{h}'
    return f'unsupported ktx fmt={hex(fmt)} {w}x{h}'


def _utf8_text(head):
    """汉字走 UTF-8 三字节，全落在 32..127 之外 —— 只按 ASCII 可打印率量，整包中文剧情脚本会被读成 bin。
    这把尺改看「能不能按 UTF-8 解开」：4096 这一刀可能正好切断半个字，只许丢那 1~3 个字节，
    丢多了就是真二进制。"""
    txt = head.decode('utf-8', 'ignore')
    if len(txt.encode('utf-8')) < len(head) - 3:
        return False
    ok = sum(1 for c in txt if c.isprintable() or c in '\t\n\r')
    return ok > 0.95 * max(1, len(txt))


def classify(payload):
    """Return (extension, kind) for a decompressed non-image entry."""
    head = payload[:4096]
    printable = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    ratio = printable / max(1, len(head))
    ascii_only = ratio > 0.95
    if ascii_only or _utf8_text(head):
        txt = head.decode('utf-8', 'replace')
        if '\nsize:' in txt and ('xy:' in txt or 'rotate:' in txt):
            return '.atlas', 'atlas'
        if txt[:1] == '<':
            return '.xml', 'xml'
        if ascii_only and txt[:1] in '{[':
            return '.json', 'json'
        return '.txt', 'text'
    return '.bin', 'bin'


MAGIC_RE = re.compile(b'\x89PNG\r\n\x1a\n|\xabKTX 11\xbb|\x78[\x01\x9c\x9f]|\xff\xd8\xff')


def carve(d, start, end):
    """Yield (kind, offset, comp_len, payload) by walking a pre-built candidate offset table.

    Entries are 4-byte aligned with zero padding, and unknown high-entropy blocks sit
    between them, so blob boundaries come from decoding rather than from the TOC.
    """
    cands = [m.start() for m in MAGIC_RE.finditer(d, start, end)]
    mv = memoryview(d)
    i, n = 0, len(cands)
    while i < n:
        o = cands[i]
        if o >= end:
            return
        head = d[o:o + 12]
        blob = None
        if head[:8] == PNG_MAGIC:
            L = png_len(d, o)
            if L:
                blob = ('png', o, L, d[o:o + L])
        elif head[:4] == KTX_MAGIC[:4]:
            try:
                info = ktx_info(d[o:o + 80])
                size = 64 + info['kv'] + 4 + struct.unpack_from('<I', d, o + 64 + info['kv'])[0]
                blob = ('ktx', o, size, d[o:o + size])
            except Exception:
                pass
        elif head[:3] == b'\xff\xd8\xff':
            L = jpg_len(d, o)
            if L:
                blob = ('jpg', o, L, d[o:o + L])
        elif head[0] == 0x78 and head[1] in (0x01, 0x9C, 0x9F):
            dz = zlib.decompressobj()
            try:
                view = mv[o:min(o + MAX_BLOB, len(d))]
                payload = dz.decompress(view, 64 << 20)
                blob = ('zlib', o, view.nbytes - len(dz.unused_data), payload)
            except Exception:
                pass
        if blob:
            yield blob
            stop = o + blob[2]
            while i < n and cands[i] < stop:
                i += 1
        else:
            i += 1
    return


def unpack(npk_path, out_dir, limit=None, verbose=True):
    d = open(npk_path, 'rb').read()
    assert d[:4] == b'NXPK', 'not NXPK'
    count = struct.unpack_from('<I', d, 4)[0]
    toc_start = struct.unpack_from('<I', d, 0x14)[0]
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    n = 0
    # 数据区一直扫到文件尾：0x14 处的 toc_start 在 gui.npk 上偏早，会漏掉尾部 44 张 atlas 页
    for i, (kind, off, clen, payload) in enumerate(carve(d, 0x18, len(d))):
        if verbose and i % 500 == 0:
            print(f'  blob {i} @ {off:,}', file=sys.stderr, flush=True)
        if limit and n >= limit:
            break
        base = f'{i:04d}'
        if kind == 'png':
            p = os.path.join(out_dir, base + '.png')
            open(p, 'wb').write(payload)
            im = Image.open(io.BytesIO(payload))
            manifest.append(dict(idx=i, kind='png', off=off, size=len(payload), w=im.width, h=im.height))
        elif kind == 'jpg':
            p = os.path.join(out_dir, base + '.jpg')
            open(p, 'wb').write(payload)
            manifest.append(dict(idx=i, kind='jpg', off=off, size=len(payload)))
        elif kind == 'zlib':
            if payload[:12] == KTX_MAGIC:
                p = os.path.join(out_dir, base + '.png')
                desc = ktx_to_png(payload, p)
                info = ktx_info(payload)
                manifest.append(dict(idx=i, kind='zlib/ktx', off=off, csize=clen,
                                     size=len(payload), fmt=info['internal'], w=info['w'], h=info['h'], note=desc))
            elif payload[:8] == PNG_MAGIC:
                p = os.path.join(out_dir, base + '.png')
                open(p, 'wb').write(payload)
                im = Image.open(io.BytesIO(payload))
                manifest.append(dict(idx=i, kind='zlib/png', off=off, csize=clen,
                                     size=len(payload), w=im.width, h=im.height))
            else:
                ext, kind_name = classify(payload)
                p = os.path.join(out_dir, base + ext)
                if ext == '.bin':
                    open(p, 'wb').write(payload)
                else:
                    # bytes, not decoded text: many entries are already CRLF and a text-mode
                    # write would turn every line break into \r\r\n, which breaks the atlas parser
                    open(p, 'wb').write(payload)
                manifest.append(dict(idx=i, kind='zlib/' + kind_name, off=off, csize=clen,
                                     size=len(payload), head=payload[:8].hex()))
            n += 1
            continue
        elif kind == 'ktx':
            p = os.path.join(out_dir, base + '.png')
            desc = ktx_to_png(payload, p)
            info = ktx_info(payload)
            manifest.append(dict(idx=i, kind='ktx', off=off, size=len(payload),
                                 fmt=info['internal'], w=info['w'], h=info['h'], note=desc))
        n += 1
    json.dump(manifest, open(os.path.join(out_dir, '_manifest.json'), 'w'), indent=1)
    if verbose:
        print(f'{os.path.basename(npk_path)}: entries={count} extracted={n} -> {out_dir}')
        for m in manifest[:6]:
            print('   ', m)
    return manifest, count, toc_start, d


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    lim = int(sys.argv[3]) if len(sys.argv) > 3 else None
    unpack(src, dst, lim)
