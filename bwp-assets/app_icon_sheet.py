"""不知火应用图标候选联系表 —— 给用户挑「应用图标换成不知火」那一张用。

为什么长这样：应用图标最终落在托盘那一格是 16 px，而素材库里那些 512 的半身像在这一档
会糊成一团 —— 只看大图挑 = 装上桌面后悔。所以每颗候选排一条横带：
112 / 48 / 32 / 16 贴深底 / 16 贴浅底 / 16 放大 4 倍看（最近邻，**和前一格是同一批像素**，
只是把每个像素画成 4×4，方便肉眼判「托盘里认不认得出」，不是又缩了一次）。
Win11 托盘默认深色，浅色主题另一样，所以 16 那两格分别贴两种底色。

每颗候选底下那行「16 px 墨占 …」是**量出来的**：把图缩到 16×16 后数 alpha>0 的格数、
和这些墨撑开的 a×b 格。数字只说明占了多少格，不等于认得出是谁 —— 认不认得还得看那两格。

用法：python app_icon_sheet.py            出 out/icon_candidates/sheet_app_icon.png
产物不进仓库（.gitignore 的 /bwp-assets/out/** 挡着）；挑中之后的 ico 用 png_to_ico.py 转。

标签纪律（用户定的）：角色一律中文名；表情那五张是骨架自带的**英文动画键名**，仓库里没有
核实过的官方中文叫法，所以标签只写「图上看得见什么」，不替它编中文名。
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)
OUT = os.path.join(ROOT, "out", "icon_candidates")
THUMB = os.path.join(ROOT, "out", "emo_thumbs")
RES = os.path.join(REPO, "deskspine", "DeskSpine", "res", "image")

BIG = 112
SMALL = [48, 32, 16, 16, 64]      # 16 深底 / 16 浅底 / 64 那一格是 16 放大 4 倍（同一批像素）
PAD = 14
STEP = BIG + 10
CARD_W = 2 * PAD + STEP * len(SMALL) + BIG
CARD_H = BIG + 112
COLS_N = 2
GUT = 14
HEAD = 56

# (中文名, 图上看得见的那一句, 来源, 裁法)
#   裁法 "full" = 墨框补成正方；"head" = 从墨框取一个正方（短边那一维不变，长边那一维切掉），
#                 切掉的是身子还是两侧由墨框的长短边决定，标签里按实测写清楚
CANDS = [
    ("不知火 · 立绘 睁眼平静", "白发双髻、头顶两根红缎带竖成角、两鬓一簇火苗、额间一枚红印、琥珀色眼", f"{THUMB}/buzhihuo_1127@idle.png", "full"),
    ("不知火 · 立绘 闭眼笑", "同一张，眼睛闭成两条弯月", f"{THUMB}/buzhihuo_1127@happy.png", "full"),
    ("不知火 · 立绘 闭眼难受", "同一张，闭眼、嘴张开一点", f"{THUMB}/buzhihuo_1127@sad.png", "full"),
    ("不知火 · 立绘 睁眼+惊叹号", "同一张，头右边多一个红色感叹号", f"{THUMB}/buzhihuo_1127@surprise.png", "full"),
    ("不知火 · 立绘 闭眼歪头", "同一张，闭眼、头往右偏", f"{THUMB}/buzhihuo_1127@thinking.png", "full"),
    ("不知火 · 立绘 切掉身子（第一张）", "墨框 228×259，取顶上 228 见方 —— 两根红角横向仍占满，切掉的只有领口那一段", f"{THUMB}/buzhihuo_1127@idle.png", "head"),
    ("不知火 · 另一套立绘 灰发那组", "灰绿长发、红瞳、额上一枚红印加眼下几点红、鬓边一朵浅色花带两条燕尾飘带、画面右下一根深色扇骨", f"{THUMB}/buzhihuo_yihua_2717@idle.png", "full"),
    ("不知火 · 另一套立绘 切掉两侧", "墨框 351×260，取中间 260 见方 —— 竖着没切、切的是左右：左边那两条飘带和右边那根扇骨都被切掉，花还留着", f"{THUMB}/buzhihuo_yihua_2717@idle.png", "head"),
    ("buzhihuo 目录 3604 那张小身（是不是她没核实）", "黑发、蓝和服红领、闭眼、一只手伸向前，头顶两枚小红角；墨只有 80×108", f"{THUMB}/buzhihuo_pifu_3604@idle.png", "full"),
    ("家纹印（台词气泡左上那枚）", "暗紫圆地上一朵金色五瓣纹 —— 本来就是给小尺寸画的", f"{RES}/dialog/crest.png", "full"),
    ("现用应用图标（上游那枚剪影）", "黑剪影：一只带刀的狐 —— 要换掉的对象，对照", f"{REPO}/deskspine/DeskSpine/appicon_dark.ico", "full"),
    ("番茄钟那颗达摩", "红达摩 + 烫金脸 —— 马上兼作整点报时那颗，对照", f"{RES}/focus_damo.ico", "full"),
]


def load(path, mode):
    """按墨裁边 → 补成正方（和 png_to_ico 那把尺同一个走法，缩下去才不会歪）"""
    im = Image.open(path).convert("RGBA")
    bb = im.getbbox()
    if bb:
        im = im.crop(bb)
    if mode == "head" and min(im.size) >= 8:
        s = min(im.size)
        x = (im.width - s) // 2
        y = 0 if im.height >= s else (im.height - s) // 2
        im = im.crop((x, y, x + s, y + s))
    side = max(im.size)
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
    return sq


def read16(src):
    """缩到 16×16 数墨：占几格 + 这些墨撑开 a×b 格。只报读数，不替用户判认不认得出"""
    tiny = src.resize((16, 16), Image.LANCZOS)
    pts = [(x, y) for y in range(16) for x in range(16) if tiny.getpixel((x, y))[3] > 0]
    if not pts:
        return "16 px 全空"
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return f"16 px 墨占 {len(pts)}/256 格, 撑开 {max(xs) - min(xs) + 1}×{max(ys) - min(ys) + 1}"


def main():
    os.makedirs(OUT, exist_ok=True)
    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 16)
    tiny = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 12)
    small = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 13)

    rows = (len(CANDS) + COLS_N - 1) // COLS_N
    sheet = Image.new("RGBA", (COLS_N * CARD_W + GUT, rows * CARD_H + HEAD), (24, 24, 28, 255))
    d = ImageDraw.Draw(sheet)
    d.text((GUT, 10), "不知火应用图标候选 —— 每颗一条横带：112 / 48 / 32 / 16 贴深底 / 16 贴浅底 / 16 放大 4 倍看（最后那格和 16 那两格是同一批像素）",
           font=small, fill=(255, 228, 132))
    d.text((GUT, 30), "挑哪一颗就回我那行的中文名。托盘里真看到的是 16 px 那一档 —— 看「16 放大 4 倍」那格，认不出是她就别选。",
           font=tiny, fill=(170, 170, 180))

    for i, (name, note, path, mode) in enumerate(CANDS):
        cx = (i % COLS_N) * CARD_W
        cy = HEAD + (i // COLS_N) * CARD_H
        d.rectangle([cx + 4, cy + 4, cx + CARD_W - 6, cy + CARD_H - 8], outline=(52, 52, 62))
        d.text((cx + PAD, cy + 12), f"{i + 1:02d}  {name}", font=font, fill=(255, 228, 132))
        d.text((cx + PAD, cy + 34), note, font=tiny, fill=(200, 200, 200))
        d.text((cx + PAD, cy + 50), os.path.basename(path), font=tiny, fill=(140, 140, 150))

        if not os.path.exists(path):
            d.text((cx + PAD, cy + 80), "图不在", font=font, fill=(255, 120, 120))
            continue
        src = load(path, mode)
        d.text((cx + PAD, cy + CARD_H - 24), read16(src), font=tiny, fill=(150, 190, 150))
        x = cx + PAD
        top = cy + 72
        for j, s in enumerate([BIG] + SMALL):
            if s == 64:
                img = src.resize((16, 16), Image.LANCZOS).resize((64, 64), Image.NEAREST)
            else:
                img = src.resize((s, s), Image.LANCZOS)
            bx, by = x + (BIG - s) // 2, top + (BIG - s) // 2
            if j == 3:
                d.rectangle([bx - 5, by - 5, bx + s + 4, by + s + 4], fill=(48, 48, 54, 255))
            elif j == 4:
                d.rectangle([bx - 5, by - 5, bx + s + 4, by + s + 4], fill=(238, 238, 240, 255))
            sheet.alpha_composite(img, (bx, by))
            d.text((x + (BIG - s) // 2, top + BIG + 4), "16×4" if s == 64 else str(s), font=tiny, fill=(150, 150, 160))
            x += STEP

    out = os.path.join(OUT, "sheet_app_icon.png")
    sheet.save(out)
    print(f"候选表: {out}  {sheet.size[0]}x{sheet.size[1]}  {len(CANDS)} 颗候选")


if __name__ == "__main__":
    sys.exit(main())
