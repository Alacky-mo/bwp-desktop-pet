"""装饰件试装表：把素材库里那些候选件，按番茄钟小窗真实放得下的位置贴到面板图上，一次看六种摆法。

底图用的是 panelshot 出的那张 shots-after/panel_w276_p0_idle.png —— 也就是 GDI+ 按现在代码画完的
成品（276x406，逐像素和窗口里那张同源），所以这里只加件、不改字，字的位置不会骗人。

坐标是从 FocusPresetForm.Arrange 的常量推出来的，不是目测：
  标题 26,12,186x44（「番茄钟」20px 只占 61px，右边 87~212 一整条是空的）
  三行选项 64..226 / 摘要行 234,24 / 开关行 266,54 / 主按钮 328,66 / 关闭键 220,12,44
件一律按素材原尺寸摆，缩过的在下面那行小字里写清楚。

用法: python deco_mock.py [面板图] [素材目录] [输出目录]
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
PANEL = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "shots-after", "panel_w276_p0_idle.png")
POOL = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "focus_ui")
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "shots-deco")

GAP, PAD = 18, 26
BG = (26, 24, 30, 255)


def tile(name):
    return Image.open(os.path.join(POOL, f"gui_ui_title_img_44_{name}.png")).convert("RGBA")


def common(name):
    return Image.open(os.path.join(POOL, f"gui_ui_common_{name}.png")).convert("RGBA")


def stamp(base, im, x, y, alpha=255, scale=None):
    """把件原尺寸（或指定缩放）摆到面板坐标上。alpha 只给「必须垫在字底下」那两类用，caption 里会写明是示意"""
    if scale:
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    if alpha < 255:
        a = im.split()[3].point(lambda v: v * alpha // 255)
        im = im.copy()
        im.putalpha(a)
    base.alpha_composite(im, (x, y))
    return im.size


def build():
    sheet = [
        ("现状：什么都不加", lambda p: None),
        ("标题右边挂金圆环", lambda p: ("金圆环 35x36 原尺寸",
                                       stamp(p, tile("yuanquan"), 96, 16))),
        ("标题右边压一条金纹横底", lambda p: ("标题金纹横底 204x45 → 缩到 0.58 倍(118x26)，摆在「番茄钟」右侧那条空档，不压字",
                                              stamp(p, tile("diban"), 92, 21, scale=0.58))),
        ("纸面对角点两枚枫叶", lambda p: ("枫叶·紫心金边 26x28 原尺寸，一枚压左上纸边、一枚落右下角空白",
                                          stamp(p, tile("fengye1"), 22, 6),
                                          stamp(p, tile("fengye1"), 240, 366))),
        ("摘要行两侧撒光点", lambda p: ("摘要句实占 183px、居中后左右各只剩约 20px 空，所以件只能贴着纸边放，再往里就盖字",
                                        stamp(p, tile("guangdian1"), 22, 238),
                                        stamp(p, tile("luoyeyou2"), 238, 243))),
        ("整张纸下垫圆形暗纹底", lambda p: ("圆形暗纹底 376x383，居中裁到面板大小，45% 透明 —— 真装的话它在字底下，这张只是示意深浅",
                                            stamp(p, common("bg_diwen").crop((0, 0, 276, 383)), 0, 12, alpha=115))),
    ]
    base = Image.open(PANEL).convert("RGBA")
    W, H = base.size
    cap = 150
    canvas = Image.new("RGBA", (PAD + (W + GAP) * len(sheet) + PAD, PAD + H + cap + PAD), BG)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("msyh.ttc", 17)
        small = ImageFont.truetype("msyh.ttc", 14)
    except OSError:
        font = small = ImageFont.load_default()

    def wrap(text, fnt, maxw):
        """按像素宽度断行 —— 说明比面板宽，不断行就会压到隔壁格"""
        lines, cur = [], ""
        for ch in text:
            if fnt.getlength(cur + ch) > maxw:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        if cur:
            lines.append(cur)
        return lines

    for i, (title, fn) in enumerate(sheet):
        art = base.copy()
        notes = fn(art)
        x = PAD + i * (W + GAP)
        canvas.paste(art, (x, PAD), art)
        draw.rectangle([x, PAD, x + W - 1, PAD + H - 1], outline=(90, 90, 110, 255))
        y = PAD + H + 10
        for line in wrap(title, font, W):
            draw.text((x, y), line, font=font, fill=(240, 236, 226, 255))
            y += 24
        y += 4
        for note in (n for n in (notes or ()) if isinstance(n, str)):
            for line in wrap(note, small, W):
                draw.text((x, y), line, font=small, fill=(150, 190, 150, 255))
                y += 19
    os.makedirs(OUT, exist_ok=True)
    a = os.path.join(OUT, "deco_mock.png")
    canvas.convert("RGB").save(a)
    b = os.path.join(OUT, "deco_mock_x2.png")
    canvas.resize((canvas.width * 2, canvas.height * 2), Image.LANCZOS).convert("RGB").save(b)
    print("试装表:", a, canvas.size)
    print("放大版:", b)


build()
