# -*- coding: utf-8 -*-
import os
from fontTools.ttLib import TTFont
p = os.path.expanduser(r"~\AppData\Local\Microsoft\Windows\Fonts\font.ttf")
f = TTFont(p)
cmap = f.getBestCmap()
need = "番茄钟短休长假连做段现在这几分钟没对上任何档分歧换弹气泡开始专注继停"
have = [c for c in need if ord(c) in cmap]
miss = [c for c in need if ord(c) not in cmap]
digits = [c for c in "0123456789" if ord(c) in cmap]
out = [
    "文件 = " + p,
    "标题+摘要+按钮全部中文 (%d 个不同字): 有字形 %d / 缺 %d" % (len(set(need)), len(have), len(miss)),
    "缺的字: " + "".join(sorted(set(miss))),
    "有的字: " + "".join(sorted(set(have))),
    "数字 0-9: 有字形 %d/10" % len(digits),
    "总码点: %d" % len(cmap),
]
open("bwp-assets/out/seiga-recheck.txt", "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out).encode("ascii", "backslashreplace").decode())
