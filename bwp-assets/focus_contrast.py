"""量每张候选图标在「气泡/托盘真正会用的底色」上看不看得见 —— 别凭肉眼猜深浅底。

用法: python focus_contrast.py <图目录> [标签.tsv] [画的像素，默认 32]
    32 = 气泡图标实际被画出来的大小；托盘那格填 16。
    底取 Win11 深色 toast/任务栏 #2b2b2b 和浅色 #f3f3f3 两种，本机用哪个看注册表
    （HKCU\\...\\Themes\\Personalize 的 AppsUseLightTheme）。
    每张缩到气泡实际会画的 32px，只数不透明像素（透明处就是底色本身，算进去会把稀疏图打成 1.0 假分），
    给三个数: 占画幅(实心比) / 中位 WCAG 对比 / 显眼像素比(对比>1.6)，得分 = 占画幅 x 显眼比。
"""
import os, sys, winreg
from PIL import Image

DARK, LIGHT = (43, 43, 43), (243, 243, 243)
BOX = 32


def theme_bg():
    k = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                       r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize')
    light = winreg.QueryValueEx(k, 'AppsUseLightTheme')[0]
    return (LIGHT if light else DARK), ('浅色' if light else '深色')


def lum(c):
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def contrast(p, bg):
    l1, l2 = sorted((lum(p), lum(bg)), reverse=True)
    return (l1 + 5) / (l2 + 5)


def score(path, bg):
    im = Image.open(path).convert('RGBA')
    s = im.resize((BOX, BOX), Image.LANCZOS)
    op = [p for p in s.getdata() if p[3] > 128]
    if not op:
        return 0, 0, 0, 0
    comp = [tuple(round(p[3] / 255 * p[i] + (1 - p[3] / 255) * bg[i]) for i in range(3)) for p in op]
    cs = sorted(contrast(c, bg) for c in comp)
    cov, med = len(op) / (BOX * BOX), cs[len(cs) // 2]
    vis = sum(1 for c in cs if c > 1.6) / len(cs)
    return cov, med, vis, cov * vis


def main(src, legend=None, box=None):
    global BOX
    if box:
        BOX = int(box)
    labels = {}
    if legend:
        # 整条留下只掐长度：截到「达摩·红色」这种会五张撞名
        for line in open(legend, encoding='utf-8'):
            if '\t' in line and not line.startswith('#'):
                k, v = line.rstrip('\n').split('\t', 1)
                labels[k] = (v[:22] + '…') if len(v) > 22 else v
    live, lname = theme_bg()
    print(f'本机是{lname}主题 → 气泡/任务栏底按 {live} 算，这张表里它才是"实际"那一栏\n')
    rows = []
    for f in sorted(os.listdir(src)):
        if not f.lower().endswith('.png'):
            continue
        stem = os.path.splitext(f)[0]
        cd = score(os.path.join(src, f), DARK)
        cl = score(os.path.join(src, f), LIGHT)
        rows.append((stem, cd, cl))
    print(f'{"中文叫法":16}{"深色底得分":>10}{"浅色底得分":>10}{"两边都不掉队":>12}')
    for stem, cd, cl in sorted(rows, key=lambda r: -min(r[1][3], r[2][3])):
        both = '★ 双底都站得住' if min(cd[3], cl[3]) > 0.45 else ''
        print(f'{labels.get(stem, stem):16}{cd[3]*100:9.0f}{cl[3]*100:11.0f}    {both}')
    print('\n细看（深色底 / 浅色底 各三列: 占画幅 中位对比 显眼比）')
    for stem, cd, cl in sorted(rows, key=lambda r: -r[1][3]):
        print(f'{labels.get(stem, stem):16} 深 {cd[0]*100:3.0f}% {cd[1]:4.2f} {cd[2]*100:3.0f}%   '
              f'浅 {cl[0]*100:3.0f}% {cl[1]:4.2f} {cl[2]*100:3.0f}%   {stem}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    main(sys.argv[1],
         sys.argv[2] if len(sys.argv) > 2 else None,
         sys.argv[3] if len(sys.argv) > 3 else None)
