# 量真数字的上色: 中心填色 / 描边色 / 外圈光晕色, 以及笔画最宽处有多粗。
# 目的是让仿的 0 和 9 用同一套色阶, 而不是我凭眼睛调。
import glob
import os
from collections import Counter

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    for p in sorted(glob.glob(os.path.join(HERE, "gui_ui_autochess_img_num_*.png"))):
        im = Image.open(p).convert("RGBA")
        px = im.load()
        a = im.split()[3].load()
        bands = Counter()
        exact = Counter()
        for y in range(im.height):
            for x in range(im.width):
                al = a[x, y]
                if al < 24:
                    continue
                r, g, b = px[x, y][:3]
                key = "实心(a>=200)" if al >= 200 else "半透(a<200)"
                bands[(key, r // 16 * 16, g // 16 * 16, b // 16 * 16)] += 1
                if al >= 200:
                    exact[(r, g, b)] += 1
        solid = [(k, v) for k, v in bands.items() if k[0].startswith("实心")]
        edge = [(k, v) for k, v in bands.items() if k[0].startswith("半透")]
        solid.sort(key=lambda kv: -kv[1])
        edge.sort(key=lambda kv: -kv[1])
        ex = [f"#{r:02x}{g:02x}{b:02x}x{n}" for (r, g, b), n in exact.most_common(4)]
        # 笔画粗细: 逐行收集「完整」的连续不透明段(横向切一笔画出来的宽度)。
        # ⚠ 这个量**不能拿来定仿字的成败**: 0 是环, 一刀切两条边, 和实心的 8 量出来一样粗, 画出来却是空心铁丝。
        #    仿字用的尺在 make_fake.heft()(墨/墨高)。这里只当「毛笔提按有多大」的参考。
        widths = []
        for y in range(im.height):
            run = 0
            for x in range(im.width):
                if a[x, y] >= 200:
                    run += 1
                else:
                    if run:
                        widths.append(run)
                    run = 0
            if run:
                widths.append(run)
        widths.sort()
        med = widths[len(widths) // 2] if widths else 0
        p90 = widths[int(len(widths) * 0.9)] if widths else 0
        print(os.path.basename(p), im.size,
              "| 实心精确主色", ex,
              "| 实心主色", [f"#{c:02x}{d:02x}{e:02x}x{n}" for (_, c, d, e), n in solid[:3]],
              "| 半透主色", [f"#{c:02x}{d:02x}{e:02x}x{n}" for (_, c, d, e), n in edge[:3]],
              "| 段宽 中位/P90/最大", med, p90, max(widths) if widths else 0)


if __name__ == "__main__":
    main()
