import struct, zlib, sys, os, collections

def probe(path):
    data = open(path, 'rb').read()
    magic = data[:4]
    print(f"=== {os.path.basename(path)} size={len(data):,} magic={magic!r}")
    print("  header u32s:", [struct.unpack_from('<I', data, o)[0] for o in range(4, 24, 4)])
    for off in (0x14, 0x18, 0x10):
        try:
            raw = zlib.decompress(data[off:])
            print(f"  inflate @ {off:#x} OK -> {len(raw):,} bytes")
            return off, raw
        except Exception as e:
            print(f"  inflate @ {off:#x} fail: {e}")
    return None, None

for p in sys.argv[1:]:
    off, raw = probe(p)
    if raw:
        print("  first 600 bytes of index:")
        print("   ", raw[:600])
        print("  printable strings:", raw[:400].decode('latin1').split('\x00')[:8])
