"""反向验台词气泡那条判据: 把 bug 一个个放回去, 看它会不会红。

每条: 备份字节 → 改源码(或改装机参数重跑装机、换装机图) → 建到 out/reverse-build/ → 跑 desk
→ 记下哪几行红 → 按备份还原。
源码一律按字节替换, 不读成文本再写回 —— DialogBubbleForm.cs 是纯 LF、Config.cs 和 PetNames.cs 是 CRLF+BOM,
文本往返会把换行整篇改掉, 那就不是「还原」了。
产物日志 out/reverse-red-dialog.txt。跑完所有文件都必须和跑之前逐字节同哈希, 否则脚本自己报错。

金线那一条改的是装机参数(install_dialog_ui.py 的 FRAME_PX 3→1)并重跑装机 ——
判据量的是装好的 png, 所以「装窄了」才是这条 bug 本来的形状, 不是拿一张假图糊过去。
"""
import hashlib
import os
import pathlib
import subprocess
import sys

# 控制台默认按 GBK 写, ✗ 和「」这类字符会炸 —— 日志和 stdout 一律走 UTF-8
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

view = pathlib.Path(__file__).parent
root = view.parents[2]
assets = root / "bwp-assets"
out = assets / "out"
src = root / "deskspine" / "DeskSpine" / "src"
res = root / "deskspine" / "DeskSpine" / "res"
form = src / "DialogBubbleForm.cs"
names = src / "PetNames.cs"      # 角色名表(UTF-8+BOM+CRLF) —— 池子的说话人和它漂一个字, 气泡就静悄悄不弹
cfg = src / "Config.cs"
menu_form = src / "ConfigForm.cs"   # 托盘「切换角色」那几行的渲染现场(GBK) —— 反向验第 22 条要动它的调用点
installer = assets / "install_dialog_ui.py"
res_bubble = res / "image" / "dialog" / "bubble.png"
res_crest = res / "image" / "dialog" / "crest.png"
res_pool = res / "dialog" / "lines.tsv"
gate = assets / "animator-test" / "bin" / "Release" / "net8.0-windows" / "bwp-animator-test.exe"
build_dir = out / "reverse-build"
target = str(build_dir / "x64" / "Release" / "net8.0-windows" / "win-x64" / "DeskSpine.dll")
log = out / "reverse-red-dialog.txt"

FILES = [form, names, cfg, menu_form, installer, res_bubble, res_crest, res_pool]

# 大红 / 烫金那两组色, 反向验要的就是「退回上一版：纸上写墨字」那个形状
PAPER = (233, 228, 229)
INK = (58, 44, 40)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def run(cmd, timeout, cwd):
    # 子进程往管道里写中文时按 GBK 编码, 拿 UTF-8 解会读成一堆乱码 —— 装机那条判据就靠认它打印的「装到」
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(cwd), env=env)
    return (r.stdout + r.stderr).decode("utf-8", errors="replace")


def desk():
    """建 + 跑, 返回 (这层红了吗, 点名的 ✗ 行, 建/跑本身有没有炸, 原文)"""
    b = run(["dotnet", "build", str(root / "deskspine" / "DeskSpine.sln"), "-c", "Release",
             "-v", "q", "--nologo", f"-p:BaseOutputPath={build_dir.as_posix()}/"], 900, root)
    if "0 个错误" not in b:
        return (False, [], "建不过: " + b.strip()[-400:], b)
    d = run([str(gate), "desk", target], 300, assets)
    if "DESK" not in d:
        return (False, [], "gate 没吐出结果: " + d.strip()[-400:], d)
    lines = d.splitlines()
    marks = [l.strip() for l in lines if l.strip().startswith("✗")]
    # 基线整份 desk 是绿的, 所以任何一条 ": 否" 都是这次注进去的 bug 点红的 —— 不再只盯台词气泡那一层
    red = any(": 否" in l for l in lines)
    return (red, marks, None, d)


cases = [
    dict(name="MaxLines 收成 3 行(池子里那句 4 行的会画到泡外)", file=form,
         edits=[(form, b"public static int MaxLines => TextArea.Height / LineAdvance;",
                 b"public static int MaxLines => TextArea.Height / (LineAdvance + 10);")],
         expect="每一条都折得进气泡正文区"),
    dict(name="默认 Show/Gap 改回 45/135(用户 2026-11-02 拍的是 15/60)", file=cfg,
         edits=[(cfg, b"public int ShowSeconds { get; set; } = 15;",
                 b"public int ShowSeconds { get; set; } = 45;"),
                (cfg, b"public int GapSeconds { get; set; } = 60;",
                 b"public int GapSeconds { get; set; } = 135;")],
         expect="默认值 = 用户拍的那三个数"),
    dict(name="Step 到点不收起(气泡常驻, 用户要的是「过一会就消失」)", file=form,
         edits=[(form, b"            return showing ? (false, Math.Max(1, gap), false)",
                 b"            return showing ? (true,  Math.Max(1, show), false)")],
         expect="亮够 ShowSeconds 就自己消失"),
    dict(name="NextVisible 不看预设小窗(两张板叠在同一块地方)", file=form,
         edits=[(form, b"internal static bool NextVisible(bool enabled, bool hasLines, bool stowed, bool presetOpen, bool thisPet)\n            => enabled && hasLines && !stowed && !presetOpen && thisPet;",
                 b"internal static bool NextVisible(bool enabled, bool hasLines, bool stowed, bool presetOpen, bool thisPet)\n            => enabled && hasLines && !stowed && thisPet;")],
         expect="32 组全枚举"),

    # —— 本轮(2026-11-02 用户四条改口)新增的判据, 每条都把对应的旧写法放回去 ——
    dict(name="BubbleBounds 从宠物左边起算", file=form,
         edits=[(form, b"            var x = pet.Right + gap - ink.X;",
                 b"            var x = pet.Left + gap - ink.X;")],
         expect="默认摆宠物右侧"),
    dict(name="摆位退回按画布贴(那 14 px 透明边算进间距, 就是用户说的「离得远」)", file=form,
         edits=[(form, b"            var x = pet.Right + gap - ink.X;",
                 b"            var x = pet.Right + gap;")],
         expect="间距量在墨上"),
    dict(name="翻到左边那侧按画布左边贴(墨右沿差一整段透明边)", file=form,
         edits=[(form, b"            if (mirrored) x = pet.Left - gap - (panel.Width - ink.X);",
                 b"            if (mirrored) x = pet.Left - gap - panel.Width;")],
         expect="右边塞不下就翻到左边"),
    dict(name="Mx 不挪件(镜像那侧家纹和正文区还压在左边)", file=form,
         edits=[(form, b"internal static int Mx(int x, int w, bool mirror) => mirror ? CanvasWidth - x - w : x;",
                 b"internal static int Mx(int x, int w, bool mirror) => x;")],
         expect="镜像只挪件"),
    dict(name="名牌尖朝向镜像搞反(尖戳进宠物那一侧)", file=form,
         edits=[(form, b"            var pts = mirror", b"            var pts = !mirror")],
         expect="名牌的尖在朝外那一端"),
    dict(name="名牌底色退回纸色(用户要的是大红底)", file=form,
         edits=[(form, b"internal static readonly Color PlateTop = Color.FromArgb(198, 48, 44);",
                 f"internal static readonly Color PlateTop = Color.FromArgb{PAPER};".encode()),
                (form, b"internal static readonly Color PlateBottom = Color.FromArgb(146, 24, 30);",
                 f"internal static readonly Color PlateBottom = Color.FromArgb{PAPER};".encode())],
         expect="名牌是大红底"),
    dict(name="名牌字退回墨色(用户要的是烫金)", file=form,
         edits=[(form, b"internal static readonly Color GoldTop = Color.FromArgb(255, 244, 196);",
                 f"internal static readonly Color GoldTop = Color.FromArgb{INK};".encode()),
                (form, b"internal static readonly Color GoldBottom = Color.FromArgb(206, 150, 32);",
                 f"internal static readonly Color GoldBottom = Color.FromArgb{INK};".encode())],
         expect="名牌是大红底"),
    dict(name="装机金线装窄成 1 档(FRAME_PX 3→1 真重跑一遍装机)", file=installer,
         edits=[(installer, b"FRAME_PX = 3", b"FRAME_PX = 1")],
         expect="金线实测 3 档粗", install=True),
    dict(name="装机图本体边上添一块邻格碎片(换脏的 bubble.png)", file=res_bubble,
         edits=[], expect="最大那一块占到全图墨的 99%", dirty=True),

    # —— 2026-11-02 用户点托盘「换一条」字不动: 作废键被 BeginLine 提前拨新的 shownText 顶掉了 ——
    dict(name="ArtFor 拿 shownText 当作废词(同侧换了台词仍复用旧图)", file=form,
         edits=[(form, b"            if (slot is not null && text == artText) return slot;",
                 b"            if (slot is not null && text == shownText) return slot;")],
         expect="换了台词同一侧重画出来的是新图"),

    # —— 2026-11-02 用户复验「气泡翻到左边那侧短句偏左、长句压到框上」: 三笔账, 每笔放回去一次 ——
    dict(name="镜像那侧气泡仍按 BubbleAt 原样摆(画布左右不等分, 纸和正文差 13 px)", file=form,
         edits=[(form, b"                g.DrawImage(bubble, mirror ? new Point(Mx(BubbleAt.X, bubble.Width, true), BubbleAt.Y) : BubbleAt);",
                 b"                g.DrawImage(bubble, BubbleAt);")],
         expect="正文都压在画出来的纸上"),
    dict(name="左侧正文退回左对齐(镜像那侧整块比纸偏左, 长句压到框上)", file=form,
         edits=[(form, b"                var x = mirror\n"
                        b"                    ? area.Right - (float)Math.Round(g.MeasureString(line, bodyFont, new PointF(0, 0), layout).Width)\n"
                        b"                    : (float)area.X;",
                 b"                var x = (float)area.X;")],
         expect="两侧互成镜像：把左摆正文"),

    # —— 2026-11-03 用户: 切了角色台词还照弹(那 22 条全是不知火的独白、名牌也写着「不知火」) ——
    dict(name="角色门恒真(切到千姬还拿不知火的家纹念不知火的词)", file=form,
         edits=[(form, b"            => speaker.Length > 0 && pet.Length > 0 && speaker == pet;",
                 b"            => true; // \xe8\xa7\x92\xe8\x89\xb2\xe9\x82\xa3\xe4\xb8\x80\xe6\x89\x87\xe9\x97\xa8\xe6\x8b\xbf\xe6\x8e\x89")],
         expect="台词池说的是谁"),
    dict(name="名表和池子的说话人漂一个字(气泡静悄悄再也不弹)", file=names,
         # PetNames.cs 是 UTF-8+BOM+CRLF, 中文按字节拼进锚点 —— b'…' 里塞不下非 ASCII
         edits=[(names, b'            ["buzhihuo_1127"] = "' + "不知火".encode() + b'",',
                 b'            ["buzhihuo_1127"] = "' + "不知火君".encode() + b'",')],
         expect="和角色名表里的写法对得上"),

    # —— 2026-11-03 新增角色蟹姬: 第 22 条(托盘「切换角色」那几行渲染成中文名)反向验两条 ——
    # A: 名表漏掉蟹姬 —— 名表那条和真展开菜单那条一起红(那一行掉回拼音 stem)
    dict(name="名表漏掉蟹姬(托盘那一行掉回拼音 stem)", file=names,
         edits=[(names, b'            ["xieji_0481"] = "' + "蟹姬".encode() + b'",\r\n', b"")],
         expect="名表把四只都翻成中文"),
    # B: 名表还在, 但托盘那几行绕过名表直接拿文件名当标题 —— 只有真展开菜单那条红,
    #    名表那条照绿。这条证明第 22 条量的是「菜单渲染的现场」, 不是名表自己查自己
    dict(name="托盘那几行绕过名表直接用文件名(渲染出拼音 stem)", file=menu_form,
         # ConfigForm.cs 是 GBK, 但这个调用点是纯 ASCII, 按字节替换不碰中文
         edits=[(menu_form, b"PetName(spine.GetSpineSkelPath(slot))",
                 b"System.IO.Path.GetFileNameWithoutExtension(spine.GetSpineSkelPath(slot))")],
         expect="真展开一次菜单"),
]


def find_spot(alpha, side, w, h):
    """在全透明区里找一块放得下 side 见方、且四周一圈也不碰本体的地方 —— 贴着本体贴会连成一坨, 那验的就不是「多一块」"""
    for y in range(1, h - side - 1, 2):
        for x in range(1, w - side - 1, 2):
            box = alpha.crop((x - 1, y - 1, x + side + 1, y + side + 1))
            if max(box.get_flattened_data()) <= 24:
                return x, y
    return None


def dirty_bubble():
    """在本体的透明空档里添一枚独立碎片。要的量级: 占本体 1.5%~14% ——
    小于 15% 才让「有分量的连通块」那条旧门槛抓不住(它就是这个洞), 大于 1% 才能把 99% 那条压红"""
    from PIL import Image
    im = Image.open(res_bubble).convert("RGBA")
    alpha = im.getchannel("A")
    body = sum(1 for a in alpha.get_flattened_data() if a > 24)
    for side in (48, 40, 32, 26):
        pct = 100.0 * side * side / body
        if not (1.5 <= pct < 15):
            continue
        spot = find_spot(alpha, side, im.width, im.height)
        if spot is None:
            continue
        x, y = spot
        im.paste(Image.new("RGBA", (side, side), (200, 30, 30, 255)), (x, y))
        im.save(res_bubble, "PNG")
        share, blobs = measure(res_bubble)
        if blobs < 2 or share >= 99:
            raise SystemExit(f"脏图没做出第二坨(blobs={blobs} share={share}%) —— 这条反向验不能假绿")
        return (f"本体 {body} 格墨, 在 ({x},{y}) 添一块 {side}x{side}={side * side} 格(占本体 {pct:.1f}%) "
                f"→ 最大那一块只剩 {share}%, 连通块 {blobs} 个")
    raise SystemExit("找不到一块放得下的透明空档, 或没有哪档尺寸落在 1.5%~14% —— 换尺寸再跑")


def measure(p):
    """和判据同一套算法: 4 邻域连通块, 返回 (最大那一块占全图墨的整数百分比, 块数)"""
    from PIL import Image
    im = Image.open(p).convert("RGBA")
    w, h = im.width, im.height
    a = im.getchannel("A").load()
    seen = [[False] * w for _ in range(h)]
    sizes = []
    for y in range(h):
        for x in range(w):
            if seen[y][x] or a[x, y] <= 24:
                continue
            stack, n = [(x, y)], 0
            seen[y][x] = True
            while stack:
                px, py = stack.pop()
                n += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < w and 0 <= ny < h and not seen[ny][nx] and a[nx, ny] > 24:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            sizes.append(n)
    total = sum(sizes)
    return (100 * max(sizes) // total if total else 0), len(sizes)


def reinstall():
    """按当前(已被打补丁的)装机参数真跑一遍装机, 返回这趟的 stdout"""
    r = run(["python", str(installer)], 600, assets)
    if "装到" not in r:
        raise SystemExit("装机脚本没跑成 —— 这条反向验不能假绿:\n" + r[-800:])
    return r


before = {p: sha(p) for p in FILES}
only = sys.argv[1:]
if only:
    cases = [c for c in cases if any(k in c["name"] for k in only)]
    if not cases:
        raise SystemExit("没有哪条名字对得上: " + " ".join(only))
report = ["反向验台词气泡" + ("(补跑 " + " ".join(only) + ")" if only else "") + ": "
          + "  ".join(f"{p.name}={s}" for p, s in before.items()), ""]
print("跑之前: " + "  ".join(f"{p.name}={s}" for p, s in before.items()))

dirty_note = ""
for c in cases:
    p = c["file"]
    bak = {f: f.read_bytes() for f in FILES}
    try:
        for f, old, new in c["edits"]:
            got = f.read_bytes().count(old)
            assert got == 1, f"{c['name']}: 锚点在 {f.name} 里命中 {got} 次"
            f.write_bytes(f.read_bytes().replace(old, new, 1))
        note = ""
        if c.get("dirty"):
            dirty_note = dirty_bubble()
            note = f"\n      脏图: {dirty_note}"
        elif c.get("install"):
            got = reinstall()
            line = [l for l in got.splitlines() if "染金" in l or "金线" in l]
            note = "\n      装机自报: " + " / ".join(x.strip() for x in line)[:300]
        red, marks, boom, _ = desk()
        hit = [m for m in marks if c["expect"] in m]
        if boom:
            verdict = "跑不起来: " + boom
        else:
            verdict = ("红了, 点的就是这一条" if red and hit else
                       ("红了但没点到这一条" if red else "没红 ← 这条判据没牙"))
        if c.get("dirty"):
            weak = [m for m in marks if "有分量的连通块" in m]
            note += (f"\n      旧的 15% 门槛{'也跟着红了' if weak else '没红 —— 碎片要占到最大那一块的 15% 才算一坨, 半截的邻格从它眼底过'}"
                     f", 新加的比例那条{'红了' if hit else '没红'}")
        print(f"  [{verdict}] {c['name']}")
        for m in marks:
            print("      " + m[:180])
        report.append(f"### {c['name']}\n  期望点名: {c['expect']}\n  结论: {verdict}{note}\n"
                      + "\n".join(marks) + "\n")
    finally:
        for f, data in bak.items():
            f.write_bytes(data)   # 图是被装机脚本重写的, 按备份还原成跑之前那一份字节
        bad = [f.name for f in FILES if sha(f) != before[f]]
        if bad:
            report.append(f"  !! {', '.join(bad)} 还原后哈希对不上")
            print(f"  !! {', '.join(bad)} 还原后哈希对不上")

after = {p: sha(p) for p in FILES}
same = all(before[p] == after[p] for p in FILES)
clean = ""
if same:
    _, marks, boom, d = desk()
    clean = "DESK OK" if "DESK OK" in d and not boom else "还红着: " + " | ".join(marks) + ("" if not boom else " " + boom)
print("\n还原: " + ("逐字节一致" if same else "对不上!") + " · 还原后复跑: " + clean[:300])
report.append(f"\n还原: {'逐字节一致' if same else '哈希对不上'} · 还原后复跑: {clean}")
text = "\n".join(report)
old = log.read_text(encoding="utf-8").rstrip() + "\n\n" if only and log.exists() else ""
log.write_text(old + text, encoding="utf-8")
print("日志: " + str(log))
sys.exit(0 if same and clean == "DESK OK" else 1)
