"""台词气泡这轮的 GBK 侧接线：Program.cs 的活体配置 + ConfigForm.cs 的节拍复用和托盘「台词」。

和 make_focus_edits.py 同一套走法 —— 锚点必须在目标里唯一命中，apply.py 自己 assert 停下。
"""
import pathlib
import subprocess
import sys

view = pathlib.Path(__file__).parent
root = view.parents[2]
target_program = root / "deskspine/DeskSpine/src/Program.cs"
target_form = root / "deskspine/DeskSpine/src/ConfigForm.cs"

edits = []


def edit(name, target, find, repl):
    f = view / f"dlg-{name}-find.txt"
    r = view / f"dlg-{name}-repl.txt"
    f.write_text(find, encoding="utf-8")
    r.write_text(repl, encoding="utf-8")
    edits.append((target, f, r))


# ---- Program.cs ----
edit("p1-fields", target_program, """\
        public static FocusPresetForm FocusPreset { get; private set; }                     // 番茄钟预设小窗, 开在宠物边上
        public static ConfigForm ConfigForm { get; private set; }                           // 设置窗口 (主窗口)
""", """\
        public static FocusPresetForm FocusPreset { get; private set; }                     // 番茄钟预设小窗, 开在宠物边上
        public static DialogBubbleForm DialogBubble { get; private set; }                   // 台词气泡, 也贴宠物右侧
        public static DialogConfig Dialog { get; private set; } = new();                    // 台词气泡那段设置的活体: 节拍每秒读它, 不碰磁盘
        public static ConfigForm ConfigForm { get; private set; }                           // 设置窗口 (主窗口)
""")

edit("p2-construct", target_program, """\
            FocusPreset = new FocusPresetForm();
""", """\
            FocusPreset = new FocusPresetForm();
            DialogBubble = new DialogBubbleForm();
""")

edit("p3-geometry", target_program, """\
            SpineWindow.GeometryChanged += FocusPreset.OnGeometryChanged;
            ConfigForm = new ConfigForm();
""", """\
            SpineWindow.GeometryChanged += FocusPreset.OnGeometryChanged;
            SpineWindow.GeometryChanged += DialogBubble.OnGeometryChanged;
            ConfigForm = new ConfigForm();
""")

edit("p4-readback", target_program, """\
                config.PomodoroConfig.BalloonIconPath = ConfigForm.FocusBalloonIconPath;

                return config;
""", """\
                config.PomodoroConfig.BalloonIconPath = ConfigForm.FocusBalloonIconPath;

                // 台词气泡整节就是活体 Dialog。漏这一行 = 「配了丢进去」, 下次装载把它抹平
                config.DialogConfig = Dialog;

                return config;
""")

edit("p5-apply-in-setter", target_program, """\
                ApplyFocus(value.PomodoroConfig);
                // 缩放、骨骼位置、出场槽位和刚装上的骨骼都动过包围盒, 头顶锚点要重算一次才跟得上
""", """\
                ApplyFocus(value.PomodoroConfig);
                Dialog = value.DialogConfig;
                // 缩放、骨骼位置、出场槽位和刚装上的骨骼都动过包围盒, 头顶锚点要重算一次才跟得上
""")

edit("p6-apply-in-init", target_program, """\
            ApplyFocus(value.PomodoroConfig);
            // 骨骼是这一刻才有的, 头顶锚点得重算一次, 不然浮窗停在「还没有包围盒」那份快照上
""", """\
            ApplyFocus(value.PomodoroConfig);
            Dialog = value.DialogConfig;
            // 骨骼是这一刻才有的, 头顶锚点得重算一次, 不然浮窗停在「还没有包围盒」那份快照上
""")

# ---- ConfigForm.cs ----
edit("c1-field", target_form, """\
        private ToolStripMenuItem commandFocus = new("番茄钟");
""", """\
        private ToolStripMenuItem commandFocus = new("番茄钟");
        private ToolStripMenuItem commandDialog = new("台词");
""")

edit("c2-ctor-menu", target_form, """\
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandPets);
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandFocus);
""", """\
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandPets);
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandFocus);
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandDialog);
""")

edit("c3-opening", target_form, """\
            RefreshPetMenu(Program.SpineWindow.Spine.ActiveSlot);
            RefreshFocusMenu();
""", """\
            RefreshPetMenu(Program.SpineWindow.Spine.ActiveSlot);
            RefreshFocusMenu();
            RefreshDialogMenu();
""")

edit("c4-tick", target_form, """\
            Program.FocusPreset.OnFocusTick();          // 小窗开着时那句「先停一下/继续」也得跟着阶段走
""", """\
            Program.FocusPreset.OnFocusTick();          // 小窗开着时那句「先停一下/继续」也得跟着阶段走
            Program.DialogBubble.OnTick();              // 台词气泡吃同一只节拍: 亮几十秒自己收, 空一段再冒下一条
""")

edit("c5-dialog-menu", target_form, """\
        private static ToolStripMenuItem FocusItem(string text, Action act, bool enabled)
""", """\
        /// <summary>
        /// 托盘「台词」: 一个开关 + 立刻换一条。
        /// 停留和空闲的秒数没做控件 —— 只有这一处要调节奏, 改 config.json 的 DialogConfig.ShowSeconds /
        /// GapSeconds 就行, 下次启动生效。开关是活体那份, 点完马上写盘, 不等 5 分钟那趟定时保存
        /// </summary>
        private void RefreshDialogMenu()
        {
            var dialog = Program.Dialog;
            commandDialog.DropDownItems.Clear();

            var toggle = new ToolStripMenuItem("台词气泡") { Checked = dialog.Enabled };
            toggle.Click += (object? s, EventArgs e) =>
            {
                dialog.Enabled = !dialog.Enabled;
                Program.LocalConfig = Program.CurrentConfig;
                Program.DialogBubble.OnTick();      // 关了立刻收、开了立刻数, 不等下一拍
            };
            commandDialog.DropDownItems.Add(toggle);
            commandDialog.DropDownItems.Add(new ToolStripSeparator());
            commandDialog.DropDownItems.Add(FocusItem("换一条", () => Program.DialogBubble.ShowNow(), dialog.Enabled));
        }

        private static ToolStripMenuItem FocusItem(string text, Action act, bool enabled)
""")

for target, find, repl in edits:
    r = subprocess.run([sys.executable, str(view / "apply.py"), str(target), str(find), str(repl)],
                       capture_output=True, text=True)
    print(("OK  " if r.returncode == 0 else "FAIL") + f" {find.stem:26} {r.stdout.strip()} {r.stderr.strip()}")
