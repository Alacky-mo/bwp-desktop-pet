# 只回答一个问题：那个注册成「素晴字体」的 font.ttf 到底有没有中文字形。
from PIL import ImageFont
import os

p = os.path.expanduser("~") + r"\AppData\Local\Microsoft\Windows\Fonts\font.ttf"
f = ImageFont.truetype(p, 28)
print("文件=", p, "存在=", os.path.exists(p))
print("家族名=", f.getname())
cm = f.font.font.tableReader["cmap"].tables
maps = {t.format: t.cmap for t in cm}
codes = set()
for t in cm:
    codes |= set(t.cmap.keys())
print("cmap 码点数=", len(codes), "表=", sorted(maps.keys()))

def has(ch):
    return ord(ch) in codes

# 抽样：常用中文、日语假名、拉丁、符号，各取几个，看它覆盖面到底落在哪
groups = {
  "小窗标题用的中文": "番茄钟分短休长假连做段现在这几没对上任何一",
  "常用中文(旁证)":   "的一是了我不人在他有这个上们来到时大地为",
  "平假名":           "あいうえおかきくけこさしすせそ",
  "片假名":           "アイウエオカキクケコサシスセソ",
  "拉丁":             "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
  "数字":             "0123456789",
}
out = []
for name, s in groups.items():
    hit = sum(1 for c in s if has(c))
    out.append(f"{name}: {hit}/{len(s)} 有字形 | 缺的={''.join(c for c in s if not has(c)) or '（无）'}")
for line in out:
    print(line)

# 它自己出的字长什么样：挑几个「有」的码位，画出来和宋体对比
have = [chr(c) for c in sorted(codes) if 0x20 < c < 0xFFFF][:0]
print("--- 前 60 个码位 ---")
print(" ".join(f"{c:04X}" for c in sorted(x for x in codes if x < 0x10000)[:60]))
