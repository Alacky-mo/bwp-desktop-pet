import struct, zlib, sys, os, re, json

def find_zlib_streams(data, limit=12):
    found = []
    for m in re.finditer(b'\x78[\x01\x9c\x9f]', data):
        off = m.start()
        try:
            d = zlib.decompressobj()
            raw = d.decompress(data[off:], 4_000_000)
            if len(raw) > 64:
                found.append((off, len(raw), data[off:] , raw))
                if len(found) >= limit:
                    break
        except Exception:
            continue
    return found

for p in sys.argv[1:]:
    data = open(p, 'rb').read()
    print(f"\n##### {os.path.basename(p)} ({len(data):,} B)  hdr u32: {[struct.unpack_from('<I',data,o)[0] for o in range(4,24,4)]}")
    print(f"  0x00-0x20: {data[:32].hex(' ')}")
    streams = find_zlib_streams(data)
    print(f"  zlib streams found: {len(streams)}")
    for off, n, _, raw in streams[:6]:
        head = raw[:180]
        print(f"   @ {off:#x} -> {n:,} B | {head!r}")
