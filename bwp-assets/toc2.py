import struct, zlib, sys, os, collections

def load(path):
    d = open(path,'rb').read()
    assert d[:4] == b'NXPK', d[:4]
    count = struct.unpack_from('<I', d, 4)[0]
    toc_start = struct.unpack_from('<I', d, 0x14)[0]
    print(f"{os.path.basename(path)}: size={len(d):,} count={count} toc_start={toc_start:,} check={len(d)-count*28:,}")
    recs = [struct.unpack_from('<7I', d, toc_start + i*28) for i in range(count)]
    return d, count, toc_start, recs

def magic_at(d, off):
    if off is None or off < 0x18 or off+8 > len(d): return None
    m = d[off:off+8]
    if m[:4] == b'\x89PNG': return 'png'
    if m[:4] == b'\xabKTX': return 'ktx'
    if m[:2] == b'\x78\x9c' or m[:2] == b'\x78\x01' or m[:2] == b'\x78\x9f': return 'zlib'
    if m[:3] == b'\xff\xd8\xff': return 'jpg'
    if m[:4] == b'RGIS': return 'rgis'
    return m[:6].hex()

for path in sys.argv[1:]:
    d, count, toc_start, recs = load(path)
    hits = collections.Counter()
    samples = []
    for i, r in enumerate(recs):
        a,b,c,e,f,g,h = r
        signed_e = e - (1<<32) if e >= (1<<31) else e
        cands = {
            'f5': f, 'f5+f6': f, 'e_signed_abs': signed_e,
            'toc+e': toc_start + signed_e, 'g': g, 'e_signed+hdr': toc_start + signed_e + 16,
        }
        got = None
        for k, off in cands.items():
            m = magic_at(d, off)
            if m in ('png','ktx','zlib','jpg','rgis'):
                got = (k, off, m); break
        if got:
            hits[got[0]+':'+got[2]] += 1
            if len(samples) < 5:
                samples.append((i, r, got))
    print("  hit patterns:", dict(hits))
    for s in samples:
        i, r, got = s
        print(f"   rec{i} raw={[f'{v:#x}/{v}' for v in r]} -> {got}")
