"""台词气泡改版出图：边框加粗（烫金）+ 名牌配色（大红底 + 烫金字）+ 镜像那一侧长什么样。

这是 PIL 合成的预览，**不是桌宠真窗口**（真窗口的字是 GDI+ 画的）。
用途只有一个：装机之前先让用户点头「金线几 px、名牌要不要红底」，别把改动画进产品再返工。
色值不是随手挑的，是从库里采的：
  金 = 分隔线 gui_ui_common_line_tips.png 的 (254,236,174) 和名牌条 biaoqian_01 的 (197,146,28)，两头拉成渐变
  红 = 达摩那支红（focus_damo.ico 均色 200,100,94）往下压深，太粉压不住金字

用法: python bubble_style_mock.py [out目录]
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, ".."))
# 染金和量金线用的是装机同一份实现（dialog_mock.py），预览和产品就不会各画各的
from dialog_mock import GOLD_DEEP, GOLD_LIGHT, GOLD_MID, gilded, lerp, solid_distance

RES = os.path.join(ROOT, "..", "..", "deskspine", "DeskSpine", "res", "image", "dialog")
FONT = r"C:\Windows\Fonts\msyh.ttc"
BG = (150, 152, 158, 255)

GOLD_TEXT_TOP = (255, 244, 196)
GOLD_TEXT_BOT = (206, 150, 32)
RED_TOP = (198, 48, 44)
RED_BOT = (146, 24, 30)
OUTLINE = (120, 74, 12)
INK = (58, 44, 40, 255)

# 和产品同一套版面常量（DialogBubbleForm.cs），改这里就等于改预览
CANVAS = (379, 188)
BUBBLE_AT = (13, 18)
CREST_AT = (5, 5)
NAME_AT = (62, 16)
TEXT_AREA = (62, 55, 280, 110)
BODY_PX = 19
LINE_ADVANCE = 27


def vgrad(w, h, top, bot):
    g = Image.new("RGBA", (max(1, w), max(1, h)))
    p = g.load()
    for y in range(g.height):
        col = lerp(top, bot, y / max(1, g.height - 1))
        for x in range(g.width):
            p[x, y] = col + (255,)
    return g


def gold_text(canvas, text, pos, font):
    """烫金字：先描一圈深金当边，再把「上亮下深」的金渐变按字的形状压上去"""
    dr = ImageDraw.Draw(canvas)
    box = dr.textbbox(pos, text, font=font)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        dr.text((pos[0] + dx, pos[1] + dy), text, font=font, fill=OUTLINE + (255,))
    mask = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
    ImageDraw.Draw(mask).text((-box[0], -box[1]), text, font=font, fill=255)
    canvas.paste(vgrad(mask.width, mask.height, GOLD_TEXT_TOP, GOLD_TEXT_BOT), (box[0], box[1]), mask)


def name_plate(canvas, text, font, style, mirror=False):
    """none=原来的深墨字 / red=大红底 + 烫金字 / gold=只有烫金字
    mirror 只挪件和形状，**字永远正排**（整张翻会把汉字翻反，那是预览里的错，不是产品行为）"""
    dr = ImageDraw.Draw(canvas)
    name_at = mirror_pos(NAME_AT, 0) if mirror else NAME_AT
    box = dr.textbbox(name_at, text, font=font)
    if style == "none":
        dr.text(name_at, text, font=font, fill=INK)
        return
    if style == "red":
        pad_x, pad_y, tip = 11, 5, 12
        if mirror:
            x0, x1 = box[0] - pad_x - tip, box[2] + pad_x - tip
            pts = [(x1, box[1] - pad_y), (x0 + tip, box[1] - pad_y), (x0, (box[1] + box[3]) // 2),
                   (x0 + tip, box[3] + pad_y), (x1, box[3] + pad_y)]
        else:
            x0, x1 = box[0] - pad_x, box[2] + pad_x
            pts = [(x0, box[1] - pad_y), (x1 - tip, box[1] - pad_y), (x1, (box[1] + box[3]) // 2),
                   (x1 - tip, box[3] + pad_y), (x0, box[3] + pad_y)]
        px0, py0, px1, py1 = min(p[0] for p in pts), min(p[1] for p in pts), \
            max(p[0] for p in pts), max(p[1] for p in pts)
        mask = Image.new("L", (px1 - px0, py1 - py0), 0)
        ImageDraw.Draw(mask).polygon([(a - px0, b - py0) for a, b in pts], fill=255)
        canvas.paste(vgrad(mask.width, mask.height, RED_TOP, RED_BOT), (px0, py0), mask)
        ImageDraw.Draw(canvas).polygon(pts, outline=GOLD_LIGHT + (255,))
    gold_text(canvas, text, name_at, font)


def mirror_pos(pt, w):
    """画布内一个左上点水平镜像后的左上点（宽 w 的那件/那块区）"""
    return (CANVAS[0] - pt[0] - w, pt[1])


def compose(bubble, style, body, font, mirror=False):
    c = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    art = bubble.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if mirror else bubble
    c.alpha_composite(art, mirror_pos(BUBBLE_AT, bubble.width) if mirror else BUBBLE_AT)
    crest = Image.open(os.path.join(RES, "crest.png")).convert("RGBA")
    c.alpha_composite(crest, mirror_pos(CREST_AT, crest.width) if mirror else CREST_AT)
    name_plate(c, "不知火", font, style, mirror)
    dr = ImageDraw.Draw(c)
    x, y, w, h = TEXT_AREA
    if mirror:
        x = CANVAS[0] - x - w
    lines, cur = [], ""
    for ch in body:
        if dr.textlength(cur + ch, font=font) <= w:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    for ln in lines[: h // LINE_ADVANCE]:
        dr.text((x, y), ln, font=font, fill=INK)
        y += LINE_ADVANCE
    return c


def sheet(title, canvas, note):
    img = Image.new("RGBA", (CANVAS[0] + 260, CANVAS[1] + 58), BG)
    dr = ImageDraw.Draw(img)
    dr.text((16, 8), title, font=ImageFont.truetype(FONT, 20), fill=(20, 20, 26, 255))
    x, y = 16, 40
    img.alpha_composite(canvas, (x, y))
    dr.rectangle((x, y, x + CANVAS[0] - 1, y + CANVAS[1] - 1), outline=(90, 92, 100, 255))
    dr.text((x + CANVAS[0] + 12, y + 8), note, font=ImageFont.truetype(FONT, 16),
            fill=(255, 240, 190, 255))
    return img


def place_sheet(title, canvas_art, ink, pet_right, head_y, gap, note):
    """摆位示意：宠物框画在左边，气泡按「画布贴」和「墨贴」两种摆法各画一次，量出来的间距写在图上"""
    img = Image.new("RGBA", (700, 430), BG)
    dr = ImageDraw.Draw(img)
    dr.text((14, 8), title, font=ImageFont.truetype(FONT, 20), fill=(20, 20, 26, 255))
    pet = (60, 120, 60 + 120, 380)
    dr.rectangle(pet, fill=(96, 98, 106, 255), outline=(40, 40, 46, 255), width=2)
    dr.text((pet[0] + 8, pet[1] + 6), "宠物框", font=ImageFont.truetype(FONT, 15), fill=(232, 232, 238, 255))
    dr.ellipse((pet_right - 5, head_y - 5, pet_right + 5, head_y + 5), fill=(250, 210, 120, 255))
    x = pet_right + gap - ink[0]          # 画布左边 = 让墨左沿落到 pet_right+gap
    y = head_y + 6 - ink[3]               # 墨下沿压过头顶一点（产品里 HeadDrop 干的事）
    img.alpha_composite(canvas_art, (x, y))
    dr = ImageDraw.Draw(img)
    dr.line((pet_right, head_y - 46, x + ink[0] - 1, head_y - 46), fill=(250, 210, 120, 255), width=2)
    dr.text((pet[0] + 8, head_y + 16), f"墨到宠物 {gap} px", font=ImageFont.truetype(FONT, 16),
            fill=(250, 210, 120, 255))
    dr.text((14, 396), note, font=ImageFont.truetype(FONT, 16), fill=(255, 240, 190, 255))
    return img


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    base = Image.open(os.path.join(RES, "bubble.png")).convert("RGBA")
    font = ImageFont.truetype(FONT, BODY_PX)      # 和产品同一号：名字和正文都是 BodyPx
    body = "『』" + "火" * 26 + "、" + "舞" * 24 + "。"
    d, solid = solid_distance(base)
    xs = [x for y in range(base.height) for x in range(base.width) if solid[y][x]]
    ys = [y for y in range(base.height) for x in range(base.width) if solid[y][x]]
    print(f"装机图 {base.size}，实体墨框 x {min(xs)}~{max(xs)} y {min(ys)}~{max(ys)}"
          f" → 画布左边到墨还有 {BUBBLE_AT[0] + min(xs)} px（这就是「离宠物远」的一大半）")
    ink = (BUBBLE_AT[0] + min(xs), BUBBLE_AT[1] + min(ys),
           BUBBLE_AT[0] + max(xs), BUBBLE_AT[1] + max(ys))
    art_for_place = compose(gilded(base, 3), "red", body, font)
    old_gap = ink[0] + 10
    place = Image.new("RGBA", (700, 880), BG)
    a = place_sheet("摆位 A：现状（画布贴 + SideGap=10）", art_for_place, ink, 180, 170, old_gap,
                    f"墨离宠物实测 {old_gap} px —— 画布那 {ink[0]} px 透明边白给了")
    b = place_sheet("摆位 B：改成按墨贴 + 间距 4", art_for_place, ink, 180, 170, 4,
                    "气泡整张往宠物挪，尾巴那侧不留空白")
    place.paste(a, (0, 0))
    place.paste(b, (0, a.height + 10))
    pp = os.path.join(out_dir, "bubble-place-mock.png")
    place.save(pp)
    print("->", pp)

    gilded3 = gilded(base, 3)
    sheets = [
        sheet("① 现状：边框 1px 金线 + 深墨名牌", compose(base, "none", body, font), "基线"),
        sheet("② 边框 3px 烫金 + 大红底金字", compose(gilded3, "red", body, font),
              "红条右端收成尖，和库里 biaoqian 名牌条同形"),
        sheet("③ 边框 5px 烫金 + 大红底金字", compose(gilded(base, 5), "red", body, font),
              "更粗一档，看压不压纸面"),
        sheet("④ 边框 3px + 无红底，只烫金", compose(gilded3, "gold", body, font),
              "最克制的一档"),
        sheet("⑤ ②摆到宠物左边：件镜像、字照旧正排", compose(gilded3, "red", body, font, mirror=True),
              "尾巴、红条、金线一起翻；字翻反是预览才有的错法"),
    ]
    out = Image.new("RGBA", (max(s.width for s in sheets), sum(s.height + 12 for s in sheets)), BG)
    y = 0
    for s in sheets:
        out.paste(s, (0, y))
        y += s.height + 12
    p = os.path.join(out_dir, "bubble-style-mock.png")
    out.save(p)
    print("->", p)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shots-dialog"))
