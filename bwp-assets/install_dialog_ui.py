# 把台词气泡要用的两张件和台词池装进 DeskSpine/res/。
#
# 和 install_focus_ui.py 同一套规矩：衍生件和台词原文都不进版本库，换台机器就是空的，
# 所以装机必须一条命令能重跑：python install_dialog_ui.py
#
# 三件处理：
# 1) 清邻格碎片 —— 这两张从图集裁出来都带着隔壁控件渗进来的像素（气泡右上角一块浅蓝方块、
#    右下角一个紫色加号、松针左上角一个黑方块）。keep_blobs 只留大连通块，阈值 0.15 的来由见 dialog_mock.py。
# 2) 等比放大 1.15 —— 原尺寸那张气泡的正文区实测只能装「一行 12 字 x 3 行 = 36 字」，
#    而台词池 22 条里有 7 条更长（最长 48 字）。放大到 1.15 就是「一行 14 字 x 4 行 = 56 字」，全装得下。
#    放大只在装机时做一次（LANCZOS），运行时 1:1 贴 —— 让 GDI 那边 NearestNeighbor 去放大会糊得难看。
#    为什么整图放大而不是拉伸：这张气泡上下两条边是斜着收尖的，横竖分开拉会把斜边拉歪
#    （docs/番茄钟界面方案.md 里那条形状判据就是冲着它写的）。
# 3) 边框染金加粗到 FRAME_PX 档（2026-11-02 用户：「对话框的边框线条更粗一些」）——
#    原图那条金线实测只有距边第 1 档（778 个像素，均色 195,178,160），第 2 档起就是纸。
#    染金只改颜色不改轮廓，所以「连通块 1 个 / 最大块占 99%」那两条判据照旧绿；
#    装完自己量一遍 band_means，金线几 px 是量出来的不是写死的。
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dialog_mock import band_means, gilded, keep_blobs

CROPS = os.path.join(HERE, "out", "shots-dialog", "pick")
POOL = os.path.join(HERE, "out", "bz-pool.tsv")
DEST = os.path.join(HERE, "..", "deskspine", "DeskSpine", "res")
SCALE = 1.15
FRAME_PX = 3          # 用户挑的那档（预览 ②）：距边 1~3 档染金，第 4 档起回纸

# 装机名 -> (库里裁片名, 目标边长, 边框染金几档；None = 不染)。
# 家纹那枚按 48 定，是 42 x 1.15 取整 —— 它不参与折行计算，
# 只是名牌左边那个印记，跟着气泡一起放大才不显得气泡变大了印记没变
ART = [("bubble", "gui_ui_common_img_bubble_02.png", None, FRAME_PX),
       ("crest", "gui_ui_scenerio_img_duoren_01.png", 48, None)]


def install_art(name, src_name, side, frame):
    src = os.path.join(CROPS, src_name)
    if not os.path.exists(src):
        return f"缺 {src}（先跑 npk_unpack + crop_named 裁出剧情/UI 页，见 crop_named.py 用法）"
    im, dropped = keep_blobs(Image.open(src).convert("RGBA"))
    w, h = (side, side) if side else (round(im.width * SCALE), round(im.height * SCALE))
    im = im.resize((w, h), Image.LANCZOS)
    if frame:
        im = gilded(im, frame)
    dst = os.path.join(DEST, "image", "dialog", f"{name}.png")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst)
    raw, solid = _blob_count(im)
    print(f"  {name+'.png':<14} {w}x{h}  抹掉碎片 {dropped} 块，装机后连通块 {raw} 个、有分量的 {solid} 个")
    if frame:
        bands = band_means(im, depth=frame + 1)
        print(f"    边框染金 {frame} 档：" + " / ".join(
            f"第{i + 1}档 rgb{c} n={n}" for i, (c, n) in enumerate(bands)))
        warm = [i + 1 for i, (c, n) in enumerate(bands) if n and c[0] - c[2] >= 40]
        if warm != list(range(1, frame + 1)):
            return f"{name}.png 金线不是量的 {frame} px：偏暖（R-B≥40）的是第 {warm} 档"
    if solid > 1:
        return f"{name}.png 装机后还有 {solid} 个有分量的连通块，碎片没清干净"
    return None


def _blob_count(im):
    """数连通块，返回 (总块数, 有分量的块数)。
    有分量 = 面积 ≥ 最大块的 15%，和 keep_blobs 同一条线：LANCZOS 放大偶尔甩出几个 1px 散点，
    那是抗锯齿不是邻格碎片（装机那张 41756 个不透明像素里散点只占 4 个），
    拿「块数 > 1」当闸门会把这种散点误判成没清干净。"""
    from collections import deque
    w, h = im.size
    a = im.getchannel("A").load()
    seen = [[False] * w for _ in range(h)]
    sizes = []
    for y in range(h):
        for x in range(w):
            if seen[y][x] or a[x, y] <= 24:
                continue
            q, seen[y][x] = deque([(x, y)]), True
            n = 0
            while q:
                cx, cy = q.popleft()
                n += 1
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and a[nx, ny] > 24:
                        seen[ny][nx] = True
                        q.append((nx, ny))
            sizes.append(n)
    if not sizes:
        return 0, 0
    top = max(sizes)
    return len(sizes), sum(1 for s in sizes if s >= 0.15 * top)


def install_pool():
    """台词池只带桌宠要用的三列进 res/dialog/lines.tsv；游戏原文不外传，仍只在本机。"""
    if not os.path.exists(POOL):
        return f"缺 {POOL}（先跑 scenerio_lines.py 解出剧情台词，再挑池子）"
    rows = [l.rstrip("\n").split("\t") for l in open(POOL, encoding="utf-8")][1:]
    dst = os.path.join(DEST, "dialog", "lines.tsv")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8", newline="") as f:
        f.write("说话人\t分组\t字数\t台词\n")
        for r in rows:
            f.write(f"不知火\t{r[0]}\t{r[4]}\t{r[3]}\n")
    print(f"  lines.tsv      {len(rows)} 条，最长 {max(int(r[4]) for r in rows)} 字")
    return None


def main():
    errs = []
    for name, src_name, side, frame in ART:
        err = install_art(name, src_name, side, frame)
        if err:
            errs.append(err)
    err = install_pool()
    if err:
        errs.append(err)
    for e in errs:
        print("!", e)
    if errs:
        return 1
    print(f"装到 {os.path.normpath(DEST)}")
    print("csproj 已带 res\\image\\dialog\\** 和 res\\dialog\\** 进输出目录，改完素材重跑这个脚本就行")
    return 0


if __name__ == "__main__":
    sys.exit(main())
