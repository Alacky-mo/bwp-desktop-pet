"""一次性写出番茄钟这轮用到的 GBK 锚点/替换对, 然后交给 apply.py 套。

find/repl 用 UTF-8 落盘 (apply.py 会读它们再把目标文件按 GBK 写回去),
这里只负责把内容写准 —— 锚点必须在目标里唯一命中, 否则 apply.py 自己 assert 停下。
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
    f = view / f"{name}-find.txt"
    r = view / f"{name}-repl.txt"
    f.write_text(find, encoding="utf-8")
    r.write_text(repl, encoding="utf-8")
    edits.append((target, f, r))


# ---- Program.cs: 配置 ↔ 引擎/托盘 三份参数一次推过去 ----
edit("p4-focus-readback", target_program, """\
                for (int i = 0; i < SpineConfig.SlotCount; i++)
                {
                    config.SpineConfig.SetSkelPath(i, SpineWindow.Spine.GetSpineSkelPath(i));
                }

                return config;
""", """\
                for (int i = 0; i < SpineConfig.SlotCount; i++)
                {
                    config.SpineConfig.SetSkelPath(i, SpineWindow.Spine.GetSpineSkelPath(i));
                }

                // 番茄钟设置
                var focus = SpineWindow.Pomodoro;
                config.PomodoroConfig.WorkMinutes = focus.WorkMinutes;
                config.PomodoroConfig.BreakMinutes = focus.BreakMinutes;
                config.PomodoroConfig.LongBreakMinutes = focus.LongBreakMinutes;
                config.PomodoroConfig.CyclesPerLongBreak = focus.CyclesPerLongBreak;
                config.PomodoroConfig.BlockSleepWhileWorking = focus.BlockSleepWhileWorking;
                config.PomodoroConfig.BalloonOnPhaseChange = ConfigForm.FocusBalloon;

                return config;
""")

edit("p5-focus-apply-in-setter", target_program, """\
                SpineWindow.Spine.ActiveSlot = value.SpineConfig.ActiveSlot;

                // 保存本地
""", """\
                SpineWindow.Spine.ActiveSlot = value.SpineConfig.ActiveSlot;
                ApplyFocus(value.PomodoroConfig);

                // 保存本地
""")

edit("p6-focus-apply-helper", target_program, """\
            SpineWindow.Spine.ActiveSlot = value.SpineConfig.ActiveSlot;
        }
    }
}
""", """\
            SpineWindow.Spine.ActiveSlot = value.SpineConfig.ActiveSlot;
            ApplyFocus(value.PomodoroConfig);
        }

        /// <summary>
        /// 番茄钟的时长一份住在引擎一份在配置文件, 这里从配置一次推过去。
        /// 「现在到底有没有在计时」是用户点出来的, 不属于配置, 所以不碰开始/暂停/停止
        /// </summary>
        private static void ApplyFocus(PomodoroConfig value)
        {
            var focus = SpineWindow.Pomodoro;
            focus.WorkMinutes = value.WorkMinutes;
            focus.BreakMinutes = value.BreakMinutes;
            focus.LongBreakMinutes = value.LongBreakMinutes;
            focus.CyclesPerLongBreak = value.CyclesPerLongBreak;
            focus.BlockSleepWhileWorking = value.BlockSleepWhileWorking;
            ConfigForm.FocusBalloon = value.BalloonOnPhaseChange;
        }
    }
}
""")

# ---- ConfigForm.cs: 托盘「番茄钟」一项 + 换阶段气泡 + 设置页读写 ----
edit("c5-focus-fields", target_form, """\
        private ShellNotifyIcon shellNotifyIcon;
        private ToolStripMenuItem commandPets = new("切换角色");
        private System.Timers.Timer hourlyChimeTimer = new(100) { AutoReset = true };
        private bool hasChimed = false;
""", """\
        private ShellNotifyIcon shellNotifyIcon;
        private ToolStripMenuItem commandPets = new("切换角色");
        private ToolStripMenuItem commandFocus = new("番茄钟");
        private System.Timers.Timer hourlyChimeTimer = new(100) { AutoReset = true };
        private System.Timers.Timer focusTimer = new(1000) { AutoReset = true };
        private int focusSeen = 0;
        private bool hasChimed = false;
""")

edit("c6-focus-ctor", target_form, """\
            hourlyChimeTimer.Elapsed += HourlyChimeTimer_Elapsed;

            // 托盘菜单在窗体 Show 之前就要能用, 而 Load 只在第一次显示时触发, 所以插菜单的活放在构造里
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandPets);
""", """\
            hourlyChimeTimer.Elapsed += HourlyChimeTimer_Elapsed;
            focusTimer.Elapsed += FocusTimer_Elapsed;
            focusTimer.Enabled = true;

            // 托盘菜单在窗体 Show 之前就要能用, 而 Load 只在第一次显示时触发, 所以插菜单的活放在构造里
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandPets);
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandFocus);
""")

edit("c7-focus-value-get", target_form, """\
                v.SpineConfig.SkelPath9 = string.IsNullOrEmpty(textBox_SkelPath9.Text) ? null : textBox_SkelPath9.Text;

                return v;
""", """\
                v.SpineConfig.SkelPath9 = string.IsNullOrEmpty(textBox_SkelPath9.Text) ? null : textBox_SkelPath9.Text;

                // 番茄钟设置
                v.PomodoroConfig.WorkMinutes = (int)numericUpDown_FocusWork.Value;
                v.PomodoroConfig.BreakMinutes = (int)numericUpDown_FocusBreak.Value;
                v.PomodoroConfig.LongBreakMinutes = (int)numericUpDown_FocusLongBreak.Value;
                v.PomodoroConfig.CyclesPerLongBreak = (int)numericUpDown_FocusCycles.Value;
                v.PomodoroConfig.BlockSleepWhileWorking = checkBox_FocusBlockSleep.Checked;
                v.PomodoroConfig.BalloonOnPhaseChange = checkBox_FocusBalloon.Checked;

                return v;
""")

edit("c8-focus-value-set", target_form, """\
                textBox_SkelPath9.Text = value.SpineConfig.SkelPath9;
            }
        }
""", """\
                textBox_SkelPath9.Text = value.SpineConfig.SkelPath9;

                // 番茄钟设置: 配置文件改得出超范围的数, NumericUpDown 越界是直接抛异常, 所以先夹再上控件
                static decimal Fit(NumericUpDown box, int minutes) => Math.Clamp(minutes, (int)box.Minimum, (int)box.Maximum);
                numericUpDown_FocusWork.Value = Fit(numericUpDown_FocusWork, value.PomodoroConfig.WorkMinutes);
                numericUpDown_FocusBreak.Value = Fit(numericUpDown_FocusBreak, value.PomodoroConfig.BreakMinutes);
                numericUpDown_FocusLongBreak.Value = Fit(numericUpDown_FocusLongBreak, value.PomodoroConfig.LongBreakMinutes);
                numericUpDown_FocusCycles.Value = Fit(numericUpDown_FocusCycles, value.PomodoroConfig.CyclesPerLongBreak);
                checkBox_FocusBlockSleep.Checked = value.PomodoroConfig.BlockSleepWhileWorking;
                checkBox_FocusBalloon.Checked = value.PomodoroConfig.BalloonOnPhaseChange;
            }
        }
""")

edit("c9-focus-balloon-flag", target_form, """\
        /// <summary>
        /// 整点报时功能
        /// </summary>
        public bool HourlyChime { get => hourlyChimeTimer.Enabled; set => hourlyChimeTimer.Enabled = value; }
""", """\
        /// <summary>
        /// 整点报时功能
        /// </summary>
        public bool HourlyChime { get => hourlyChimeTimer.Enabled; set => hourlyChimeTimer.Enabled = value; }

        /// <summary>
        /// 番茄钟换阶段弹不弹气泡。计时器一直在数阶段变化, 关了只是不弹 ——
        /// 不然重新打开时会补弹一个早就过期的
        /// </summary>
        public bool FocusBalloon { get; set; } = true;
""")

edit("c10-focus-menu-refresh", target_form, """\
            RefreshPetMenu(Program.SpineWindow.Spine.ActiveSlot);
        }
""", """\
            RefreshPetMenu(Program.SpineWindow.Spine.ActiveSlot);
            RefreshFocusMenu();
        }
""")

edit("c11-focus-menu-and-tip", target_form, """\
        private void SwitchPet(int slot)
        {
            var currentConfig = Program.CurrentConfig;
            Program.SpineWindow.Spine.ActiveSlot = slot;
            currentConfig.SpineConfig.ActiveSlot = Program.SpineWindow.Spine.ActiveSlot;
            Program.LocalConfig = currentConfig;
        }
""", """\
        private void SwitchPet(int slot)
        {
            var currentConfig = Program.CurrentConfig;
            Program.SpineWindow.Spine.ActiveSlot = slot;
            currentConfig.SpineConfig.ActiveSlot = Program.SpineWindow.Spine.ActiveSlot;
            Program.LocalConfig = currentConfig;
        }

        /// <summary>
        /// 番茄钟那一项每次展开现读: 剩多久、今天做了几段都是会变的, 写死在菜单上就晚了
        /// </summary>
        private void RefreshFocusMenu()
        {
            var focus = Program.SpineWindow.Pomodoro;
            commandFocus.DropDownItems.Clear();
            commandFocus.DropDownItems.Add(new ToolStripMenuItem(
                FocusText(focus.Phase, focus.IsPaused, focus.Remaining, focus.CompletedToday)) { Enabled = false });
            commandFocus.DropDownItems.Add(new ToolStripSeparator());

            var running = focus.Phase != TinyEngine.PomodoroPhase.Off;
            commandFocus.DropDownItems.Add(FocusItem(focus.IsPaused ? "继续这一段" : "开始番茄",
                                    () => focus.Start(), !running || focus.IsPaused));
            commandFocus.DropDownItems.Add(FocusItem("暂停这一段", () => focus.Pause(),
                                    running && !focus.IsPaused));
            commandFocus.DropDownItems.Add(FocusItem("跳过这一段", () => focus.Skip(), running));
            commandFocus.DropDownItems.Add(FocusItem("停止番茄钟", () => focus.Abort(), running));
        }

        private static ToolStripMenuItem FocusItem(string text, Action act, bool enabled)
        {
            var item = new ToolStripMenuItem(text) { Enabled = enabled };
            item.Click += (object? s, EventArgs e) => act();
            return item;
        }

        /// <summary>
        /// 托盘上那一行状态字。抽成纯函数是为了无头判据能直接喂假值对文字, 不用真等 25 分钟
        /// </summary>
        internal static string FocusText(TinyEngine.PomodoroPhase phase, bool paused, TimeSpan remaining, int completed)
        {
            if (phase == TinyEngine.PomodoroPhase.Off) return $"没在计时 · 今日 {completed}";
            var left = remaining.ToString(@"mm\\:ss");
            return $"{(paused ? "已暂停" : FocusPhaseName(phase))} 剩 {left} · 今日 {completed}";
        }

        internal static string FocusPhaseName(TinyEngine.PomodoroPhase phase) => phase switch
        {
            TinyEngine.PomodoroPhase.Working => "专注中",
            TinyEngine.PomodoroPhase.ShortBreak => "短休息",
            TinyEngine.PomodoroPhase.LongBreak => "长休息",
            _ => "没在计时",
        };

        /// <summary>
        /// 换阶段气泡的正文。宠物那侧已经有表情和一句语音, 气泡是给正开着别的应用、没看桌面的人留的
        /// </summary>
        internal static string FocusTip(TinyEngine.PomodoroPhase phase, int minutes, int completed) => phase switch
        {
            TinyEngine.PomodoroPhase.Working => $"开始 {minutes} 分钟, 专心",
            TinyEngine.PomodoroPhase.ShortBreak => $"这一段做完了, 今日 {completed} 个, 歇 {minutes} 分钟",
            TinyEngine.PomodoroPhase.LongBreak => $"连着做完一轮, 今日 {completed} 个, 歇 {minutes} 分钟",
            _ => "",
        };

        /// <summary>
        /// 盯着番茄钟的阶段切换, 换了就弹一句; 计数照常跟, 关气泡时不会攒出一个过期的
        /// </summary>
        private void FocusTimer_Elapsed(object? sender, System.Timers.ElapsedEventArgs e)
        {
            var focus = Program.SpineWindow.Pomodoro;
            var id = focus.TransitionId;
            if (id == focusSeen) return;
            focusSeen = id;
            if (!FocusBalloon || focus.Phase == TinyEngine.PomodoroPhase.Off) return;
            ShowBalloonTip("番茄钟", FocusTip(focus.Phase, focus.PhaseMinutes, focus.CompletedToday));
        }
""")

for target, find, repl in edits:
    r = subprocess.run([sys.executable, str(view / "apply.py"), str(target), str(find), str(repl)],
                       capture_output=True, text=True)
    print(("OK  " if r.returncode == 0 else "FAIL") + f" {find.stem:26} {r.stdout.strip()} {r.stderr.strip()}")
