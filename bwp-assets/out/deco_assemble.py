"""把「右侧那一列飘落叶」这套装饰件按真坐标贴到真面板图上，先看构图再动产品代码。

底图是 panelshot 反射真画法合成出来的 panel_w276_p0_idle.png（276x406），
坐标就是将来 Compose 里要用的坐标，所以这张对得上，产品侧才对得上。
用法: python deco_assemble.py
"""
import io
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.join(HERE, "shots-border", "panel_w276_p0_idle.png")
POOL = os.path.join(HERE, "focus_ui")
OUT = os.path.join(HERE, "shots-deco")
PRE = "gui_ui_title_img_44_"

# 定稿那一族：右下角摆一小景（金坠子 → 枫叶 → 光点），不在左侧那一路散开
# （V1 那种「右侧一路飘下来」在真面板上读起来像纸上有脏东西，V3 顶部单片像杂点，都排掉了）
BITS = [
    ("zhenzi1", (246, 296)),      # 金坠子
    ("fengye1", (240, 332)),      # 枫叶·紫心金边
    ("guangdian1", (244, 364)),   # 金色光点(几乎空)
]

# 打靶框（照 FocusPresetForm.Arrange 在 276 宽下算出来的那几块），用来验装饰件不压控件
SPOTS = {
    "Title": (26, 12, 186, 44), "Close": (220, 12, 44, 44),
    "Row0": (65, 64, 166, 54), "Row1": (65, 118, 166, 54), "Row2": (65, 172, 166, 54),
    "Summary": (26, 234, 224, 24), "Switch": (65, 266, 166, 54), "Start": (73, 328, 150, 66),
}


def overlap(a, b):
    return not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or
                a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1])


def main():
    with Image.open(BASE) as src:
        panel = src.convert("RGBA")
    report = io.StringIO()
    placed = []
    for stem, (x, y) in BITS:
        with Image.open(os.path.join(POOL, PRE + stem + ".png")) as bit:
            im = bit.convert("RGBA")
        box = (x, y, im.width, im.height)
        placed.append((stem, box))
        hits = [n for n, r in SPOTS.items() if overlap(box, r)]
        off = not (21 <= x and x + im.width <= 272 and 0 <= y and y + im.height <= panel.height)
        report.write(f"{stem:14} {im.width}x{im.height} @({x},{y}) "
                     f"压到={hits or '无'} 出纸界={'是' if off else '否'}\n")
        panel.alpha_composite(im, (x, y))

    os.makedirs(OUT, exist_ok=True)
    panel.save(os.path.join(OUT, "assemble.png"))
    panel.resize((panel.width * 3, panel.height * 3), Image.NEAREST).save(
        os.path.join(OUT, "assemble_x3.png"))

    # 旁边再摆一张把打靶框画出来的，肉眼好核对「没盖住能点的地方」
    guide = panel.copy()
    d = ImageDraw.Draw(guide)
    for n, (x, y, w, h) in SPOTS.items():
        d.rectangle([x, y, x + w - 1, y + h - 1], outline=(200, 60, 60, 200), width=1)
    guide.resize((guide.width * 3, guide.height * 3), Image.NEAREST).save(
        os.path.join(OUT, "assemble_guide_x3.png"))

    with io.open(os.path.join(OUT, "assemble-report.txt"), "w", encoding="utf-8") as f:
        f.write(report.getvalue())
    print(report.getvalue())
    print("→", os.path.join(OUT, "assemble_x3.png"))


if __name__ == "__main__":
    main()
