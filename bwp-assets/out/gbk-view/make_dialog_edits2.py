"""台词气泡第二轮: 设置窗那一趟不许把 DialogConfig 顶回默认值(keptDialog)。

和 make_dialog_edits.py 同一套走法 —— 锚点必须唯一命中。
"""
import pathlib
import subprocess
import sys

view = pathlib.Path(__file__).parent
root = view.parents[2]
target_form = root / "deskspine/DeskSpine/src/ConfigForm.cs"

edits = []


def edit(name, target, find, repl):
    f = view / f"dlg2-{name}-find.txt"
    r = view / f"dlg2-{name}-repl.txt"
    f.write_text(find, encoding="utf-8")
    r.write_text(repl, encoding="utf-8")
    edits.append((target, f, r))


edit("d1-field", target_form, """\
        /// 否则 Value 的 getter 拿 new Config() 的默认值 -1 顶掉它 = 图层模式(全部槽位叠着显示)
        /// </summary>
        private int keptActiveSlot = -1;
""", """\
        /// 否则 Value 的 getter 拿 new Config() 的默认值 -1 顶掉它 = 图层模式(全部槽位叠着显示)
        /// </summary>
        private int keptActiveSlot = -1;

        /// <summary>
        /// 台词气泡那段也是原样带回: 这窗上没有它的控件(开关在托盘「台词」里), 而 Value 的 getter
        /// 是 new Config() 现攒的 —— 不回灌就是「用户在托盘上关了开关, 点一次应用又活了」
        /// </summary>
        private DialogConfig keptDialog = new();
""")

edit("d2-value-get", target_form, """\
                v.PomodoroConfig.AutoStartWork = checkBox_FocusAutoWork.Checked;

                return v;
""", """\
                v.PomodoroConfig.AutoStartWork = checkBox_FocusAutoWork.Checked;

                // 台词气泡设置: 整段靠 keptDialog 带回来, 一个键都不在这儿现攒
                v.DialogConfig = keptDialog;

                return v;
""")

edit("d3-value-set", target_form, """\
                keptActiveSlot = value.SpineConfig.ActiveSlot;
""", """\
                keptActiveSlot = value.SpineConfig.ActiveSlot;
                keptDialog = value.DialogConfig;
""")

for target, find, repl in edits:
    r = subprocess.run([sys.executable, str(view / "apply.py"), str(target), str(find), str(repl)],
                       capture_output=True, text=True)
    print(("OK  " if r.returncode == 0 else "FAIL") + f" {find.stem:26} {r.stdout.strip()} {r.stderr.strip()}")
