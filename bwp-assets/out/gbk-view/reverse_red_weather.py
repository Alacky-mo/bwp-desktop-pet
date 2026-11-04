"""反向验第 23/24 条(功能菜单 + 天气卡片): 把 bug 一个个放回去, 看它会不会红。

每条: 备份字节 → 按字节改源码 → 建到 out/reverse-build/ → 跑 desk → 看点名的是不是这一条 → 还原。
源码一律按字节替换, 不读成文本再写回 —— WeatherService/PetMenuForm/WeatherForm 是 UTF-8+BOM+LF,
ConfigForm.cs 是 GBK+CRLF, 文本往返会把换行和中文一起改掉, 那就不是「还原」了。
锚点里带中文的一律用 "…".encode() 拼(b'…' 里塞不下非 ASCII)。

产物日志 out/reverse-red-weather.txt。跑完所有文件都必须和跑之前逐字节同哈希, 否则脚本自己报错。
"""
import hashlib
import os
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

view = pathlib.Path(__file__).parent
root = view.parents[2]
assets = root / "bwp-assets"
out = assets / "out"
src = root / "deskspine" / "DeskSpine" / "src"
svc = src / "WeatherService.cs"
menu = src / "PetMenuForm.cs"
card = src / "WeatherForm.cs"
cform = src / "ConfigForm.cs"          # GBK+CRLF —— 只动纯 ASCII 那一句, 不碰中文
preset = src / "FocusPresetForm.cs"    # 三扇小框对齐用的那把尺就写在这一份里
names = src / "PetNames.cs"            # 托盘上的中文名对照表 —— 她那档认的名字要和这一份一模一样
gate = assets / "animator-test" / "bin" / "Release" / "net8.0-windows" / "bwp-animator-test.exe"
build_dir = out / "reverse-build"
target = str(build_dir / "x64" / "Release" / "net8.0-windows" / "win-x64" / "DeskSpine.dll")
log = out / "reverse-red-weather.txt"

FILES = [svc, menu, card, cform, preset, names]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()[:12]


def run(cmd, timeout, cwd):
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    r = subprocess.run(cmd, capture_output=True, timeout=timeout, cwd=str(cwd), env=env)
    return (r.stdout + r.stderr).decode("utf-8", errors="replace")


def desk():
    """建 + 跑, 返回 (整份红了吗, 点名行(✗ 行和「: 否」那几层), 建/跑本身有没有炸, 原文)"""
    b = run(["dotnet", "build", str(root / "deskspine" / "DeskSpine.sln"), "-c", "Release",
             "-v", "q", "--nologo", f"-p:BaseOutputPath={build_dir.as_posix()}/"], 900, root)
    if "0 个错误" not in b:
        return (False, [], "建不过: " + b.strip()[-400:], b)
    d = run([str(gate), "desk", target], 300, assets)
    if "DESK" not in d:
        return (False, [], "gate 没吐出结果: " + d.strip()[-400:], d)
    lines = d.splitlines()
    marks = [l.strip() for l in lines if l.strip().startswith("✗") or ": 否" in l]
    red = any(": 否" in l for l in lines)
    return (red, marks, None, d)


cases = [
    # —— 换算表: 每一格都是「接口改口 / 少抄一条」时界面上真会看到的形状 ——
    dict(name="WMO 表漏掉 code 3(阴转那天板上写「其他天象」)", file=svc,
         edits=[(svc, b'            [3] = "' + "阴".encode() + b'",\n', b"")],
         expect="28 个 WMO 码逐条对中文"),
    dict(name="八方位表里南和西南挪了一格(风把西南念成南)", file=svc,
         edits=[(svc, "北\", \"东北\", \"东\", \"东南\", \"南\", \"西南".encode(),
                 "北\", \"东北\", \"东\", \"东南\", \"西南\", \"南".encode())],
         expect="八方位"),
    dict(name="温度取整读成向下(12.6° 写成 12°)", file=svc,
         edits=[(svc, b"(int)Math.Round(c, MidpointRounding.AwayFromZero)", b"(int)Math.Floor(c)")],
         expect="温度取整朝外走"),
    dict(name="读数缓存永不过期(半小时内不联网变成永远不联网)", file=svc,
         edits=[(svc, b"            return age >= TimeSpan.Zero && age < TimeSpan.FromMinutes(ttlMinutes);",
                 b"            return true;")],
         expect="缓存新不新"),

    # —— 解析: 少字段该点名, 不许抛; 端点不许走明文 ——
    dict(name="daily 少一项时抛出去(整扇窗停在「读取中…」没影了)", file=svc,
         edits=[(svc, b"            if (Child(parent, key) is not JsonArray list || list.Count == 0) return null;",
                 b"            if (Child(parent, key) is not JsonArray list || list.Count == 0)"
                 + b" throw new InvalidOperationException(" + '"没有这一组"'.encode() + b");")],
         expect="没有一个抛"),
    dict(name="主力 IP 源退回明文 http(大致位置出门不加密)", file=svc,
         edits=[(svc, b'{ "https://ipwho.is/"', b'{ "http://ipwho.is/"')],
         expect="四个端点全 HTTPS"),

    # —— 功能菜单: 一张表一个去向 ——
    dict(name="第二行的去向写成番茄钟(点「查看天气」开的是小窗)", file=menu,
         edits=[(menu, b'(Door.Weather, "' + "查看天气".encode() + b'"),',
                b'(Door.Pomodoro, "' + "查看天气".encode() + b'"),')],
         expect="第一行去番茄钟, 第二行去天气"),
    dict(name="两行顺序对调(画和打靶都跟着换, 用户点的和看到的不是同一行)", file=menu,
         edits=[(menu, b'            (Door.Pomodoro, "' + "番茄钟".encode() + b'"),\n'
                     b'            (Door.Weather, "' + "查看天气".encode() + b'"),',
                b'            (Door.Weather, "' + "查看天气".encode() + b'"),\n'
                b'            (Door.Pomodoro, "' + "番茄钟".encode() + b'"),')],
         expect="这张表就两行, 顺序和字都对"),

    # —— 天气卡版面与仲裁: 只有真造窗口才抓得住的那两条 ——
    dict(name="当前读数那行没大一号(「一眼要看的那一行」和正文一样粗)", file=card,
         edits=[(card, b"heroFont = new(SystemFonts.MessageBoxFont!.FontFamily, 26f",
                 b"heroFont = new(SystemFonts.MessageBoxFont!.FontFamily, 17f")],
         expect="当前读数那一行确实大一号也真粗"),
    dict(name="天气卡上桌时不让番茄钟(两张板叠在同一块地方)", file=card,
         edits=[(card, b"            Program.PetMenu?.Yield();\n            Program.FocusPreset?.Yield();\n",
                 b"            Program.PetMenu?.Yield();\n")],
         expect="菜单和番茄钟都让干净"),

    # —— 配置六段: 新那一段在设置窗里也会被「默认值顶掉」这个洞 ——
    dict(name="设置窗没把定位缓存带回来(每次重开都要重新问一趟 IP)", file=cform,
         edits=[(cform, b"v.WeatherConfig = keptWeather;", b"v.WeatherConfig = new();")],
         expect="配置全键往返"),

    # —— 2026-11-03 用户拍「三扇小框整体长度一致，都和番茄钟一样，延长的部分暂时空白」——
    # 这四条各打一个新判据的一角：两张板各自缩回去、尺子被抄死、行被摊开
    dict(name="功能菜单退回按两行数高度(比番茄钟矮一截)", file=menu,
         edits=[(menu, b"new Rectangle(0, 0, panelWidth, Math.Max(y - Gap + PadY, FocusPresetForm.PanelHeight(panelWidth)))",
                 b"new Rectangle(0, 0, panelWidth, y - Gap + PadY)")],
         expect="高跟番茄钟那张板同一个数"),
    dict(name="天气卡退回按四行数高度(238, 和三扇窗不一样长)", file=card,
         edits=[(card, b"new Rectangle(0, 0, panelWidth, Math.Max(y - Gap + PadY, FocusPresetForm.PanelHeight(panelWidth)))",
                 b"new Rectangle(0, 0, panelWidth, y - Gap + PadY)")],
         expect="面板高跟番茄钟那张板同一个数"),
    dict(name="对齐那把尺被抄死成 200(Presets 增减行数就跟着漂)", file=preset,
         edits=[(preset, b"internal static int PanelHeight(int panelWidth) => Arrange(Presets, panelWidth).Panel.Height;",
                 b"internal static int PanelHeight(int panelWidth) => 200;")],
         expect="同一个数"),
    # 这条只挪第一行的起点, 面板高度那条照旧绿 —— 证明「空白只许留在底下」量的是行的落点, 不是板子大小
    dict(name="两行整块往下坠 100(空白跑到顶上来了)", file=menu,
         edits=[(menu, b"            var y = TitleY + TitleH + Gap;", b"            var y = TitleY + TitleH + Gap + 100;")],
         expect="空白只许留在底下"),

    # —— 2026-11-03「天气改成今日天气」那两条(标题 + 三行建议里的行数, 已被下面那一轮改成一句话) ——
    dict(name="标题轮·标题退回「天气」(用户点名要的是今日天气)", file=card,
         edits=[(card, b'internal const string Caption = "' + "今日天气".encode() + b'";',
                 b'internal const string Caption = "' + "天气".encode() + b'";')],
         expect="标题那四个字是「今日天气」"),

    # —— 2026-11-03 用户拍「换成一句话 + 只有不知火用她的腔 + 折两行」这一轮的新判据 ——
    # 每条只放回去一个洞, 看点名的是不是该它的那一条
    dict(name="一句话轮·雨码漏了 82(暴雨那天板上念的是别的那句)", file=svc,
         edits=[(svc, b"        private static readonly int[] RainCodes = "
                      b"{ 51, 53, 55, 61, 63, 65, 80, 81, 82 };",
                 b"        private static readonly int[] RainCodes = { 51, 53, 55, 61, 63, 65, 80, 81 };")],
         expect="28 个 WMO 码在建议这一侧也各有归属"),
    dict(name="一句话轮·穿衣只看当前温度(最低 5° 的中午天教人穿透气的)", file=svc,
         edits=[(svc, b"Math.Min(c.TempC, c.LowC) switch", b"c.TempC switch")],
         expect="穿衣按当前温度和今日最低里更低的那个"),
    dict(name="一句话轮·风大那档提到 7 级(6 级大风还说适合出门走走)", file=svc,
         edits=[(svc, b"            if (c.WindGrade >= 6) return ", b"            if (c.WindGrade >= 7) return ")],
         expect="一句话只说按优先级挑出来的那件"),
    dict(name="一句话轮·语域门拆了(谁在屏幕上都说她那口吻)", file=svc,
         edits=[(svc, b"            => pet == Shiranui ? HerNote(PickNote(c)) : NeutralNote(PickNote(c));",
                 b"            => HerNote(PickNote(c));")],
         expect="只有不知火用她的腔"),
    dict(name="一句话轮·代码里她的名字漂一个字(名表「不知火」, 代码「不知伙」)", file=svc,
         edits=[(svc, b'internal const string Shiranui = "' + "不知火".encode() + b'";',
                 b'internal const string Shiranui = "' + "不知伙".encode() + b'";')],
         expect="她那一档认的就是托盘名表里那三个字"),
    dict(name="一句话轮·名表里她改叫「不知火姬」(两头对不上就永远只念中性)", file=names,
         edits=[(names, b'["buzhihuo_1127"] = "' + "不知火".encode() + b'",',
                 b'["buzhihuo_1127"] = "' + "不知火姬".encode() + b'",')],
         expect="她那一档认的就是托盘名表里那三个字"),
    dict(name="一句话轮·她那档抄成中性那句(换了腔等于没换)", file=svc,
         edits=[(svc, b'            Note.Thunder => "' + "要落雷了，别在空旷处站着呢".encode() + b'",',
                 b'            Note.Thunder => "' + "雷阵雨，躲开空旷处".encode() + b'",')],
         expect="各有一句、且两档不同字"),
    dict(name="一句话轮·她那句漏配成空(板上凭空少一行字)", file=svc,
         edits=[(svc, b'            Note.Rain => "' + "出门把那把伞带上，别淋着了".encode() + b'",',
                 b'            Note.Rain => "",')],
         expect="整片扫过去两档都不出空句也不抛"),
    dict(name="一句话轮·前缀又写回板上(用户 2026-11-03 要的是不罗列)", file=svc,
         edits=[(svc, b"            => pet == Shiranui ? HerNote(PickNote(c)) : NeutralNote(PickNote(c));",
                 b'            => "' + "出行：".encode()
                 + b'" + (pet == Shiranui ? HerNote(PickNote(c)) : NeutralNote(PickNote(c)));')],
         expect="没有「出行：」这种前缀"),
    dict(name="一句话轮·她那句写成 22 字(顶破「她 ≤16」那一档)", file=svc,
         edits=[(svc, b'            Note.Windy => "' + "风这样大，帽子收好，别叫它吹跑了".encode() + b'",',
                 b'            Note.Windy => "' + "风这样大，帽子替我收好，千万别叫它一路吹到河对岸去呢".encode() + b'",')],
         expect="两档各最长几个字"),
    dict(name="一句话轮·她那句写成 34 字(折成三行, 那一格真 GDI+ 装不下)", file=svc,
         edits=[(svc, b'            Note.Fog => "' + "起了雾，你看不远，今天就少开车".encode() + b'",',
                 b'            Note.Fog => "' + "起了雾, 你看不远, 今天要是没什么要紧事就别开车了, 留在家里喝杯茶吧"
                 .encode() + b'",')],
         expect="都真拿 GDI+ 折过"),

    # —— 同一轮的接线那几条：折行、许不许折、那一行接没接上 ——
    dict(name="一句话轮·LinesOf 底下那一行没接上(那截空白还是空的)", file=card,
         edits=[(card, b"                new Line(WeatherService.AdviceSentence(c, pet), Face.Body, Wrap: true),\n", b"")],
         expect="读到五行"),
    dict(name="一句话轮·那句没挂许它折的标记(板子为它变宽, 撞破等宽那条约定)", file=card,
         edits=[(card, b"AdviceSentence(c, pet), Face.Body, Wrap: true)",
                 b"AdviceSentence(c, pet), Face.Body, Wrap: false)")],
         expect="那句建议不参与开宽"),
    dict(name="一句话轮·折行不看那个标记(读数那四行也被切开)", file=card,
         edits=[(card, b"                if (!line.Wrap)\n", b"                if (line.Wrap && !line.Wrap)\n")],
         expect="折行只折许它折的那几行"),
    dict(name="一句话轮·折行把断点那一字吞了(板上少半句)", file=card,
         edits=[(card, b"                        rows.Add(new Line(cur, line.Face));\n                        cur = ch.ToString();",
                 b"                        rows.Add(new Line(cur, line.Face));\n                        cur = \"\";")],
         expect="拼回去一字不差"),
]


before = {p: sha(p) for p in FILES}
only = sys.argv[1:]
if only:
    cases = [c for c in cases if any(k in c["name"] for k in only)]
    if not cases:
        raise SystemExit("没有哪条名字对得上: " + " ".join(only))
report = ["反向验功能菜单 + 天气卡片" + ("(补跑 " + " ".join(only) + ")" if only else "") + ": "
          + "  ".join(f"{p.name}={s}" for p, s in before.items()), ""]
print("跑之前: " + "  ".join(f"{p.name}={s}" for p, s in before.items()))

for c in cases:
    bak = {f: f.read_bytes() for f in FILES}
    try:
        for f, old, new in c["edits"]:
            data = f.read_bytes()
            got = data.count(old)
            assert got == 1, f"{c['name']}: 锚点在 {f.name} 里命中 {got} 次"
            f.write_bytes(data.replace(old, new, 1))
        red, marks, boom, _ = desk()
        hit = [m for m in marks if c["expect"] in m]
        if boom:
            verdict = "跑不起来: " + boom
        else:
            verdict = ("红了, 点的就是这一条" if red and hit else
                       ("红了但没点到这一条: " + " | ".join(m[:90] for m in marks) if red else "没红 ← 这条判据没牙"))
        print(f"  [{verdict}] {c['name']}")
        for m in marks:
            print("      " + m[:200])
        report.append(f"### {c['name']}\n  期望点名: {c['expect']}\n  结论: {verdict}\n"
                      + "\n".join(marks) + "\n")
    finally:
        for f, data in bak.items():
            f.write_bytes(data)
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
