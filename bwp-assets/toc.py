import struct, sys

def analyze(name, slice_bytes, count, total_size, slice_start):
    d = slice_bytes
    print(f"\n##### {name}: count={count} total={total_size:,} slice={len(d):,}@{slice_start:,}")
    best = []
    for R in range(12, 64, 4):
        toc_len = count * R
        if toc_len > len(d):
            continue
        toc = d[len(d)-toc_len:]
        cols = [struct.unpack_from(f'<{R//4}I', toc, i*R) for i in range(count)]
        # score each column for monotonic increase
        for c in range(R//4):
            vals = [row[c] for row in cols]
            inc = sum(1 for a, b in zip(vals, vals[1:]) if b > a)
            if inc > count*0.95 and max(vals) < total_size:
                best.append((R, c, inc, vals[:4], vals[-2:]))
    for b in best[:6]:
        R, c, inc, head, tail = b
        print(f"  record={R}B col{c} monotonic={inc}/{count} first={head} last={tail}")
    if not best:
        print("  no monotonic column found; dumping first 6 records of R=24/28/32")
        for R in (24, 28, 32):
            toc = d[len(d)-count*R:]
            for i in range(4):
                print(f"   R={R} #{i}: {[f'{v:#x}({v})' for v in struct.unpack_from(f'<{R//4}I', toc, i*R)]}")

# texture_card1: header count=2739 total=564,090,140 ; slice pulled with bs=1048576 skip=533
d = open('heads/texture_card1.tail.bin','rb').read()
analyze('texture_card1', d, 2739, 564090140, 533*1048576)
d2 = open('heads/loading.tail.bin','rb').read()
analyze('loading', d2, 139, 318188244, 299*1048576)
d3 = open('heads/char.tail.bin','rb').read()
analyze('char', d3, 2581, 110097460, 100*1048576)
