# -*- coding: utf-8 -*-
# 修正版字体候选表。和上一轮的差别只有一条：这一张每张卡片都由那一款字体**自己**画。
# PIL 缺字直接画豆腐块、不会像 GDI+ 那样悄悄借宋体代笔，所以「这一格是不是它自己出的字」
# 在这张表里是结构性保证，不用再靠人去猜。
import io, os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots-fonts")
os.makedirs(OUT, exist_ok=True)
# 底子用**装机那张**（左边邻格碎片已经逐行贴线抹过），不是素材池里的原图 —— 不然表上会多出一排桌面根本看不见的碎片
TILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "deskspine", "out", "x64", "Release", "net8.0-windows", "win-x64",
                    "res", "image", "focus_ui", "bg_tips_3.png")
INK = (43, 43, 43)
PAPER_X, PAPER_W = 26, 224          # 纸面内容区（左边线在 x=20，右边线 x=272）
TITLE_Y, SUM_Y = 12, 234            # 和 FocusPresetForm 的 Arrange 同一套坐标

# 中文名取自那张字体自己声明的 name 表，不是我这边的翻译
CAND = [
    ("宋体 ← 上一轮表里「素晴字体」那一格真实的样子", r"C:\Windows\Fonts\simsun.ttc", 0, "番茄钟", 20, True),
    ("华文中宋", r"C:\Windows\Fonts\STZHONGS.TTF", 0, "番茄钟", 20, True),
    ("楷体", r"C:\Windows\Fonts\simkai.ttf", 0, "番茄钟", 20, True),
    ("华文行楷", r"C:\Windows\Fonts\STXINGKA.TTF", 0, "番茄钟", 20, True),
    ("方正舒体", r"C:\Windows\Fonts\FZSTK.TTF", 0, "番茄钟", 20, True),
    ("华文新魏", r"C:\Windows\Fonts\STXINWEI.TTF", 0, "番茄钟", 20, True),
    ("思源宋体", r"C:\Windows\Fonts\NotoSerifSC-VF.ttf", 0, "番茄钟", 20, True),
    ("黑体", r"C:\Windows\Fonts\simhei.ttf", 0, "番茄钟", 20, False),
    ("微软雅黑（现状）", r"C:\Windows\Fonts\msyh.ttc", 0, "番茄钟", 20, True),
    ("素晴字体（本机 font.ttf）", os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Fonts\font.ttf"),
     0, "番茄钟", 20, True),
]
SMALL = [
    ("微软雅黑 15 常规 ← 现状", r"C:\Windows\Fonts\msyh.ttc", 0, 15, 0),
    ("微软雅黑 17 加粗", r"C:\Windows\Fonts\msyhbd.ttc", 0, 17, 0),
    ("等线 17 加粗", r"C:\Windows\Fonts\Dengb.ttf", 0, 17, 0),
    ("黑体 17 常规", r"C:\Windows\Fonts\simhei.ttf", 0, 17, 0),
    ("思源黑体 17 常规", r"C:\Windows\Fonts\NotoSansSC-VF.ttf", 0, 17, 0),
    ("微软雅黑 17 常规", r"C:\Windows\Fonts\msyh.ttc", 0, 17, 0),
]
SENT = "短休 5 · 长假 15 · 连做 4 段"
FALLBACK = "现在这几分钟没对上任何一档"

def load(path, size):
    f = ImageFont.truetype(path, size)
    return f

def faux_bold(draw, xy, text, font, fill, bold):
    # 统一用描边加粗，这样各款之间比的是同一套「加粗量」，不是各家自带的 Bold
    draw.text(xy, text, font=font, fill=fill,
              stroke_width=1 if bold else 0, stroke_fill=fill)

def card(label, tile, hi=118):
    c = tile.crop((0, 0, PAPER_W + 40, hi)).copy()
    return label, c

def panelize(tile, height):
    # 桌面上那张纸是九宫格拉出来的（FocusArt.PanelInset=33），素材本身只有 232 高。
    # 直接按面板坐标去裁原图会裁到纸外面，所以这里先按同样的切法把它拉成 406 高。
    inset = 33
    top, mid, bot = tile.crop((0, 0, tile.width, inset)), \
        tile.crop((0, inset, tile.width, tile.height - inset)), \
        tile.crop((0, tile.height - inset, tile.width, tile.height))
    out = Image.new("RGBA", (tile.width, height), (0, 0, 0, 0))
    out.paste(top, (0, 0))
    out.paste(mid.resize((tile.width, height - inset * 2), Image.BILINEAR), (0, inset))
    out.paste(bot, (0, height - inset))
    return out


base = panelize(Image.open(TILE).convert("RGBA"), 406)
CW, GAPY = 300, 10
lab_w = 320
rows_t = []
for label, path, idx, text, size, bold in CAND:
    t = base.copy()
    g = ImageDraw.Draw(t)
    try:
        f = ImageFont.truetype(path, size, index=idx)
        faux_bold(g, (PAPER_X, TITLE_Y + 6), text, f, INK, bold)
    except Exception as e:
        g.text((PAPER_X, TITLE_Y + 6), "装不上: %s" % e, fill=INK)
    rows_t.append((label, t.crop((0, 0, 276, 64))))
rows_s = []
for label, path, idx, size, _ in SMALL:
    t = base.copy()
    g = ImageDraw.Draw(t)
    f = ImageFont.truetype(path, size, index=idx)
    # 这一列比的是「哪张文件自带的那个重量」，所以一律不额外描边：msyhbd/Dengb 本身就是真 Bold 面
    faux_bold(g, (PAPER_X, SUM_Y), SENT, f, INK, False)
    w = g.textlength(SENT, font=f)
    rows_s.append((f"{label}  实测 {int(round(w))}/224 px", t.crop((0, 224, 276, 268))))

def sheet(rows, name, lab_w=340, scale=2):
    h = sum(max(c.height for _, c in rows) + GAPY for _ in rows)
    out = Image.new("RGBA", (lab_w + 276, h), (26, 24, 30, 255))
    g = ImageDraw.Draw(out)
    lf = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 15)
    y = 0
    for label, c in rows:
        g.text((8, y + c.height // 2 - 8), label, font=lf, fill=(235, 235, 235))
        out.paste(c, (lab_w, y), c)
        y += c.height + GAPY
    out = out.convert("RGB").resize((out.width * scale, out.height * scale), Image.NEAREST)
    out.save(os.path.join(OUT, name))
    print(name, out.size)

sheet(rows_t, "title_family.png")
sheet(rows_s, "small_size.png")
io.open(os.path.join(OUT, "sheet-note.txt"), "w", encoding="utf-8").write(
    "PIL 直接渲染，缺字画豆腐块（GDI+ 才会借笔）。宽度是 PIL 量的，装机前还要用 GDI+ 复核。\n")
