"""把一张 PNG 打成 DeskSpine 用的多帧 .ico（托盘/气泡图标只吃 .ico，不吃 png）。

用法: python png_to_ico.py <输入.png> <输出.ico> [--sizes 16,32,48,64,128,256]
    出文件的形状照抄现场那两个: res/image/hourlychime.ico 和 appicon_dark.ico
    —— planes=1、bpp=32、小帧 BMP 载荷、256 帧 PNG 载荷。
    PIL 自己的 ICO 写出器不给这个形状（只出 4 帧、planes=0、还把 64 写成 63 高），所以手搓。
    帧集合默认不写死 6 帧: 现场读码实测 ConfigForm.cs:73 是 new Bitmap(path)，GDI+ 拿 .ico 取的是
    **最大那一帧**（拿 hourlychime.ico 试过，回来 256x256），所以最大帧就是气泡上真正显示的尺寸 ——
    比原图大的帧只会凭空放大糊一层，默认只出「不超过原图的最大标准档 + 刚够包住原图的那一档」。
"""
import io, os, struct, sys
from PIL import Image

SIZES = (16, 32, 48, 64, 128, 256)


def frames_for(w, h, sizes=SIZES):
    """最大帧取「离原图长边最近的那一档」（按比值取对数比远近，128 对 123 和 256 对 224 都算近），
    比它小的标准档全带上。这样既不浪费原图的细节，也不凭空吹出一张糊的 256。"""
    import math
    long_edge = max(w, h)
    top = min(sizes, key=lambda s: abs(math.log(s / long_edge)))
    return [s for s in sizes if s <= top]




def square(im, n):
    """等比缩到「长边 = n」再居中垫成 n x n 透明画布 —— 图标必须方，硬拉会变形。"""
    w, h = im.size
    s = n / max(w, h)
    nw, nh = max(1, round(w * s)), max(1, round(h * s))
    canvas = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    canvas.paste(im.resize((nw, nh), Image.LANCZOS), ((n - nw) // 2, (n - nh) // 2))
    return canvas


def bmp_frame(im):
    """32bpp BI_RGB 的位图载荷: 头 + 自下而上的 BGRA + 全 0 的 AND 掩码（透明度走 alpha 通道，掩码留着但别挡）。"""
    w, h = im.size
    px = im.load()
    out = [struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, 32, 0, 0, 0, 0, 0, 0)]
    for y in range(h - 1, -1, -1):
        row = bytearray()
        for x in range(w):
            r, g, b, a = px[x, y]
            row += bytes((b, g, r, a))
        out.append(bytes(row))
    out.append(b'\x00' * (((w + 31) // 32) * 4) * h)
    return b''.join(out)


def png_frame(im):
    buf = io.BytesIO()
    im.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def build(src, dst, sizes=None):
    im = Image.open(src).convert('RGBA')
    sizes = list(sizes) if sizes else frames_for(im.width, im.height)
    entries = []
    for n in sizes:
        sq = square(im, n)
        payload = png_frame(sq) if n >= 256 else bmp_frame(sq)
        entries.append((n, payload))
    head = struct.pack('<HHH', 0, 1, len(entries))
    off = 6 + 16 * len(entries)
    dir_, body = b'', b''
    for n, payload in entries:
        dir_ += struct.pack('<BBBBHHII', n % 256, n % 256, 0, 0, 1, 32, len(payload), off)
        body += payload
        off += len(payload)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    with open(dst, 'wb') as f:
        f.write(head + dir_ + body)
    print(f'{src} -> {dst}  {len(entries)} 帧 {",".join(str(n) for n, _ in entries)}  '
          f'{os.path.getsize(dst)} 字节')
    verify(dst)


def verify(path):
    """写完立刻自查: 帧数/尺寸/载荷类型对不对得上现场那两个 ico 的形状，PIL 能不能读回来。"""
    b = open(path, 'rb').read()
    n = struct.unpack_from('<H', b, 4)[0]
    got = []
    for i in range(n):
        w, h, _, _, planes, bits, size, off = struct.unpack_from('<BBBBHHII', b, 6 + 16 * i)
        kind = 'PNG' if b[off:off + 4] == b'\x89PNG' else 'BMP'
        got.append((w or 256, h or 256, planes, bits, kind))
    for w, h, planes, bits, kind in got:
        assert w == h, f'{w}x{h} 不是方的'
        assert planes == 1 and bits == 32, f'{w}px 帧 planes={planes} bpp={bits}，和 hourlychime.ico 不一致'
        assert (kind == 'PNG') == (w >= 256), f'{w}px 帧用了 {kind}，现场那两个是「小帧 BMP、256 帧 PNG」'
    assert [g[0] for g in got] == sorted(g[0] for g in got), '帧尺寸没按小到大排'
    Image.open(path).ico.sizes()
    print('  自查 OK: ' + ' '.join(f'{w}px/{k}' for w, _, _, _, k in got))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    sizes = next((tuple(int(x) for x in a.split('=', 1)[1].split(','))
                  for a in sys.argv[1:] if a.startswith('--sizes=')), None)
    if len(args) != 2:
        raise SystemExit(__doc__)
    build(args[0], args[1], sizes)
