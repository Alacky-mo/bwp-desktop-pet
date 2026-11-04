"""九宫格拉伸试验：库里的框只有 22~32 px，拉成面板那么大到底会成什么样。

数字判据用**圆角起点**，不用「边框厚度」—— 现场量下来这批东西**大多是实心板子不是空框**
（bg_tips_3、img_bubble_02 一刀切下去整行都是实的，量出 250 px 那种数不是边框，是板宽），
所以「第一道实心段多宽」对它们没有意义。起拱 = 最顶上那颗实心像素离左边多远
（和最左边那颗离顶上多远取大）：整图缩放会把它按倍数放大（22 px 的角拉到 280 宽，实测从 4 px 涨到 54 px，
圆角变成一颗蛋），九宫格该原样保住（这个数不涨）—— 这个数对实心板和空框都成立，且只要求「拉完前后不涨」，不要求量出真半径。
再配一个**平坦率**：剥掉一圈之后内部有多少比例是几乎单色。平坦率高才敢拉中间，
低的（满幅底纹那种）拉了就是抹，只能原尺寸用或者平铺。
还有第三把尺 **要保的边带**（edge_inset）：圆角起点只看得见弧，看不见「边上那道亮边/花纹有多宽」——
方角的 bg_kuang03 起点量出 0，可它有一圈半透明亮边，inset 比亮边小的话边会被拉进板子里抹平。
inset 取「圆角起点」和「要保的边带」里大的那个，两个都不许漏。

**每档尺寸都会出数，形状不合也出**：先前把「形状不贴边」的图直接跳过不给数字，结果判据自己筛掉了
它本该测的那些板子（阈值、留白容差写死得不对，见 solid_thr/_spans_edge）。现在形状只当一行提示，
数字照量照打 —— 读表的人看见 bg_diwen 起点 294 自然知道那是一张满幅底纹不是框。

用法: python nine_patch_test.py <图目录> <out目录> [inset,...] [名字片段,...] [宽x高,...]
    例: python nine_patch_test.py out/focus_ui out/nine_patch 3,4,5,6,8 kuang,bubble,tips,diwen,btn
        python nine_patch_test.py out/shots-dialog/scenerio out/x 8,12,16 talk_frame 320x120,440x150
    最后一档自己给是因为**尺子要跟着用途换**：默认那三档是给 22~32px 的小框往大拉用的，
    对 1047x145 那种整条剧情框来说三档都比原图小，量出来永远是「要保的边带比目标尺寸还宽」，
    那是尺子不对不是图不行。
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

# 三档目标：小面板、设置小窗、以及**倒计时浮窗那种横条**。
# 第三档才是真正考九宫格的：28 px 的框拉成 420 宽 = 横向 15 倍、纵向 5 倍，
# 整图缩放会把圆角拉成橄榄球，九宫格该原样保住角。
TARGETS = [(160, 110), (280, 200), (420, 150)]
RIM = 12                             # 量平坦率先剥掉的一圈（按图大小自动收）
FONT = "C:/Windows/Fonts/msyh.ttc"


def solid_thr(img):
    """这图的「实心」阈值 = 它自己 alpha 峰值的一半（下限 32），**只从原图算一次**，拉伸后共用。
    为什么不能写死 200：库里 bg_kuang03 本来就是一层半透明的框，alpha 峰值根本到不了 200，
    按 200 读它就是「全透明、没内容」，起点量成 0、判据整个失灵。
    为什么前后必须同一个数：换阈值等于换尺子，量出来的偏差就不是偏差了。"""
    return max(32, int(round(0.5 * int(np.asarray(img)[:, :, 3].max()))))


def corner_r(img, thr):
    """左上「圆角起点」= 最顶行第一颗实心像素离左边多远（和最左列那个离顶多远取大）。
    **不等于几何半径** —— 拿 PIL 画的 r=6 圆角板实测读出 4，阈值吃掉了弧顶那几列；
    它随半径单调，判据要的只是「拉完前后这个数不涨」，不是量出真半径。"""
    a = np.asarray(img)[:, :, 3] >= thr
    ys, xs = np.nonzero(a)
    if not len(ys):
        return 0
    return int(max(int(xs[ys == ys.min()].min()), int(ys[xs == xs.min()].min())))


def _spans_edge(seq, tol):
    """这一行/列是不是「一条完整的边」：墨从左铺到右（两端各容忍 tol px 的软阴影留白），
    中间只许留**一段**空腔（空心框的内腔），不许是散点（人偶四肢、图标）。实心板子没空腔，也算过。
    tol 得跟着图宽走：bg_tips_3 那块板四周有 5 px 投影，写死「离边 2 px 内必须有墨」会把它判成不贴边，
    可它恰恰就是本项目最该测的那种板子。"""
    xs = np.nonzero(seq)[0]
    if not len(xs) or xs[0] > tol or xs[-1] < len(seq) - 1 - tol:
        return False
    gaps = np.nonzero(~seq[xs[0]:xs[-1] + 1])[0]
    return not len(gaps) or (gaps.max() - gaps.min() + 1) == len(gaps)


def rect_art(img, thr):
    """这图是不是「有平直边的板子」（实心或空心框）—— 只有这种谈得上九宫格。
    取越过起拱处（2 倍起拱，那里早该离开弧面）的一行一列来判：
    圆角矩形过了圆角就是平直的边；人偶/圆钮/图标在那一行是断的
    （达摩 02 起拱量出 0 是因为脑门顶到画布上沿，光看起拱会放它过关，看这条边才拦得住；
     圆钮的起拱就是半径，2 倍顶到边外，直接判否）。"""
    a = np.asarray(img)[:, :, 3] >= thr
    ys, xs = np.nonzero(a)
    if not len(ys):
        return False
    h, w = a.shape
    tol = max(3, round(0.03 * max(w, h)))
    if xs.min() > tol or ys.min() > tol or xs.max() < w - 1 - tol or ys.max() < h - 1 - tol:
        return False
    y = 2 * corner_r(img, thr)
    if y >= min(h, w):
        return False
    return _spans_edge(a[y], tol) and _spans_edge(a[:, y], tol)


def busy_mask(img):
    """每颗像素「忙不忙」：3x3 邻域里 RGB **或 alpha** 的最大-最小差 >= 18 就算忙。
    为什么 alpha 也要看：bg_kuang03 那圈半透明亮边 RGB 几乎不变，只看颜色会漏判成「平的」，
    于是 inset 取到它里面去，亮边被当成可拉伸的中间块拉没了。"""
    arr = np.asarray(img).astype(np.int16)
    h, w = arr.shape[:2]
    pad = np.pad(arr, ((1, 1), (1, 1), (0, 0)), mode="edge")
    near = np.stack([pad[dy:dy + h, dx:dx + w] for dy in range(3) for dx in range(3)])
    return (near.max(0) - near.min(0)).max(axis=2) >= 18


def _probe(seq, min_flat=6):
    """从一头往里走，走到「往后连着 min_flat 颗都是平的」为止 —— 走过的这段就是必须原样保住的边带。
    一整行都没这么平过（全是花纹/图案）就返回一个超过半宽的大数，等于在说「这图做不了九宫格」。
    为什么不用「最后一个忙像素的坐标」：图四周必然有一圈透明→实心的 alpha 渐变，
    那个数会被外沿渐变整个带跑（量出来永远是「整行都忙」）。"""
    flat = ~seq
    for i in range(len(seq) - min_flat):
        if flat[i:i + min_flat].all():
            return i
    return len(seq) // 2 + 1


def edge_inset(img, busy=None):
    """最小可用 inset：四条边各往里探一次取最大。只看正中间那一行/一列 ——
    装饰都贴在边上，中间行是最不容易被圆角骗到的探针。"""
    b = busy_mask(img) if busy is None else busy
    h, w = b.shape
    return max(_probe(b[h // 2]), _probe(b[h // 2][::-1]),
               _probe(b[:, w // 2]), _probe(b[:, w // 2][::-1]))


def flat_ratio(img, thr, busy=None, rim=RIM):
    """内部（剥掉 rim 一圈）有多少比例是「平」的；没内部可言返回 None。
    两个坑：
    1) 只算**实心**像素 —— 空心框（bg_kuang02）的内部是透明的，convert("RGB") 在那儿读出的是
       随机的 RGB，当成「颜色差很多」是我自己造出来的假信号。
    2) rim 跟着图大小收 —— 库里的框才 28 px，写死剥 12 只剩 4 px，量了等于没量。"""
    arr = np.asarray(img)
    solid = arr[:, :, 3] >= thr
    b = busy_mask(img) if busy is None else busy
    rim = max(2, min(rim, (min(img.size) - 6) // 2))
    if arr.shape[0] <= 2 * rim + 2 or arr.shape[1] <= 2 * rim + 2:
        return None
    inr = solid[rim:-rim, rim:-rim]
    if inr.sum() < 20:
        return None
    return float(1.0 - b[rim:-rim, rim:-rim][inr].mean())


def nine_slice(img, k, w, h):
    """四角 k×k 原样贴，上下/左右边各只沿一个方向拉，中间块两向拉"""
    W, H = img.size
    if 2 * k >= min(W, H) or min(w, h) <= 2 * k:
        return None
    cx = [(0, k, 0, k), (k, W - 2 * k, k, w - 2 * k), (W - k, k, w - k, k)]
    cy = [(0, k, 0, k), (k, H - 2 * k, k, h - 2 * k), (H - k, k, h - k, k)]
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for sx, sw, dx, dw in cx:
        for sy, sh, dy, dh in cy:
            tile = img.crop((sx, sy, sx + sw, sy + sh)).resize((max(1, dw), max(1, dh)), Image.LANCZOS)
            out.paste(tile, (dx, dy), tile)
    return out


def on_bg(im):
    bg = Image.new("RGB", im.size, (43, 43, 43))     # 本机深色主题实测的提示底色
    bg.paste(im, (0, 0), im)
    return bg


def look(img, thr):
    """看得见看不见，是两个数：峰值 alpha（整块有多实）和实心像素的平均亮度。
    本机桌面是深色主题，亮度低于 ~100 或峰值 alpha 低于 ~180 的贴上去等于隐形 ——
    挑素材先看这两个数，别等接进桌宠才发现「那块板呢？」。"""
    a = np.asarray(img).astype(np.float32)
    m = a[:, :, 3]
    solid = m >= thr
    if not solid.any():
        return int(m.max()), 0
    lum = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2])[solid]
    return int(m.max()), int(lum.mean())


def measure(img, insets):
    """一张图的全部数：阈值只算一次，拉伸前后共用同一把尺"""
    thr = solid_thr(img)
    busy = busy_mask(img)
    r0 = corner_r(img, thr)
    # inset 要同时盖住两样东西：圆角的弧（r0）和边上那道亮边/花纹（edge_inset）。
    # 只按 r0 选会翻车 —— bg_kuang03 是方角（r0=0）但有一圈半透明亮边，inset=2 拉完亮边没了。
    need = max(r0, edge_inset(img, busy))
    flat = flat_ratio(img, thr, busy)
    peak, lum = look(img, thr)
    whole = [corner_r(img.resize(t, Image.LANCZOS), thr) for t in TARGETS]
    # 搜的范围跟着量出来的数走，不能写死 3..8；下限 2 是因为 k=0 那档角块是 0 宽，裁出来是空图。
    cands = sorted({k for k in set(insets) | {need, need + 1, need + 2, need + 4} if k >= 2 and k >= need})
    best = None
    for k in cands:
        ims = {t: nine_slice(img, k, *t) for t in TARGETS}
        if any(v is None for v in ims.values()):
            continue
        err = max(abs(corner_r(v, thr) - r0) for v in ims.values())
        if best is None or err < best[0]:
            best = (err, k, ims)
    return dict(thr=thr, r0=r0, need=need, flat=flat, whole=whole, best=best, peak=peak, lum=lum,
                shape=rect_art(img, thr))


def verdict(m):
    if not m["shape"]:
        s = "形状不贴边（图标/异形/满幅底纹），下面这些数只当参考"
        return s + ("｜而且边带比目标尺寸还宽，做不了九宫格" if m["best"] is None else "")
    if m["best"] is None:
        return f"要保的边带宽 {m['need']}px，比目标尺寸还大，做不了九宫格"
    if m["flat"] is not None and m["flat"] < 0.5:
        return "圆角保住了，但中间不平 —— 拉了会抹纹理"
    return "九宫格可用" if m["best"][0] <= 1 else "圆角保不住，别拉"


def main(src_dir, out_dir, insets, needles=()):
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(f for f in os.listdir(src_dir)
                   if f.lower().endswith(".png") and (not needles or any(n in f.lower() for n in needles)))
    if not files:
        raise SystemExit(f"{src_dir} 下没有匹配的图，先跑 gui_page_map.py 裁图")
    rows, skipped = [], []
    for f in files:
        img = Image.open(os.path.join(src_dir, f)).convert("RGBA")
        if min(img.size) < 12:
            skipped.append(f"{f}: {img.size[0]}x{img.size[1]} 太小，谈不上九宫格")
            continue
        m = measure(img, insets)
        m.update(name=f, img=img, note=verdict(m))
        if m["lum"] < 100 or m["peak"] < 180:
            m["note"] += f"｜贴深底偏暗（亮度{m['lum']}、峰值alpha{m['peak']}）"
        rows.append(m)
        fl = "—" if m["flat"] is None else f"{m['flat']:.0%}"
        if m["best"] is None:
            got, err = "—", "—"
        else:
            err = m["best"][0]
            got = f"inset={m['best'][1]}→{[corner_r(m['best'][2][t], m['thr']) for t in TARGETS]}"
        print(f"{f:<40} 起点={m['r0']:>3}px 边带={m['need']:>3}px 平坦={fl:>4} 亮度={m['lum']:>3} "
              f"整图缩放→{m['whole']}  九宫格 {got}  偏差={err}px  {m['note']}")
    for s in skipped:
        print("跳过 " + s)

    with open(os.path.join(out_dir, "结果.tsv"), "w", encoding="utf-8") as fh:
        fh.write("图\t原尺寸\t实心阈值\t峰值alpha\t实心亮度\t圆角起点px\t要保的边带px\t平坦率\t"
                 + "".join(f"整图缩放{w}x{h}\t" for w, h in TARGETS)
                 + "最优inset\t"
                 + "".join(f"九宫格{w}x{h}\t" for w, h in TARGETS)
                 + "最大偏差px\t形状贴边\t结论\n")
        for m in rows:
            err, k, ims = (m["best"] if m["best"] else ("", "", {}))
            fl = "" if m["flat"] is None else f"{m['flat']:.2f}"
            fh.write(f"{m['name']}\t{m['img'].width}x{m['img'].height}\t{m['thr']}\t{m['peak']}\t{m['lum']}"
                     f"\t{m['r0']}\t{m['need']}\t{fl}"
                     + "".join(f"\t{c}" for c in m["whole"])
                     + f"\t{k}"
                     + "".join(f"\t{corner_r(ims[t], m['thr']) if t in ims else ''}" for t in TARGETS)
                     + f"\t{err}\t{'是' if m['shape'] else '否'}\t{m['note']}\n")
    path = os.path.join(out_dir, "拉伸对比.png")
    # 对比图只排「拉得出名堂」的那些：这张图是拿来肉眼分辨拉伸伪影的。
    # 人偶/叶子/满幅底纹本来就不打算拉（平坦率低于一半就是花纹铺满），排进去只是把图撑到一万四千像素高。
    look = [m for m in rows if m["best"] is not None
            and (m["shape"] or (m["flat"] is not None and m["flat"] >= 0.5))]
    sheet(path, look)
    print(f"表: {os.path.join(out_dir, '结果.tsv')}（全部 {len(rows)} 行）  "
          f"图: {path}（只排拉得出名堂的 {len(look)} 行）")


def sheet(path, rows):
    """每张一行：原图(NEAREST 放大到看得见像素) | 每档目标两列：整图缩放 / 九宫格"""
    # 格子宽跟着最宽的目标走：写死 300 的话 420 宽那张会溢到隔壁格，
    # 看图的人以为那是图本身带的「小耳朵」（我第一次就被骗了）。
    cw, ch = max(300, max(w for w, h in TARGETS) + 24), 240
    ncol = 1 + 2 * len(TARGETS)
    canvas = Image.new("RGB", (cw * ncol + 20, (ch + 44) * len(rows) + 52), (24, 24, 26))
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, 15)
    heads = ["原图 NEAREST 放大"] + [f"整图缩放 {t}" for t in TARGETS] + [f"九宫格 {t}" for t in TARGETS]
    for j, head in enumerate(heads):
        d.text((14 + j * cw, 24), head, font=font, fill=(160, 160, 168))
    for i, m in enumerate(rows):
        img, thr, best = m["img"], m["thr"], m["best"]
        y = 52 + i * (ch + 44)
        fl = "—" if m["flat"] is None else f"{m['flat']:.0%}"
        head = (f"{m['name']}  圆角起点 {m['r0']}px 边带 {m['need']}px｜平坦 {fl}｜"
                f"亮度 {m['lum']} 峰值alpha {m['peak']}｜{m['note']}")
        if best:
            head += (f"｜整图缩放撑到 {m['whole']}，九宫格 inset={best[1]} 拉完是 "
                     f"{[corner_r(best[2][t], thr) for t in TARGETS]}")
        d.text((14, y - 20), head, font=font, fill=(226, 214, 190))
        z = max(1, 150 // max(1, img.height))
        zoom = img.resize((img.width * z, img.height * z), Image.NEAREST)
        canvas.paste(on_bg(zoom), (14 + (cw - zoom.width) // 2, y + (ch - zoom.height) // 2))
        for j, t in enumerate(TARGETS):
            canvas.paste(on_bg(img.resize(t, Image.LANCZOS)), (14 + (1 + j) * cw + 10, y + (ch - t[1]) // 2))
            if best:
                canvas.paste(on_bg(best[2][t]), (14 + (1 + len(TARGETS) + j) * cw + 10, y + (ch - t[1]) // 2))
    canvas.save(path)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) > 4:
        TARGETS = [tuple(int(v) for v in x.lower().split("x")) for x in a[4].split(",") if x]
    main(a[0], a[1],
         tuple(int(x) for x in a[2].split(",")) if len(a) > 2 else (3, 4, 5, 6, 8),
         tuple(x for x in a[3].split(",") if x) if len(a) > 3 else ())
