# 把倒计时浮窗和预设小窗要用的素材装进 DeskSpine/res/image/focus_ui/。
# 数字是仿+重染+配平出来的、框和面板是从库里裁出来的，两边都是版权衍生件，不进版本库，
# 所以「装机」这一步必须能一条命令重跑：python install_focus_ui.py
import os
import shutil
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
# warm/ 是「每个字各自裁到墨迹」那一版，读着 5 明显比别的胖一块；
# balanced/ 是去掉杂点、按宽高比配平、全部坐同一条基线的那一版 —— 装的是这版
DIGITS = os.path.join(HERE, "out", "focus_digits", "balanced")
CROPS = os.path.join(HERE, "out", "focus_ui")
DEST = os.path.join(HERE, "..", "deskspine", "DeskSpine", "res", "image", "focus_ui")

# 名字在这里统一：素材库里的长名（gui_ui_common_bg_kuang02.png）桌宠侧读着费劲。
# 尺寸、能不能拉伸、深底看不看得见，实测数都在 out/nine_patch/结果.tsv（中文名在 focus_ui_labels.tsv）
FILES = [(os.path.join(CROPS, f"gui_ui_common_{n}.png"), f"{n}.png") for n in
         ["bg_kuang02",                                        # 浮窗的框（28px 九宫格拉成横条）
          "bg_tips_3", "btn_select_on", "btn_select_off",     # 小窗的底 + 单选钮（off 是半透明的，配浅纸底才看得出）
          "com_btn_normal", "com_btn_press", "com_btn_close"  # 主按钮（两端斜切，不能拉，按原尺寸摆）+ 关闭钮
          ]] + [
        # 右下角那一小景的两枚叶子（名字照 focus_ui_labels.tsv），库里这几枚本来就是同一组标题装饰的零件。
        # 落选那几枚各差在哪：金坠子在游戏里是挂在标题金底下面的，金底这轮用不上（204 宽会把关闭键那头的
        # 箭头压住），让它单独悬在纸上就是又一排「裁了一半」；落叶·右飘6 整片淡金、铺在这张浅纸上对比不够，
        # 读着像纸屑；金色光点更甚，378 格里只有 37 格有值、平均 alpha 55，纸上基本看不见。
        (os.path.join(CROPS, f"gui_ui_title_img_44_{n}.png"), os.path.join("deco", f"{n}.png"))
        for n in ["fengye2", "fengye1"]] + [
        (os.path.join(DIGITS, f"{c}.png"), os.path.join("digits", f"{c}.png"))
        for c in list("0123456789") + ["colon"]]

# 和风纸面板左边 0~13 列是隔壁控件渗进图集格子的碎片（四角星、菱形、箭头、卷纹），
# 九宫格会把左边那条边带整条竖着拉满 406 高，所以碎片不清掉就是桌面上一排「裁了一半」。
#
# 但碎片不能按一条竖线抹：纸自己的左边线是**会漂的**，逐段量出来是
#   y=1~8 在 x=16（左上角那一横）、9~19 在 17、20~36 在 18、37~63 在 19、
#   64~173 在 20、174~193 又退回 18~19，195 往后是左下角那截卷角。
# 之前那版一刀抹掉 x<20，等于把上小半条线整个抹没、中段抹成 1 格 —— 桌面看就是左边框忽粗忽细。
# 现在改成逐行找到那条线，只抹线以外（碎片和它的半透明毛边），线本身连抗锯齿边一起留住。
# 只处理到 y<195：碎片那一排最远到 y=189 就没了，y=195 起是左下角那截卷角自己的墨（一路连到 y=224），
# 抹它等于把卷角的头削掉；那两截都落在九宫格左下角那一块，卷角本体（y>=199）根本不会被拉。
TRIM = {"bg_tips_3": (195, 15, 27)}     # 图名 -> (只处理 y 小于几, 找线从第几列起扫, 扫到第几列)
                                        # 起扫列卡在 15：碎片最远伸到 x=13，线最近只到 x=16，中间那一格是空档


def trim_left(path, below, scan_from, scan_to):
    """逐行贴着那条会漂的左边线，把线外的像素抹成透明；返回图片尺寸好打印"""
    with Image.open(path) as src:
        im = src.convert("RGBA")

    def dark(x, y):
        r, g, b, a = im.getpixel((x, y))
        return a >= 120 and (r + g + b) / 3 < 200

    rows = min(below, im.height)
    line = [next((x for x in range(scan_from, min(scan_to, im.width)) if dark(x, y)), None)
            for y in range(rows)]
    # 有几行线自己就断了（卷角那一截并进来、或抗锯齿掉到阈值以下），拿最近一行的位置顶上，
    # 别拿 scan_from 当兜底 —— 那等于把线又抹一次
    last = next((v for v in line if v is not None), scan_from)
    for y in range(rows):
        if line[y] is None:
            line[y] = last
        else:
            last = line[y]
    for y in range(rows):
        for x in range(max(0, line[y] - 2)):    # 往左多留 2 格，把墨线的抗锯齿边留住
            if im.getpixel((x, y))[3]:
                im.putpixel((x, y), (0, 0, 0, 0))
    im.save(path)
    return im.width, im.height


def main():
    missing = [s for s, _ in FILES if not os.path.exists(s)]
    if missing:
        print("衍生图不进版本库，本机没跑过管线就是空的。先补这两步再重跑装机:")
        if any(m.startswith(DIGITS) for m in missing):
            print(f"  cd {os.path.join(HERE, 'out', 'focus_digits')} && python make_fake.py 0 9 && python make_set.py && python make_balanced.py")
        if any(m.startswith(CROPS) for m in missing):
            print("  python gui_page_map.py npk/gui.npk out/gui_scan_all.tsv out/gui_atlas.json out/focus_ui <资源前缀>"
                  "  (裁哪 53 张见 focus_ui_labels.tsv, 细节看 gui_page_map.py 开头的用法)")
        for m in missing:
            print(f"  缺 {m}")
        return 1

    for src, name in FILES:
        dst = os.path.join(DEST, name)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        if os.path.splitext(name)[0] in TRIM:
            trim_left(dst, *TRIM[os.path.splitext(name)[0]])
        im = Image.open(dst)
        print(f"  {name:<20} {im.width}x{im.height}  <- {os.path.relpath(src, HERE)}")
    print(f"装到 {os.path.normpath(DEST)}")
    print("csproj 已经带 res\\image\\focus_ui\\** 进输出目录, 改完素材重跑这个脚本就行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
