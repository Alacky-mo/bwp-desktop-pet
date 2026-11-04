# 番茄钟语义这一轮的 GBK 接线: 两处 Program.cs + 五处 ConfigForm.cs, 一次生成锚点并逐个套
# 规矩和 make_focus_edits.py 一样: 每处锚点必须只命中一次, 全用 utf-8 写锚点, 落盘仍是 gbk + CRLF
import pathlib

view = pathlib.Path(__file__).resolve().parent
root = view.parents[2]
PROG = root / "deskspine/DeskSpine/src/Program.cs"
FORM = root / "deskspine/DeskSpine/src/ConfigForm.cs"

EDITS = [
    # ---- Program.cs: 配置那一份推给引擎 ----
    (PROG, "p10-apply-focus", """            focus.BlockSleepWhileWorking = value.BlockSleepWhileWorking;
            ConfigForm.FocusBalloon = value.BalloonOnPhaseChange;""", """            focus.BlockSleepWhileWorking = value.BlockSleepWhileWorking;
            focus.AutoStartBreak = value.AutoStartBreak;
            focus.AutoStartWork = value.AutoStartWork;
            ConfigForm.FocusBalloon = value.BalloonOnPhaseChange;"""),

    # ---- Program.cs: CurrentConfig 的 getter 是 new Config() 现攒的, 没控件的键要现读回去 ----
    (PROG, "p11-current-config-readback", """                config.PomodoroConfig.BlockSleepWhileWorking = focus.BlockSleepWhileWorking;
                config.PomodoroConfig.BalloonOnPhaseChange = ConfigForm.FocusBalloon;""", """                config.PomodoroConfig.BlockSleepWhileWorking = focus.BlockSleepWhileWorking;
                // 这两个开关设置窗上没有控件, 从引擎现读: 漏一行就是「存得进去、读不出来」(desk 第 16 条咬这个)
                config.PomodoroConfig.AutoStartBreak = focus.AutoStartBreak;
                config.PomodoroConfig.AutoStartWork = focus.AutoStartWork;
                config.PomodoroConfig.BalloonOnPhaseChange = ConfigForm.FocusBalloon;"""),

    # ---- ConfigForm.cs: 没有控件的键靠原样带回, 形状照 keptActiveSlot ----
    (FORM, "c19-kept-auto-fields", """        private int keptActiveSlot = -1;""", """        private int keptActiveSlot = -1;

        /// <summary>
        /// 番茄钟那两个「到点自己串下一段」的开关。这轮只补语义、界面一个字没动, 所以设置窗上没有它们的控件,
        /// 和 keptActiveSlot 同一个形状: 全靠原样带回, 否则 getter 拿 new Config() 的默认值把用户手改的 JSON 顶掉。
        /// 只兜没有控件的那两键、不整段带回 —— 整段带回会让「越界时长夹得住」那条判据退化
        /// </summary>
        private bool keptAutoBreak = true;
        private bool keptAutoWork = true;"""),

    (FORM, "c20-value-get", """                v.PomodoroConfig.BalloonIconPath = FocusBalloonIconPath;""", """                v.PomodoroConfig.BalloonIconPath = FocusBalloonIconPath;
                v.PomodoroConfig.AutoStartBreak = keptAutoBreak;
                v.PomodoroConfig.AutoStartWork = keptAutoWork;"""),

    (FORM, "c21-value-set", """                FocusBalloonIconPath = value.PomodoroConfig.BalloonIconPath;""", """                FocusBalloonIconPath = value.PomodoroConfig.BalloonIconPath;
                keptAutoBreak = value.PomodoroConfig.AutoStartBreak;
                keptAutoWork = value.PomodoroConfig.AutoStartWork;"""),

    # ---- ConfigForm.cs: 托盘那一行状态字多念「本轮 N/M」; 浮窗和小窗的版面不动 ----
    (FORM, "c22-focus-text-round", """        internal static string FocusText(TinyEngine.PomodoroPhase phase, bool paused, TimeSpan remaining, int completed)
        {
            if (phase == TinyEngine.PomodoroPhase.Off) return $"没在计时 · 今日 {completed}";
            // 不能用 @"mm\\:ss": 那是「分」这一位(0..59), 而时长上限给到 180 —— 两小时会读成 00:00
            var left = $"{(int)remaining.TotalMinutes:00}:{remaining.Seconds:00}";
            return $"{(paused ? "已暂停" : FocusPhaseName(phase))} 剩 {left} · 今日 {completed}";
        }""", """        internal static string FocusText(TinyEngine.PomodoroPhase phase, bool paused, TimeSpan remaining,
                                         int completed, int round, int rounds)
        {
            if (phase == TinyEngine.PomodoroPhase.Off) return $"没在计时 · 今日 {completed}";
            // 不能用 @"mm\\:ss": 那是「分」这一位(0..59), 而时长上限给到 180 —— 两小时会读成 00:00
            var left = $"{(int)remaining.TotalMinutes:00}:{remaining.Seconds:00}";
            // 「本轮第几段」只进这一行文字: 这轮先补语义, 浮窗和小窗的版面一个字没动(用户拍板)
            return $"{(paused ? "已暂停" : FocusPhaseName(phase))} 剩 {left} · 本轮 {round}/{rounds} · 今日 {completed}";
        }"""),

    (FORM, "c23-tray-call-site", """                FocusText(focus.Phase, focus.IsPaused, focus.Remaining, focus.CompletedToday)) { Enabled = false });""", """                FocusText(focus.Phase, focus.IsPaused, focus.Remaining, focus.CompletedToday,
                          focus.WorkRoundNumber, focus.RoundsPerLongBreak)) { Enabled = false });"""),
]


def clip(s):
    return '\r\n' + s.replace('\r\n', '\n').replace('\n', '\r\n')


texts = {}
for target, name, find, repl in EDITS:
    key = str(target)
    text = texts.get(key) or open(target, 'rb').read().decode('gbk')
    f, r = clip(find), clip(repl)
    hits = text.count(f)
    assert hits == 1, f'{name}: 锚点命中 {hits} 次, 要求 1 次'
    texts[key] = text.replace(f, r)
    (view / f'{name}-find.txt').write_text(find, encoding='utf-8', newline='\n')
    (view / f'{name}-repl.txt').write_text(repl, encoding='utf-8', newline='\n')
    print(f'OK {name}')

for key, text in texts.items():
    data = text.encode('gbk')
    open(key, 'wb').write(data)
    back = open(key, 'rb').read().decode('gbk')
    print(f'{pathlib.Path(key).name}: bom={data[:3] == b"\\xef\\xbb\\xbf"} crlf={data.count(bytes([13, 10]))} '
          f'bare-LF={data.count(bytes([10])) - data.count(bytes([13, 10]))} 解得回来={back == text}')
