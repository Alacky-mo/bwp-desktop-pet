"""把候选对话框素材拼成「方案预览图」，交用户肉眼挑。

这是 PIL 合成的一张预览，**不是桌宠真窗口**：真窗口要走 LayeredPaint 逐像素贴，字也是 GDI+ 画的，
这边只是让人看得出「哪套组合像和风、哪套不像」。挑完再落产品代码。

两条自己踩过的坑写在这儿：
1. 气泡那两张（img_bubble / bubble_02）九切会把右边的青海波纹拉糊、左下的尾巴拉扁 ——
   所以按原尺寸贴，字放不下就削台词池，不削美术。
2. 这两张的裁片里混着**邻格碎片**（一块浅蓝方块、一个紫色加号），不是气泡自己的像素。
   预览先用 keep_blobs 只留大连通块；产品里要真做一次清洗，和上次小窗左边线那条同一回事。

用法: python dialog_mock.py <素材目录> <out目录> [台词池.tsv]
    台词池是 out/bz-pool.tsv（游戏原文，不入库）；没给就用等长的占位串，脚本里不嵌版权文本。
"""
import csv
import os, sys
from collections import deque
from PIL import Image, ImageDraw, ImageFont

SRC = None
INK = (58, 44, 40, 255)
INK_LIGHT = (248, 242, 233, 255)
FONT = r'C:\Windows\Fonts\msyh.ttc'
BG = (150, 152, 158, 255)          # 桌面感的中间底：气泡是浅色，落在纸上等于没出图

# 烫金那一支：深金取 biaoqian_01 的 (197,146,28) 压深、亮金取 line_tips 的 (254,236,174)
GOLD_DEEP = (150, 100, 20)
GOLD_MID = (212, 160, 45)
GOLD_LIGHT = (252, 228, 152)


def lerp(c1, c2, t):
    return tuple(round(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def load_pool(path):
    """读台词池，返回按字数排的 [(字数, 显示文本)]。
    字数按**带『』的那一列**算 —— 屏幕上贴出去的就是带引号那条，少算两个字会把上限吹高。"""
    if not path or not os.path.exists(path):
        return None
    rows = list(csv.reader(open(path, encoding='utf-8'), delimiter='\t'))
    out = [(len(r[3]), r[3]) for r in rows[1:]]
    return sorted(out, reverse=True)


def pick_lines(pool):
    """MID = 最长的「塞得进最窄那档」的一条；LONG = 池子里最长的一条。
    最窄档是 36 字（A/B 两个气泡实测上限），比它长的只能进 C/D。"""
    if pool is None:
        return '『』' + '一' * 32 + '……' * 1, '『』' + '二' * 44 + '……' * 1
    fit36 = [t for n, t in pool if n <= 36]
    return fit36[0], pool[0][1]


LONG = MID = ''
PROBE = '一' * 80


def art(name):
    return Image.open(os.path.join(SRC, name)).convert('RGBA')


def solid_distance(img, alpha_gate=200):
    """实体像素（alpha ≥ gate）到「非实体」的最短距离图，4 邻域 BFS。
    边框加粗靠它：实测这张气泡的金线就是距边第 1 档那 778 个像素（均色 195,178,160），第 2 档起就是纸
    —— 所以「边框几 px」= 把距边 ≤k 的那几档染成金。"""
    w, h = img.size
    a = img.getchannel('A').load()
    solid = [[a[x, y] >= alpha_gate for x in range(w)] for y in range(h)]
    inf = 1 << 15
    d = [[inf if solid[y][x] else 0 for x in range(w)] for y in range(h)]
    q = deque((x, y) for y in range(h) for x in range(w) if not solid[y][x])
    while q:
        cx, cy = q.popleft()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if 0 <= nx < w and 0 <= ny < h and solid[ny][nx] and d[ny][nx] > d[cy][cx] + 1:
                d[ny][nx] = d[cy][cx] + 1
                q.append((nx, ny))
    return d, solid


def band_means(img, depth=4, alpha_gate=200):
    """距边第 1..depth 档各自的均色 —— 装机脚本用它自证「金线真的有这么粗」，不靠嘴说"""
    d, solid = solid_distance(img, alpha_gate)
    acc = [[0, 0, 0, 0] for _ in range(depth)]
    px = img.load()
    for y in range(img.height):
        for x in range(img.width):
            if not solid[y][x] or d[y][x] > depth:
                continue
            k = d[y][x] - 1
            r, g, b, _ = px[x, y]
            acc[k][0] += r; acc[k][1] += g; acc[k][2] += b; acc[k][3] += 1
    out = []
    for c in acc:
        rgb = tuple(v // c[3] for v in c[:3]) if c[3] else (0, 0, 0)
        out.append((rgb, c[3]))
    return out


def gilded(img, px, keep=0.15):
    """边框加粗：距边 <=px 的那几档按「外深内亮」染金，保留原像素 keep 让纸面明暗还在。
    只动颜色、不动轮廓 —— 装机判据那两条（有分量的连通块 1 个、最大块占全图墨 99%）量的就是轮廓，照旧绿。
    色值取库里：深金 = 名牌条 biaoqian_01 的 (197,146,28) 再压深，亮金 = 分隔线 line_tips 的 (254,236,174)"""
    out = img.copy()
    d, solid = solid_distance(img)
    src, dst = img.load(), out.load()
    for y in range(img.height):
        for x in range(img.width):
            if not solid[y][x] or d[y][x] > px:
                continue
            t = (d[y][x] - 1) / max(1, px - 1)
            gold = lerp(GOLD_DEEP, GOLD_MID, t / 0.6) if t < 0.6 else lerp(GOLD_MID, GOLD_LIGHT, (t - 0.6) / 0.4)
            dst[x, y] = tuple(round(src[x, y][i] + (gold[i] - src[x, y][i]) * (1 - keep)) for i in range(3)) + \
                (src[x, y][3],)
    return out


def keep_blobs(img, min_ratio=0.15, alpha_gate=24):
    """只留面积够大的连通块 —— 气泡本体和尾巴是连着的，邻格碎片是散开的小块。
    0.15 这条线是量出来的：松针那张的邻格方块占本体的 0.124，气泡那两张的碎片只有 0.02，
    而枫叶是单块（比例恒为 1），所以一刀切不会把小装饰件抹没。"""
    w, h = img.size
    a = img.getchannel('A').load()
    seen = [[False] * w for _ in range(h)]
    comps = []
    for y in range(h):
        for x in range(w):
            if seen[y][x] or a[x, y] <= alpha_gate:
                continue
            q, cells = deque(((x, y),)), []
            seen[y][x] = True
            while q:
                cx, cy = q.popleft()
                cells.append((cx, cy))
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and a[nx, ny] > alpha_gate:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            comps.append(cells)
    if not comps:
        return img, 0
    top = max(len(c) for c in comps) * min_ratio
    out = img.copy()
    px = out.load()
    for cells in comps:
        if len(cells) < top:
            for cx, cy in cells:
                px[cx, cy] = (0, 0, 0, 0)
    dropped = sum(1 for c in comps if len(c) < top)
    return out, dropped


def three_slice(img, cap, w, h):
    """两端原样、只拉中段 —— 剧情框那族九宫格拉不了（斜头把边带撑得比目标还宽），
    但中段列均色最大偏离只有 3~4/255，横着拉看不出来。"""
    sw, sh = img.size
    base = img.resize((max(w, int(sw * h / sh)), h), Image.LANCZOS)
    bw = base.size[0]
    c = max(1, int(cap * bw / sw))
    c = min(c, w // 2 - 1)
    body = base.crop((c, 0, bw - c, h)).resize((w - 2 * c, h), Image.LANCZOS)
    out = Image.new('RGBA', (w, h))
    out.paste(base.crop((0, 0, c, h)), (0, 0))
    out.paste(body, (c, 0))
    out.paste(base.crop((bw - c, 0, bw, h)), (w - c, 0))
    return out


def nine_slice(img, inset, w, h):
    sw, sh = img.size
    l, r, t, b = inset, sw - inset, inset, sh - inset
    out = Image.new('RGBA', (w, h))
    cols = ((0, 0, l, l), (l, l, r, w - r), (w - inset, r, sw, inset))
    rows = ((0, 0, t, t), (t, t, b, h - b), (h - inset, b, sh, inset))
    for dx, x0, x1, dw in cols:
        for dy, y0, y1, dh in rows:
            if dw <= 0 or dh <= 0 or x1 <= x0 or y1 <= y0:
                continue
            out.paste(img.crop((x0, y0, x1, y1)).resize((dw, dh), Image.LANCZOS), (dx, dy))
    return out


def wrap(draw, text, font, width):
    lines, cur = [], ''
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def draw_text(canvas, text, font, area, fill=INK):
    dr = ImageDraw.Draw(canvas)
    x, y, w, h = area
    for line in wrap(dr, text, font, w):
        dr.text((x, y), line, font=font, fill=fill)
        y += font.size + 8
    if y > area[1] + area[3]:
        dr.rectangle((x, area[1], x + w, area[1] + area[3]), outline=(220, 60, 60, 255), width=2)
    return canvas


def plate_name(canvas, text, pos, font, fill=INK, plate=None, pad=(12, 6)):
    """名牌：底条素材本身是斜口的，一拉就糊，按原样贴。"""
    dr = ImageDraw.Draw(canvas)
    x, y = pos
    if plate is not None:
        canvas.alpha_composite(plate, (x - pad[0], y - pad[1]))
    dr.text((x + 2, y), text, font=font, fill=fill)


def capacity(font, area):
    """一行几个字、能排几行 —— 这两个数必须量出来，不能我手写。"""
    probe = Image.new('RGBA', (8, 8))
    lines = wrap(ImageDraw.Draw(probe), PROBE, font, area[2])
    per = len(lines[0]) if len(lines) > 1 else area[2] // font.size
    rows = area[3] // (font.size + 8)
    return per, rows


def panel(name, size, body, builder):
    canvas, info = builder(Image.new('RGBA', size, (255, 255, 255, 0)), size)
    per, rows = capacity(info['font'], info['area'])
    notes = [f"正文区 {info['area'][2]}x{info['area'][3]}，实测一行 {per} 字 x {rows} 行 = 上限 {per * rows} 字"]
    notes += info.get('notes', [])
    img = Image.new('RGBA', (max(size[0] + 40, 640), size[1] + 74 + 22 * len(notes)), BG)
    dr = ImageDraw.Draw(img)
    dr.text((20, 12), name, font=ImageFont.truetype(FONT, 21), fill=(20, 20, 26, 255))
    x, y = 20, 44
    img.paste(canvas, (x, y), canvas)
    dr.rectangle((x, y, x + size[0] - 1, y + size[1] - 1), outline=(90, 92, 100, 255))
    dr.text((x + size[0] + 14, y + 4), f'{size[0]}x{size[1]}',
            font=ImageFont.truetype(FONT, 18), fill=(236, 236, 240, 255))
    dr.text((x + size[0] + 14, y + 30), f'台词 {len(body)} 字',
            font=ImageFont.truetype(FONT, 18), fill=(236, 236, 240, 255))
    ty = y + size[1] + 10
    for n in notes:
        dr.text((x, ty), n, font=ImageFont.truetype(FONT, 17), fill=(255, 214, 150, 255))
        ty += 22
    return img, per, rows


def main(src, out_dir, pool_path=None):
    global SRC, LONG, MID
    SRC = src
    os.makedirs(out_dir, exist_ok=True)
    pool = load_pool(pool_path)
    MID, LONG = pick_lines(pool)
    fbody = ImageFont.truetype(FONT, 19)      # 预览按 19px 排；产品里正文下限那条是 17px 粗
    fname = ImageFont.truetype(FONT, 20)

    def A(canvas, box):
        """奶油气泡原尺寸 + 左上松针金扇压在角上。"""
        w, h = box
        bub, dropped = keep_blobs(art('gui_ui_common_img_bubble.png'))
        canvas.alpha_composite(bub, (w - bub.width, h - bub.height))
        sz, d2 = keep_blobs(art('gui_ui_scenerio_img_songzhen.png'))
        sz = sz.resize((int(sz.width * 0.72), int(sz.height * 0.72)), Image.LANCZOS)
        canvas.alpha_composite(sz, (0, 0))
        line = art('gui_ui_common_line_tips.png').resize((140, 4), Image.LANCZOS)
        canvas.alpha_composite(line, (150, 36))
        plate_name(canvas, '不知火', (150, 12), fname)
        area = (158, 48, w - 194, h - 68)
        draw_text(canvas, MID, fbody, area)
        return canvas, {'font': fbody, 'area': area,
                        'notes': [f'邻格碎片：气泡抹掉 {dropped} 块、松针抹掉 {d2} 块（产品里要真清洗一次）',
                                  '松针金扇压在气泡左上角，尾巴在左下 —— 贴头部右上时正好指回宠物']}

    def B(canvas, box):
        """青海波气泡原尺寸 + 左上家纹圆印当说话人印记。"""
        w, h = box
        bub, dropped = keep_blobs(art('gui_ui_common_img_bubble_02.png'))
        canvas.alpha_composite(bub, (w - bub.width, h - bub.height))
        crest, d2 = keep_blobs(art('gui_ui_scenerio_img_duoren_01.png'))
        crest = crest.resize((42, 42), Image.LANCZOS)
        canvas.alpha_composite(crest, (4, 4))
        plate_name(canvas, '不知火', (54, 14), fname)
        area = (54, 48, w - 86, h - 68)
        draw_text(canvas, MID, fbody, area)
        return canvas, {'font': fbody, 'area': area,
                        'notes': [f'邻格碎片：气泡抹掉 {dropped} 块、家纹抹掉 {d2} 块',
                                  '青海波纹在右半边，所以装饰全挪到左边，不压花纹']}

    def C(canvas, box):
        """官方剧情框三切（不加流光：那条是深色带，压在浅框上把框啃黑了一块）。"""
        w, h = box
        bar = three_slice(art('gui_ui_scenerio_img_duihuakuang02.png'), 63, w, h)
        canvas.paste(bar, (0, 0), bar)
        plate_name(canvas, '不知火', (26, 12), fname, INK_LIGHT,
                   art('gui_ui_scenerio_img_title_bg.png'))
        for fn, pos in (('gui_ui_title_img_44_fengye1.png', (w - 78, 6)),
                        ('gui_ui_title_img_44_fengye2.png', (w - 46, 22))):
            canvas.alpha_composite(art(fn), pos)
        area = (30, 48, w - 116, h - 60)
        draw_text(canvas, MID, fbody, area)
        return canvas, {'font': fbody, 'area': area,
                        'notes': ['和游戏里剧情框同款：横着长、竖着矮',
                                  '枫叶压在右端斜口上方，会盖掉一点框自己的花纹']}

    def D(canvas, box):
        """和纸卷轴：现有小窗同族那张（九切实测最大偏差 1px）+ 分隔线 + 双枫叶。"""
        w, h = box
        paper = nine_slice(art('gui_ui_common_bg_tips_3.png'), 16, w, h)
        canvas.paste(paper, (0, 0), paper)
        line = art('gui_ui_common_line_tips.png').resize((w - 96, 4), Image.LANCZOS)
        canvas.alpha_composite(line, (30, 44))
        for fn, pos in (('gui_ui_title_img_44_fengye1.png', (w - 46, 12)),
                        ('gui_ui_title_img_44_fengye2.png', (w - 26, 30))):
            canvas.alpha_composite(art(fn), pos)
        plate_name(canvas, '不知火', (30, 16), fname)
        area = (30, 56, w - 60, h - 74)
        draw_text(canvas, LONG, fbody, area)
        return canvas, {'font': fbody, 'area': area,
                        'notes': ['九切实测最大偏差 1px，这张拉伸最稳',
                                  '和番茄钟小窗同一张纸，风格统一；代价是没有气泡尾巴']}

    rows_out = []
    sheets = []
    for name, size, body, fn in (
            ('方案A 奶油气泡 + 松针金扇', (372, 196), MID, A),
            ('方案B 青海波气泡 + 家纹印', (330, 164), MID, B),
            ('方案C 戏台横幅（官方剧情框三切）', (470, 150), MID, C),
            ('方案D 和纸卷轴（现有小窗同族 + 枫叶）', (300, 232), LONG, D)):
        img, per, rows = panel(name, size, body, fn)
        sheets.append(img)
        rows_out.append((name, per, rows, per * rows))

    W = max(s.width for s in sheets)
    H = sum(s.height + 16 for s in sheets)
    out = Image.new('RGBA', (W, H), BG)
    y = 0
    for s in sheets:
        out.paste(s, (0, y), s)
        y += s.height + 16
    out.save(os.path.join(out_dir, 'dialog-mock.png'))
    print('->', os.path.join(out_dir, 'dialog-mock.png'))

    # 每档能装多少字、池子里有几条装得下 —— 这两个数是量出来的，不是手写进图注的
    if pool:
        print(f'\n台词池 {len(pool)} 条，最长 {pool[0][0]} 字，最短 {pool[-1][0]} 字')
    for name, per, rows, limit in rows_out:
        tail = f'｜池子里 {sum(1 for n, _ in pool if n <= limit)}/{len(pool)} 条放得下' if pool else ''
        print(f'{name:28s} 一行 {per} 字 x {rows} 行 = 上限 {limit} 字{tail}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
