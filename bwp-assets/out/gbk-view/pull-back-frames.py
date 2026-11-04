# 一次性把头像框的桌宠接入从 GBK 源文件里撤掉 (Program.cs / ConfigForm.cs)
# 和 apply.py 同一套规矩: gbk 读、替换、gbk 写, 每条锚点必须命中恰好一次
import sys

CHANGES = [
    (
        "Program.cs",
        """                config.SpineConfig.ActiveSlot = SpineWindow.Spine.ActiveSlot;
                config.SpineConfig.ActiveFrame = SpineWindow.Frames.ActiveFrame;
                for (int i = 0; i < SpineConfig.SlotCount; i++)
                {
                    config.SpineConfig.SetSkelPath(i, SpineWindow.Spine.GetSpineSkelPath(i));
                    config.SpineConfig.SetFramePath(i, SpineWindow.Frames.GetFramePath(i));
                }
""",
        """                config.SpineConfig.ActiveSlot = SpineWindow.Spine.ActiveSlot;
                for (int i = 0; i < SpineConfig.SlotCount; i++)
                {
                    config.SpineConfig.SetSkelPath(i, SpineWindow.Spine.GetSpineSkelPath(i));
                }
""",
    ),
    (
        "Program.cs",
        """                // 头像框也逐格装载, 再放行出场的那一格
                try
                {
                    for (int i = 0; i < SpineConfig.SlotCount; i++)
                        SpineWindow.Frames.SetFrame(value.SpineConfig.GetFramePath(i), i);
                }
                catch (Exception ex)
                {
                    MessageBox.Show(ConfigForm, $"头像框装载失败\\n\\n{ex}", "Spine 资源加载失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
                }
                SpineWindow.Frames.ActiveFrame = value.SpineConfig.ActiveFrame;
""",
        "",
    ),
    (
        "Program.cs",
        """            // 头像框也逐格装载, 再放行出场的那一格
            try
            {
                for (int i = 0; i < SpineConfig.SlotCount; i++)
                    SpineWindow.Frames.SetFrame(value.SpineConfig.GetFramePath(i), i);
            }
            catch (Exception ex)
            {
                MessageBox.Show(ConfigForm, $"头像框装载失败\\n\\n{ex}", "Spine 资源加载失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
            SpineWindow.Frames.ActiveFrame = value.SpineConfig.ActiveFrame;
""",
        "",
    ),
    (
        "ConfigForm.cs",
        """        private ToolStripMenuItem commandFrames = new("头像框");
""",
        "",
    ),
    (
        "ConfigForm.cs",
        """            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandPets);
            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandFrames);
""",
        """            contextMenuStrip.Items.Insert(contextMenuStrip.Items.IndexOf(commandConfig), commandPets);
""",
    ),
    (
        "ConfigForm.cs",
        """            RefreshFrameMenu(Program.SpineWindow.Frames.ActiveFrame);
""",
        "",
    ),
    (
        "ConfigForm.cs",
        """
        /// <summary>
        /// 按已装载的头像框重建「头像框」菜单; 一格一项, 勾选的是正戴着的那格, 最后一项用来摘框
        /// </summary>
        private void RefreshFrameMenu(int activeFrame)
        {
            commandFrames.DropDownItems.Clear();

            var frames = Program.SpineWindow.Frames;
            var loaded = frames.LoadedFrames.ToArray();
            commandFrames.Enabled = loaded.Length > 0;
            if (!commandFrames.Enabled)
            {
                commandFrames.DropDownItems.Add(new ToolStripMenuItem("(未装载头像框)") { Enabled = false });
                return;
            }

            foreach (var index in loaded)
            {
                var item = new ToolStripMenuItem($"头像框 {index + 1:00}");
                item.Checked = index == activeFrame;
                item.Click += (object? s, EventArgs e) => SwitchFrame(index);
                commandFrames.DropDownItems.Add(item);
            }

            commandFrames.DropDownItems.Add(new ToolStripSeparator());
            var none = new ToolStripMenuItem("不显示") { Checked = activeFrame < 0 };
            none.Click += (object? s, EventArgs e) => SwitchFrame(-1);
            commandFrames.DropDownItems.Add(none);
        }

        private void SwitchFrame(int frame)
        {
            var currentConfig = Program.CurrentConfig;
            Program.SpineWindow.Frames.ActiveFrame = frame;
            currentConfig.SpineConfig.ActiveFrame = Program.SpineWindow.Frames.ActiveFrame;
            Program.LocalConfig = currentConfig;
        }
""",
        "",
    ),
]

SRC = "DeskSpine/src/"
for i in range(len(CHANGES)):
    name, find, repl = CHANGES[i]
    path = SRC + name
    text = open(path, "rb").read().decode("gbk")
    f = "\r\n" + find.replace("\r\n", "\n").replace("\n", "\r\n").rstrip("\r\n")
    r = ("\r\n" + repl.replace("\r\n", "\n").replace("\n", "\r\n").rstrip("\r\n")) if repl else ""
    hits = text.count(f)
    if hits != 1:
        sys.exit(f"锚点 #{i} ({name}) 命中 {hits} 次, 要求 1 次 —— 一个字节都没改")
    open(path, "wb").write(text.replace(f, r).encode("gbk"))
    print(f"OK [{i}] {name}")
