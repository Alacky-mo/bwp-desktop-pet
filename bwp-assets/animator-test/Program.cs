using System.Collections.ObjectModel;
using System.Reflection;
using SFML.Window;

Console.OutputEncoding = System.Text.Encoding.UTF8;

// 验证 BwpHero 的两件事:
//   sweep —— 用 909 个真实骨架的动画名集合跑角色解析, 确认动作都能解析出来
//   drive —— 加载真实模型, 逐个触发交互, 确认选中了预期动画且能自动回到待机
//   roster —— 多只一起装进 SpineSlot, 确认 ActiveSlot 名册模式只画/只循环出场那一只
//   desk —— 反射 BwpDesktopPet.dll 跑 26 条: 名册和番茄钟配置存回去读得出来、设置窗往返不吃掉选中的角色、
//            越界时长夹得住、达摩 .ico 读得出且坏路径静默退回、托盘菜单在构造里就插好了、
//            配置六段每个键过一遍设置窗都不被默认值顶掉、两个自动开始开关真挂在番茄钟页上且勾得动、
//            浮窗贴头顶的算式、右键单击/拖动分流和浮窗露收规则(含「谁点都不收」)、两块底板九宫格拉不花、
//            预设小窗的版面/打靶/摆位/写盘、数字条十个字配得平(画布/基线/高差)、
//            版面里每句话放不放得下与小字够不够粗、右下角装饰件压没压到点得着的地方,
//            台词气泡的装机件/池子折行/「亮 15 秒自己消失再空 60 秒」那张表/摆位/挑词/换台词那侧重画没重画,
//            真建一次宠物窗口验「启动别卡死在建窗那一步」、真贴一次图验「分层窗贴得上去」、
//            真装四只骨架展开一次托盘「切换角色」验那几行渲染成中文名而不是拼音,
//            右键那张功能菜单两行各开哪一扇(真造三扇窗真喂鼠标事件)、天气卡片从真抓回的 JSON 到板上那一句建议每一跳、
//            应用图标那颗的链子(装机六帧/和源图同字节/三处都过 AppIcon.Resolve/没那张时退回占位/resx 里没夹带版权件/
//            exe 里那颗 PE 图标逐像素就是它/报时那颗并表达摩活得过 Load)、
//            对外那层的名字(dll/exe/中文显示名/托盘 tooltip/关于窗标题/安装包字符串)且数据目录名和 Mutex 名那半没跟着改
//   seed —— 拿 release 附件里的真素材(不是合成假骨架)在临时目录把首启登记跑一遍: 登记几只、路径真在场且就在包里、
//            托盘显示中文名、V306/模式5 读得回来、已有配置不动; 配置写到临时目录，先撞上本机那份就拒绝跑
//   weather —— 天气那三跳真跑一遍(全仓库只有这一趟会出门), 打印板上会给用户看的那五行(读数四 + 建议一句); 一次假数据都不许有
//   voice —— 反射 Speaker 解出来的句池, 确认切脸挑得出句子、而且一轮播完才重洗(会真出声)
//   pomodoro —— 假时钟快进整一轮番茄钟, 确认边界换对脸、专注期间不许睡、藏着窗口也不丢时间
if (args.Length < 1)
{
    Console.Error.WriteLine("usage: bwp-animator-test sweep <census.tsv ...> | drive <skel> <atlas> | roster <skel> <skel> [...] | desk [BwpDesktopPet.dll] | seed <BwpDesktopPet.dll> <包内 res\\spine> <临时目录> | weather [BwpDesktopPet.dll] | voice <skel> [...] | pomodoro <skel> [...]");
    return 2;
}
return args[0] switch
{
    "sweep" => Sweep(args.Skip(1)),
    "roster" => Roster(args.Skip(1).ToArray()),
    "desk" => Desk(args.Skip(1).ToArray()),
    "seed" => SeedProbe(args.Skip(1).ToArray()),
    "weather" => WeatherProbe(args.Skip(1).ToArray()),
    "voice" => Voice(args.Skip(1).ToArray()),
    "pomodoro" => Pomo(args.Skip(1).ToArray()),
    _ => Drive(args[1], args[2]),
};

static Type ActionsType()
{
    var t = typeof(TinyEngine.Animator).Assembly.GetType("TinyEngine.BwpHero+Actions");
    if (t is null) throw new InvalidOperationException("TinyEngine.BwpHero+Actions not found");
    return t;
}

static object NewActions(Type t, IEnumerable<string> names) =>
    Activator.CreateInstance(t,
        BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance,
        null,
        new object[] { new ReadOnlyCollection<string>(names.ToList()) },
        null)!;

static string Field(object actions, Type t, string name) => (string)t.GetField(name)!.GetValue(actions)!;

static string[] Moods(object actions, Type t) =>
    ((System.Collections.ObjectModel.ReadOnlyCollection<string>)t.GetField("Moods")!.GetValue(actions)!).ToArray();

/// <summary>
/// SpineSlot 不对外暴露槽位上的骨骼, 判据要读它播的是哪张脸就只能反射拿
/// </summary>
static Spine.Spine SlotSpine(TinyEngine.SpineSlot slot, int index) =>
    ((Spine.Spine[])typeof(TinyEngine.SpineSlot)
        .GetField("slots", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(slot)!)[index];

int Sweep(IEnumerable<string> tsPaths)
{
    var t = ActionsType();
    var rows = new List<(string Set, string Idle, string Alert, string Attack, string Cast, string Entrance, string Sleep, string Moods)>();
    foreach (var path in tsPaths)
        foreach (var line in File.ReadLines(path))
        {
            var col = line.Split('\t');
            if (col.Length < 18 || col[1] != "ok") continue;
            var names = col[17].Split(';').Where(x => x.Length > 0).Select(x => x.Split(':')[0]).ToArray();
            if (names.Length == 0) continue;
            var a = NewActions(t, names);
            rows.Add((string.Join("|", names.OrderBy(x => x)),
                      Field(a, t, "Idle"), Field(a, t, "Alert"), Field(a, t, "Attack"),
                      Field(a, t, "Cast"), Field(a, t, "Entrance") ?? "-",
                      Field(a, t, "Sleep"), string.Join(",", Moods(a, t))));
        }

    var groups = rows.GroupBy(r => r.Set).Select(g => (g.Key, g.Count(), g.First())).ToList();
    Console.WriteLine($"resolved {rows.Count} skeletons, {groups.Count} distinct name sets, " +
                      $"{rows.Count(r => r.Moods.Length > 0)} 走表情映射");

    int bad = 0;
    foreach (var (set, n, r) in groups)
    {
        var nameSet = set.Split('|');
        var resolved = new[] { r.Idle, r.Alert, r.Attack, r.Cast, r.Sleep }.Concat(
            r.Entrance == "-" ? Array.Empty<string>() : new[] { r.Entrance })
            .Concat(r.Moods.Length > 0 ? r.Moods.Split(',') : Array.Empty<string>());
        var outside = resolved.Where(x => x.Length == 0 || !nameSet.Contains(x)).ToArray();
        // 表情骨架四个交互全撞在同一张脸上就没意义了, 除非它本来就只有一两个表情
        var faces = new[] { r.Alert, r.Attack, r.Cast, r.Entrance }.Where(x => x != r.Idle).Distinct().Count();
        var tooFlat = r.Moods.Split(',', StringSplitOptions.RemoveEmptyEntries).Length > 2 && faces < 2;
        if (outside.Length > 0 || tooFlat) bad++;
        Console.WriteLine($"{(outside.Length > 0 ? "BAD " : tooFlat ? "FLAT" : "    ")}x{n,-4} [{set}]" +
                          $" idle={r.Idle} alert={r.Alert} attack={r.Attack} cast={r.Cast} entrance={r.Entrance} sleep={r.Sleep}" +
                          (r.Moods.Length > 0 ? $" moods=[{r.Moods}]" : "") +
                          (outside.Length > 0 ? $"  !! 非法解析: {string.Join(",", outside)}" : ""));
    }
    Console.WriteLine(bad == 0 ? "SWEEP OK" : $"SWEEP FAIL: {bad} 个名称集合解析异常");
    return bad == 0 ? 0 : 1;
}

int Drive(string skel, string atlas)
{
    var spine = Spine.Spine.New(Spine.SpineVersion.V36, skel, atlas, defaultMix: 0.15f);
    Console.WriteLine($"animations: {string.Join(", ", spine.AnimationNames)}");

    var t = ActionsType();
    var a = NewActions(t, spine.AnimationNames);
    Console.WriteLine($"映射: idle={Field(a, t, "Idle")} 拖拽={Field(a, t, "Alert")} 单击={Field(a, t, "Attack")} " +
                      $"双击/滚轮={Field(a, t, "Cast")} 登场/报时={Field(a, t, "Entrance") ?? "-"} 睡觉={Field(a, t, "Sleep")} " +
                      $"随机=[{string.Join(",", Moods(a, t))}]");

    // 每段都用全新控制器, 让随机小动作的计时器不参与轨迹;
    // 但拖拽和睡眠必须成对跑, 因为唤醒/松手依赖上一段留下的状态
    Run(spine, ("装载登场", a => a.Reset(), 8f));
    Run(spine, ("左键单击", a => a.Click(Mouse.Button.Left), 9f));
    Run(spine, ("左键双击", a => a.DoubleClick(Mouse.Button.Left), 9f));
    Run(spine, ("滚轮滚动", a => a.Scroll(Mouse.Wheel.VerticalWheel, 1f), 9f));
    Run(spine, ("按住拖拽", a => a.DragBegin(Mouse.Button.Right), 2f),
                ("松开拖拽", a => a.DragEnd(Mouse.Button.Right), 6f));
    Run(spine, ("闲置入睡", a => a.SleepStateChange(true), 2f),
                ("回来唤醒", a => a.SleepStateChange(false), 8f));
    Run(spine, ("整点报时", a => { a.HourlyChime(); a.Update(1f / 30f); }, 8f));
    Soak(spine, "闲置随机", 120f);
    return 0;
}

/// <summary>
/// 空跑一段时间, 统计随机小动作实际抽到了哪些动画, 每个都必须能回到待机
/// </summary>
static void Soak(Spine.Spine spine, string label, float seconds)
{
    var animator = TinyEngine.Animator.New(TinyEngine.AnimatorType.BwpHero, new Spine.Spine[] { spine });
    var seen = new Dictionary<string, int>();
    int frames = (int)(seconds * 30);
    for (int i = 0; i < frames; i++)
    {
        animator.Update(1f / 30f);
        spine.Update(1f / 30f);
        seen[spine.CurrentAnimation] = seen.GetValueOrDefault(spine.CurrentAnimation) + 1;
    }
    var picks = seen.Where(kv => kv.Key != spine.AnimationNames[0]).ToList();
    Console.WriteLine($"  {label,-10} {string.Join("  ", seen.Select(kv => $"{kv.Key}x{kv.Value}"))}" +
                      $"  (抽到 {picks.Count} 种)");
}

/// <summary>
/// 在同一批控制器上按顺序触发动作, 每个动作后记录动画走向
/// </summary>
void Run(Spine.Spine spine, params (string Label, Action<TinyEngine.Animator> Act, float Watch)[] steps)
{
    var animator = TinyEngine.Animator.New(TinyEngine.AnimatorType.BwpHero, new Spine.Spine[] { spine });
    foreach (var (label, act, watch) in steps)
    {
        act(animator);
        Report(animator, spine, label, watch);
    }
}

/// <summary>
/// 推进逻辑帧直到动画名发生变化; 没变化就说明该动作是持续循环的
/// </summary>
static void Report(TinyEngine.Animator animator, Spine.Spine sp, string label, float watch)
{
    var first = sp.CurrentAnimation;
    var seq = new List<string> { first };
    int frames = (int)(watch * 30);
    for (int i = 0; i < frames && seq.Count == 1; i++)
    {
        animator.Update(1f / 30f);
        sp.Update(1f / 30f);
        if (sp.CurrentAnimation != first) seq.Add(sp.CurrentAnimation);
    }
    Console.WriteLine($"  {label,-10} {string.Join(" -> ", seq)}{(seq.Count > 1 ? "" : "  (持续循环)")}");
}

/// <summary>
/// 名册模式验收: 三只一起装进一个 SpineSlot, 图层模式应当叠成一片, 逐格出场应当各自只有一只。
/// 渲染到 RenderTexture 后统计不透明像素数和平均色, 既证明门控生效, 也证明换的是不同的角色。
/// </summary>
int Roster(string[] skels)
{
    if (skels.Length < 2)
    {
        Console.Error.WriteLine("usage: bwp-animator-test roster <skel> <skel> [...]");
        return 2;
    }

    var outDir = Path.Combine("out", "roster");
    Directory.CreateDirectory(outDir);

    using var slot = new TinyEngine.SpineSlot(skels.Length);
    slot.Version = Spine.SpineVersion.V36;
    slot.AnimatorType = TinyEngine.AnimatorType.BwpHero;
    slot.UsePremultipliedAlpha = true;
    for (int i = 0; i < skels.Length; i++) slot.SetSpine(skels[i], i);

    Console.WriteLine($"装载 {skels.Length} 只, 图层模式 ActiveSlot={slot.ActiveSlot}, 名册={string.Join(",", slot.LoadedSlots)}");

    var texture = new SFML.Graphics.RenderTexture(512, 512, false);
    var view = new SFML.Graphics.View
    {
        Center = new SFML.System.Vector2f(0, 68),
        Size = new SFML.System.Vector2f(183, -183),
    };
    texture.SetView(view);

    (string Label, int Lit, string Mean) Shoot(string label)
    {
        for (int i = 0; i < 30; i++) slot.Update(1f / 30f);   // 走一秒, 让登场动作播进稳定帧
        texture.Clear(new SFML.Graphics.Color(0, 0, 0, 0));
        slot.Render(texture);
        texture.Display();
        using var image = texture.Texture.CopyToImage();
        var path = Path.Combine(outDir, label + ".png");
        image.SaveToFile(path);

        int lit = 0; long r = 0, g = 0, b = 0;
        for (uint y = 0; y < 512; y++)
            for (uint x = 0; x < 512; x++)
            {
                var p = image.GetPixel(x, y);
                if (p.A == 0) continue;
                lit++; r += p.R; g += p.G; b += p.B;
            }
        return (label, lit, lit == 0 ? "空" : $"#{r / lit:x2}{g / lit:x2}{b / lit:x2}");
    }

    var stackedShot = Shoot("layer");
    Console.WriteLine($"  图层模式(全部槽位)  -> 亮像素{stackedShot.Lit} 均色{stackedShot.Mean}");
    var solo = new List<(string Label, int Lit, string Mean)>();
    for (int i = 0; i < skels.Length; i++)
    {
        slot.ActiveSlot = i;
        var shot = Shoot($"slot{i}");
        solo.Add(shot);
        Console.WriteLine($"  名册 ActiveSlot={i} -> 亮像素{shot.Lit} 均色{shot.Mean}  ({Path.GetFileNameWithoutExtension(skels[i])})");
    }
    // Ctrl+滚轮: 从第 0 格开始绕一圈, 应当把名册里的每只都轮一遍再回到起点
    slot.ActiveSlot = 0;
    bool wrapsAround = true;
    for (var dir = 1; dir >= -1; dir -= 2)
    {
        var order = new List<int> { slot.ActiveSlot };
        for (int i = 0; i < skels.Length + 1; i++)
        {
            if (!slot.SwitchActive(dir)) break;
            order.Add(slot.ActiveSlot);
        }
        wrapsAround &= order[skels.Length] == order[0] && order.Distinct().Count() == skels.Length;
        Console.WriteLine($"  {(dir > 0 ? "向前" : "向后")}滚轮循环: {string.Join(" -> ", order)}");
    }

    var stacked = stackedShot.Lit > solo.Max(s => s.Lit);
    var distinct = solo.Select(s => s.Mean).Distinct().Count() == skels.Length;
    Console.WriteLine($"  叠画比单只大: {(stacked ? "是" : "否")}  各槽位是不同的角色: {(distinct ? "是" : "否")}  滚轮绕回起点: {(wrapsAround ? "是" : "否")}");
    var pass = stacked && distinct && wrapsAround;
    Console.WriteLine(pass ? "ROSTER OK" : "ROSTER FAIL");
    return pass ? 0 : 1;
}

/// <summary>
/// 无头验 DeskSpine 这一侧: 名册和番茄钟都写得进配置读得回来、设置窗控件往返不丢数、
/// 托盘菜单在构造函数里就插好了 (踩过放 Load 太晚的坑)、托盘和气泡的文字喂假值对得出来、
/// 倒计时浮窗那条「世界框→屏幕矩形」的链算得对、右键单击和右键拖动分得开、浮窗该露该收、
/// 两块底板九宫格拉不花、预设小窗的版面/打靶/摆位, 走小窗改一档时别的段一个键都没被默认值顶掉、
/// 配置六段每个键过一遍设置窗都原样回得来 (§4.3 要删控件, 先靠这条兜底),
/// 数字条十个字同一张画布、同一条基线、高差收在窄带里 (配平在素材侧, 代码不管),
/// 台词气泡那两张件咬得住画布、池子每条折得进正文区、那张一秒一格的表真按「亮 15 秒自己消失、空 60 秒再来」走,
/// 最后真建一扇宠物窗口确认启动不会卡死在建窗那一步
/// </summary>
int Desk(string[] args)
{
    var target = args.Length > 0 ? Path.GetFullPath(args[0]) : FindDeskDll();
    if (!File.Exists(target))
    {
        Console.WriteLine($"  找不到 {target}");
        return 1;
    }
    Console.WriteLine($"  反射 {target}");

    var asm = Assembly.LoadFrom(target);
    var configType = asm.GetType("DeskSpine.SpineConfig")!;
    var rootType = asm.GetType("DeskSpine.Config")!;
    var setSkel = configType.GetMethod("SetSkelPath")!;
    var getSkel = configType.GetMethod("GetSkelPath")!;
    // 偶数格给路径, 奇数格留空, 看 null 能不能原样回来
    var want = Enumerable.Range(0, 10).Select(i => i % 2 == 0 ? $@"C:\pets\s{i + 1:00}.skel" : null).ToList();

    var cfg = Activator.CreateInstance(configType)!;
    for (int i = 0; i < want.Count; i++) setSkel.Invoke(cfg, new object?[] { i, want[i] });
    configType.GetProperty("ActiveSlot")!.SetValue(cfg, 2);

    var root = Activator.CreateInstance(rootType)!;
    rootType.GetProperty("SpineConfig")!.SetValue(root, cfg);
    var tmp = Path.Combine(Path.GetTempPath(), $"bwp-roster-config-{Guid.NewGuid():N}.json");
    var saved = (bool)rootType.GetMethod("Save", new[] { typeof(string) })!.Invoke(root, new object[] { tmp })!;
    var back = Activator.CreateInstance(rootType)!;
    var loaded = (bool)rootType.GetMethod("Load", new[] { typeof(string) })!.Invoke(back, new object[] { tmp })!;
    File.Delete(tmp);

    var backCfg = rootType.GetProperty("SpineConfig")!.GetValue(back)!;
    var got = Enumerable.Range(0, 10).Select(i => (string?)getSkel.Invoke(backCfg, new object[] { i })).ToList();
    var active = (int)configType.GetProperty("ActiveSlot")!.GetValue(backCfg)!;
    var rosterOk = saved && loaded && active == 2 && got.SequenceEqual(want);
    Console.WriteLine($"  名册存回读出: {(rosterOk ? "是" : "否")}  ActiveSlot={active}  非空格 {got.Count(p => p is not null)} 个");
    if (!rosterOk) Console.WriteLine($"    实际: {string.Join(" | ", got.Select(p => p ?? "(空)"))}");

    // 窗体全程不 Show, 只在构造里插菜单, 所以要看到「切换角色」和「番茄钟」都排在「设置」前面
    var formType = asm.GetType("DeskSpine.ConfigForm")!;
    var menuField = formType.GetField("contextMenuStrip", BindingFlags.NonPublic | BindingFlags.Instance)!;
    var texts = Array.Empty<string>();
    var pomoType = asm.GetType("DeskSpine.PomodoroConfig")!;

    // 番茄钟的七项: 用一组和默认值全不同的数, 免得「没接线」和「刚好是默认值」看不出区别。
    // 图标路径必须一起走: 这键哪天在保存路上被谁漏掉, 用户手改的 config.json 会被默认值悄悄盖回去
    var ico = Path.Combine(Path.GetDirectoryName(asm.Location)!, "res", "image", "focus_damo.ico");
    var slotProp = asm.GetType("DeskSpine.SpineConfig")!.GetProperty("ActiveSlot")!;
    var focusWant = new (string Name, object Value)[]
    {
        ("WorkMinutes", 17), ("BreakMinutes", 3), ("LongBreakMinutes", 23),
        ("CyclesPerLongBreak", 6), ("BlockSleepWhileWorking", false), ("BalloonOnPhaseChange", false),
        ("BalloonIconPath", ico),
    };
    object MakeFocusConfig()
    {
        var pc = Activator.CreateInstance(pomoType)!;
        foreach (var (name, value) in focusWant) pomoType.GetProperty(name)!.SetValue(pc, value);
        var whole = Activator.CreateInstance(rootType)!;
        rootType.GetProperty("PomodoroConfig")!.SetValue(whole, pc);
        // 顺手把「切换角色」选中的槽位也摆成第 3 只: 设置窗上没有它的控件,
        // 它的 getter 是 new Config() 现攒的, 不带回来就会被默认值 -1(图层模式: 全部槽位叠着) 顶掉
        slotProp.SetValue(rootType.GetProperty("SpineConfig")!.GetValue(whole), 2);
        return whole;
    }
    int ReadSlot(object? whole) => whole is null ? -999
        : (int)slotProp.GetValue(rootType.GetProperty("SpineConfig")!.GetValue(whole))!;
    (string Key, object? Got)[] ReadFocus(object? whole)
    {
        var pc = whole is null ? null : rootType.GetProperty("PomodoroConfig")!.GetValue(whole);
        return focusWant.Select(f => (f.Name, pc is null ? null : pomoType.GetProperty(f.Name)!.GetValue(pc))).ToArray();
    }

    // 第一层: 配置文件本身存得回读得出
    var jsonFile = Path.Combine(Path.GetTempPath(), $"bwp-focus-config-{Guid.NewGuid():N}.json");
    var jsonSaved = (bool)rootType.GetMethod("Save", new[] { typeof(string) })!.Invoke(MakeFocusConfig(), new object[] { jsonFile })!;
    var jsonBack = Activator.CreateInstance(rootType)!;
    var jsonLoaded = (bool)rootType.GetMethod("Load", new[] { typeof(string) })!.Invoke(jsonBack, new object[] { jsonFile })!;
    File.Delete(jsonFile);
    var jsonGot = ReadFocus(jsonBack);
    var focusJsonOk = jsonSaved && jsonLoaded
        && focusWant.Zip(jsonGot).All(f => Equals(f.First.Value, f.Second.Got));
    Console.WriteLine($"  番茄钟配置存回读出: {(focusJsonOk ? "是" : "否")}  {string.Join(" ", jsonGot.Select(g => $"{g.Key}={g.Got}"))}");

    // 现场那份 config.json 是旧版存的, 里面**根本没有** BalloonIconPath, 而 Load 是整段换掉 PomodoroConfig 的:
    // 默认值要只写在 Config() 构造里就会被 new 出来的对象冲成 null, 气泡悄悄变回报时那颗钟, 谁都不报错
    var legacyJson = Path.Combine(Path.GetTempPath(), $"bwp-focus-legacy-{Guid.NewGuid():N}.json");
    File.WriteAllText(legacyJson,
        "{\"PomodoroConfig\":{\"WorkMinutes\":25,\"BreakMinutes\":5,\"LongBreakMinutes\":15," +
        "\"CyclesPerLongBreak\":4,\"BlockSleepWhileWorking\":true,\"BalloonOnPhaseChange\":true}}");
    var legacyBack = Activator.CreateInstance(rootType)!;
    var legacyLoaded = (bool)rootType.GetMethod("Load", new[] { typeof(string) })!
        .Invoke(legacyBack, new object[] { legacyJson })!;
    File.Delete(legacyJson);
    var legacyPath = (string)pomoType.GetProperty("BalloonIconPath")!.GetValue(
        rootType.GetProperty("PomodoroConfig")!.GetValue(legacyBack));
    // 只比文件名: 默认值是按「exe 旁边那个 res 目录」算的, 判据进程是 bwp-animator-test, 它指到测试自己的 bin 里去了
    var legacyFresh = (string)pomoType.GetProperty("BalloonIconPath")!.GetValue(
        rootType.GetProperty("PomodoroConfig")!.GetValue(Activator.CreateInstance(rootType)!));
    var legacyOk = legacyLoaded && legacyPath is not null && Path.GetFileName(legacyPath) == "focus_damo.ico"
        && Equals(legacyPath, legacyFresh);
    Console.WriteLine($"  旧配置没这个键也还有图标: {(legacyOk ? "是" : "否")}  {(legacyPath is null ? "(空)" : Path.GetFileName(legacyPath))}");

    // 第二层: 设置窗控件往返一次 (Value 的 getter 在位置/尺寸那几个框锁着时会去读 Program.SpineWindow,
    // 无头跑那里是空的, 所以按「用户已解锁位置」的那种状态来跑)
    (string Key, object? Got)[] formGot = Array.Empty<(string, object?)>();
    var clampGot = (Work: 0, Break: 0);
    var focusIcon = (Good: "(没跑)", Bad: "(没跑)");
    int slotKept = -999;
    // 第 16 条的结果。STA 线程里算, Join 之后才读, 所以不用锁
    var keySentries = 0;
    var keyDrift = new List<string>();
    var keyError = new List<string>();
    var keySkip = new List<string>();
    // 第 17 条要拿这扇设置窗当「配置推过去之后落在哪」的收件方, 所以把实例留到线程外
    object? staForm = null;
    // 两个自动开始开关必须真挂在番茄钟页上: 只接线不摆控件, 用户就只能手改 config.json
    var switchOk = false;
    var switchNotes = new List<string>();
    var sta = new Thread(() =>
    {
        var form = Activator.CreateInstance(formType)!;
        staForm = form;
        var menu = (System.Windows.Forms.ContextMenuStrip)menuField.GetValue(form)!;
        texts = menu.Items.Cast<System.Windows.Forms.ToolStripItem>().Select(i => i.Text).ToArray();

        // 构造函数把 1 秒一轮的番茄钟气泡计时器武装上了, 而这里 Program.SpineWindow 是空的。
        // 不关掉的话判据崩不崩取决于进程有没有活过那一秒 —— 关掉, 结果就跟时间无关了
        ((System.Timers.Timer)formType.GetField("focusTimer", BindingFlags.NonPublic | BindingFlags.Instance)!
                .GetValue(form)!).Stop();

        // 下拉框的 DataSource 在 Load 里才绑上, 不跑它 getter 会拿 (SpineVersion)null 去强转直接抛
        formType.GetMethod("ConfigForm_Load", BindingFlags.NonPublic | BindingFlags.Instance)!
                .Invoke(form, new object?[] { null, EventArgs.Empty });
        foreach (var name in new[] { "numericUpDown_PositionX", "numericUpDown_PositionY",
                                     "numericUpDown_SizeX", "numericUpDown_SizeY",
                                     "numericUpDown_SpinePositionX", "numericUpDown_SpinePositionY" })
            ((System.Windows.Forms.Control)formType.GetField(name, BindingFlags.NonPublic | BindingFlags.Instance)!
                    .GetValue(form)!).Enabled = true;

        var valueProp = formType.GetProperty("Value")!;
        var iconField = formType.GetField("focusBalloonIcon", BindingFlags.NonPublic | BindingFlags.Instance)!;
        valueProp.SetValue(form, MakeFocusConfig());
        formGot = ReadFocus(valueProp.GetValue(form));
        slotKept = ReadSlot(valueProp.GetValue(form));
        // 那颗 .ico 真被 GDI+ 读出来了没有（new Bitmap 拿的是最大那一帧）
        focusIcon.Good = (iconField.GetValue(form) as System.Drawing.Bitmap) is { } ok
            ? $"{ok.Width}x{ok.Height}" : "(没读出来)";

        // 手改的 config.json 给得出越界的时长, 而 NumericUpDown 越界是直接抛的: 该夹到控件的两头
        var wild = MakeFocusConfig();
        var wildPc = rootType.GetProperty("PomodoroConfig")!.GetValue(wild)!;
        pomoType.GetProperty("WorkMinutes")!.SetValue(wildPc, 999);
        pomoType.GetProperty("BreakMinutes")!.SetValue(wildPc, -5);
        // 顺手验读不到的图标是「静默退回共用那颗」而不是弹窗 —— 弹窗会把无头判据卡在那一秒
        pomoType.GetProperty("BalloonIconPath")!.SetValue(wildPc, @"q:\没有这个文件.ico");
        valueProp.SetValue(form, wild);
        focusIcon.Bad = iconField.GetValue(form) is null ? "(空, 已退回)" : "还留着上一张";
        var wildBack = rootType.GetProperty("PomodoroConfig")!.GetValue(valueProp.GetValue(form))!;
        clampGot = ((int)pomoType.GetProperty("WorkMinutes")!.GetValue(wildBack)!,
                    (int)pomoType.GetProperty("BreakMinutes")!.GetValue(wildBack)!);

        // 第 16 条: 配置全键往返。反射把四段里每个「能读又能写」的键都灌成非默认的哨兵值,
        // 过一遍设置窗的 Value 再逐键要回来。这条是 §4.3 的前置: 那个 getter 是 new Config() 现攒的,
        // 谁没了控件、又没在别处回灌, 点一次「应用」就被类默认值顶掉 —— 上次「图层模式」是一行行读码才找到的,
        // 这回红就要说得出「哪一段.哪一键」
        object? PeekMember(object holder, MemberInfo m) => m switch
        {
            PropertyInfo p => p.GetValue(holder),
            FieldInfo f => f.GetValue(holder),
            _ => null,
        };
        void PokeMember(object holder, MemberInfo m, object value)
        {
            if (m is PropertyInfo p) p.SetValue(holder, value);
            else if (m is FieldInfo f) f.SetValue(holder, value);
        }
        // 下拉框只认自己映射表里的值: 递个表里没有的枚举进去, SelectedValue 会变成 null,
        // getter 那一下强转直接抛 —— 那是判据自己造的假红
        var combos = new Dictionary<string, string>
        {
            ["SpineConfig.SpineVersion"] = "comboBox_SpineVersion_KV",
            ["SpineConfig.InteractMode"] = "comboBox_WindowType_KV",
        };
        object? SentryFor(string path, MemberInfo m, object? current)
        {
            var type = m is PropertyInfo p ? p.PropertyType : ((FieldInfo)m).FieldType;
            if (type == typeof(string)) return @"Z:\哨兵.skel";
            if (type == typeof(bool)) return !(bool)current!;
            if (type == typeof(int)) return (int)current! + 7;
            if (type == typeof(uint)) return (uint)current! + 7u;
            if (type == typeof(byte)) return (byte)((byte)current! >= 240 ? 233 : (byte)current! + 7);
            // 缩放那格走的是整数百分比的滑块, 挑个 1.5 这种存进滑块还能原样回得来的数
            if (type == typeof(float)) return 1.5f;
            // 位置缓存那两格是坐标: 设置窗不画控件、只整段原样带回来, 所以随便一个非零小数都行
            if (type == typeof(double)) return 36.6683;
            // 定着那一刻。挑个和默认值(0001-01-01)差得远的, 被 new 顶掉才看得出来
            if (type == typeof(DateTimeOffset)) return new DateTimeOffset(2026, 11, 3, 8, 30, 0, TimeSpan.FromHours(8));
            if (combos.TryGetValue(path, out var kv))
            {
                var dict = formType.GetField(kv, BindingFlags.NonPublic | BindingFlags.Static)!.GetValue(null)!;
                var values = (System.Collections.IEnumerable)dict.GetType().GetProperty("Values")!.GetValue(dict)!;
                return values.Cast<object>().FirstOrDefault(v => !Equals(v, current));
            }
            // 背景色那三个框的 ValueChanged 会把 B 拽平成 R, 所以哨兵得 R == B 才回得来
            if (type.Name == "Color") return Activator.CreateInstance(type, (byte)11, (byte)22, (byte)11, (byte)0);
            return null;    // 认不出的形状不硬试, 但会点名进 keySkip, 不许悄悄少比一条
        }
        var whole = Activator.CreateInstance(rootType)!;
        var sentries = new List<(string Path, object Want)>();
        foreach (var section in new[] { "SystemConfig", "BasicConfig", "SpineConfig", "PomodoroConfig", "DialogConfig", "WeatherConfig" })
        {
            var holder = rootType.GetProperty(section)!.GetValue(whole)!;
            var members = holder.GetType().GetMembers(BindingFlags.Public | BindingFlags.Instance)
                .Where(m => m is FieldInfo { IsPublic: true }
                         || m is PropertyInfo { CanRead: true, CanWrite: true } p && p.GetIndexParameters().Length == 0)
                .OrderBy(m => m.Name, StringComparer.Ordinal);
            foreach (var m in members)
            {
                var path = $"{section}.{m.Name}";
                object? want;
                try { want = SentryFor(path, m, PeekMember(holder, m)); }
                catch (Exception ex) { keyError.Add($"{path} 哨兵造不出({ex.GetType().Name})"); continue; }
                if (want is null) { keySkip.Add(path); continue; }
                try { PokeMember(holder, m, want); }
                catch (Exception ex) { keyError.Add($"{path} 灌不进({ex.GetType().Name})"); continue; }
                sentries.Add((path, want));
            }
        }
        keySentries = sentries.Count;
        try
        {
            valueProp.SetValue(form, whole);
            var back = valueProp.GetValue(form)!;
            foreach (var (path, want) in sentries)
            {
                var parts = path.Split('.');
                var holderBack = rootType.GetProperty(parts[0])!.GetValue(back)!;
                var m = (MemberInfo?)holderBack.GetType().GetProperty(parts[1]) ?? holderBack.GetType().GetField(parts[1])!;
                var got = PeekMember(holderBack, m);
                if (!Equals(got, want)) keyDrift.Add($"{path}: 进去 {want} 回来 {got ?? "(空)"}");
            }
        }
        catch (Exception ex) { keyError.Add($"Value 往返抛 {ex.GetType().Name}: {ex.Message}"); }

        // 第 18 条: 两个自动开始开关看得见、点得动。判据查三样 —— 控件在、挂在「番茄钟」页上、
        // 勾一下能从 Value 里读到新值。第 16 条只保证「键不丢」, 没有控件时它照样全绿(靠 kept 字段兜着),
        // 所以「用户找得到」这件事得单独立一条
        bool SwitchWorks(string field, string key)
        {
            var box = formType.GetField(field, BindingFlags.NonPublic | BindingFlags.Instance)?.GetValue(form)
                as System.Windows.Forms.CheckBox;
            if (box is null) { switchNotes.Add($"{field} 不存在"); return false; }
            var up = box.Parent;
            while (up is not null && up is not System.Windows.Forms.TabPage) up = up.Parent;
            if (up is not System.Windows.Forms.TabPage page) { switchNotes.Add($"{field} 没挂到任何页上"); return false; }
            if (page.Text != "番茄钟") { switchNotes.Add($"{field} 挂在「{page.Text}」页, 不在番茄钟页"); return false; }
            bool Read()
            {
                var cfg = rootType.GetProperty("PomodoroConfig")!.GetValue(valueProp.GetValue(form))!;
                return (bool)pomoType.GetProperty(key)!.GetValue(cfg)!;
            }
            var before = Read();
            box.Checked = !before;
            var after = Read();
            if (after == before) { switchNotes.Add($"{field} 勾了但 Value 里没变"); return false; }
            switchNotes.Add($"{field} 在「{page.Text}」页, 勾一下就传出去");
            return true;
        }
        var breakOk = SwitchWorks("checkBox_FocusAutoBreak", "AutoStartBreak");
        var workOk = SwitchWorks("checkBox_FocusAutoWork", "AutoStartWork");
        switchOk = breakOk && workOk;
    });
    sta.SetApartmentState(ApartmentState.STA);
    sta.Start();
    sta.Join();
    var focusFormOk = focusWant.Zip(formGot).All(f => Equals(f.First.Value, f.Second.Got));
    Console.WriteLine($"  番茄钟过一遍设置窗: {(focusFormOk ? "是" : "否")}  {string.Join(" ", formGot.Select(g => $"{g.Key}={g.Got}"))}");

    // 这一项对的是那个「点应用就自动切图层模式」的 bug: 槽位 2 进得去也要出得来, 掉回 -1 就是三只叠着显示
    var slotOk = slotKept == 2;
    Console.WriteLine($"  设置窗不吃掉选中的角色: {(slotOk ? "是" : "否")}  进去槽位 2, 回读 {slotKept}{(slotKept < 0 ? " (负数=图层模式, 全部槽位叠着)" : "")}");

    var clampOk = clampGot == (180, 1);
    Console.WriteLine($"  越界时长夹得住: {(clampOk ? "是" : "否")}  999→{clampGot.Work}  -5→{clampGot.Break}");

    // 气泡图标是这张 .ico、且坏路径时静默退回（不弹窗，否则无头判据会卡住）
    var focusIconOk = File.Exists(ico) && focusIcon.Good == "128x128" && focusIcon.Bad == "(空, 已退回)";
    Console.WriteLine($"  番茄钟气泡图标: {(focusIconOk ? "是" : "否")}  {Path.GetFileName(ico)} 存在={File.Exists(ico)} 读出来={focusIcon.Good} 坏路径时={focusIcon.Bad}");

    // 第 16 条的账: 一个键都不许被悄悄漏掉 —— 认不出形状的、灌不进的、往返路上抛的、回来变样的, 分开点名。
    // keySentries 那道下限防的是「反射一个键都没抓到」这种自己骗自己的全绿
    var keyOk = keyDrift.Count == 0 && keyError.Count == 0 && keySkip.Count == 0 && keySentries >= 30;
    Console.WriteLine($"  配置全键往返: {(keyOk ? "是" : "否")}  {keySentries} 个键灌进设置窗又原样回来"
        + (keySkip.Count == 0 ? "" : $"  没认出的形状: {string.Join(",", keySkip)}")
        + (keyError.Count == 0 ? "" : $"  出错: {string.Join(" | ", keyError)}")
        + (keyDrift.Count == 0 ? "" : $"  被默认值顶掉: {string.Join(" | ", keyDrift)}"));

    // 第 18 条: 光有键没有控件 = 用户只能手改 JSON。这条红了就是「设置窗里找不到」
    Console.WriteLine($"  番茄钟页的两个自动开始开关: {(switchOk ? "是" : "否")}  {string.Join(" / ", switchNotes)}");

    // 第三层: 托盘那两行文字是纯函数, 直接喂假值对文案, 不用真等 25 分钟
    var phaseType = typeof(TinyEngine.PomodoroPhase);
    var textMethod = formType.GetMethod("FocusText", BindingFlags.NonPublic | BindingFlags.Static)!;
    var tipMethod = formType.GetMethod("FocusTip", BindingFlags.NonPublic | BindingFlags.Static)!;
    object Phase(object ordinal) => Enum.ToObject(phaseType, ordinal);
    var focusTextCases = new (string Got, string Want)[]
    {
        // 没在计时就不念轮内第几段 —— 那会儿根本没有「这一轮」
        ((string)textMethod.Invoke(null, new[] { Phase(0), false, TimeSpan.Zero, 3, 1, 4 })!, "没在计时 · 今日 3"),
        ((string)textMethod.Invoke(null, new[] { Phase(1), false, TimeSpan.FromMinutes(4.5), 1, 2, 4 })!, "专注中 剩 04:30 · 本轮 2/4 · 今日 1"),
        ((string)textMethod.Invoke(null, new[] { Phase(1), true, TimeSpan.FromSeconds(30), 0, 1, 4 })!, "已暂停 剩 00:30 · 本轮 1/4 · 今日 0"),
        ((string)textMethod.Invoke(null, new[] { Phase(2), false, TimeSpan.FromMinutes(5), 2, 3, 6 })!, "短休息 剩 05:00 · 本轮 3/6 · 今日 2"),
        // 时长上限给到 180, 而 mm 是「分」这一位: 两小时要是读成 00:00, 气泡和托盘会一起骗人
        ((string)textMethod.Invoke(null, new[] { Phase(1), false, TimeSpan.FromHours(2), 0, 4, 4 })!, "专注中 剩 120:00 · 本轮 4/4 · 今日 0"),
        ((string)tipMethod.Invoke(null, new[] { Phase(1), 25, 0 })!, "开始 25 分钟, 专心"),
        ((string)tipMethod.Invoke(null, new[] { Phase(3), 15, 4 })!, "连着做完一轮, 今日 4 个, 歇 15 分钟"),
    };
    var focusTextOk = focusTextCases.All(c => c.Got == c.Want);
    foreach (var c in focusTextCases.Where(c => c.Got != c.Want))
        Console.WriteLine($"    ✗ 文案: 「{c.Got}」 应为 「{c.Want}」");

    int At(string text) => Array.IndexOf(texts, text);
    // 「头像框」这一项已经撤了, 留着当判据: 托盘里不该再有它。
    // 「查看天气」是右键改道多出来的那一步之外的一条近路 —— 托盘上不留它, 用户就只能每次先挑菜单
    var menuOk = At("切换角色") >= 0 && At("番茄钟") >= 0 && At("台词") >= 0 && At("查看天气") >= 0
        && At("设置(&S)") > At("切换角色") && At("设置(&S)") > At("番茄钟") && At("设置(&S)") > At("台词")
        && At("设置(&S)") > At("查看天气")
        && At("头像框") < 0;
    Console.WriteLine($"  托盘菜单: {(menuOk ? "是" : "否")}  {string.Join(" → ", texts.Take(Math.Max(At("设置(&S)"), 0) + 1))}");

    // 第四层: 倒计时浮窗该摆在哪、该不该摆、底板拉不花。全是纯函数, 不碰窗口, 所以照样无头
    var anchorOk = FloatAnchor(asm);
    var gestureOk = FloatGesture(asm);
    var plateOk = PlateStretch(asm);
    // 第五层: 预设小窗的版面、打靶和写盘那一步
    var presetOk = PresetWindow(asm);
    // 第六层: 真建一扇宠物窗口。前面几条全是纯函数, 谁都碰不到「启动卡死」这一类
    var bootOk = PetWindowBoots(asm);
    // 第七层: 配置那一腿真推到引擎没有 —— 借上面那扇窗口, 八个键逐个对一遍
    var focusLegOk = FocusLegLands(asm, staForm!);
    // 第八层: 真往窗口上贴一次图。摆位那几条只回答「该在哪」, 这一条回答「贴上了没有」
    var pushOk = LayeredPushLands(asm);
    // 第九层: 数字条齐不齐现在全在素材里, 代码一行都不管, 那就对着装好的 png 量
    var digitOk = DigitSetBalanced(asm);
    // 第十层: 字和装饰件这两样只能量 —— 每句话放不放得下、小字够不够粗、右下角那几枚压没压到点得着的地方
    var typeDecoOk = TypeAndDeco(asm);
    // 第十一层: 台词气泡。装机的两张件、池子里每一条折得开折不开、还有那张一秒一格的表
    var bubbleOk = SpeechBubble(asm);
    // 第十二层: 托盘「切换角色」那几行。名表漏一只, 那一行就掉回拼音 stem, 而这件事只有托盘展开那一刻才发生
    var petMenuOk = PetMenuNames(asm, staForm!);
    // 第十三层: 右键弹的功能选择小窗。一行一句话一个去向, 加「点下去到底开了哪一扇」的真调度
    var chooserOk = PetMenuChooser(asm);
    // 第十四层: 天气卡片。三家真回包 → 一张卡片 → 板上五行(底下那句建议再折成两行), 一跳一跳对答案(全程只喂字符串, 判据自己不联网)
    var weatherOk = WeatherCard(asm);
    // 第二十五层: 应用图标那颗换成了不知火。图不进仓库, 所以这量的是链子: 装机的在不在/接了三处没有/没那张退不退得回占位/
    // resx 有没有夹带版权件/正式产物 exe 里那颗是不是它, 顺带报时那颗并表达摩的默认值
    var iconOk = AppIconChain(asm);
    // 第二十六层: 对外那一层整体换成 BwpDesktopPet + 百闻牌桌宠, 内层那半(数据目录/Mutex/注册表值名/命名空间)还得是 DeskSpine
    var nameOk = VisibleNameChain(asm);
    // 第二十七层: 随附件带过去的素材, 首启自己登记进名册(配置只认 LOCALAPPDATA, 不登记就是空名册)
    var bundleOk = BundledSeed(asm);

    var pass = rosterOk && menuOk && focusJsonOk && legacyOk && focusFormOk && slotOk && clampOk
        && focusTextOk && focusIconOk && keyOk && switchOk && anchorOk && gestureOk && plateOk && presetOk
        && bootOk && focusLegOk && pushOk && digitOk && typeDecoOk && bubbleOk && petMenuOk
        && chooserOk && weatherOk && iconOk && nameOk && bundleOk;
    Console.WriteLine(pass ? "DESK OK" : "DESK FAIL");
    return pass ? 0 : 1;
}

/// <summary>从 bwp-assets 里跑和从 bin 里跑都要找得到, 所以一路往上找仓库根。装的是 BwpDesktopPet.dll(对外那层的名字), exe 只是原生壳</summary>
static string FindDeskDll()
{
    for (var dir = new DirectoryInfo(Directory.GetCurrentDirectory()); dir is not null; dir = dir.Parent)
    {
        var candidate = Path.Combine(dir.FullName, "deskspine", "out", "x64", "Release", "net8.0-windows", "win-x64", "BwpDesktopPet.dll");
        if (File.Exists(candidate)) return candidate;
    }
    return "BwpDesktopPet.dll";
}

/// <summary>
/// 天气那三跳真跑一遍 —— 全仓库只有这一趟会出门。第 24 条量的是「字符串进、答案出」,
/// 端点还活不活着、回来的城名是不是中文、这一趟要等几秒, 只有这里能替用户说话。
/// 一次假数据都不许有: 拿不到就照实说拿不到, 拿到的就是板上会给用户看的那五行(读数四 + 底下一句建议)
/// </summary>
int WeatherProbe(string[] args)
{
    var target = args.Length > 0 ? Path.GetFullPath(args[0]) : FindDeskDll();
    if (!File.Exists(target))
    {
        Console.WriteLine($"  找不到 {target}");
        return 1;
    }
    var asm = Assembly.LoadFrom(target);
    var svc = asm.GetType("DeskSpine.WeatherService")!;
    var all = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static;

    var started = DateTimeOffset.Now;
    object? outcome;
    try
    {
        var task = (Task)svc.GetMethod("Fetch", all)!.Invoke(null, Array.Empty<object>())!;
        if (!task.Wait(TimeSpan.FromSeconds(40)))
        {
            Console.WriteLine($"  WEATHER FAIL  四十秒还没回来(每一跳的上限是 {svc.GetField("TimeoutSeconds", all)!.GetValue(null)} 秒)");
            return 1;
        }
        outcome = task.GetType().GetProperty("Result")!.GetValue(task);
    }
    catch (Exception ex)
    {
        var e = ex.GetBaseException();
        Console.WriteLine($"  WEATHER FAIL  这趟直接抛了({e.GetType().Name}: {e.Message}) —— 产品里那一层本该把异常收成一句中文");
        return 1;
    }

    var reason = outcome!.GetType().GetProperty("Reason")!.GetValue(outcome) as string;
    var card = outcome.GetType().GetProperty("Card")!.GetValue(outcome);
    if (card is null)
    {
        Console.WriteLine($"  WEATHER FAIL  没卡片, 理由是「{reason ?? "(连理由都没给)"}」(跑了 {Math.Round((DateTimeOffset.Now - started).TotalSeconds, 1)} 秒)");
        return 1;
    }
    string Line(string m) => (string)svc.GetMethod(m, all)!.Invoke(null, new[] { card })!;
    var t = card.GetType();
    string V(string p) => $"{t.GetProperty(p)!.GetValue(card)}";
    Console.WriteLine($"  WEATHER OK  真跑一趟 {Math.Round((DateTimeOffset.Now - started).TotalSeconds, 1)} 秒");
    Console.WriteLine($"  板上读数四行: 「{Line("CityLine")}」 / 「{Line("NowLine")}」 / 「{Line("WindLine")}」 / 「{Line("TodayLine")}」");
    var adv = svc.GetMethod("PickNote", all)!.Invoke(null, new[] { card })!;
    string Sent(string pet) => (string)svc.GetMethod("AdviceSentence", all)!.Invoke(null, new[] { card, pet })!;
    Console.WriteLine($"  板上那句建议: 挑中 {adv} → 中性「{Sent("")}」 / 她「{Sent("不知火")}」"
        + "(屏幕上是谁由桌宠自己报, 这一趟两档都打出来给你对眼)");
    Console.WriteLine($"  卡片原件: 温度 {V("TempC")} 现象 {V("Phenomenon")} 风 {V("WindFrom")} {V("WindGrade")} 级 "
        + $"今日 {V("LowC")} ~ {V("HighC")} 定在 {V("ResolvedAt")}");
    var snap = svc.GetMethod("Snapshot", all)!.Invoke(null, Array.Empty<object>())!;
    // Snapshot 回的是 ValueTuple, Item1~Item4 是字段不是属性(属性那一路会拿到 null)
    string S(string i) => $"{snap.GetType().GetField(i)!.GetValue(snap)}";
    Console.WriteLine($"  手里这份位置(写盘就抄它): 「{S("Item1")}」 {S("Item2")},{S("Item3")} 定在 {S("Item4")}");
    return 0;
}

/// <summary>
/// 「启动就卡死」的守门人: 基类的构造把建窗丢给渲染线程, 自己在 windowCreatedEvent 上等,
/// 而建窗流程里会调子类的虚属性 —— 那一刻派生类的字段还没赋上, 一抛 NullReferenceException 就没人 Set(),
/// UI 线程永远等下去。表现是进程活着却没桌宠、托盘也没图标, 再点一次只弹「程序已在运行」。
/// 纯函数判据碰不到这条, 所以这里真建一扇窗口, 只给它 10 秒
/// </summary>
static bool PetWindowBoots(Assembly asm)
{
    var slotCount = (int)asm.GetType("DeskSpine.SpineConfig")!
        .GetField("SlotCount", BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;

    var job = Task.Run(() =>
    {
        var window = new TinyEngine.SpineRenderWindow(slotCount);
        try
        {
            var g = window.Geometry;
            return (Handle: window.Handle != IntPtr.Zero,
                    Window: g.WindowPosition, Size: g.WindowSize, Head: g.HeadAnchor);
        }
        finally { window.Dispose(); }
    });

    var cameBack = job.Wait(TimeSpan.FromSeconds(10));
    var boom = job.IsCompleted && job.IsFaulted ? job.Exception!.GetBaseException() : null;
    var got = cameBack && boom is null ? job.Result
                                       : (Handle: false, Window: new SFML.System.Vector2i(),
                                         Size: new SFML.System.Vector2u(), Head: new SFML.System.Vector2i());
    // 骨骼还没装载, 包围盒是空的, 锚点就该退到窗口上沿居中; 停在 (0,0) 等于浮窗钉在屏幕左上角
    var topCentre = got.Head.X == got.Window.X + (int)got.Size.X / 2 && got.Head.Y == got.Window.Y;

    return Criteria("宠物窗口建得出来也不卡死(启动路径)", new (string, bool, string, string)[]
    {
        ("渲染线程把窗口交回来了", cameBack && boom is null,
            !cameBack ? "10 秒没回来" : boom is null ? "回来了" : $"抛了 {boom!.GetType().Name}: {boom.Message}", "10 秒内回来且不抛"),
        ("窗口句柄拿到了", got.Handle, got.Handle ? "有" : "无", "有"),
        ("空包围盒时锚点退到窗口上沿居中", topCentre,
            $"窗口 {got.Window.X},{got.Window.Y} 尺寸 {got.Size.X}x{got.Size.Y} → 锚点 {got.Head.X},{got.Head.Y}",
            $"({got.Window.X + (int)got.Size.X / 2},{got.Window.Y})"),
    });
}

/// <summary>
/// 配置那一腿到底推没推到引擎: <c>ApplyFocus</c> 是「存一次盘 → 引擎认账」的唯一通路, 前面几条看的都是
/// 配置自己在 JSON 和控件之间怎么走, 谁都没碰到「这八个键逐个交给 Pomodoro」那一下。
/// 漏一个的形状就是「设置里改了时长没反应」, 而这轮新加的两个自动开始开关正好走这条腿。
/// 借第 14 条那种真窗口 + 已经建好的设置窗, 把 Program 那两个 private setter 顶一次, 读完立刻还原
/// </summary>
static bool FocusLegLands(Assembly asm, object form)
{
    var programType = asm.GetType("DeskSpine.Program")!;
    var cfgType = asm.GetType("DeskSpine.Config")!;
    var windowProp = programType.GetProperty("SpineWindow", BindingFlags.Public | BindingFlags.Static)!;
    var formProp = programType.GetProperty("ConfigForm", BindingFlags.Public | BindingFlags.Static)!;
    var apply = programType.GetMethod("ApplyFocus", BindingFlags.NonPublic | BindingFlags.Static)!;
    var slotCount = (int)asm.GetType("DeskSpine.SpineConfig")!
        .GetField("SlotCount", BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;

    // 七个键喂一组和默认值全不同的数; 气泡开关和图标是推给设置窗的, 单独对
    var keys = new[] { "WorkMinutes", "BreakMinutes", "LongBreakMinutes", "CyclesPerLongBreak",
                       "BlockSleepWhileWorking", "AutoStartBreak", "AutoStartWork" };
    var feed = new object[] { 17, 3, 23, 6, false, false, false };
    const string SentinelIcon = @"Z:\哨兵.ico";

    var job = Task.Run(() =>
    {
        var window = new TinyEngine.SpineRenderWindow(slotCount);
        windowProp.SetValue(null, window);
        formProp.SetValue(null, form);
        try
        {
            var focusCfg = cfgType.GetProperty("PomodoroConfig")!.GetValue(Activator.CreateInstance(cfgType))!;
            var balloonProp = form.GetType().GetProperty("FocusBalloon")!;
            var iconProp = form.GetType().GetProperty("FocusBalloonIconPath")!;
            // 先把这两样拧到「和待会推过去的相反」, 不然它本来就是那个值, 这一行永远绿
            balloonProp.SetValue(form, false);
            iconProp.SetValue(form, null);
            for (int i = 0; i < keys.Length; i++)
                focusCfg.GetType().GetProperty(keys[i])!.SetValue(focusCfg, feed[i]);
            focusCfg.GetType().GetProperty("BalloonOnPhaseChange")!.SetValue(focusCfg, true);
            focusCfg.GetType().GetProperty("BalloonIconPath")!.SetValue(focusCfg, SentinelIcon);

            apply.Invoke(null, new[] { focusCfg });

            var engine = window.Pomodoro!;
            var drift = new List<string>();
            for (int i = 0; i < keys.Length; i++)
            {
                var got = engine.GetType().GetProperty(keys[i])!.GetValue(engine);
                if (!Equals(got, feed[i])) drift.Add($"{keys[i]}={got}");
            }
            return (Drift: drift,
                    Balloon: Equals(balloonProp.GetValue(form), true),
                    Icon: Equals(iconProp.GetValue(form), SentinelIcon));
        }
        finally
        {
            windowProp.SetValue(null, null);
            formProp.SetValue(null, null);
            window.Dispose();
        }
    });

    var cameBack = job.Wait(TimeSpan.FromSeconds(10));
    var boom = job.IsCompleted && job.IsFaulted ? job.Exception!.GetBaseException() : null;
    var got2 = cameBack && boom is null
        ? job.Result
        : (Drift: new List<string> { boom is null ? "10 秒没回来" : $"抛了 {boom.GetType().Name}: {boom.Message}" },
           Balloon: false, Icon: false);

    return Criteria("配置那一腿真推到引擎(ApplyFocus)", new (string, bool, string, string)[]
    {
        ($"{keys.Length} 个键逐个交给 Pomodoro", got2.Drift.Count == 0,
            got2.Drift.Count == 0 ? "全对" : string.Join(",", got2.Drift), "17/3/23/6/关/关/关"),
        ("气泡开关推给设置窗那个勾选", got2.Balloon, got2.Balloon ? "开了" : "没开", "跟着配置开"),
        ("番茄钟自己那颗图标也推到了", got2.Icon, got2.Icon ? "哨兵路径" : "空", SentinelIcon),
    });
}

/// <summary>
/// 第十二层: 托盘「切换角色」那几行。名表漏一只, 那一行就掉回拼音 stem, 而这件事只有真展开一次菜单才发生 ——
/// 名表自己查自己绿不代表菜单绿, 中间还隔着 SetSpine 装载和 RefreshPetMenu 渲染两道。
/// 所以这里两腿都量: ① 名表把库里出货的四只都翻得出中文(纯函数); ② 真建窗口、真装四只骨架、
/// 真调一次私有的 RefreshPetMenu, 把 commandPets 上那几行字读回来, 对一遍是不是中文名而不是拼音
/// </summary>
static bool PetMenuNames(Assembly asm, object form)
{
    // 库里出货的四只, 以及名表该给的中文名(和 PetNames.cs 一字不差)
    var pets = new (string Stem, string Name)[]
    {
        ("buzhihuo_1127", "不知火"),
        ("qianji_0552", "千姬"),
        ("maozhanggui_sp_yihua_3754", "猫掌柜焕宴"),
        ("xieji_0481", "蟹姬"),
    };

    var display = asm.GetType("DeskSpine.PetNames")!
        .GetMethod("Display", BindingFlags.Public | BindingFlags.Static)!;
    // ① 名表这一腿: 只喂假路径看翻不翻得出中文, 不碰窗口。漏一只这里就先红
    var tableMiss = pets
        .Select(p => (p.Name, Got: (string)display.Invoke(null, new object?[] { $@"C:\res\spine\{p.Stem}\{p.Stem}.skel" })!))
        .Where(x => x.Got != x.Name)
        .Select(x => $"{x.Name}→{x.Got}")
        .ToArray();

    // 真骨架在 bwp-assets/t/spine_emotion 下, 从哪跑都要找得到 → 一路上翻找仓库根
    string? libRoot = null;
    for (var dir = new DirectoryInfo(Directory.GetCurrentDirectory()); dir is not null; dir = dir.Parent)
    {
        var cand = Path.Combine(dir.FullName, "bwp-assets", "t", "spine_emotion");
        if (Directory.Exists(cand)) { libRoot = cand; break; }
    }
    var skels = pets.Select(p => libRoot is null ? null : Path.Combine(libRoot, p.Stem, p.Stem + ".skel")).ToArray();
    var missing = pets.Where((p, i) => skels[i] is null || !File.Exists(skels[i])).Select(p => p.Stem).ToArray();

    var slotCount = (int)asm.GetType("DeskSpine.SpineConfig")!
        .GetField("SlotCount", BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;
    var windowProp = asm.GetType("DeskSpine.Program")!
        .GetProperty("SpineWindow", BindingFlags.Public | BindingFlags.Static)!;
    var formType = form.GetType();
    var refresh = formType.GetMethod("RefreshPetMenu", BindingFlags.NonPublic | BindingFlags.Instance)!;
    var petsField = formType.GetField("commandPets", BindingFlags.NonPublic | BindingFlags.Instance)!;

    // ② 托盘那几行: 真建窗口、真装四只、真调一次 RefreshPetMenu, 把菜单上的字读回来
    var menuTexts = Array.Empty<string>();
    var boomNote = "";
    if (missing.Length == 0)
    {
        var job = Task.Run(() =>
        {
            var window = new TinyEngine.SpineRenderWindow(slotCount);
            windowProp.SetValue(null, window);
            try
            {
                var spine = window.Spine;
                spine.Version = Spine.SpineVersion.V36;
                spine.AnimatorType = TinyEngine.AnimatorType.BwpHero;
                spine.UsePremultipliedAlpha = true;
                for (int i = 0; i < skels.Length; i++) spine.SetSpine(skels[i]!, i);
                refresh.Invoke(form, new object?[] { 0 });
                var host = petsField.GetValue(form)!;
                var drop = (System.Collections.IEnumerable)host.GetType().GetProperty("DropDownItems")!.GetValue(host)!;
                var texts = new List<string>();
                foreach (var it in drop)
                {
                    var t = (string)it.GetType().GetProperty("Text")!.GetValue(it)!;
                    if (t.Length > 0) texts.Add(t);   // 分隔条 Text 为空, 跳过
                }
                return texts.ToArray();
            }
            finally { windowProp.SetValue(null, null); window.Dispose(); }
        });
        var cameBack = job.Wait(TimeSpan.FromSeconds(30));
        var boom = job.IsCompleted && job.IsFaulted ? job.Exception!.GetBaseException() : null;
        if (cameBack && boom is null) menuTexts = job.Result;
        else boomNote = !cameBack ? "30 秒没回来" : $"{boom!.GetType().Name}: {boom.Message}";
    }
    else boomNote = $"库里缺骨架: {string.Join(",", missing)}";

    // 名册多于一只时末尾那行「图层模式(全部槽位)」也要在
    var expected = pets.Select(p => p.Name).Append("图层模式(全部槽位)").ToArray();
    var menuOk = menuTexts.SequenceEqual(expected);

    return Criteria("托盘「切换角色」那几行都渲染成中文名", new (string, bool, string, string)[]
    {
        ("名表把四只都翻成中文", tableMiss.Length == 0,
            tableMiss.Length == 0 ? "四只都对" : string.Join(",", tableMiss), "不知火/千姬/猫掌柜焕宴/蟹姬"),
        ("四只骨架都在库里找得到", missing.Length == 0,
            missing.Length == 0 ? "都在" : string.Join(",", missing), "bwp-assets/t/spine_emotion 下四只都在"),
        ("真展开一次菜单, 那几行是中文名不是拼音", menuOk,
            boomNote.Length > 0 ? boomNote : string.Join("|", menuTexts), string.Join("|", expected)),
    });
}

/// <summary>
/// 贴上去这一步只有真贴一次才算验过：UpdateLayeredWindow 的声明和 Win32 的表只差最后三个参数的顺序，
/// API 就直接返回 false —— bounds 算得再对、图也画得再好，屏幕上还是空的，窗口停在构造时那个大小，
/// 桌面表现就是「右键没反应」。前面几条看的都是「该摆在哪」，这一条看「摆上了没有」
/// </summary>
static bool LayeredPushLands(Assembly asm)
{
    var paint = asm.GetType("DeskSpine.LayeredPaint")!;
    var push = paint.GetMethod("Push", BindingFlags.Public | BindingFlags.Static)!;
    var hide = paint.GetMethod("Hide", BindingFlags.Public | BindingFlags.Static)!;

    var want = new Rectangle(317, 211, 40, 20);      // 故意不给构造默认的那个 300x300
    var got = Rectangle.Empty;
    var painted = false;
    var threw = "";
    var done = new ManualResetEventSlim(false);

    var sta = new Thread(() =>
    {
        try
        {
            using var form = new System.Windows.Forms.Form
            {
                FormBorderStyle = System.Windows.Forms.FormBorderStyle.None,
                ShowInTaskbar = false,
                StartPosition = System.Windows.Forms.FormStartPosition.Manual,
                Size = new Size(300, 300),
            };
            var hwnd = form.Handle;
            // 真小窗是在 CreateParams 里挂的 WS_EX_LAYERED，这儿没本子类可改，建好之后补上同一位
            Win32Probe.SetWindowLong(hwnd, Win32Probe.GWL_EXSTYLE,
                Win32Probe.GetWindowLong(hwnd, Win32Probe.GWL_EXSTYLE) | Win32Probe.WS_EX_LAYERED);
            form.Show();
            using var art = new Bitmap(want.Width, want.Height, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
            using (var g = Graphics.FromImage(art)) g.Clear(Color.Transparent);
            painted = (bool)push.Invoke(null, new object[] { hwnd, art, want })!;
            Win32Probe.GetWindowRect(hwnd, out var r);
            got = new Rectangle(r.Left, r.Top, r.Right - r.Left, r.Bottom - r.Top);
            hide.Invoke(null, new object[] { hwnd });
            form.Close();
        }
        catch (Exception e) { threw = $"{e.GetType().Name}: {e.Message}"; }
        finally { done.Set(); }
    });
    sta.SetApartmentState(ApartmentState.STA);
    sta.IsBackground = true;
    sta.Start();
    var cameBack = done.Wait(TimeSpan.FromSeconds(10));

    return Criteria("逐像素透明真贴得上去(浮窗和小窗共用的那一层)", new (string, bool, string, string)[]
    {
        ("贴这一趟跑完了", cameBack && threw.Length == 0,
            !cameBack ? "10 秒没回来" : threw.Length == 0 ? "跑完了" : threw, "10 秒内跑完且不抛"),
        ("UpdateLayeredWindow 认这次贴图", painted, painted ? "贴上了" : "返回 false", "贴上了"),
        ("窗口落在给的矩形上, 不是停在构造大小", got == want, $"{got.X},{got.Y}~{got.Width}x{got.Height}",
            $"{want.X},{want.Y}~{want.Width}x{want.Height}"),
    });
}

/// <summary>
/// 数字条齐不齐如今全写在素材里 —— FocusArt.DigitStrip 只把整图缩到 36 高, 谁高谁矮它不管。
/// 所以这条只能对着装好的 png 量: 十一个字坐同一张画布(不然「等比缩」就不是等比)、
/// 本体底边坐在同一条基线上(冒号两点在腰上, 不参与)、墨迹高收在一个窄带里。
/// 上一套 warm/ 前两条就红: 画布 88..103、底边留白 0~7, 因为 5 的右下角挂着一颗 76 px 的墨点
/// 把框撑到 82x103 而本体只有 66x96 —— 用户说「5 不协调」, 量出来就是这个形状
/// </summary>
static bool DigitSetBalanced(Assembly asm)
{
    var dir = Path.Combine(Path.GetDirectoryName(asm.Location)!, @"res\image\focus_ui\digits");
    var rows = new List<(string Name, int Canvas, int Top, int Bottom)>();
    foreach (var ch in "0123456789:")
    {
        var file = Path.Combine(dir, ch == ':' ? "colon.png" : $"{ch}.png");
        if (!File.Exists(file))
        {
            Console.WriteLine($"  数字条配平: 否  读不到 {file}（先跑 python ../bwp-assets/install_focus_ui.py）");
            return false;
        }
        // 读进内存再放手, 免得锁住输出目录那张
        using var bmp = new Bitmap(new MemoryStream(File.ReadAllBytes(file)));
        int top = bmp.Height, bottom = -1;
        for (var y = 0; y < bmp.Height; y++)
            for (var x = 0; x < bmp.Width; x++)
                if (bmp.GetPixel(x, y).A >= 24)
                {
                    if (y < top) top = y;
                    if (y > bottom) bottom = y;
                }
        rows.Add((Path.GetFileName(file), bmp.Height, top, bottom));
    }

    var canvases = rows.Select(r => r.Canvas).Distinct().OrderBy(v => v).ToArray();
    var ten = rows.Where(r => r.Name != "colon.png").ToArray();
    var feet = ten.Select(r => r.Canvas - 1 - r.Bottom).ToArray();   // 底边到画布下沿留了几格
    var heights = ten.Select(r => r.Bottom - r.Top + 1).OrderBy(v => v).ToList();
    var spread = 100.0 * (heights[^1] - heights[0]) / heights[heights.Count / 2];

    return Criteria("数字条十个字配得平(素材那一侧的画布/基线/高差)", new (string, bool, string, string)[]
    {
        ("十一个字同一张画布高", canvases.Length == 1, string.Join("/", canvases), "一个数"),
        ("本体底边坐在同一条基线上(冒号在腰上, 不算)", feet.Distinct().Count() == 1,
            $"底边留白 {feet.Min()}~{feet.Max()} 格", "全等"),
        ("墨迹高收在窄带里", spread <= 8,
            $"{heights[0]}~{heights[^1]} 格, 极差 {spread:F1}%", "≤ 中位高的 8%"),
    });
}

/// <summary>
/// 浮窗落点那条链: 骨骼世界包围盒 →(翻了 Y 的视图)→ 窗口像素 → 屏幕锚点 → 浮窗矩形, 一路喂假数对坐标。
/// 上下最容易写反, 反了浮窗就贴到肚子上 —— 而那只有肉眼看得出, 所以先把算式钉死
/// </summary>
static bool FloatAnchor(Assembly asm)
{
    // 现场那个视图: Center=(0,200)、Size.Y 是负的, 所以世界里的「上」就是屏幕上的「上」
    var centre = new SFML.System.Vector2f(0, 200);
    var size = new SFML.System.Vector2u(320, 420);
    var headMethod = asm.GetType("DeskSpine.FocusArt")!
        .GetMethod("HeadBounds", BindingFlags.Public | BindingFlags.Static)!;
    Rectangle Float(Point head, Size panel, Rectangle work)
        => (Rectangle)headMethod.Invoke(null, new object[] { head, panel, work, 6 })!;
    SFML.System.Vector2i AnchorAt(int x, int y, SFML.Graphics.FloatRect box)
        => new TinyEngine.LayeredRenderWindow.PetGeometry(new(x, y), size, box).HeadAnchor;

    // 假骨骼: 脚在 y=100、头顶在 y=300, 宽 160 居中 —— 换成缩放一半就是脚 y=50、头顶 y=150
    var pixel = TinyEngine.LayeredRenderWindow.WorldToPixel(new(-80, 100, 160, 200), centre, size);
    var half = TinyEngine.LayeredRenderWindow.WorldToPixel(new(-40, 50, 80, 100), centre, size);
    var head = AnchorAt(400, 300, pixel);
    var moved = AnchorAt(700, 150, pixel);
    var small = AnchorAt(400, 300, half);
    var blank = AnchorAt(400, 300, default);
    var panel = new Size(220, 64);
    var work = new Rectangle(0, 0, 1920, 1040);
    var box = Float(new Point(head.X, head.Y), panel, work);
    var corner = Float(new Point(20, 10), panel, work);
    var edge = Float(new Point(1910, 1035), panel, work);
    var inside = (Rectangle r) => work.Left <= r.Left && work.Top <= r.Top && r.Right <= work.Right && r.Bottom <= work.Bottom;

    var cases = new (string What, bool Ok, string Got, string Want)[]
    {
        // 110 是头顶、310 是脚: 世界里最高的那条边落到像素的小 y 上, 才是屏幕的上方
        ("世界框翻成窗口像素(头顶没翻到脚下去)",
            Approx(pixel.Left, 80) && Approx(pixel.Top, 110) && Approx(pixel.Top + pixel.Height, 310),
            $"顶={pixel.Top:0} 底={pixel.Top + pixel.Height:0}", "顶=110 底=310"),
        ("锚点坐在头顶上沿的中点", head.X == 560 && head.Y == 410, $"({head.X},{head.Y})", "(560,410)"),
        ("窗口挪走 300,-150 锚点跟着挪同样这么多",
            moved.X - head.X == 300 && moved.Y - head.Y == -150, $"({moved.X},{moved.Y})", "(860,260)"),
        ("骨骼缩到一半, 头顶落回下面 150 格", small.X == 560 && small.Y - head.Y == 150, $"({small.X},{small.Y})", "(560,560)"),
        ("骨骼还没装载就退到窗口上沿居中", blank.X == 560 && blank.Y == 300, $"({blank.X},{blank.Y})", "(560,300)"),
        // 这条就是「贴头顶」的语义: 浮窗的水平中线压在锚点上, 下沿离锚点正好一个 gap
        ("浮窗居中且下沿坐在头顶上",
            box.X == 450 && box.Y == 340 && box.Bottom + 6 == head.Y && box.X + panel.Width / 2 == head.X,
            $"({box.X},{box.Y},{box.Width},{box.Height})", "(450,340,220,64)"),
        ("宠物贴屏幕左上角时夹回工作区", corner.X == 0 && corner.Y == 0 && inside(corner),
            $"({corner.X},{corner.Y})", "(0,0)"),
        ("宠物贴屏幕右下角时也不会跑到屏外", inside(edge), $"({edge.X},{edge.Y},{edge.Width},{edge.Height})", "整条留在工作区里"),
    };
    return Criteria("浮窗贴在宠物头顶(算式)", cases);
}

static bool Approx(float got, float want) => Math.Abs(got - want) < 0.5f;

/// <summary>
/// 右键是全场唯一空闲的手势(右键拖动=移动宠物), 所以「没挪窝的右键」归预设小窗当入口。
/// 浮窗不再听右键开关, 也不再接受「点一下收起来」—— 计时中就一直露, 只有宠物收起来才跟着收。
/// 判的是那道共用的阈值闸门和这张露/收的表 —— 真鼠标有没有走对分支还得桌面复验
/// </summary>
static bool FloatGesture(Assembly asm)
{
    var form = asm.GetType("DeskSpine.FocusFloatForm")!;
    var flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    bool Next(bool running, bool stowed)
        => (bool)form.GetMethod("NextVisible", flags)!.Invoke(null,
            new object[] { running, stowed })!;
    string Clock(TimeSpan left) => (string)form.GetMethod("ClockText", flags)!.Invoke(null, new object[] { left })!;

    var dragCases = new ((int X, int Y) Delta, bool Drag)[]
    {
        ((0, 0), false), ((3, 0), false), ((0, -4), false), ((4, 4), false),
        ((5, 0), true), ((0, 6), true), ((0, -5), true), ((-5, 3), true),
    };
    var dragOk = dragCases.All(c =>
        TinyEngine.LayeredRenderWindow.IsDragMove(new SFML.System.Vector2i(c.Delta.X, c.Delta.Y)) == c.Drag);
    foreach (var c in dragCases.Where(c =>
        TinyEngine.LayeredRenderWindow.IsDragMove(new SFML.System.Vector2i(c.Delta.X, c.Delta.Y)) != c.Drag))
        Console.WriteLine($"    ✗ 位移 {c.Delta} 该{(c.Drag ? "算拖动" : "算单击")}");

    var cases = new (string What, bool Ok, string Got, string Want)[]
    {
        ($"按下到抬起挪 {dragCases.Max(c => c.Drag ? 0 : Math.Max(Math.Abs(c.Delta.X), Math.Abs(c.Delta.Y)))} 格以内还算单击、{dragCases.Min(c => c.Drag ? Math.Max(Math.Abs(c.Delta.X), Math.Abs(c.Delta.Y)) : 99)} 格就改算拖动",
            dragOk, dragOk ? "分得开" : "分不开", "4/5 之间翻脸"),
        ("没计时就不占屏幕", !Next(false, false), "", ""),
        ("计时中就一直露着（谁点都不收）", Next(true, false), "", ""),
        ("宠物沉进壁纸层就把浮窗一起收走", !Next(true, true), "", ""),
        ("宠物从壁纸层回来, 计时中就重新露", Next(true, false), "", ""),
        // 点一下就把整段倒计时收走, 误触之后就没进度感了 —— 这条按用户要求撤掉, 判它别悄悄回来
        ("浮窗不再自己接单击", form.GetMethod("OnMouseClick", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly) is null,
            form.GetMethod("OnMouseClick", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly) is null ? "没接" : "还接着", "没有这个重写"),
        ("浮窗里没有『点掉的那一段』这种状态", form.GetField("dismissedAt", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly) is null,
            form.GetField("dismissedAt", BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly) is null ? "没这个字段" : "还有这个字段", "没有这个字段"),
        ("走字 4 分半", Clock(TimeSpan.FromMinutes(4.5)) == "04:30", Clock(TimeSpan.FromMinutes(4.5)), "04:30"),
        ("走字 30 秒", Clock(TimeSpan.FromSeconds(30)) == "00:30", Clock(TimeSpan.FromSeconds(30)), "00:30"),
        // 设到 60 分钟以上时旧写法(ToString(@"mm\:ss"))会把两小时读成 00:00, 而时长上限给到 180
        ("走字两小时不折回 00:00", Clock(TimeSpan.FromHours(2)) == "120:00", Clock(TimeSpan.FromHours(2)), "120:00"),
    };
    return Criteria("右键分流 / 浮窗露收规则", cases);
}

/// <summary>
/// 两张底板都不到 300 px, 浮窗条要 420x150、小窗板要 276x406: 三段切九块贴才拉得开。
/// 整图缩放做不到 —— 圆角和边带会跟着一起涨, 所以两种做法都跑一遍, 让「不涨」这条真有对比对象。
/// 边带宽一律现从 FocusArt 读, 不在这儿写死 —— 写死了代码改 inset 判据还跟着旧值夸, 那就白验了。
/// 实心板 bg_tips_3 四角几乎是直角、整行都是墨, 量不出「边带厚度」; 它会被拉花的地方是顶栏那两笔墨痕
/// </summary>
static bool PlateStretch(Assembly asm)
{
    var dir = Path.Combine(Path.GetDirectoryName(asm.Location)!, @"res\image\focus_ui");
    var art = asm.GetType("DeskSpine.FocusArt")!;
    var crisp = art.GetMethod("Crisp", BindingFlags.Public | BindingFlags.Static)!;
    var slice = art.GetMethod("NineSlice", BindingFlags.Public | BindingFlags.Static)!;
    int Inset(string field) => (int)art.GetField(field, BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;
    var all = new List<(string What, bool Ok, string Got, string Want)>();

    foreach (var (name, file, inset, to, hollow) in new (string, string, int, Size, bool)[]
    {
        ("浮窗条", "bg_kuang02.png", Inset("FrameInset"), new Size(420, 150), true),
        ("小窗板", "bg_tips_3.png", Inset("PanelInset"), new Size(276, 406), false),
    })
    {
        var tilePath = Path.Combine(dir, file);
        if (!File.Exists(tilePath))
        {
            Console.WriteLine($"  九宫格底板: 否  读不到 {tilePath}（先跑 python ../bwp-assets/install_focus_ui.py）");
            return false;
        }
        // 读进内存再放手, 免得锁住输出目录那张, 下次构建覆盖不了
        using var tile = new Bitmap(new MemoryStream(File.ReadAllBytes(tilePath)));

        Bitmap Paint(bool wholeImage)
        {
            var bmp = new Bitmap(to.Width, to.Height, System.Drawing.Imaging.PixelFormat.Format32bppArgb);
            using var g = Graphics.FromImage(bmp);
            g.Clear(Color.Transparent);
            crisp.Invoke(null, new object[] { g });
            var dest = new Rectangle(0, 0, to.Width, to.Height);
            if (wholeImage) g.DrawImage(tile, dest);
            else slice.Invoke(null, new object[] { g, tile, dest, inset });
            return bmp;
        }
        using var sliced = Paint(false);
        using var blown = Paint(true);

        // 「看得见」= alpha 32 以上: 白框外圈那道亮边本来就是半透明的
        bool Ink(Bitmap b, int x, int y) => b.GetPixel(x, y).A >= 32;
        int ClearRun(Func<int, bool> ink, int max) { var i = 0; while (i < max && !ink(i)) i++; return i; }  // 开头空了几格
        int InkRun(Func<int, bool> ink, int max) { var i = 0; while (i < max && ink(i)) i++; return i; }      // 开头有墨几格
        // 探的是图自己那条边线, 不是画布第 0 格: 小窗板左边 20 列是装机抹掉邻格碎片留下的空白, 拿 x=0 探会探到一片空
        int LeftEdge(Bitmap b) => Enumerable.Range(0, b.Width).First(x => Ink(b, x, b.Height / 2));
        int TopEdge(Bitmap b) => Enumerable.Range(0, b.Height).First(y => Ink(b, b.Width / 2, y));
        int TopRun(Bitmap b) => ClearRun(i => Ink(b, LeftEdge(b), i), b.Height);   // 左边线空到第几格 = 圆角竖着占几格
        int LeftRun(Bitmap b) => ClearRun(i => Ink(b, i, TopEdge(b)), b.Width);    // 上边线空到第几格 = 圆角横着占几格
        int BandX(Bitmap b) => InkRun(i => Ink(b, i, b.Height / 2), b.Width);      // 左边界带有多厚

        // 顶栏那两笔墨痕竖着占几行: 上边线以下 6 格起算, 免得把边线自己数进去; 横向只认纸面里那一段 x=85~211
        int TopMark(Bitmap b) => Enumerable.Range(TopEdge(b) + 6, Math.Min(60, b.Height - TopEdge(b) - 6)).Count(y =>
            Enumerable.Range(85, 127).Any(x => x < b.Width &&
                b.GetPixel(x, y).A >= 120 &&
                (b.GetPixel(x, y).R + b.GetPixel(x, y).G + b.GetPixel(x, y).B) / 3 < 130));

        bool Dark(Bitmap b, int x, int y) =>
            b.GetPixel(x, y).A >= 120 && (b.GetPixel(x, y).R + b.GetPixel(x, y).G + b.GetPixel(x, y).B) / 3 < 200;

        // 纸自己那条左边线: 逐行找最左的一坨墨, 数它连着几格粗。装机抹邻格碎片那一刀要是抹过了头,
        // 就会留下「细的」(1 格)和「断的」(那行最左的墨一下跳到顶栏那两笔上去)两类
        (int thin, int gone, int min) LeftStroke(Bitmap b)
        {
            int thin = 0, gone = 0, min = 99;
            for (int y = TopEdge(b) + 1; y < b.Height - TopEdge(b) - 1; y++)
            {
                if (b.GetPixel(100, y).A < 120) continue;                 // 这一行连纸都没有, 不欠它一条线
                var xs = Enumerable.Range(0, 60).Where(x => Dark(b, x, y)).ToList();
                if (xs.Count == 0 || xs[0] > 40) { gone++; continue; }
                int t = 1;
                while (t < xs.Count && xs[t] == xs[t - 1] + 1) t++;
                if (t < 2) thin++;
                min = Math.Min(min, t);
            }
            return (thin, gone, min == 99 ? 0 : min);
        }

        // 空心框: 沿边带中线拉一圈都该有墨, 拉断了就露馅
        bool NoSeam(Bitmap b) =>
            Enumerable.Range(inset, b.Width - 2 * inset).All(x => Ink(b, x, 2)) &&
            Enumerable.Range(inset, b.Height - 2 * inset).All(y => Ink(b, 2, y));

        // 实心板是带软边和花纹的装饰图, 边带那几格本来就是透的, 量不了「有墨」;
        // 能量的是内圈: 有墨的两头之间不许夹透明 —— 九块漏贴一块就是这种一条缝
        int GapCount(IEnumerable<bool> line)
        {
            var flags = line.ToArray();
            var first = Array.FindIndex(flags, f => f);
            if (first < 0) return flags.Length;
            var last = Array.FindLastIndex(flags, f => f);
            return Enumerable.Range(first, last - first + 1).Count(i => !flags[i]);
        }
        int InnerGaps(Bitmap b) =>
            new[] { b.Height / 4, b.Height / 2, b.Height * 3 / 4 }
                .Sum(y => GapCount(Enumerable.Range(inset * 2, b.Width - 4 * inset).Select(x => Ink(b, x, y)))) +
            new[] { b.Width / 4, b.Width / 2, b.Width * 3 / 4 }
                .Sum(x => GapCount(Enumerable.Range(inset * 2, b.Height - 4 * inset).Select(y => Ink(b, x, y))));

        all.Add(($"{name}圆角不涨(拉成 {to.Width}x{to.Height} 还是 {TopRun(tile)}/{LeftRun(tile)} 格)",
            TopRun(sliced) == TopRun(tile) && LeftRun(sliced) == LeftRun(tile),
            $"{TopRun(sliced)}/{LeftRun(sliced)}", $"{TopRun(tile)}/{LeftRun(tile)}"));
        if (hollow)
        {
            all.Add(($"{name}边带不涨(原图 {BandX(tile)} 格厚)",
                BandX(sliced) == BandX(tile), $"{BandX(sliced)}", $"{BandX(tile)}"));
            all.Add(($"{name}九块都贴上了, 边带中间没有断口",
                NoSeam(sliced), NoSeam(sliced) ? "不断" : "有缝", "不断"));
        }
        else
        {
            all.Add(($"{name}内圈没多出裂缝(横竖各三条, 原图 {InnerGaps(tile)} 处 → 拉出来 {InnerGaps(sliced)} 处)",
                InnerGaps(sliced) == InnerGaps(tile), $"{InnerGaps(sliced)} 处", $"{InnerGaps(tile)} 处"));
            all.Add(($"{name}顶栏那两笔墨痕没被拉长(原图竖着占 {TopMark(tile)} 行)",
                TopMark(sliced) == TopMark(tile), $"{TopMark(sliced)} 行", $"{TopMark(tile)} 行"));
            var ls = LeftStroke(sliced);
            all.Add(($"{name}左边线逐行都还连着且够 2 格粗(原图最细 {LeftStroke(tile).min} 格)",
                ls.thin == 0 && ls.gone == 0, $"最细 {ls.min} 格, 细的 {ls.thin} 行、断的 {ls.gone} 行", "细 0 行、断 0 行"));
            var edge = (Bitmap b) => (Enumerable.Range(0, b.Width).First(x => Ink(b, x, b.Height / 2)),
                                      Enumerable.Range(0, b.Width).Last(x => Ink(b, x, b.Height / 2)));
            all.Add(($"{name}左右两块边带都贴上了(中间那行墨从第 {edge(tile).Item1} 格到第 {edge(tile).Item2} 格)",
                edge(sliced) == edge(tile), $"{edge(sliced).Item1}~{edge(sliced).Item2}",
                $"{edge(tile).Item1}~{edge(tile).Item2}"));
        }
        all.Add(($"{name}整图缩放会涨(对照, 证明判据有牙)",
            hollow ? TopRun(blown) > TopRun(sliced) && BandX(blown) > BandX(sliced)
                   : TopMark(blown) > TopMark(sliced),
            $"圆角 {TopRun(blown)}/{LeftRun(blown)}" + (hollow ? $" 边带 {BandX(blown)}" : $" 墨痕 {TopMark(blown)} 行"),
            hollow ? "比九宫格那版大" : "比九宫格那版占的行多"));
    }
    return Criteria("底板九宫格拉不花(浮窗条 + 小窗板)", all.ToArray());
}

/// <summary>
/// 预设小窗那一层: 版面排得开吗、点得准吗、摆在宠物哪边, 以及最要紧的一条 ——
/// 走小窗写盘只许动番茄钟这一段, 别的段一个键都不许被默认值顶掉(「图层模式」那个 bug 的同类)。
/// 全是纯函数和一份反射搭出来的 Config, 所以照样无头
/// </summary>
static bool PresetWindow(Assembly asm)
{
    var form = asm.GetType("DeskSpine.FocusPresetForm")!;
    var flags = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    var spotsType = asm.GetType("DeskSpine.FocusPresetForm+Spots")!;
    var presets = (Array)form.GetField("Presets", flags)!.GetValue(null)!;
    var spots = form.GetMethod("Arrange", flags)!.Invoke(null, new object[] { presets, 276 })!;
    var hitMethod = form.GetMethod("HitTest", flags)!;
    var art = asm.GetType("DeskSpine.FocusArt")!;
    var side = art.GetMethod("SideBounds", BindingFlags.Public | BindingFlags.Static)!;

    Rectangle Rect(string name) => (Rectangle)spotsType.GetProperty(name)!.GetValue(spots)!;
    Rectangle[] RowRects(string name) => (Rectangle[])spotsType.GetProperty(name)!.GetValue(spots)!;
    Point Centre(Rectangle r) => new(r.X + r.Width / 2, r.Y + r.Height / 2);
    (string What, int Index) Spot(Point at)
    {
        var t = hitMethod.Invoke(null, new object[] { spots, at })!;
        var type = t.GetType();
        return (type.GetField("Item1")!.GetValue(t)!.ToString()!, (int)type.GetField("Item2")!.GetValue(t)!);
    }

    var panel = Rect("Panel");
    var rows = RowRects("Rows");
    var clickable = rows.Concat(new[] { Rect("Switch"), Rect("Start"), Rect("Close") }).ToArray();
    var insidePanel = (Rectangle r) => panel.Left <= r.Left && panel.Top <= r.Top
        && r.Right <= panel.Right && r.Bottom <= panel.Bottom;
    var clashes = clickable.Where((a, i) => clickable.Skip(i + 1).Any(b => a.IntersectsWith(b))).ToArray();
    var rowHits = rows.Select((r, i) => { var s = Spot(Centre(r)); return s.What == "Preset" && s.Index == i; }).ToArray();
    var named = new (string At, (string What, int Index) Got)[]
    {
        ("×", Spot(Centre(Rect("Close")))), ("主按钮", Spot(Centre(Rect("Start")))),
        ("开关行", Spot(Centre(Rect("Switch")))), ("摘要行", Spot(Centre(Rect("Summary")))),
        ("行缝", Spot(new Point(Centre(rows[0]).X, rows[^1].Bottom + 4))),
    };

    int Int(object holder, string name) => (int)holder.GetType().GetProperty(name)!.GetValue(holder)!;
    bool Bool(object holder, string name) => (bool)holder.GetType().GetProperty(name)!.GetValue(holder)!;

    // 摆位: 默认贴宠物右边, 右边放不下翻左边, 两头都挤就夹回工作区
    var work = new Rectangle(0, 0, 1920, 1040);
    var size = panel.Size;
    Rectangle Side(Rectangle pet) => (Rectangle)side.Invoke(null, new object[] { pet, size, work, 8 })!;
    var mid = Side(new Rectangle(900, 300, 320, 420));
    var rightEdge = Side(new Rectangle(1700, 100, 320, 420));
    var bottom = Side(new Rectangle(600, 900, 320, 420));

    // 喂给 SideBounds 的到底是哪一块矩形。宠物窗口整扇铺满屏幕, 拿窗口矩形去摆位的话
    // 左右两头都放不下, 小窗会被夹到屏幕左上角 —— 桌面表现就是「右键没反应」
    var petRect = art.GetMethod("PetScreenRect", BindingFlags.Public | BindingFlags.Static)!;
    Rectangle Screen(Point at, Size win, RectangleF box)
        => (Rectangle)petRect.Invoke(null, new object[] { at, win, box })!;
    var winSize = new Size(2560, 1599);
    var sprite = Screen(new Point(0, 0), winSize, new RectangleF(2197, 1086, 294, 391));
    var spriteMoved = Screen(new Point(120, 60), winSize, new RectangleF(500, 300, 280, 390));
    var noBox = Screen(new Point(0, 0), winSize, new RectangleF(0, 0, 0, 0));
    var wide = new Rectangle(0, 0, 2560, 1504);
    Rectangle SideWide(Rectangle pet) => (Rectangle)side.Invoke(null, new object[] { pet, size, wide, 8 })!;
    var besideSprite = SideWide(sprite);
    var fromWholeWindow = SideWide(new Rectangle(0, 0, winSize.Width, winSize.Height));

    var matchCases = new (int[] Live, int Want)[]
    {
        (new[] { 25, 5, 15, 4 }, 0), (new[] { 45, 10, 20, 3 }, 1),
        (new[] { 50, 10, 25, 3 }, 2), (new[] { 30, 5, 15, 4 }, -1),
    };
    var matchMethod = form.GetMethod("MatchIndex", flags)!;
    var matched = matchCases.Select(c => (int)matchMethod.Invoke(null,
        new object[] { c.Live[0], c.Live[1], c.Live[2], c.Live[3] })! == c.Want).ToArray();
    var labelMethod = form.GetMethod("PrimaryLabel", flags)!;
    string Label(bool running, bool paused) => (string)labelMethod.Invoke(null, new object[] { running, paused })!;

    // 写盘那一步: 先把每一段都灌成非默认值, 再走小窗那条路改一档, 然后逐键比回去
    var cfgType = asm.GetType("DeskSpine.Config")!;
    var cfg = Activator.CreateInstance(cfgType)!;
    object Section(string name) => cfgType.GetProperty(name)!.GetValue(cfg)!;
    var basic = Section("BasicConfig");
    var spine = Section("SpineConfig");
    var system = Section("SystemConfig");
    var pomodoro = Section("PomodoroConfig");
    // 逐键灌值/比回去: 大多数键是属性, HourlyChime 这种老键是公有字段, 两种都得认
    object Peek(object holder, string name) => holder.GetType().GetProperty(name) is { } p
        ? p.GetValue(holder)! : holder.GetType().GetField(name)!.GetValue(holder)!;
    void Poke(object holder, string name, object value)
    {
        if (holder.GetType().GetProperty(name) is { } prop) prop.SetValue(holder, value);
        else holder.GetType().GetField(name)!.SetValue(holder, value);
    }
    object Bump(object holder, string name)
    {
        object next = Peek(holder, name) switch
        {
            int i => i + 7, uint u => u + 7u, bool b => !b, _ => "Z:\\哨兵.skel"
        };
        Poke(holder, name, next);
        return next;
    }
    var keep = new (object Holder, string Name, object Want)[]
    {
        (basic, "PositionX", Bump(basic, "PositionX")), (basic, "PositionY", Bump(basic, "PositionY")),
        (basic, "SizeX", Bump(basic, "SizeX")), (basic, "SizeY", Bump(basic, "SizeY")),
        (basic, "WallpaperMode", Bump(basic, "WallpaperMode")),
        (basic, "MouseClickThrough", Bump(basic, "MouseClickThrough")),
        (spine, "ActiveSlot", Bump(spine, "ActiveSlot")), (spine, "SkelPath0", Bump(spine, "SkelPath0")),
        (system, "BalloonIconPath", Bump(system, "BalloonIconPath")), (system, "HourlyChime", Bump(system, "HourlyChime")),
        (pomodoro, "BlockSleepWhileWorking", Bump(pomodoro, "BlockSleepWhileWorking")),
        // 同一段里那两个不属于预设的键最容易被顺手 new 掉: 上次「整段替换吃掉默认值」就栽在这儿
        (pomodoro, "BalloonIconPath", Bump(pomodoro, "BalloonIconPath")),
    };
    // 逐键比回去要排在 Write 之后, 先比就等于拿改动前的值自己和自己比
    var after = form.GetMethod("Write", flags)!.Invoke(null, new object[] { cfg, 1, false })!;
    string Drift() => string.Join(",", keep.Where(k => !Equals(Peek(k.Holder, k.Name), k.Want)).Select(k => k.Name));
    var p1 = presets.GetValue(1)!;
    var sameCfg = ReferenceEquals(after, cfg) && ReferenceEquals(Section("PomodoroConfig"), pomodoro);
    var renamed = new (string Preset, string Config)[]
    {
        ("Work", "WorkMinutes"), ("Break", "BreakMinutes"),
        ("LongBreak", "LongBreakMinutes"), ("Cycles", "CyclesPerLongBreak"),
    };
    var tookPreset = renamed.All(r => Int(pomodoro, r.Config) == Int(p1, r.Preset));

    return Criteria("预设小窗(版面/打靶/摆位/写盘不吃掉别的段)", new (string, bool, string, string)[]
    {
        ($"面板宽照素材原宽 {size.Width}, 高比那张 {232} 的板子行得出来, 三档行数对得上",
            panel.Width == 276 && rows.Length == presets.Length && panel.Height > 232,
            $"({panel.Width},{panel.Height}) 行数 {rows.Length}", "(276,>232) 行数 3"),
        ("×、主按钮、开关和每一行都在面板里", clickable.All(insidePanel),
            clickable.All(insidePanel) ? "都在" : $"出界 {clickable.Count(r => !insidePanel(r))} 块", "都在"),
        ("两块能点的地方不打架", clashes.Length == 0, $"{clashes.Length} 处重叠", "0 处"),
        ($"点每一行选中对应那一档(行宽 {string.Join("/", rows.Select(r => r.Width))})",
            rowHits.All(h => h), rowHits.All(h => h) ? "分得开" : "点错了", "对得上"),
        ($"×/主按钮/开关各点各的, 摘要行和行缝点空: {string.Join(" ", named.Select(n => n.At + "→" + n.Got.What))}",
            named[0].Got.What == "Close" && named[1].Got.What == "Start" && named[2].Got.What == "Switch"
                && named[3].Got.What == "None" && named[4].Got.What == "None",
            string.Join(",", named.Select(n => n.Got.What)), "Close,Start,Switch,None,None"),
        ("小窗摆在宠物右边", mid == new Rectangle(1228, 300, size.Width, size.Height),
            $"({mid.X},{mid.Y})", "(1228,300)"),
        ("宠物贴右边缘时翻到左边且还在工作区里",
            rightEdge.Right <= work.Right && rightEdge.X + size.Width + 8 <= 1700,
            $"({rightEdge.X},{rightEdge.Y})", "宠物左边"),
        ("宠物贴下边缘时夹进工作区, 不跑到屏外",
            bottom.Y + size.Height <= work.Bottom && bottom.Bottom >= work.Top, $"({bottom.X},{bottom.Y})", "顶不越界"),
        ($"摆位喂的是骨骼那一块, 窗口挪了它跟着挪: 空包围盒退成头顶那一个点",
            sprite == new Rectangle(2197, 1086, 294, 391) && spriteMoved == new Rectangle(620, 360, 280, 390)
                && noBox == new Rectangle(1280, 0, 0, 0),
            $"{sprite} / {spriteMoved} / {noBox}", "(2197,1086,294,391) / (620,360,280,390) / (1280,0,0,0)"),
        ($"那块放不下右边就翻左边; 拿整扇窗口矩形去摆会被夹到左上角(那条 bug 的形状)",
            besideSprite == new Rectangle(1913, 1086, size.Width, size.Height)
                && fromWholeWindow.X == 0 && fromWholeWindow.Y == 0,
            $"骨骼 {besideSprite} / 整窗 {fromWholeWindow}", "(1913,1086) / (0,0)"),
        ($"现在这几分钟对上第几档(对不上给 -1): {string.Join("/", matchCases.Select((c, i) => matched[i] ? "√" : "✗"))}",
            matched.All(m => m), "", ""),
        ("按钮那句跟着阶段走", Label(false, false) == "开始专注" && Label(true, false) == "先停一下" && Label(true, true) == "继续",
            $"{Label(false, false)}/{Label(true, false)}/{Label(true, true)}", "开始专注/先停一下/继续"),
        ("走小窗改一档: 返回的就是传进去那一份(不是 new 的)", sameCfg, sameCfg ? "同一份" : "换了对象", "同一份"),
        ($"走小窗改一档: 别的段一个键都没被顶掉", Drift().Length == 0,
            Drift().Length == 0 ? "没丢" : $"丢了 {Drift()}", "没丢"),
        ("走小窗改一档: 四档分钟数真的换成了那一档", tookPreset,
            $"{Int(pomodoro, "WorkMinutes")}/{Int(pomodoro, "BreakMinutes")}/{Int(pomodoro, "LongBreakMinutes")}/{Int(pomodoro, "CyclesPerLongBreak")}",
            $"{Int(p1, "Work")}/{Int(p1, "Break")}/{Int(p1, "LongBreak")}/{Int(p1, "Cycles")}"),
        ("走小窗点的那一下只换分钟数, 气泡开关听用户点的那个", !Bool(pomodoro, "BalloonOnPhaseChange"),
            Bool(pomodoro, "BalloonOnPhaseChange") ? "还是开着" : "关了", "跟着点走"),
    });
}

/// <summary>
/// 字和装饰件这两样长在画上, 前面那些纯函数一条都碰不到。这一条搬的是「量得出」的那半:
/// 每一句话在它那个盒子里放不放得下、小字有没有真的又粗又高、右下角那几枚叶子有没有压到点得着的地方。
/// 字形覆盖不在这里验 —— GDI+ 认得出家族名却没有字形时会悄悄借别人的笔(上一轮「素晴字体」那一格就是这么蒙过去的),
/// 借来的笔照样量得下尺寸, 所以那一半只能对着字体文件自己的 cmap 逐个字看: python ../bwp-assets/out/font_cover.py --check
/// </summary>
static bool TypeAndDeco(Assembly asm)
{
    var formType = asm.GetType("DeskSpine.FocusPresetForm")!;
    var spotsType = asm.GetType("DeskSpine.FocusPresetForm+Spots")!;
    var shared = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    var member = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    var art = asm.GetType("DeskSpine.FocusArt")!;
    var presets = (Array)formType.GetField("Presets", shared)!.GetValue(null)!;
    var dir = Path.Combine(Path.GetDirectoryName(asm.Location)!, @"res\image\focus_ui");
    int Const(string name) => (int)formType.GetField(name, shared)!.GetValue(null)!;
    int Pub(string name) => (int)art.GetField(name, BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;
    object Val(object holder, string name) => holder.GetType().GetProperty(name)!.GetValue(holder)!;

    // 面板宽就是那张纸的原宽: 产品里 Arrange 喂的是 assets.Panel.Width
    var paperFile = Path.Combine(dir, "bg_tips_3.png");
    if (!File.Exists(paperFile))
    {
        Console.WriteLine($"  版面字与装饰件: 否  读不到 {paperFile}（先跑 python ../bwp-assets/install_focus_ui.py）");
        return false;
    }
    int width;
    using (var probe = new Bitmap(new MemoryStream(File.ReadAllBytes(paperFile)))) width = probe.Width;
    var spots = formType.GetMethod("Arrange", shared)!.Invoke(null, new object[] { presets, width })!;
    Rectangle Rect(string name) => (Rectangle)spotsType.GetProperty(name)!.GetValue(spots)!;
    Rectangle[] RowRects(string name) => (Rectangle[])spotsType.GetProperty(name)!.GetValue(spots)!;
    var panel = Rect("Panel");
    var plates = RowRects("Plates");

    // 三支笔是实例字段, 只能在 UI 线程上把窗口搭起来再摸出来(不 Show)。
    // 但窗口一 Dispose 就把这三张笔和两个排版格式一起 Dispose 掉了(FocusPresetForm.Dispose 里明写的),
    // 所以量完之前不能关 —— 早先在这儿踩过一次「Parameter is not valid」
    Font title = null, body = null, small = null;
    StringFormat left = null, centre = null;
    System.Windows.Forms.Form window = null;
    var sta = new Thread(() =>
    {
        window = (System.Windows.Forms.Form)Activator.CreateInstance(formType)!;
        var type = window.GetType();
        title = (Font)type.GetField("titleFont", member)!.GetValue(window);
        body = (Font)type.GetField("bodyFont", member)!.GetValue(window);
        small = (Font)type.GetField("smallFont", member)!.GetValue(window);
        left = (StringFormat)type.GetField("leftText", member)!.GetValue(window);
        centre = (StringFormat)type.GetField("centreText", member)!.GetValue(window);
    });
    sta.SetApartmentState(ApartmentState.STA);
    sta.Start();
    sta.Join();
    if (title is null || body is null || small is null)
    {
        Console.WriteLine("  版面字与装饰件: 否  三支笔没摸出来(小窗构造没跑起来)");
        window?.Dispose();
        return false;
    }

    using var canvas = new Bitmap(width, panel.Height, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
    using var g = Graphics.FromImage(canvas);
    g.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAlias;
    var need = new List<(string What, bool Ok, string Got, string Want)>();
    // 盒子内边距是画上去时那个 Rectangle, 所以量出来的自然宽度要能塞进去
    void Fits(string what, string text, Font font, StringFormat fmt, Rectangle box)
    {
        var size = g.MeasureString(text, font, PointF.Empty, fmt);
        need.Add(($"「{text}」放进 {what}({box.Width}x{box.Height})",
            size.Width <= box.Width + 0.5 && size.Height <= box.Height + 0.5,
            $"{size.Width:F0}x{size.Height:F0}", "宽和高都不超过盒子"));
    }

    var labelMethod = formType.GetMethod("PrimaryLabel", shared)!;
    string Label(bool running, bool paused) => (string)labelMethod.Invoke(null, new object[] { running, paused })!;
    int Int(object holder, string name) => (int)Val(holder, name);
    Func<object, string> summaryOf = p => $"短休 {Int(p, "Break")} · 长假 {Int(p, "LongBreak")} · 连做 {Int(p, "Cycles")} 段";
    var worstSummary = presets.Cast<object>().Select(summaryOf)
        .Concat(new[] { "现在这几分钟没对上任何一档" })
        .OrderByDescending(t => g.MeasureString(t, small, PointF.Empty, centre).Width).First();

    Fits("标题", "番茄钟", title, left, Rect("Title"));
    Fits("摘要", worstSummary, small, centre, Rect("Summary"));
    foreach (var caption in new[] { Label(false, false), Label(true, false), Label(true, true) })
        Fits("主按钮", caption, body, centre, Rect("Start"));
    Fits("气泡开关那行", "换阶段弹气泡", body, left,
        new Rectangle(Rect("Switch").X + Const("RadioBox") + Const("Gap"), Rect("Switch").Y,
                      Rect("Switch").Width - Const("RadioBox") - Const("Gap"), Rect("Switch").Height));
    // 数字素材没装机时那一格退回文字, 那句也得躺在深色小板里
    var widest = presets.Cast<object>().Select(p => $"{Int(p, "Work")} 分").
        OrderByDescending(t => g.MeasureString(t, body, PointF.Empty, centre).Width).First();
    Fits("数字板(退文字那一版)", widest, body, centre, plates[0]);

    // 「分」那一小截: 数字条占掉多少, 剩下的宽度要还装得下一个 17 号粗体「分」
    var digits = new Dictionary<char, Bitmap>();
    foreach (var ch in "0123456789:")
    {
        var f = Path.Combine(dir, "digits", ch == ':' ? "colon.png" : $"{ch}.png");
        if (File.Exists(f)) digits[ch] = new Bitmap(new MemoryStream(File.ReadAllBytes(f)));
    }
    var stripMethod = art.GetMethod("DigitStrip", BindingFlags.Public | BindingFlags.Static);
    if (stripMethod is not null && digits.Count == 11)
    {
        var gapPx = Pub("DigitGap");
        var stripH = (int)art.GetField("DigitHeight", BindingFlags.Public | BindingFlags.Static)!.GetValue(null)!;
        for (int i = 0; i < presets.Length; i++)
        {
            var plate = plates[i];
            // DigitStrip 后两个参数在产品里走默认值, 反射不认默认值, 照着原样补上
            var strip = (Bitmap)stripMethod.Invoke(null,
                new object[] { $"{Int(presets.GetValue(i), "Work")}", digits, stripH, gapPx });
            if (strip is null) continue;
            var left0 = plate.X + (plate.Height - strip.Height) / 2;
            Fits("「分」(数字条旁边那截)", "分", small, left,
                new Rectangle(left0 + strip.Width + gapPx, plate.Y,
                              plate.Right - left0 - strip.Width - gapPx, plate.Height));
            strip.Dispose();
        }
    }
    foreach (var tile in digits.Values) tile.Dispose();

    var titleFamily = (string)formType.GetField("TitleFamily", shared)!.GetValue(null);
    need.Add(("标题那支笔真是表里点的那一家(GDI+ 名字认不出会退成别家)",
        string.Equals(title.FontFamily.Name, titleFamily, StringComparison.OrdinalIgnoreCase),
        $"{title.FontFamily.Name} @ {title.Size:F0}px", titleFamily));
    // 小字那条是这一轮的用户要求: 要么加粗要么换字体, 目的是不费眼
    need.Add(("小字真的又粗又不比正文小", small.Bold && small.Size >= body.Size,
        $"{small.FontFamily.Name} {small.Size:F0}px {(small.Bold ? "粗" : "常规")}", "≥ 正文且加粗"));

    var decoTable = (Array)formType.GetField("DecoSpots", shared)!.GetValue(null)!;
    var clickable = RowRects("Rows").Concat(new[] { Rect("Switch"), Rect("Start"), Rect("Close"),
        Rect("Summary") }).Concat(plates).Concat(new[] { Rect("Title") }).ToArray();
    var paperMargin = Const("PaperMargin");
    var decoBoxes = new List<Rectangle>();
    var decoNotes = new List<string>();
    foreach (var entry in decoTable)
    {
        var type = entry.GetType();
        var file = (string)type.GetField("Item1")!.GetValue(entry)!;
        var gapPx = (int)type.GetField("Item2")!.GetValue(entry)!;
        var atY = (int)type.GetField("Item3")!.GetValue(entry)!;
        var path = Path.Combine(dir, file);
        // 装机没这张图, DrawDeco 会一声不响地一枚都不画 —— 界面上看就是「装饰件没了」
        if (!File.Exists(path))
        {
            decoNotes.Add($"✗{file} 没装机");
            continue;
        }
        using var tile = new Bitmap(new MemoryStream(File.ReadAllBytes(path)));
        var box = new Rectangle(panel.Right - gapPx - tile.Width, atY, tile.Width, tile.Height);
        decoBoxes.Add(box);
        decoNotes.Add($"{Path.GetFileNameWithoutExtension(file)}({box.X},{box.Y},{box.Width}x{box.Height})");
        need.Add(($"{Path.GetFileNameWithoutExtension(file)} 落在纸上不越边",
            box.X >= paperMargin && box.Right <= panel.Width - 4 && box.Bottom <= panel.Height - 4,
            $"x {box.X}~{box.Right} y {box.Y}~{box.Bottom}", $"x≥{paperMargin} 右边≤{panel.Width - 4} 底≤{panel.Height - 4}"));
        var onTop = clickable.Where(c => c.IntersectsWith(box)).ToArray();
        need.Add(($"{Path.GetFileNameWithoutExtension(file)} 不压文字和点得着的地方",
            onTop.Length == 0, onTop.Length == 0 ? "没压" : $"压到 {onTop.Length} 块", "0 块"));
    }
    need.Add(("每一枚装饰件装机都有这张图(没装机 DrawDeco 静悄悄跳过那一枚)",
        decoBoxes.Count == decoTable.Length, string.Join(" ", decoNotes), "全在"));
    need.Add(("装饰件表里有人(空表 = 右下角那一小景被删干净了)",
        decoTable.Length > 0, $"{decoTable.Length} 枚", "≥1 枚"));
    need.Add(("装饰件彼此不打架",
        decoBoxes.Where((a, i) => decoBoxes.Skip(i + 1).Any(b => a.IntersectsWith(b))).Count() == 0,
        $"{decoBoxes.Count} 枚", "互不重叠"));

    // 顶栏那两笔墨痕长在纸上(装机图 y=17~28), 前面所有算式都碰不到它: 标题盒算得再对,
    // 字真画下去压在那两笔墨上就是用户看到的「被装饰物挡住」。这一条按像素问, 不问算式。
    // 纸的顶栏那 33 行是九宫格原样贴上去的, 所以装机图的坐标就是面板坐标。
    using (var paper = new Bitmap(new MemoryStream(File.ReadAllBytes(paperFile))))
    {
        var inset = Pub("PanelInset");
        bool PaperInk(int x, int y)
        {
            if (x < paperMargin + 3 || x >= Math.Min(paper.Width, panel.Width) - 4 || y < 0 || y >= inset) return false;
            var c = paper.GetPixel(x, y);
            return c.A > 40 && (c.R + c.G + c.B) / 3.0 < 120;
        }
        var marks = new HashSet<long>();
        for (var y = 0; y < inset; y++)
            for (var x = 0; x < paper.Width; x++)
                if (PaperInk(x, y)) marks.Add(((long)y << 16) | (uint)x);
        var titleBox = Rect("Title");
        using var scratch = new Bitmap(titleBox.Width, titleBox.Height, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
        using (var tg = Graphics.FromImage(scratch))
        {
            tg.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAlias;
            tg.DrawString("番茄钟", title, Brushes.Black, new RectangleF(0, 0, titleBox.Width, titleBox.Height), left);
            var hit = 0;
            int top = int.MaxValue, bottom = int.MinValue, inked = 0;
            for (var dy = 0; dy < titleBox.Height; dy++)
                for (var dx = 0; dx < titleBox.Width; dx++)
                {
                    var c = scratch.GetPixel(dx, dy);
                    if (c.A <= 40) continue;
                    inked++;
                    top = Math.Min(top, dy); bottom = Math.Max(bottom, dy);
                    if (marks.Contains(((long)(titleBox.Y + dy) << 16) | (uint)(titleBox.X + dx))) hit++;
                }
            need.Add(("标题的墨不压顶栏那两笔墨痕(按像素对)",
                inked > 0 && hit == 0,
                inked == 0 ? "一个字都没画出来" : $"墨 y {titleBox.Y + top}~{titleBox.Y + bottom}, 压上 {hit} 格",
                "与顶栏装饰墨 0 格重合"));
        }

        // 摘要那行原来照 PaperMargin 起, 盒子中线 138 = 整幅宽的一半, 而选项组和主按钮都坐在纸面中线 148 上,
        // 看着就是这一行比别的东西偏左。这一条盯的是「同一把尺」, 不是「放得下」
        int RightLine(int y) => Enumerable.Range(paperMargin, paper.Width - paperMargin)
            .LastOrDefault(x => { var c = paper.GetPixel(x, y); return c.A > 40 && (c.R + c.G + c.B) / 3.0 < 120; });
        var rightLine = RightLine(paper.Height / 2);
        var paperCentre = (paperMargin + rightLine) / 2.0;
        var summary = Rect("Summary");
        var summaryCentre = summary.X + summary.Width / 2.0;
        var rowsCentre = RowRects("Rows")[0].X + RowRects("Rows")[0].Width / 2.0;
        need.Add(("摘要和选项组坐在同一条纸面中线上",
            Math.Abs(summaryCentre - paperCentre) <= 1.5 && Math.Abs(rowsCentre - paperCentre) <= 1.5,
            $"摘要中线 {summaryCentre:F0}, 选项组中线 {rowsCentre:F0}, 纸面中线 {paperCentre:F0}(右边线在第 {rightLine} 格)",
            $"两个都≈{paperCentre:F0}"));
    }

    // 关窗会把那三支笔和两个排版格式一起带走, 所以必须排在所有量完之后
    window.Dispose();
    return Criteria("版面里的字与右下角装饰件(每句放不放得下/小字够不够粗/叶子压没压到地方)", need.ToArray());
}

/// <summary>
/// 第十一层: 台词气泡。装机那两张件咬不咬得住画布、池子里每一条折不折得进气泡、
/// 那张一秒一格的表是不是「亮几十秒自己消失、空一段再来」、这一拍该露该收、摆在哪儿、
/// 挑词会不会连着两条撞同一个人设。全是纯函数 + 对着装好的 png 量, 不碰窗口
/// </summary>
static bool SpeechBubble(Assembly asm)
{
    var formType = asm.GetType("DeskSpine.DialogBubbleForm")!;
    var lineType = asm.GetType("DeskSpine.DialogLine")!;
    var dialogType = asm.GetType("DeskSpine.DialogConfig")!;
    var rootType = asm.GetType("DeskSpine.Config")!;
    var shared = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    var bin = Path.GetDirectoryName(asm.Location)!;
    var bubbleFile = Path.Combine(bin, @"res\image\dialog\bubble.png");
    var crestFile = Path.Combine(bin, @"res\image\dialog\crest.png");
    var poolFile = Path.Combine(bin, @"res\dialog\lines.tsv");

    int Const(string name) => (int)formType.GetField(name, shared)!.GetValue(null)!;
    Point At(string name) => (Point)formType.GetField(name, shared)!.GetValue(null)!;
    var textArea = (Rectangle)formType.GetField("TextArea", shared)!.GetValue(null)!;
    var maxLines = (int)formType.GetProperty("MaxLines", shared)!.GetValue(null)!;
    var wrapM = formType.GetMethod("WrapLines", shared)!;
    var stepM = formType.GetMethod("Step", shared)!;
    var visM = formType.GetMethod("NextVisible", shared)!;
    var boundsM = formType.GetMethod("BubbleBounds", shared)!;
    var pickM = formType.GetMethod("PickLine", shared)!;

    // 素材没装机时产品那边整条不弹(NextVisible 里 hasLines 那一路), 判据要指得出是谁的锅
    if (!File.Exists(bubbleFile) || !File.Exists(crestFile) || !File.Exists(poolFile))
    {
        Console.WriteLine("  台词气泡: 否  装机件不全 " +
            $"bubble={File.Exists(bubbleFile)} crest={File.Exists(crestFile)} lines.tsv={File.Exists(poolFile)}" +
            " —— 先跑 python ../bwp-assets/install_dialog_ui.py");
        return false;
    }

    using var body = new Font(SystemFonts.MessageBoxFont!.FontFamily, Const("BodyPx"),
                              FontStyle.Regular, GraphicsUnit.Pixel);
    int Lines(string text) => ((Array)wrapM.Invoke(null, new object[] { text, body, textArea.Width })!).Length;

    // 连通块按面积数出来。装机是 LANCZOS 放大过的, 边上会留一圈 1 像素毛点,
    // 数「连通块有几个」会把毛点算成碎屑, 所以两条一起看:
    //   有分量的块(≥最大那一块 15%) —— 抓「另一格整块印进来了」那种大块
    //   最大那一块占全图墨的比例 —— 15% 那条门槛放不住半截的邻格(当年那枚 12.4%), 比例才抓得住
    List<int> Blobs(Bitmap bmp)
    {
        var w = bmp.Width; var h = bmp.Height;
        var seen = new bool[w, h];
        var sizes = new List<int>();
        var queue = new Queue<Point>();
        for (var y0 = 0; y0 < h; y0++)
        for (var x0 = 0; x0 < w; x0++)
        {
            if (seen[x0, y0] || bmp.GetPixel(x0, y0).A <= 24) continue;
            seen[x0, y0] = true;
            queue.Enqueue(new Point(x0, y0));
            var size = 0;
            while (queue.Count > 0)
            {
                var p = queue.Dequeue();
                size++;
                foreach (var d in new[] { new Point(-1, 0), new Point(1, 0), new Point(0, -1), new Point(0, 1) })
                {
                    var nx = p.X + d.X; var ny = p.Y + d.Y;
                    if (nx < 0 || ny < 0 || nx >= w || ny >= h || seen[nx, ny] || bmp.GetPixel(nx, ny).A <= 24) continue;
                    seen[nx, ny] = true;
                    queue.Enqueue(new Point(nx, ny));
                }
            }
            sizes.Add(size);
        }
        return sizes;
    }

    int SolidBlobs(List<int> sizes) => sizes.Count == 0 ? 0 : sizes.Count(s => s >= 0.15 * sizes.Max());
    int OpaqueShare(List<int> sizes) => sizes.Sum() == 0 ? 0 : 100 * sizes.Max() / sizes.Sum();

    // 距边第 k 档的均色「偏暖」多少（R-B）。原图那条金线实测只有第 1 档（778 个像素），
    // 装机把 1~FRAME 档染金，所以「边框几 px」是量出来的：前三档 R-B 大、第四档回纸(≈4)
    int[] BandWarmth(Bitmap bmp, int depth)
    {
        var w = bmp.Width; var h = bmp.Height;
        var solid = new bool[w, h];
        var d = new int[w, h];
        var q = new Queue<Point>();
        for (var y = 0; y < h; y++)
            for (var x = 0; x < w; x++)
            {
                solid[x, y] = bmp.GetPixel(x, y).A >= 200;
                if (solid[x, y]) d[x, y] = 1 << 12;
                else q.Enqueue(new Point(x, y));
            }
        while (q.Count > 0)
        {
            var p = q.Dequeue();
            foreach (var nd in new[] { new Point(-1, 0), new Point(1, 0), new Point(0, -1), new Point(0, 1) })
            {
                var nx = p.X + nd.X; var ny = p.Y + nd.Y;
                if (nx < 0 || ny < 0 || nx >= w || ny >= h || !solid[nx, ny] || d[nx, ny] <= d[p.X, p.Y] + 1) continue;
                d[nx, ny] = d[p.X, p.Y] + 1;
                q.Enqueue(new Point(nx, ny));
            }
        }
        var sum = new long[depth]; var cnt = new long[depth];
        for (var y = 0; y < h; y++)
            for (var x = 0; x < w; x++)
            {
                if (!solid[x, y] || d[x, y] > depth) continue;
                var c = bmp.GetPixel(x, y);
                sum[d[x, y] - 1] += c.R - c.B; cnt[d[x, y] - 1]++;
            }
        return Enumerable.Range(0, depth).Select(k => cnt[k] == 0 ? 0 : (int)(sum[k] / cnt[k])).ToArray();
    }

    var need = new List<(string What, bool Ok, string Got, string Want)>();
    using var bubble = new Bitmap(new MemoryStream(File.ReadAllBytes(bubbleFile)));
    using var crest = new Bitmap(new MemoryStream(File.ReadAllBytes(crestFile)));
    var bubbleBlobs = Blobs(bubble);
    var crestBlobs = Blobs(crest);

    // 1) 图按原尺寸贴, 所以画布那几个常量和装机图必须互相算得出来。哪天重装机换了一档而画布没跟着改,
    //    就是字画出泡外或者泡被裁一角
    need.Add(("气泡图和画布互相咬得住(原尺寸贴、不拉伸)",
        At("BubbleAt").X + bubble.Width == Const("CanvasWidth") && At("BubbleAt").Y + bubble.Height == Const("CanvasHeight"),
        $"图 {bubble.Width}x{bubble.Height} 贴 ({At("BubbleAt").X},{At("BubbleAt").Y}), 画布 {Const("CanvasWidth")}x{Const("CanvasHeight")}",
        "图 + 起点 = 画布"));
    need.Add(("气泡图上没有邻格碎屑(有分量的连通块只有一个)",
        SolidBlobs(bubbleBlobs) == 1, $"{SolidBlobs(bubbleBlobs)} 坨", "1 坨"));
    need.Add(("气泡整张就是本体(最大那一块占到全图墨的 99% 以上)",
        OpaqueShare(bubbleBlobs) >= 99, $"{OpaqueShare(bubbleBlobs)}%", "≥99%"));
    need.Add(("家纹印是 48 见方那一枚", crest.Width == 48 && crest.Height == 48,
        $"{crest.Width}x{crest.Height}", "48x48"));
    need.Add(("家纹印上没有邻格碎屑", SolidBlobs(crestBlobs) == 1, $"{SolidBlobs(crestBlobs)} 坨", "1 坨"));
    need.Add(("家纹整张就是本体(最大那一块占到全图墨的 99% 以上)",
        OpaqueShare(crestBlobs) >= 99, $"{OpaqueShare(crestBlobs)}%", "≥99%"));

    // 用户 2026-11-02 要「边框线条更粗一些」, 对着预览图拍的是 3px。装机把距边 1~3 档染金,
    // 所以「粗了几 px」不是嘴上说的: 量装机图每一档的偏暖程度, 第 4 档必须回纸(否则就是染过了)
    var band = BandWarmth(bubble, 4);
    need.Add(("金线实测 3 档粗、第 4 档已经回纸",
        band.Take(3).All(v => v >= 40) && band[3] < 20,
        $"第 1~4 档 R-B = {string.Join("/", band)}", "前三档 ≥40、第四档 <20"));

    // 2) 池子: 装机脚本写出来的四列, 产品只认「说话人/分组/字数/台词」。逐条拿产品自己那支笔折,
    //    超过 MaxLines 的那条会把气泡的字画到泡外 —— 这条红了就是「池子里塞了句太长的」
    var pool = File.ReadAllLines(poolFile, System.Text.Encoding.UTF8)
        .Select(l => l.Split('\t'))
        .Where(c => c.Length >= 4 && c[0] != "说话人" && c[3].Trim().Length > 0)
        .Select(c => (Group: c[1].Trim(), Text: c[3].Trim()))
        .ToArray();
    var overflow = pool.Select((p, i) => (i, n: Lines(p.Text))).Where(t => t.n > maxLines).ToArray();
    var longest = pool.Length == 0 ? 0 : pool.Max(p => Lines(p.Text));
    need.Add(("池子非空(空池 = 装机脚本没跑或台词列没对上)", pool.Length > 0, $"{pool.Length} 条", "≥1 条"));
    need.Add(("每一条都折得进气泡正文区", overflow.Length == 0,
        $"{pool.Length} 条里最长的占 {longest} 行, 上限 {maxLines} 行", $"全部 ≤{maxLines} 行"
        + (overflow.Length == 0 ? "" : $"  装不下的行号: {string.Join(",", overflow.Select(t => t.i))}")));
    need.Add(("开机头一条有「开场」那一组可挑", pool.Count(p => p.Group == "开场") > 0,
        $"开场 {pool.Count(p => p.Group == "开场")} 条", "≥1 条"));

    // 3) 那张一秒一格的表。用户 2026-11-02 改口「15 秒够读完，空档跟着缩到 60」，两件事都要数得出来:
    //    亮着的连续段正好是 ShowSeconds(不是常驻)，收起的连续段正好是 GapSeconds(不是再也出不来)
    (bool on, int left, bool opened) Step(bool on, int left, int show, int gap)
    {
        var t = ((ValueTuple<bool, int, bool>)stepM.Invoke(null, new object[] { on, left, show, gap })!);
        return (t.Item1, t.Item2, t.Item3);
    }
    var runs = new List<(bool On, int Len)>();
    var st = (On: false, Left: Const("BootDelay"));
    var openedAtBoot = 0;
    for (int i = 0; i < 1000; i++)
    {
        var n = Step(st.On, st.Left, 15, 60);
        if (n.opened && openedAtBoot == 0) openedAtBoot = i + 1;
        st = (n.on, n.left);
        if (runs.Count > 0 && runs[^1].On == st.On) runs[^1] = (st.On, runs[^1].Len + 1);
        else runs.Add((st.On, 1));
    }
    // 头一段是 BootDelay 那一截不足 135 的空闲, 尾一段被循环的整数拍截断 —— 都只数走满的段
    var full = runs.Skip(1).Take(runs.Count - 2).ToArray();
    var onRuns = full.Where(r => r.On).Select(r => r.Len).ToArray();
    var offRuns = full.Where(r => !r.On).Select(r => r.Len).ToArray();
    need.Add(("亮够 ShowSeconds 就自己消失(不是常驻)",
        onRuns.Length > 1 && onRuns.All(n => n == 15), $"亮着的段 {string.Join(",", onRuns)}", "每段都是 15"));
    need.Add(("收起后空够 GapSeconds 再来下一条(不是再也不出来)",
        offRuns.Length > 1 && offRuns.All(n => n == 60), $"空着的段 {string.Join(",", offRuns)}", "每段都是 60"));
    need.Add(("开机先等 BootDelay 拍, 登场动画没跳完不顶一句话",
        openedAtBoot == Const("BootDelay"), $"第 {openedAtBoot} 拍冒第一条", $"{Const("BootDelay")} 拍"));
    // 手改 config.json 改得出 0 和负数, 那会儿表会卡在「每拍都翻档」—— 两头都夹到 1
    need.Add(("秒数被手改成 0 也翻不出每拍一跳",
        Step(true, 1, 0, 0).left == 1 && Step(false, 1, 0, 0).left == 1,
        $"收→{Step(true, 1, 0, 0).left} 拍, 亮→{Step(false, 1, 0, 0).left} 拍", "都 ≥1"));

    // 4) 该露该收: 五个布尔全枚举对着公式走一遍
    var truth = new List<string>();
    foreach (var e in new[] { true, false })
    foreach (var l in new[] { true, false })
    foreach (var s in new[] { true, false })
    foreach (var p in new[] { true, false })
    foreach (var t in new[] { true, false })
    {
        var got = (bool)visM.Invoke(null, new object[] { e, l, s, p, t })!;
        if (got != (e && l && !s && !p && t)) truth.Add($"({e},{l},{s},{p},{t})→{got}");
    }
    need.Add(("开关、池子、宠物藏没藏、板子开没开(菜单/预设/天气三张都算)、是不是这只角色 —— 32 组全枚举",
        truth.Count == 0, truth.Count == 0 ? "32 组都对" : string.Join(" ", truth),
        "enabled && hasLines && !stowed && !panelOpen && thisPet"));

    // 4.5) 台词是谁的就只在谁出场时弹。池子那 22 条全是不知火的独白、名牌也写着「不知火」,
    //      切到千姬还接着念就是拿不知火的家纹念不知火的词(2026-11-03 用户抓的)。
    //      「屏幕上是哪只」读的是引擎的 ActiveSlot(-1 = 图层模式, 几格叠着画), 名字走托盘那同一张表 PetNames
    var ownM = formType.GetMethod("PoolIsThisPet", shared)!;
    bool Own(string speaker, string pet) => (bool)ownM.Invoke(null, new object[] { speaker, pet })!;
    var owners = File.ReadAllLines(poolFile, System.Text.Encoding.UTF8)
        .Select(c => c.Split('\t'))
        .Where(c => c.Length >= 4 && c[0] != "说话人" && c[3].Trim().Length > 0)
        .Select(c => c[0].Trim()).Distinct().ToArray();
    var own = owners.Length == 1 ? owners[0] : "";
    var petNames = asm.GetType("DeskSpine.PetNames")!.GetMethod("Display")!;
    string Display(string stem) => (string)petNames.Invoke(null, new object[] { $@"C:\res\spine\{stem}\{stem}.skel" })!;
    var bad = new List<string>();
    foreach (var (sp, pe, want) in new[]
    {
        ("不知火", "不知火", true),            // 池子和屏幕上对得上
        ("不知火", "千姬", false),             // 切到别只 → 闭嘴
        ("不知火", "猫掌柜焕宴", false),        // 同上, 表里另外那只
        ("不知火", "", false),                // 图层模式(说不出哪一只) → 闭嘴
        ("", "不知火", false),                // 空池 / 装机没跑 → 闭嘴
        ("千姬", "千姬", true),                // 别把归属硬编成"只有不知火才行", 将来别人的池子接得上
    })
        if (Own(sp, pe) != want) bad.Add($"「{sp}」→屏幕「{pe}」={Own(sp, pe)} 应为 {want}");
    need.Add(("台词池说的是谁、屏幕上就得正是那只(切角色还念不知火的词就红在这)",
        bad.Count == 0 && own.Length > 0,
        bad.Count == 0 ? $"池子归属「{own}」, 六组对照都对" : string.Join(" ", bad),
        "同名才弹, 对不上/说不出都不弹"));
    need.Add(("池子里那个说话人和角色名表里的写法对得上(漂一个字气泡就静悄悄不弹)",
        own == Display("buzhihuo_1127"),
        $"池子写「{own}」 / 名表里 buzhihuo_1127 叫「{Display("buzhihuo_1127")}」", "两边一模一样"));

    // 5) 摆位: 按「看得见的墨」定位（画布左边那段透明边不该算进间距）; 默认在宠物右边、
    //    墨底沿压过头顶; 右边塞不下翻到左边并镜像美术件（整张翻会把汉字翻反）
    var panel = new Size(Const("CanvasWidth"), Const("CanvasHeight"));
    var artInk = (Rectangle)formType.GetMethod("InkOf", shared)!.Invoke(null, new object[] { bubble })!;
    var ink = new Rectangle(artInk.X + At("BubbleAt").X, artInk.Y + At("BubbleAt").Y, artInk.Width, artInk.Height);
    (Rectangle b, bool mir) Place(Rectangle p, Point h, Rectangle a)
    {
        var t = (ValueTuple<Rectangle, bool>)boundsM.Invoke(null,
            new object[] { p, h, panel, ink, a, Const("SideGap"), Const("HeadLift") })!;
        return (t.Item1, t.Item2);
    }
    var work = new Rectangle(0, 0, 1920, 1040);
    var petR = new Rectangle(400, 300, 500, 500);
    var headR = new Point(650, 360);
    var right = Place(petR, headR, work);
    need.Add(("默认摆宠物右侧：墨左沿离宠物 SideGap、墨底沿压过头顶",
        !right.mir && right.b.X + ink.X == petR.Right + Const("SideGap")
                  && right.b.Y + ink.Bottom == headR.Y - Const("HeadLift"),
        $"({right.b.X},{right.b.Y}) 墨左 {right.b.X + ink.X} 墨底 {right.b.Y + ink.Bottom} 镜像={right.mir}",
        $"墨左={petR.Right + Const("SideGap")} 墨底={headR.Y - Const("HeadLift")} 镜像=False"));
    need.Add(("间距量在墨上、不量在画布上（画布那段透明边白给，不该算近）",
        ink.X > Const("SideGap") && right.b.X < petR.Right
                  && right.b.X + ink.X - petR.Right == Const("SideGap"),
        $"透明边 {ink.X} px, 画布左边 {right.b.X} 已压进宠物右边 {petR.Right} 之内 {petR.Right - right.b.X} px",
        "墨左沿 - 宠物右边 = SideGap, 且画布左边比宠物右边更靠左"));
    var tight = new Rectangle(0, 0, 1200, 1040);
    var petL = new Rectangle(700, 300, 480, 500);
    var flip = Place(petL, new Point(900, 360), tight);
    need.Add(("右边塞不下就翻到左边，那一侧按墨右沿贴、并置镜像位（越过宠物左边的只有透明边）",
        flip.mir && flip.b.X + panel.Width - ink.X == petL.Left - Const("SideGap")
                  && flip.b.Right - petL.Left < ink.X,
        $"({flip.b.X},{flip.b.Y}) 墨右 {flip.b.X + panel.Width - ink.X}, 宠物左边 {petL.Left}, 镜像={flip.mir}, 画布压过去 {flip.b.Right - petL.Left} px(透明边 {ink.X})",
        $"墨右={petL.Left - Const("SideGap")} 镜像=True 压过去的像素 <{ink.X}"));
    var mxM = formType.GetMethod("Mx", shared)!;
    int Mx(int x, int w, bool m) => (int)mxM.Invoke(null, new object[] { x, w, m })!;
    var textMirror = new Rectangle(Mx(textArea.X, textArea.Width, true), textArea.Y, textArea.Width, textArea.Height);
    need.Add(("镜像只挪件、不翻字：正文区翻过去但宽不变、翻两次回原位",
        Mx(Mx(textArea.X, textArea.Width, true), textArea.Width, true) == textArea.X
          && textMirror.X == Const("CanvasWidth") - textArea.X - textArea.Width
          && textMirror.Width == textArea.Width && textMirror.Height == textArea.Height,
        $"镜像正文区 ({textMirror.X},{textMirror.Y}) {textMirror.Width}x{textMirror.Height}",
        $"({Const("CanvasWidth") - textArea.X - textArea.Width},{textArea.Y}) {textArea.Width}x{textArea.Height}"));
    var squeeze = Place(new Rectangle(300, 300, 380, 400), new Point(450, 360), new Rectangle(0, 0, 700, 1040));
    need.Add(("翻到左边还塞不下就夹在工作区里, 不飘出屏幕",
        squeeze.b.X >= 0 && squeeze.b.Right <= 700, $"x={squeeze.b.X}~{squeeze.b.Right}", "0~700"));
    var high = Place(petR, new Point(650, 60), work);
    need.Add(("头顶快贴屏幕顶时整张往下夹", high.b.Y >= work.Top && high.b.Bottom <= work.Bottom,
        $"y={high.b.Y}~{high.b.Bottom}", $"顶 ≥0 底 ≤{work.Bottom}"));

    // 5.5) 名牌：大红底 + 烫金字。拿产品自己那支笔画到一张空图上按像素量，镜像那侧的尖要朝左
    var plateM = formType.GetMethod("DrawSpeakerPlate", shared)!;
    (int wide, int red, int gold, int lH, int rH) Plate(bool mirror)
    {
        using var bmp = new Bitmap(260, 70, System.Drawing.Imaging.PixelFormat.Format32bppPArgb);
        using var gg = Graphics.FromImage(bmp);
        gg.Clear(Color.Transparent);
        gg.TextRenderingHint = System.Drawing.Text.TextRenderingHint.AntiAlias;
        var tbox = (Rectangle)plateM.Invoke(null, new object[] { gg, "不知火", body, new Point(12, 18), mirror })!;
        var red = 0; var gold = 0;
        var cols = new int[bmp.Width];
        for (var y = 0; y < bmp.Height; y++)
            for (var x = 0; x < bmp.Width; x++)
            {
                var c = bmp.GetPixel(x, y);
                if (c.A < 200) continue;
                cols[x]++;
                // 金字只数名牌那一格字: 名牌整圈描边本来就是烫金的, 算进来「字退回墨色」那种 bug 从它眼底过
                var inName = x >= tbox.X && x < tbox.X + tbox.Width && y >= tbox.Y && y < tbox.Y + tbox.Height;
                if (c.R - c.B >= 120 && c.G < 110) red++;
                else if (inName && c.R - c.B >= 40 && c.G >= 140) gold++;
            }
        var first = Array.FindIndex(cols, n => n > 0);
        var last = Array.FindLastIndex(cols, n => n > 0);
        if (first < 0 || last - first < 6) return (0, red, gold, 0, 0);
        return (last - first + 1, red, gold, cols[first + 3], cols[last - 3]);
    }
    var pr = Plate(false);
    var pm = Plate(true);
    need.Add(("名牌是大红底 + 烫金字（红底数得出、那一格字也数得出）",
        pr.red > 400 && pr.gold > 100, $"红底 {pr.red} 格, 金字 {pr.gold} 格", "红底 >400 且金字 >100"));
    need.Add(("名牌的尖在朝外那一端：右摆尖在右、左摆尖在左（两侧镜像对称）",
        pr.lH >= 20 && pr.rH <= 14 && pm.rH >= 20 && pm.lH <= 14,
        $"右摆 左列 {pr.lH} 高 / 右列 {pr.rH} 高；左摆 左列 {pm.lH} 高 / 右列 {pm.rH} 高",
        "平头那一列 ≥20、尖头那一列 ≤14，两边反过来"));

    // 6) 挑词: 开机头一条从「开场」那组, 之后整池随机但不连着撞同一个人设
    var listOf = typeof(List<>).MakeGenericType(lineType);
    object MakePool((string Group, string Text)[] items)
    {
        var l = (System.Collections.IList)Activator.CreateInstance(listOf)!;
        foreach (var (g, t) in items) l.Add(Activator.CreateInstance(lineType, g, t)!);
        return l;
    }
    int Pick(object lines, int last, bool first, Random rng)
        => (int)pickM.Invoke(null, new object[] { lines, last, first, rng })!;
    var three = MakePool(new[] { ("舞台", "A"), ("开场", "B"), ("夜之乐屋", "C") });
    var rng1 = new Random(20261102);
    var firstPicks = Enumerable.Range(0, 60).Select(_ => Pick(three, -1, true, rng1)).ToArray();
    need.Add(("开机头一条落在「开场」那一组", firstPicks.All(i => i == 1),
        $"60 次抽到 {string.Join(",", firstPicks.Distinct())}", "全部是那一组下标 1"));
    var rng2 = new Random(20261102);
    var walk = new List<int>();
    for (int i = 0, last = -1; i < 80; i++) { last = Pick(three, last, false, rng2); walk.Add(last); }
    var repeats = walk.Zip(walk.Skip(1)).Count(p => p.First == p.Second);
    need.Add(("连着两条不重复同一条(随机但避开上一条)", repeats == 0,
        $"{walk.Count} 次里 {walk.Distinct().Count()} 种, 连重 {repeats} 次", "0 次连重"));
    var single = MakePool(new[] { ("舞台", "A") });
    need.Add(("池子只有一条时也发得出去(不是返回 -1 让气泡空转)",
        Pick(single, 0, false, rng2) == 0 && Pick(single, -1, true, rng2) == 0,
        $"{Pick(single, 0, false, rng2)}", "0"));
    need.Add(("空池返回 -1(装机脚本没跑时不硬画半张)",
        Pick(MakePool(Array.Empty<(string, string)>()), -1, true, rng2) == -1,
        $"{Pick(MakePool(Array.Empty<(string, string)>()), -1, true, rng2)}", "-1"));

    // 6.5) 换台词要真重画。ArtFor 的作废键只能是「这两张缓存画的是哪条」, 不能是「现在该显示哪条」——
    //      后者被 BeginLine 提前拨新, Render 传进去那句和它一比恒等, 同一侧就永远拿回旧位图
    //      (2026-11-02 用户点托盘「换一条」看到字不动, 就是这一条)。
    //      不走 BeginLine 是因为它随机挑、判据要能固定喂某一句: 把 shownText 拨成池子里的那句,
    //      再按 Render 那一行的走法 ArtFor(shownText, 哪一侧) 取图
    var instFlags = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    // 产品的装载器按 Application.ExecutablePath 找 res（= 测试 exe 自己那格），所以把传进来的那份
    // 产物里的三件复制过来 —— 不然 Compose 只画得出字，「正文离框多远」这类判据没法连框一起量
    foreach (var rel in new[] { @"image\dialog\bubble.png", @"image\dialog\crest.png", @"dialog\lines.tsv" })
    {
        var dst = Path.Combine(AppContext.BaseDirectory, "res", rel);
        Directory.CreateDirectory(Path.GetDirectoryName(dst)!);
        File.Copy(Path.Combine(bin, "res", rel), dst, true);
    }
    var bubbleForm = Activator.CreateInstance(formType)!;
    var artM = formType.GetMethod("ArtFor", instFlags)!;
    var shownF = formType.GetField("shownText", instFlags)!;
    Bitmap Art(string text, bool mirror)
    {
        shownF.SetValue(bubbleForm, text);
        return (Bitmap)artM.Invoke(bubbleForm, new object[] { text, mirror })!;
    }
    string Fingerprint(Bitmap b)
    {
        long h = 1469598103934665603L;
        for (int y = 0; y < b.Height; y++)
            for (int x = 0; x < b.Width; x++)
            {
                var c = b.GetPixel(x, y);
                h = (h ^ c.A ^ (c.R << 8) ^ (c.G << 16) ^ (c.B << 24)) * 1099511628211L;
            }
        return h.ToString("x16");
    }
    var realTexts = pool.Select(p => p.Text).Distinct().ToArray();
    var texts = realTexts.Length >= 2 ? new[] { realTexts[0], realTexts[1] }
                                      : new[] { "哨兵台词甲", "哨兵台词乙" };
    need.Add(("池子里凑得出两句不同台词(重画那条才有得比)", realTexts.Length >= 2,
        $"{pool.Length} 条里 {realTexts.Length} 句不同", "≥2 句"));
    var artA = Art(texts[0], false);
    var sumA = Fingerprint(artA);
    var artB = Art(texts[1], false);
    var sumB = Fingerprint(artB);
    var artBAgain = Art(texts[1], false);
    var artBm = Art(texts[1], true);
    var sumBm = Fingerprint(artBm);
    need.Add(("换了台词同一侧重画出来的是新图(点「换一条」字要跟着换)",
        !ReferenceEquals(artA, artB) && sumA != sumB,
        $"指纹 {sumA[..8]} → {sumB[..8]}", "两句台词两张指纹"));
    need.Add(("同一条在同一侧不重画(复用那张, 别每拍重排一遍字)",
        ReferenceEquals(artB, artBAgain), artBAgain == artB ? "复用" : "重画了", "复用同一张"));
    need.Add(("同一条翻到另一侧另画一张镜像, 且不动正排那张(两侧真的对称)",
        !ReferenceEquals(artB, artBm) && sumBm != sumB && ReferenceEquals(artB, artBAgain),
        $"正排 {sumB[..8]} / 镜像 {sumBm[..8]}", "两张指纹不同"));

    // 6.6) 正文块、纸、两侧对称。上一版只数「折成几行」, 从没量过画出来的字落在泡的哪一块 ——
    //      2026-11-02 用户复验: 气泡翻到左边那侧「短句偏左、长句压到框上」, 右边那侧看不出来。
    //      量法: 同一侧画「有字」和「没字」两张 —— 差出来的那一块是正文, 「没字」那张自己的墨就是**画出来的纸**。
    //      纸必须量画出来的: 只按 BubbleAt+Mx 推, 镜像轴差 13 px 那一笔会跟着算术一起被推对, 反而把 bug 洗白。
    //      2026-11-02 用户拍板保留运行时拉伸(这台 200% 上整张纸被拉成两倍), 右、下两道金线跑到画布外、纸被裁在画布边上 ——
    //      「两侧那张纸互成镜像」在这一版量不出来(两侧都被裁成贴到画布右沿), 撤了; 原点挪没挪改由「正文和纸之间留得住富余」盯:
    //      纸往右多摆 13 px, 左边那侧的字就压到纸外 —— 两条判据: 正文压在画出来的纸上 / 两侧正文互成镜像
    var composeM = formType.GetMethod("Compose", instFlags)!;
    Bitmap Flat(string text, bool mirror) => (Bitmap)composeM.Invoke(bubbleForm, new object[] { text, mirror })!;
    Rectangle BoxOf(Func<int, int, bool> hit, int w, int h)
    {
        int x0 = int.MaxValue, y0 = int.MaxValue, x1 = -1, y1 = -1;
        for (int y = 0; y < h; y++)
            for (int x = 0; x < w; x++)
                if (hit(x, y)) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
        return x1 < 0 ? Rectangle.Empty : Rectangle.FromLTRB(x0, y0, x1 + 1, y1 + 1);
    }
    Rectangle TextBlock(string text, bool mirror)
    {
        using var withText = Flat(text, mirror);
        using var bare = Flat("", mirror);
        return BoxOf((x, y) => withText.GetPixel(x, y) != bare.GetPixel(x, y),
                     Const("CanvasWidth"), Const("CanvasHeight"));
    }
    int Mxv(int x, int w, bool mirror) => (int)mxM.Invoke(null, new object[] { x, w, mirror })!;
    // 「纸」量画出来的那一张, 不拿算术推: 轴差那一笔 bug 的形状正是「算术里纸翻过去了、画出来还在原位」,
    // 按 BubbleAt+Mx 推出来的 frame 会跟着一起错, 反而把 bug 洗白
    Rectangle DrawnFrame(bool mirror)
    {
        using var bare = Flat("", mirror);
        return BoxOf((x, y) => bare.GetPixel(x, y).A >= 200, Const("CanvasWidth"), Const("CanvasHeight"));
    }
    var (frameR, frameL) = (DrawnFrame(false), DrawnFrame(true));
    var probe = new[] { pool.OrderByDescending(p => p.Text.Length).First().Text,
                        pool.OrderBy(p => p.Text.Length).First().Text };
    var (tR0, tL0) = (TextBlock(probe[0], false), TextBlock(probe[0], true));
    var (tR1, tL1) = (TextBlock(probe[1], false), TextBlock(probe[1], true));
    string Pad(Rectangle t, Rectangle f) =>
        $"左{t.X - f.X} 右{f.Right - t.Right} 上{t.Y - f.Y} 下{f.Bottom - t.Bottom}";
    bool Fits(Rectangle t, Rectangle f, int margin) =>
        !t.IsEmpty && t.X - margin >= f.X && t.Right + margin <= f.Right
        && t.Y - margin >= f.Y && t.Bottom + margin <= f.Bottom;
    need.Add(("最长和最短那句的正文都压在画出来的纸上、四边各留 2 px 富余（左右两侧都算；纸往右多摆 13 px 这边就压到纸外）",
        Fits(tR0, frameR, 2) && Fits(tR1, frameR, 2) && Fits(tL0, frameL, 2) && Fits(tL1, frameL, 2),
        $"右摆长句 {Pad(tR0, frameR)} / 左摆长句 {Pad(tL0, frameL)}；右摆短句 {Pad(tR1, frameR)} / 左摆短句 {Pad(tL1, frameL)}" +
        $"（纸: 右 {frameR.X}~{frameR.Right} 左 {frameL.X}~{frameL.Right}, 画布 {Const("CanvasWidth")}x{Const("CanvasHeight")}）",
        "四边富余都 ≥ 2"));
    need.Add(("两侧互成镜像：把左摆正文按画布翻回右边要和右摆对上（±2 px，左侧右对齐没生效就差一整行宽）",
        Math.Abs(Mxv(tL0.X, tL0.Width, true) - tR0.X) <= 2 && Math.Abs(tL0.Y - tR0.Y) <= 2
        && Math.Abs(Mxv(tL1.X, tL1.Width, true) - tR1.X) <= 2 && Math.Abs(tL1.Y - tR1.Y) <= 2,
        $"长句 右摆 x {tR0.X}~{tR0.Right} / 左摆翻回 {Mxv(tL0.X, tL0.Width, true)}~" +
        $"{Mxv(tL0.X, tL0.Width, true) + tL0.Width}，短句 {tR1.X} / {Mxv(tL1.X, tL1.Width, true)}" +
        $"（纸: 右 {frameR.X}~{frameR.Right} 左 {frameL.X}~{frameL.Right}）",
        "同一句两侧对上 ≤2 px"));

    // 7) 裁定那三个默认值要写在键上: 默认开、亮 15 秒、空 60 秒
    var fresh = Activator.CreateInstance(dialogType)!;
    string D(string name) => dialogType.GetProperty(name)!.GetValue(fresh)!.ToString()!;
    need.Add(("默认值 = 用户拍的那三个数",
        D("Enabled") == "True" && D("ShowSeconds") == "15" && D("GapSeconds") == "60",
        $"开={D("Enabled")} 亮={D("ShowSeconds")} 空={D("GapSeconds")}", "True 15 60"));

    // 写得进读得回: 换成一组和默认值全不同的哨兵, 免得「没接线」和「刚好是默认值」看不出区别
    var whole = Activator.CreateInstance(rootType)!;
    var section = rootType.GetProperty("DialogConfig")!.GetValue(whole)!;
    dialogType.GetProperty("Enabled")!.SetValue(section, false);
    dialogType.GetProperty("ShowSeconds")!.SetValue(section, 22);
    dialogType.GetProperty("GapSeconds")!.SetValue(section, 88);
    var tmp = Path.Combine(Path.GetTempPath(), $"bwp-dialog-config-{Guid.NewGuid():N}.json");
    rootType.GetMethod("Save", new[] { typeof(string) })!.Invoke(whole, new object[] { tmp });
    var back = Activator.CreateInstance(rootType)!;
    rootType.GetMethod("Load", new[] { typeof(string) })!.Invoke(back, new object[] { tmp });
    File.Delete(tmp);
    var backSection = rootType.GetProperty("DialogConfig")!.GetValue(back)!;
    string B(string name) => dialogType.GetProperty(name)!.GetValue(backSection)!.ToString()!;
    need.Add(("三个键写进 config.json 再读回来一个不变",
        B("Enabled") == "False" && B("ShowSeconds") == "22" && B("GapSeconds") == "88",
        $"开={B("Enabled")} 亮={B("ShowSeconds")} 空={B("GapSeconds")}", "False 22 88"));

    return Criteria("台词气泡(装机件/池子折行/那张一秒一格的表/该不该露/是不是这只角色/摆位/挑词/换台词真重画/两个键)", need.ToArray());
}

/// <summary>
/// 第 23 层: 右键弹的那张功能选择小窗。它自己不装任何功能, 只做「一行一句话一个去向」——
/// Items 那一张表同时管画、管打靶、管开哪扇, 所以「第二行开成了番茄钟」这种错位只能红在这儿,
/// 不该等用户在桌面上点错了才发现。
/// 版面和命中是纯函数; 真调度那一腿在 STA 线程上真造三扇窗(不 Show)、真喂一对鼠标事件。
/// 那条线程一次消息都不泵, 所以三扇窗的 Apply 一回都跑不到: 这层既不联网, 也不碰 Program.SpineWindow
/// </summary>
static bool PetMenuChooser(Assembly asm)
{
    var formType = asm.GetType("DeskSpine.PetMenuForm")!;
    var spotsType = asm.GetType("DeskSpine.PetMenuForm+Spots")!;
    var shared = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    var member = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    int Const(string name) => (int)formType.GetField(name, shared)!.GetValue(null)!;
    var native = Const("NativePanelWidth");
    var gap = Const("Gap");
    var buttonW = Const("ButtonW");
    var buttonH = Const("ButtonH");
    var paperMargin = Const("PaperMargin");
    var need = new List<(string What, bool Ok, string Got, string Want)>();

    // 这张表就是这扇窗的全部: 几行、每行写什么、每行开哪扇, 逐行读回来对
    var items = (Array)formType.GetField("Items", shared)!.GetValue(null)!;
    var labels = items.Cast<object>().Select(r => (string)r.GetType().GetField("Item2")!.GetValue(r)!).ToArray();
    var doors = items.Cast<object>().Select(r => r.GetType().GetField("Item1")!.GetValue(r)!.ToString()!).ToArray();

    var spots = formType.GetMethod("Arrange", shared)!.Invoke(null, new object[] { native })!;
    var hitM = formType.GetMethod("HitTest", shared)!;
    Rectangle Rect(object s, string name) => (Rectangle)spotsType.GetProperty(name)!.GetValue(s)!;
    Rectangle[] Rows(object s) => (Rectangle[])spotsType.GetProperty("Rows")!.GetValue(s)!;
    Point Centre(Rectangle r) => new(r.X + r.Width / 2, r.Y + r.Height / 2);
    (string Hit, int Index) Spot(object s, Point at)
    {
        var t = hitM.Invoke(null, new object[] { s, at })!;
        return (t.GetType().GetField("Item1")!.GetValue(t)!.ToString()!,
                (int)t.GetType().GetField("Item2")!.GetValue(t)!);
    }

    var panel = Rect(spots, "Panel");
    var rows = Rows(spots);
    var close = Rect(spots, "Close");
    var titleBox = Rect(spots, "Title");
    var inside = (Rectangle r) => panel.Left <= r.Left && panel.Top <= r.Top
        && r.Right <= panel.Right && r.Bottom <= panel.Bottom;
    var clickable = rows.Append(close).ToArray();
    var clashes = clickable.Where((a, i) => clickable.Skip(i + 1).Any(b => a.IntersectsWith(b))).ToArray();
    var midLine = (panel.Width + paperMargin) / 2.0;
    var rowHits = rows.Select((r, i) => Spot(spots, Centre(r))).ToArray();
    var seams = rows.Select((r, i) => Spot(spots, new Point(Centre(r).X,
        i + 1 < rows.Length ? (r.Bottom + rows[i + 1].Top) / 2 : r.Bottom + gap / 2))).ToArray();
    var offPanel = new[] { new Point(panel.Right + 5, Centre(rows[0]).Y), new Point(-4, -4),
        new Point(Centre(rows[0]).X, panel.Bottom + 3) }.Select(at => Spot(spots, at)).ToArray();

    need.Add(("这张表就两行, 顺序和字都对", labels.SequenceEqual(new[] { "番茄钟", "查看天气" }),
        string.Join("|", labels), "番茄钟|查看天气"));
    need.Add(("第一行去番茄钟, 第二行去天气(画和开用的是同一张表, 错位跑不了)",
        doors.SequenceEqual(new[] { "Pomodoro", "Weather" }), string.Join("|", doors), "Pomodoro|Weather"));
    // 用户 2026-11-03 拍：三扇小框整体长度一致，都照番茄钟那张板的高；两行数不满，空的那一段留在底下
    var presetH = PresetPanelHeight(asm, native);
    var rowStackH = Const("TitleY") + Const("TitleH") + gap + items.Length * (buttonH + gap) - gap + Const("PadY");
    need.Add(("面板宽照那张纸的原宽 276, 高跟番茄钟那张板同一个数, 行数跟着这张表长",
        panel.Width == native && rows.Length == items.Length && presetH > 0 && panel.Height == presetH,
        $"({panel.Width},{panel.Height}) 行数 {rows.Length} 番茄钟 {presetH}", $"({native},和番茄钟同高) 行数 2"));
    need.Add(("空白只许留在底下：第一行还坐在标题下那一格, 最后一行底下空出一整截",
        rows[0].Top == Const("TitleY") + Const("TitleH") + gap && rows[^1].Bottom == rowStackH - Const("PadY")
        && panel.Bottom - rows[^1].Bottom >= presetH - rowStackH && rowStackH < presetH,
        $"第一行顶 {rows[0].Top} 最后一行底 {rows[^1].Bottom} 面板底 {panel.Bottom} 两行数出来 {rowStackH}",
        "行不摊开, 延长的那段空着"));
    need.Add(("两行和 × 都躺在面板里", clickable.All(inside),
        clickable.Count(r => !inside(r)) == 0 ? "都在" : $"{clickable.Count(r => !inside(r))} 块出界", "都在"));
    need.Add(("两行和 × 互不重叠(叠上了就是压字)", clashes.Length == 0,
        clashes.Length == 0 ? "不打架" : $"{clashes.Length} 处重叠", "0 处"));
    need.Add(("标题盒不压 ×", titleBox.Right <= close.Left,
        $"标题右 {titleBox.Right}, × 左 {close.Left}", "标题右边 ≤ × 左边"));
    var two = rows.Length >= 2;
    need.Add(("每行都坐在纸面中线上(照整幅宽居会把内容顶到纸边上去)",
        rows.All(r => Math.Abs(r.X + r.Width / 2.0 - midLine) <= 1),
        string.Join("/", rows.Select(r => (r.X + r.Width / 2.0).ToString("F0"))), midLine.ToString("F0")));
    need.Add(("两行一般宽一样高, 中间只留一个行缝",
        two && rows.Select(r => r.Width).Distinct().Count() == 1 && rows.Select(r => r.Height).Distinct().Count() == 1
        && rows[1].Top - rows[0].Bottom == gap && rows[0].Width == buttonW && rows[0].Height == buttonH,
        two ? $"{rows[0].Width}x{rows[0].Height}, 行距 {rows[1].Top - rows[0].Bottom}" : "凑不齐两行",
        $"{buttonW}x{buttonH}(按钮原尺寸一格不缩), 行距 {gap}"));
    need.Add(("点每一行的中心认到对应那一行",
        rowHits.Select((h, i) => h.Hit == "Row" && h.Index == i).All(h => h),
        string.Join("/", rowHits.Select(h => $"{h.Hit}{h.Index}")), "Row0/Row1"));
    need.Add(("行缝点空(不该把上一行或下一行连进来)", seams.All(s => s.Hit == "None"),
        string.Join("/", seams.Select(s => s.Hit)), "None/None"));
    need.Add(("板外三个点(右边框外/左上角外/底边外)都认空", offPanel.All(o => o.Hit == "None"),
        string.Join("/", offPanel.Select(o => o.Hit)), "None/None/None"));
    need.Add(("× 那一点认到 ×, 不认成任何一行", Spot(spots, Centre(close)).Hit == "Close",
        Spot(spots, Centre(close)).Hit, "Close"));

    // 真调度: 三扇窗真造出来挂到 Program 那三个静态位上, 再按下/抬起各喂一次。
    // 「HitTest 说第二行是天气」和「点下去真开的是天气」中间还隔着 Act 那一句 switch, 这里量的是后一句
    var note = "";
    var sta = new Thread(() =>
    {
        try
        {
            var program = asm.GetType("DeskSpine.Program")!;
            object Create(string name) => Activator.CreateInstance(asm.GetType("DeskSpine." + name)!)!;
            void Attach(string prop, object window)
                => program.GetProperty(prop, BindingFlags.Public | BindingFlags.Static)!.SetValue(null, window);
            var menu = Create("PetMenuForm");
            var preset = Create("FocusPresetForm");
            var card = Create("WeatherForm");
            Attach("PetMenu", menu); Attach("FocusPreset", preset); Attach("Weather", card);
            bool Wanted(object w) => (bool)w.GetType().GetProperty("IsWanted", member)!.GetValue(w)!;
            string Who() => string.Join("+", new[] { (menu, "菜单"), (preset, "番茄钟"), (card, "天气") }
                .Where(x => Wanted(x.Item1)).Select(x => x.Item2));
            void Call(object w, string method) => w.GetType()
                .GetMethod(method, BindingFlags.Public | BindingFlags.Instance)!.Invoke(w, Array.Empty<object>());
            void Mouse(object w, bool down, Point at) => w.GetType()
                .GetMethod(down ? "OnMouseDown" : "OnMouseUp", BindingFlags.NonPublic | BindingFlags.Instance)!
                .Invoke(w, new object[] { new System.Windows.Forms.MouseEventArgs(
                    System.Windows.Forms.MouseButtons.Left, 1, at.X, at.Y, 0) });
            void Click(Point at) { Mouse(menu, true, at); Mouse(menu, false, at); }
            var mine = menu.GetType().GetField("spots", member)!.GetValue(menu)!;
            var mineRows = Rows(mine);
            void Only(string what, string want) => need.Add((what, Who() == want,
                Who().Length == 0 ? "(三张都关着)" : Who(), want.Length == 0 ? "(都关着)" : want));

            need.Add(("实例起手那份版面就是 Arrange(纸原宽)那一张(不是自己另攒一套)",
                Rect(mine, "Panel") == panel && Rect(mine, "Close") == close
                && Rect(mine, "Title") == titleBox && mineRows.Zip(rows).All(p => p.First == p.Second),
                $"({Rect(mine, "Panel").Width},{Rect(mine, "Panel").Height})", $"({panel.Width},{panel.Height})"));
            Only("起手三张板都不该开着", "");
            Call(menu, "OpenAtPet");
            Only("右键那一下弹的是功能菜单(番茄钟和天气都还没开)", "菜单");
            Click(Centre(mineRows[0]));
            Only("点第一行「番茄钟」: 菜单收起, 开的是番茄钟那一扇", "番茄钟");
            Call(preset, "Yield"); Call(menu, "OpenAtPet");
            Click(Centre(mineRows[1]));
            Only("点第二行「查看天气」: 开的是天气那一扇, 不是番茄钟", "天气");
            Call(card, "Yield"); Call(menu, "OpenAtPet");
            Mouse(menu, true, Centre(mineRows[0]));
            Mouse(menu, false, Centre(mineRows[1]));
            Only("按下和抬起不在同一行就不算一次点(哪扇都不开, 菜单还挂着)", "菜单");
            Click(Rect(mine, "Close").Location);
            Only("点 ×: 菜单自己收起, 谁都不开", "");
            // 三张板抢的是宠物右侧同一块地方: 谁要上这块地, 另外两张就得让
            Call(menu, "OpenAtPet"); Call(preset, "OpenAtPet");
            Only("番茄钟那一扇要上这块地, 菜单跟着让", "番茄钟");
            Call(card, "OpenAtPet");
            Only("天气卡要上这块地, 菜单和番茄钟都让干净", "天气");
            Call(menu, "OpenAtPet");
            Only("菜单再开一次, 天气卡也收干净", "菜单");
            Call(menu, "Yield");
        }
        catch (Exception ex) { note = $"{ex.GetBaseException().GetType().Name}: {ex.GetBaseException().Message}"; }
    });
    sta.SetApartmentState(ApartmentState.STA);
    sta.Start();
    sta.Join();
    need.Add(("真调度那一段跑得下来(三扇窗造得起、鼠标事件喂得进)", note.Length == 0,
        note.Length == 0 ? "跑完了" : note, "不抛"));

    return Criteria("功能选择小窗(一张表一个去向/版面/打靶/真调度让位)", need.ToArray());
}

/// <summary>
/// 第 24 层: 天气卡片。这一层验的全是「字符串进、答案出」的那几跳 —— 三份回包形状是从真机上抓下来的,
/// 数字就是实测到的那一组(济南 / 20.0°C / code 3 / 13.6 km/h @ 212° / 12.6~20.3°; IP 那格换成文档段占位)。
/// 判据自己一次网络都不发: 端点还活不活着由 weather 子命令真跑一趟去说, 那才是这条链的凭据
/// </summary>
static bool WeatherCard(Assembly asm)
{
    var svc = asm.GetType("DeskSpine.WeatherService")!;
    var formType = asm.GetType("DeskSpine.WeatherForm")!;
    var lineType = asm.GetType("DeskSpine.WeatherForm+Line")!;
    var faceType = asm.GetType("DeskSpine.WeatherForm+Face")!;
    var noteType = asm.GetType("DeskSpine.WeatherService+Note")!;
    var spotsType = asm.GetType("DeskSpine.WeatherForm+Spots")!;
    var cardType = asm.GetType("DeskSpine.WeatherService+Card")!;
    var placeType = asm.GetType("DeskSpine.WeatherService+Place")!;
    var outcomeType = asm.GetType("DeskSpine.WeatherService+Outcome")!;
    var cfgType = asm.GetType("DeskSpine.WeatherConfig")!;
    var shared = BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
    var member = BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic;
    var need = new List<(string What, bool Ok, string Got, string Want)>();
    var threw = new List<string>();

    object Call(Type owner, string name, params object?[] args)
        => owner.GetMethod(name, shared)!.Invoke(null, args.ToArray())!;
    // 判据里凡是「产品那边可能抛」的那几跳都包一层: 抛了要红得看得见, 不能把整轮 desk 带崩
    object? Try(string what, Func<object?> f)
    {
        try { return f(); }
        catch (Exception ex) { threw.Add($"{what}→{ex.GetBaseException().GetType().Name}"); return null; }
    }
    string SOf(object? o) => o is null ? "(抛了)" : o.ToString()!;
    int IOf(object? o) => o is null ? -9999 : (int)o;
    bool BOf(object? o) => o is not null && (bool)o;
    Array AsArray(object? o) => o as Array ?? Array.Empty<object>();
    object Item(object t, int n) => t.GetType().GetField($"Item{n}")!.GetValue(t)!;
    string ReasonOf(object? tuple, int n) => tuple is null ? "(抛了)" : Item(tuple, n)?.ToString() ?? "(没给理由)";
    string Str(object o, string name) => (string)o.GetType().GetProperty(name)!.GetValue(o)!;
    int Num(object o, string name) => (int)o.GetType().GetProperty(name)!.GetValue(o)!;
    double Real(object o, string name) => (double)o.GetType().GetProperty(name)!.GetValue(o)!;
    object Place(string city, double lat, double lon)
        => Activator.CreateInstance(placeType, city, lat, lon)!;
    object Box(object? value) => value is null ? null!
        : Activator.CreateInstance(typeof(Nullable<>).MakeGenericType(value.GetType()), value)!;
    object MakeCard(string city, int temp, int code, string pheno, string from, int grade, int low, int high, DateTimeOffset at)
        => Activator.CreateInstance(cardType, city, temp, code, pheno, from, grade, low, high, at)!;
    object MakeOutcome(object? card, string? reason) => card is null
        ? outcomeType.GetConstructors().Single().Invoke(new object?[] { null, reason })!
        : Activator.CreateInstance(outcomeType, Box(card), reason)!;
    object MakeLine(string text, string face, bool wrap = false)
        => Activator.CreateInstance(lineType, text, Enum.Parse(faceType, face), wrap)!;
    Array MakeLines(params (string Text, string Face)[] src)
    {
        var arr = Array.CreateInstance(lineType, src.Length);
        for (int i = 0; i < src.Length; i++) arr.SetValue(MakeLine(src[i].Text, src[i].Face), i);
        return arr;
    }
    // 板上第五行（那句建议）带的就是这一档：它按行盒折行、不开宽，判据要能把它和读数那四行分开
    Array MakeWrapLines(params string[] src)
    {
        var arr = Array.CreateInstance(lineType, src.Length);
        for (int i = 0; i < src.Length; i++) arr.SetValue(MakeLine(src[i], "Body", true), i);
        return arr;
    }
    bool WrapOf(object line) => (bool)line.GetType().GetProperty("Wrap")!.GetValue(line)!;
    string TextOf(object line) => Str(line, "Text");
    string FaceOf(object line) => line.GetType().GetProperty("Face")!.GetValue(line)!.ToString()!;
    string ConstStr(string name) => (string)formType.GetField(name, shared)!.GetValue(null)!;
    int ConstInt(Type t, string name) => (int)t.GetField(name, shared)!.GetValue(null)!;
    string Host(string url) => new string(url.Skip(url.IndexOf("//") + 2).TakeWhile(c => c != '/').ToArray());

    // —— 1) 三份真回包: 一跳一跳对到最后那四行 ——
    const string ipMain = @"{""success"":true,""city"":""Jinan"",""latitude"":36.6683,""longitude"":116.9972}";
    const string ipBack = @"{""city"":""Jinan"",""latitude"":36.6683,""longitude"":116.9972}";
    const string geoName = @"{""results"":[{""name"":""济南"",""admin1"":""山东"",""latitude"":36.66833,""longitude"":116.99722}]}";
    const string forecast = @"{""timezone"":""Asia/Shanghai"",""current"":{""time"":""2026-11-03T12:00"",""interval"":900,"
        + @"""temperature_2m"":20.0,""weather_code"":3,""wind_speed_10m"":13.6,""wind_direction_10m"":212.0},"
        + @"""daily"":{""time"":[""2026-11-03""],""temperature_2m_max"":[20.3],""temperature_2m_min"":[12.6]}}";
    var now = new DateTimeOffset(2026, 11, 3, 12, 0, 0, TimeSpan.FromHours(8));

    var ipTuple = Try("ParseIp(主力)", () => Call(svc, "ParseIp", ipMain));
    var located = ipTuple is null ? null : Item(ipTuple, 1);
    var mainShape = located is not null && Str(located, "City") == "Jinan"
        && Real(located, "Latitude") == 36.6683 && Real(located, "Longitude") == 116.9972;
    need.Add(("主力那颗 IP 源: 城名和坐标都读出来(形状照真抓回来的那份)", mainShape,
        located is null ? "(没读出来)" : $"{Str(located, "City")} {Real(located, "Latitude")},{Real(located, "Longitude")}",
        "Jinan 36.6683,116.9972"));
    var backTuple = Try("ParseIp(兜底)", () => Call(svc, "ParseIp", ipBack));
    need.Add(("第二颗源没有 success 位, 缺那一格照样算查着了(别把兜底那趟判成挂)",
        backTuple is not null && Item(backTuple, 1) is not null && Item(backTuple, 2) is null,
        backTuple is null ? "(没跑)" : (Item(backTuple, 1) is null ? ReasonOf(backTuple, 2) : "读出来了"),
        "读出来了"));

    var named = Try("ParseName", () => Call(svc, "ParseName", geoName, Place("Jinan", 36.6683, 116.9972)))!;
    need.Add(("地名接口把英文名换成中文(板子上给用户看的是这个名)",
        Str(named, "City") == "济南", $"「{Str(named, "City")}」", "「济南」"));
    var keepEnglish = Place("Jinan", 1.0, 2.0);
    var noSwap = new[] { @"{""results"":[]}", @"{""results"":[{""name"":""济""}]}", "<html>500</html>", "" }
        .Select(j => Try("ParseName(换不着)", () => Call(svc, "ParseName", j, keepEnglish)))
        .Select(p => p is null ? "(抛了)" : Str(p, "City")).ToArray();
    need.Add(("中文名换不着就用英文名接着走 —— 这一跳不该把整张卡片拖黄, 也不能抛",
        noSwap.All(c => c == "Jinan"), string.Join("|", noSwap), "四组全退成 Jinan"));

    var cardTuple = Try("ParseForecast", () => Call(svc, "ParseForecast", forecast, "济南", now));
    var card = cardTuple is null ? null : Item(cardTuple, 1);
    need.Add(("取数那一跳: 真抓回来的 JSON → 一张卡片(温度取整、现象、八方位、蒲福级全换算完)",
        card is not null && Num(card, "TempC") == 20 && Str(card, "Phenomenon") == "阴"
        && Str(card, "WindFrom") == "西南" && Num(card, "WindGrade") == 3
        && Num(card, "LowC") == 13 && Num(card, "HighC") == 20,
        card is null ? "(没读出来)"
            : $"{Num(card, "TempC")}° {Str(card, "Phenomenon")}, {Str(card, "WindFrom")}{Num(card, "WindGrade")} 级, {Num(card, "LowC")}~{Num(card, "HighC")}",
        "20° 阴, 西南3 级, 13~20"));
    need.Add(("卡片上盖的是这一刻(新鲜度就按它算)",
        card is not null && (DateTimeOffset)card.GetType().GetProperty("ResolvedAt")!.GetValue(card)! == now,
        card is null ? "(没读出来)" : "对得上", now.ToString("HH:mm")));

    // 读数那四行: 用户要的那几条(城名 + 当前 + 现象 + 风 + 今日高低)一字一字对
    var lines = card is null ? Array.Empty<object>() : new[]
    {
        Call(svc, "CityLine", card), Call(svc, "NowLine", card),
        Call(svc, "WindLine", card), Call(svc, "TodayLine", card),
    };
    need.Add(("板上读数那四行的字(城名 / 「20° 阴」 / 「西南风 3 级」 / 「今日 13° ~ 20°」)",
        lines.Length == 4 && string.Join("|", lines) == "济南|20° 阴|西南风 3 级|今日 13° ~ 20°",
        string.Join("|", lines), "济南|20° 阴|西南风 3 级|今日 13° ~ 20°"));
    var cold = MakeCard("哈尔滨", -12, 75, "大雪", "西北", 6, -19, -11, now);
    need.Add(("零下和别座城一样念(负号、大号字都走同一条算式)",
        $"{Call(svc, "NowLine", cold)} / {Call(svc, "WindLine", cold)} / {Call(svc, "TodayLine", cold)}"
        == "-12° 大雪 / 西北风 6 级 / 今日 -19° ~ -11°",
        $"{Call(svc, "NowLine", cold)} / {Call(svc, "WindLine", cold)} / {Call(svc, "TodayLine", cold)}",
        "-12° 大雪 / 西北风 6 级 / 今日 -19° ~ -11°"));

    // —— 1b) 等高多出来的那段空白填的那一句建议(用户 2026-11-03 拍「换成一句话, 不要机械的罗列,
    //        最好有不知火的语气」)。全部从卡上已有的数算出来, 一趟都不多联网;
    //        判据照 WMO 码判, 不照现象词判 —— 现象词是给人看的那张中文名, 哪天改口不该把「带伞」那一档悄悄判丢
    object C(int temp, int code, int grade = 3, int low = 13, int high = 20)
        => MakeCard("测试城", temp, code, "占位", "西南", grade, low, high, now);
    string Adv(string what, Func<object?> f) => Try(what, f)?.ToString() ?? "(抛了)";
    string NoteOf(object c) => Adv($"PickNote", () => Call(svc, "PickNote", c));
    string NoteText(string fn, string note) => Adv($"{fn}({note})", () => Call(svc, fn, Enum.Parse(noteType, note)));
    string Neutral(object c) => Adv("中性那句", () => Call(svc, "AdviceSentence", c, ""));
    string Hers(object c) => Adv("她那句", () => Call(svc, "AdviceSentence", c, "不知火"));
    var advGroups = new (string Name, int[] Codes, string Want)[]
    {
        ("结冰", new[] { 56, 57, 66, 67 }, "路上结冰，走慢点"),
        ("雪", new[] { 71, 73, 75, 77, 85, 86 }, "有雪，路面滑"),
        ("雷", new[] { 95, 96, 99 }, "雷阵雨，躲开空旷处"),
        ("雨", new[] { 51, 53, 55, 61, 63, 65, 80, 81, 82 }, "出门带伞"),
        ("雾", new[] { 45, 48 }, "能见度低，少开车"),
        ("晴到阴", new[] { 0, 1, 2, 3 }, "适合出门走走"),
    };
    var advAll = advGroups.SelectMany(g => g.Codes.Select(code => (code, Group: g.Name, Want: g.Want,
        Got: Neutral(C(20, code))))).ToArray();
    var advOff = advAll.Where(a => a.Got != a.Want).Select(a => $"{a.code}→「{a.Got}」").ToArray();
    need.Add(($"{advAll.Length} 个 WMO 码在建议这一侧也各有归属(漏一条就掉进下面那一档, 板上念的是另一句)",
        advAll.Length == 28 && advOff.Length == 0,
        advOff.Length == 0 ? $"{advAll.Length} 条各归一家" : string.Join(",", advOff), "28 条都对且一家不多一家不少"));
    // 穿衣那六档排在链尾, 前面每一档都得先按下去才轮得到它; 扫的时候把今日高低配成同一格,
    // 否则先被「早晚温差」那句接走, 六档边界根本对不到档上（上一版判据就假红在这）。
    // 22° 往上那三档从当前温度够不到（20~28 归晴好那句）, 所以是从「最低那格」去撞它 —— 这条就是这次改写的取舍
    var dressWant = new (string Why, object Card, string Want)[]
    {
        ("当前 -12°", C(-12, 3, low: -12, high: -12), "穿厚外套，戴围巾"),
        ("0° 正好压在上沿", C(0, 3, low: 0, high: 0), "穿厚外套，戴围巾"),
        ("1° 就掉下档", C(1, 3, low: 1, high: 1), "加件外套"),
        ("8° 还在这一档", C(8, 3, low: 8, high: 8), "加件外套"),
        ("9° 掉下档", C(9, 3, low: 9, high: 9), "长袖加外套"),
        ("15° 还在这一档", C(15, 3, low: 15, high: 15), "长袖加外套"),
        ("16° 掉下档", C(16, 3, low: 16, high: 16), "长袖就够"),
        ("19° 还没进晴好那档(20 才进)", C(19, 3, low: 19, high: 19), "长袖就够"),
        ("22° 那一档只能从最低那格够到", C(29, 3, low: 22, high: 29), "长袖就够"),
        ("23° 掉下档", C(29, 3, low: 23, high: 29), "穿薄一点"),
        ("27° 还在这一档", C(29, 3, low: 27, high: 29), "穿薄一点"),
        ("28° 掉下档", C(29, 3, low: 28, high: 29), "穿透气的"),
    };
    var dressOff = dressWant.Where(p => Neutral(p.Card) != p.Want)
        .Select(p => $"{p.Why}→「{Neutral(p.Card)}」").ToArray();
    need.Add(("穿衣按当前温度和今日最低里更低的那个, 六档上沿逐一对(照中午穿会冻着)", dressOff.Length == 0,
        dressOff.Length == 0 ? $"{dressWant.Length} 个打点各落各档" : string.Join(",", dressOff), "每档一字不差"));
    // 一次只说一句, 所以「谁压住谁」就是板上那句话的全部规矩
    var priorWant = new (string Why, object Card, string Want)[]
    {
        ("冻雨压过风大", C(-1, 66, grade: 9), "路上结冰，走慢点"),
        ("雷压过晴的那句多走走", C(25, 95), "雷阵雨，躲开空旷处"),
        ("雾压过风大", C(10, 45, grade: 7), "能见度低，少开车"),
        ("风大压过晴好那句", C(24, 0, grade: 6), "风大，收好帽子"),
        ("热到三十先说防晒(晴到天上没东西掉下来也一样)", C(30, 0), "防晒多喝水"),
        ("晴好那句压住早晚温差", C(24, 1, low: 13, high: 25), "适合出门走走"),
        ("晴好那句也压住穿衣档(25° 但最低 5° 也只说多走走)", C(25, 3, low: 5, high: 25), "适合出门走走"),
        ("早晚温差压住穿衣档", C(18, 1, low: 9, high: 20), "早晚温差大，备件衣"),
        ("都不沾就按更低的那格穿衣(-12° 但今日最高 20°)", C(-12, 3, low: 20, high: 20), "穿厚外套，戴围巾"),
        ("冷到零下也不劝人多走走", C(-3, 0), "穿厚外套，戴围巾"),
    };
    var priorOff = priorWant.Where(p => Neutral(p.Card) != p.Want)
        .Select(p => $"{p.Why}→「{Neutral(p.Card)}」").ToArray();
    need.Add(("一句话只说按优先级挑出来的那件: 天象 > 风大 > 热 > 晴好温度 > 早晚温差 > 穿衣",
        priorOff.Length == 0,
        priorOff.Length == 0
            ? $"{priorWant.Length} 条各让对了(晴好那句={NoteOf(C(24, 1, low: 13, high: 25))}, 温差那条={NoteOf(C(18, 1, low: 9, high: 20))})"
            : string.Join(",", priorOff), "各按该压住的那条念"));
    var noteNames = Enum.GetNames(noteType);
    var textOff = noteNames.Select(nm => (nm, Neu: NoteText("NeutralNote", nm), Her: NoteText("HerNote", nm)))
        .Where(x => x.Neu is "" or "(抛了)" || x.Her is "" or "(抛了)" || x.Neu == x.Her)
        .Select(x => $"{x.nm}→中性「{x.Neu}」她「{x.Her}」").ToArray();
    need.Add(("十五种下场在两档文案表里各有一句、且两档不同字(加一格忘了配文案、或两档抄成同一句就红在这)",
        noteNames.Length == 15 && textOff.Length == 0,
        textOff.Length == 0 ? $"{noteNames.Length} 格 × 两档都填满且不同字" : string.Join(",", textOff),
        "15 格, 两档各一句且不同字"));
    // 语域门: 屏幕上是谁决定用哪一档 —— 和台词气泡那轮「台词只跟着它的主角弹」同一类闸
    var gateCard = C(25, 95);
    string Sent(string pet) => Adv($"语域({pet})", () => Call(svc, "AdviceSentence", gateCard, pet));
    var regWant = new (string Pet, bool Hers)[]
    {
        ("不知火", true), ("千姬", false), ("蟹姬", false), ("猫掌柜焕宴", false), ("", false), ("(空)", false),
    };
    var regOff = regWant.Where(r => Sent(r.Pet) != (r.Hers ? Hers(gateCard) : Neutral(gateCard)))
        .Select(r => $"「{r.Pet}」→「{Sent(r.Pet)}」(该走{(r.Hers ? "她" : "中性")}那档)").ToArray();
    need.Add(("只有不知火用她的腔, 别的角色和图层模式(说不出是哪只, 名字是空串)一律退回中性",
        regOff.Length == 0 && Sent("不知火") != Sent("千姬"),
        regOff.Length == 0 ? $"同一张卡片: 她「{Sent("不知火")}」/ 千姬「{Sent("千姬")}」" : string.Join(",", regOff),
        "两档不同句, 只认那三个字"));
    var petNameOf = asm.GetType("DeskSpine.PetNames")!.GetMethod("Display", shared)!;
    string NameOf(string skel) => (string)petNameOf.Invoke(null, new object[] { skel })!;
    var shiranuiKey = (string)svc.GetField("Shiranui", shared)!.GetValue(null)!;
    need.Add(("她那一档认的就是托盘名表里那三个字(名表和常量漂开, 桌面上就永远只会念中性那句)",
        NameOf("buzhihuo_1127.json") == shiranuiKey && NameOf("qianji_0552.json") != shiranuiKey,
        $"名表里 buzhihuo_1127 叫「{NameOf("buzhihuo_1127.json")}」, 代码里写「{shiranuiKey}」", "一模一样"));
    var herLongest = noteNames.Select(nm => NoteText("HerNote", nm)).OrderByDescending(s => s.Length).First();
    var neuLongest = noteNames.Select(nm => NoteText("NeutralNote", nm)).OrderByDescending(s => s.Length).First();
    need.Add(("两档各最长几个字(十五档全扫: 中性那句进一行, 她那句最多折成两行, 都不许顶宽板子)",
        neuLongest.Length <= 13 && herLongest.Length <= 16,
        $"中性最长 {neuLongest.Length} 字「{neuLongest}」 / 她最长 {herLongest.Length} 字「{herLongest}」",
        "中性 ≤13, 她 ≤16"));
    var adviceOne = Adv("AdviceSentence(济南)", () => Call(svc, "AdviceSentence", card, ""));
    need.Add(("板上底下就一句, 没有「出行：」这种前缀了(用户 2026-11-03 要的是不罗列)",
        !adviceOne.Contains("：") && adviceOne == Neutral(card),
        $"「{adviceOne}」", "一句、无前缀"));
    // 「有没有空句 / 有没有抛」不许只在上面那二十几个打点上验：整片码 × 温度 × 风档扫过去
    var advCodes = advAll.Select(a => a.code).ToArray();
    var advSweep = advCodes.Select(code => C(20, code))
        .Concat(advCodes.SelectMany(code => new[] { -25, -1, 4, 12, 19, 26, 34 }
            .Select(t => C(t, code, grade: 8, low: t - 12, high: t + 3))))
        .Concat(new[] { 6, 9, 12 }.SelectMany(g => advCodes.Select(code => C(20, code, grade: g))))
        .ToArray();
    var sweepBad = advSweep.SelectMany(c => new[] { Neutral(c), Hers(c) })
        .Where(s => s.Length == 0 || s == "(抛了)").ToArray();
    need.Add(("整片扫过去两档都不出空句也不抛(念空了就是板上凭空少一行, 除了那句什么都没有)",
        sweepBad.Length == 0 && advSweep.Length > 300,
        $"{advSweep.Length} 张 × 两档, 坏 {sweepBad.Length} 句", "0 句空、0 句抛"));

    // —— 2) 少哪一样就说哪一样, 而且一个都不许抛 ——
    var ipCases = new (string Json, string Want)[]
    {
        (@"{""success"":false,""city"":""Nowhere""}", "定位源查不着这地方"),
        (@"{""latitude"":36.6,""longitude"":116.9}", "定位没给城市名"),
        (@"{""city"":""Jinan""}", "定位没给坐标"),
        (@"{""city"":""Jinan"",""latitude"":999,""longitude"":116.9}", "坐标不在地球上"),
        (@"{""city"":123,""latitude"":36.6,""longitude"":116.9}", "定位没给城市名"),
        (@"<html><body>网关错误</body></html>", "回来的不是数据"),
        (@"", "回来的不是数据"),
    };
    var ipGot = ipCases.Select(c => ReasonOf(Try($"ParseIp「{c.Want}」",
        () => Call(svc, "ParseIp", c.Json)), 2)).ToArray();
    need.Add(("定位回包少哪一样点名哪一样(数字当城名、HTML、空身子都不抛)",
        threw.Count == 0 && ipGot.SequenceEqual(ipCases.Select(c => c.Want)),
        threw.Count > 0 ? $"{threw.Count} 组抛了: {string.Join(",", threw)}"
            : string.Join(" | ", ipCases.Select((c, i) => $"{c.Want}={ipGot[i]}")), "七组逐组对上"));
    var fcCases = new (string Json, string Want)[]
    {
        (@"{""current"":{}}", "当前温度没读到"),
        (@"{""current"":{""temperature_2m"":20.0}}", "天气代码没读到"),
        (@"{""current"":{""temperature_2m"":20.0,""weather_code"":3}}", "风速没读到"),
        (@"{""current"":{""temperature_2m"":20.0,""weather_code"":3,""wind_speed_10m"":13.6}}", "风向没读到"),
        (@"{""current"":{""temperature_2m"":""暖"",""weather_code"":3,""wind_speed_10m"":13.6,""wind_direction_10m"":212.0}}", "当前温度没读到"),
        (@"{""current"":{""temperature_2m"":20.0,""weather_code"":3,""wind_speed_10m"":13.6,""wind_direction_10m"":360.0},""daily"":{""temperature_2m_max"":[20.3],""temperature_2m_min"":[12.6]}}", "风向没读到"),
        (@"{""current"":{""temperature_2m"":20.0,""weather_code"":3,""wind_speed_10m"":13.6,""wind_direction_10m"":212.0}}", "今日最高没读到"),
        (@"{""current"":{""temperature_2m"":20.0,""weather_code"":3,""wind_speed_10m"":13.6,""wind_direction_10m"":212.0},""daily"":{""temperature_2m_max"":[],""temperature_2m_min"":[12.6]}}", "今日最高没读到"),
        (@"{""current"":{""temperature_2m"":20.0,""weather_code"":3,""wind_speed_10m"":13.6,""wind_direction_10m"":212.0},""daily"":{""temperature_2m_max"":[""高""],""temperature_2m_min"":[12.6]}}", "今日最高没读到"),
        (@"{""daily"":{}}", "没回当前这一组"),
        (@"抱歉，服务器忙", "回来的不是数据"),
    };
    var fcGot = fcCases.Select(c => ReasonOf(Try($"ParseForecast「{c.Want}」",
        () => Call(svc, "ParseForecast", c.Json, "济南", now)), 2)).ToArray();
    need.Add(("取数回包少哪一项点名哪一项(用户不必猜「读不到」是少哪一样)",
        fcGot.SequenceEqual(fcCases.Select(c => c.Want)),
        string.Join(" | ", fcCases.Select((c, i) => fcGot[i] == c.Want ? "√" : $"{c.Want}→{fcGot[i]}")), "十一组逐组对上"));
    need.Add(("上面那十八组里没有一个抛到判据手里(抛到 UI 线程就是整扇窗没影)",
        threw.Count == 0, threw.Count == 0 ? "一个都没抛" : string.Join(",", threw), "0 组抛"));

    // —— 3) 换算表: 现象、方位、风级、取整 ——
    var wmo = new (int Code, string Name)[]
    {
        (0, "晴"), (1, "少云"), (2, "局部多云"), (3, "阴"), (45, "雾"), (48, "雾凇"),
        (51, "小毛毛雨"), (53, "毛毛雨"), (55, "大毛毛雨"), (56, "小冻毛毛雨"), (57, "大冻毛毛雨"),
        (61, "小雨"), (63, "中雨"), (65, "大雨"), (66, "小冻雨"), (67, "大冻雨"),
        (71, "小雪"), (73, "中雪"), (75, "大雪"), (77, "雪粒"),
        (80, "小阵雨"), (81, "中阵雨"), (82, "急阵雨"), (85, "小阵雪"), (86, "大阵雪"),
        (95, "雷阵雨"), (96, "雷阵雨伴小冰雹"), (99, "雷阵雨伴冰雹"),
    };
    var wmoGot = wmo.Select(c => SOf(Try($"Phenomenon({c.Code})", () => Call(svc, "Phenomenon", c.Code)))).ToArray();
    var wmoOff = Enumerable.Range(0, wmo.Length).Where(i => wmoGot[i] != wmo[i].Name)
        .Select(i => $"{wmo[i].Code}→「{wmoGot[i]}」").ToArray();
    // 只看这一条自己的账: Phenomenon 要是抛了, SOf 会写成「(抛了)」, 那就已经落在 wmoOff 里了 ——
    // 再把 threw 并进来会让这条红得没道理(明明 28 条都对), 抛不抛有「没有一个抛」那一条管
    need.Add(($"{wmo.Length} 个 WMO 码逐条对中文(漏一条就退成「其他天象」, 界面上看就是「天气不说人话」)",
        wmoOff.Length == 0, wmoOff.Length == 0 ? $"{wmo.Length} 条都对" : string.Join(",", wmoOff),
        "每条一字不差"));
    var odd = SOf(Try("Phenomenon(72)", () => Call(svc, "Phenomenon", 72)));
    need.Add(("表里没有的码也给一句话(以后接口多出来的一格不许空白)",
        odd == (string)svc.GetField("PhenomenonFallback", shared)!.GetValue(null)!, $"72→「{odd}」", "别的码 → 有词的兜底"));
    var compass = new (double Deg, string Name)[]
    {
        (0, "北"), (22.4, "北"), (22.5, "东北"), (45, "东北"), (67.4, "东北"), (67.5, "东"),
        (180, "南"), (212, "西南"), (337.4, "西北"), (337.5, "北"), (359, "北"),
        (-100, "西"), (400, "东北"), (720, "北"),
    };
    var compassGot = compass.Select(c => SOf(Try($"Compass({c.Deg})", () => Call(svc, "Compass", c.Deg)))).ToArray();
    var compassOff = Enumerable.Range(0, compass.Length).Where(i => compassGot[i] != compass[i].Name)
        .Select(i => $"{compass[i].Deg}→{compassGot[i]}(该是{compass[i].Name})").ToArray();
    need.Add(("八方位: 每格 45°、中心压在正方位上, 缝口(22.5/67.5/337.5)归哪边都定死了; 负角和超过一圈先折回",
        compassOff.Length == 0, compassOff.Length == 0 ? "十四格都对" : string.Join(",", compassOff),
        "212→西南, 337.5→北, -100→西, 400→东北"));
    var beaufort = new (double Kmh, int Grade)[] { (0, 0), (1, 0), (1.1, 1), (5, 1), (5.1, 2), (11, 2),
        (11.1, 3), (13.6, 3), (19, 3), (19.1, 4), (102, 10), (102.1, 11), (117, 11), (117.1, 12), (300, 12) };
    var bfGot = beaufort.Select(c => IOf(Try("Beaufort", () => Call(svc, "Beaufort", c.Kmh)))).ToArray();
    need.Add(("蒲福风级: 实测那 13.6 km/h 是 3 级, 每道门槛两侧都试一格, 顶端封顶 12",
        bfGot.SequenceEqual(beaufort.Select(c => c.Grade)), string.Join("/", bfGot),
        string.Join("/", beaufort.Select(c => c.Grade))));
    var roundCases = new (double C, int Want)[] { (20.0, 20), (20.3, 20), (12.6, 13), (0.5, 1), (-0.5, -1), (-19.4, -19) };
    var roundGot = roundCases.Select(c => IOf(Try("Round", () => Call(svc, "Round", c.C)))).ToArray();
    need.Add(("温度取整朝外走(12.6→13, -0.5→-1, 不在 .5 上含糊)",
        roundGot.SequenceEqual(roundCases.Select(c => c.Want)), string.Join("/", roundGot),
        string.Join("/", roundCases.Select(c => c.Want))));

    // —— 4) 新鲜度和开机灌回的那份位置缓存 ——
    var freshCases = new (int OffsetMinutes, int Ttl, bool Want)[] { (0, 30, true), (-15, 30, true),
        (-29, 30, true), (-30, 30, false), (-31, 30, false), (5, 30, false), (-721, 720, false) };
    var freshGot = freshCases.Select(c => BOf(Try("IsFresh", () => Call(svc, "IsFresh",
        now.AddMinutes(c.OffsetMinutes), now, c.Ttl)))).ToArray();
    need.Add(("缓存新不新: 整点那道算旧(等于 TTL 就不等了), 时间戳跑到未来也算旧(改过系统钟宁可多问一次)",
        freshGot.SequenceEqual(freshCases.Select(c => c.Want)), string.Join("/", freshGot),
        string.Join("/", freshCases.Select(c => c.Want))));

    object Cache(string? city, double lat, double lon, DateTimeOffset when)
    {
        var c = Activator.CreateInstance(cfgType)!;
        cfgType.GetProperty("CityName")!.SetValue(c, city);
        cfgType.GetProperty("Latitude")!.SetValue(c, lat);
        cfgType.GetProperty("Longitude")!.SetValue(c, lon);
        cfgType.GetProperty("ResolvedAt")!.SetValue(c, when);
        return c;
    }
    (string? City, double Lat, double Lon) Snap()
    {
        var t = Try("Snapshot", () => Call(svc, "Snapshot"));
        return t is null ? (null, -1, -1) : ((string?)Item(t, 1), (double)Item(t, 2)!, (double)Item(t, 3)!);
    }
    Try("Seed(新鲜)", () => Call(svc, "Seed", Cache("哨兵城", 12.5, -34.5, now.AddMinutes(-10)), now));
    var seeded = Snap();
    need.Add(("开机把盘里那份位置缓存灌回内存, 省掉那一趟 IP 查询",
        seeded.City == "哨兵城" && seeded.Lat == 12.5, $"{seeded.City} {seeded.Lat}", "哨兵城 12.5"));
    foreach (var (label, stale) in new (string, object)[]
    {
        ("过期十三小时", Cache("旧城", 1.0, 2.0, now.AddMinutes(-(720 + 5)))),
        ("没城名(还没定位过)", Cache(null, 3.0, 4.0, now)),
        ("空城名", Cache("", 3.0, 4.0, now)),
        ("坐标出界", Cache("歪城", 200.0, 2.0, now)),
        ("坐标是 NaN", Cache("歪城", double.NaN, 2.0, now)),
    })
    {
        Try($"Seed({label})", () => Call(svc, "Seed", stale, now));
        var kept = Snap();
        need.Add(($"{label}的那份不灌(收了就等于上周那台机器还坐在上周那座城; NaN 更会把整份配置写盘炸掉)",
            kept.City == "哨兵城", $"手里是「{kept.City}」", "还是哨兵城"));
    }

    // —— 5) 板上的行表: 三种下场各几行、哪一行用大号字 ——
    string[] FacesOf(Array ls) => ls.Cast<object>().Select(FaceOf).ToArray();
    string[] TextsOf(Array ls) => ls.Cast<object>().Select(TextOf).ToArray();
    int H(string face) => IOf(Try($"HeightOf({face})",
        () => Call(formType, "HeightOf", Enum.Parse(faceType, face))));
    var loadingLines = AsArray(Try("LinesOf(空)", () => Call(formType, "LinesOf", Box(null), "不知火")));
    need.Add(("还没回来就一行「读取中…」",
        loadingLines.Length == 1 && TextsOf(loadingLines)[0] == ConstStr("Loading") && FacesOf(loadingLines)[0] == "Body",
        $"{loadingLines.Length} 行「{string.Join("|", TextsOf(loadingLines))}」", $"1 行「{ConstStr("Loading")}」"));
    var badLines = AsArray(Try("LinesOf(失败)",
        () => Call(formType, "LinesOf", Box(MakeOutcome(null, "路上不通")), "不知火")));
    need.Add(("读不到两行: 这板不行 + 为什么(那句理由就写在板上)",
        badLines.Length == 2 && TextsOf(badLines)[0] == ConstStr("Failed") && TextsOf(badLines)[1] == "路上不通",
        $"{badLines.Length} 行「{string.Join("|", TextsOf(badLines))}」", $"2 行「{ConstStr("Failed")}|路上不通」"));
    var muteLines = AsArray(Try("LinesOf(没理由)", () => Call(formType, "LinesOf", Box(MakeOutcome(null, null)), "不知火")));
    need.Add(("一句理由都没给也不许出现空行(顶上「没给理由」)",
        TextsOf(muteLines).Length == 2 && TextsOf(muteLines)[1] == ConstStr("NoReason")
        && TextsOf(muteLines).All(t => t.Length > 0),
        $"「{string.Join("|", TextsOf(muteLines))}」", $"「{ConstStr("Failed")}|{ConstStr("NoReason")}」"));
    var hersLines = AsArray(Try("LinesOf(她)", () => Call(formType, "LinesOf", Box(MakeOutcome(card, null)), "不知火")));
    var neutralLines = AsArray(Try("LinesOf(别只角色)",
        () => Call(formType, "LinesOf", Box(MakeOutcome(card, null)), "蟹姬")));
    need.Add(("读到五行, 而且只有当前读数那一行用大号字(读数四行 + 底下一句建议, 建议跟着正文一号)",
        hersLines.Length == 5 && FacesOf(hersLines).SequenceEqual(new[] { "Body", "Hero", "Body", "Body", "Body" })
        && !WrapOf(hersLines.GetValue(0)) && !WrapOf(hersLines.GetValue(3)) && WrapOf(hersLines.GetValue(4)),
        $"{hersLines.Length} 行 {string.Join("/", FacesOf(hersLines))} / 许不许折 {string.Join("/", hersLines.Cast<object>().Select(WrapOf))}",
        "5 行 Body/Hero/Body/Body/Body, 只有第五行许折"));
    // 等高多出来那段空白填的就是这一句：判据认的是「板上第五行 == 那一句建议」，不是行数凑够五
    var boardAdv = hersLines.Cast<object>().Skip(4).Select(TextOf).ToArray();
    // 底下那一行取成数组再比 —— .Single() 在产品少给一行时当场抛, 整轮 desk 就只剩「跑不起来」而不是红字
    var neutralAdv = neutralLines.Cast<object>().Skip(4).Select(TextOf).ToArray();
    need.Add(("底下那一行就是那句建议, 而且它跟着屏幕上是谁走(板上第五行 ≠ 随手多写的读数)",
        boardAdv.Length == 1 && boardAdv[0] == Hers(card) && boardAdv[0] != Neutral(card)
        && neutralAdv.Length == 1 && neutralAdv[0] == Neutral(card),
        $"她「{string.Join("|", boardAdv)}」/ 蟹姬「{string.Join("|", neutralAdv)}」",
        "第五行 = 那一句, 两档各归各"));
    need.Add(("行高跟着字号走: 大号那档比正文那档高, 正文那档容得下 17 号字",
        H("Hero") > H("Body") && H("Body") >= 30, $"大 {H("Hero")} / 正文 {H("Body")}", "两档, 正文 ≥30"));

    // —— 6) 板子该多宽 + 那句话怎么折: 假尺子把算式钉死(真机那把量出来会随字体漂移, 对不住常数) ——
    var fake = typeof(HarnessRuler).GetMethod("MeasureByChar")!.MakeGenericMethod(lineType)
        .CreateDelegate(typeof(Func<,>).MakeGenericType(lineType, typeof(Size)));
    int WideFor(int native, params (string Text, string Face)[] src)
        => IOf(Try("WidthFor", () => Call(formType, "WidthFor", MakeLines(src), fake, native)));
    Array Fold(Array src, int rowWidth)
        => AsArray(Try("WrapRows", () => Call(formType, "WrapRows", src, fake, rowWidth)));
    var cap = ConstInt(formType, "MaxPanelWidth");
    need.Add(("字少就用素材原宽兜底(276), 不许缩成一条小票",
        WideFor(276, ("济南", "Body")) == 276, $"{WideFor(276, ("济南", "Body"))}", "276"));
    need.Add(("最长那行是大号字时按大号的尺量(读串了档就少 40 格)",
        WideFor(100, ("短", "Body"), ("20° 阴", "Hero")) == 140,
        $"{WideFor(100, ("短", "Body"), ("20° 阴", "Hero"))}", "140(Hero 那行 5 字 × 20 + 两头纸边距)"));
    // 「今日 13° ~ 20°」整串 12 格（今日+空格+13+°+空格+~+空格+20+°），照假尺子一格 12 px = 144，两头各留 20 格纸边距
    var bodyLine = (Text: "今日 13° ~ 20°", Face: "Body");
    need.Add(("宽 = 最长那行 + 两头纸边距(20 各一份)",
        bodyLine.Text.Length * HarnessRuler.BodyPerChar + 40 == 184
        && WideFor(100, bodyLine) == bodyLine.Text.Length * HarnessRuler.BodyPerChar + 40,
        $"{WideFor(100, bodyLine)}", "184(12 格 × 12 + 两头各 20)"));
    need.Add(("理由那一句再长也封顶(别家一长串英文不许把板子顶成横幅)",
        WideFor(276, (new string('理', 40), "Body")) == cap && WideFor(276, (new string('理', 200), "Body")) == cap,
        $"40 字→{WideFor(276, (new string('理', 40), "Body"))} 200 字→{WideFor(276, (new string('理', 200), "Body"))}",
        $"都封顶 {cap}"));
    // 同一串字挂上 Wrap 就该折、不挂照旧顶宽 —— 这一条把「那句建议不开宽」和「报错理由照旧开宽」钉在同一把尺上
    var wide30 = new string('天', 30);
    need.Add(("那句建议不参与开宽(挂上 Wrap 就 276 不动, 摘掉就顶到 400 —— 顶宽就撞破等宽那条约定)",
        IOf(Try("WidthFor(挂 Wrap)", () => Call(formType, "WidthFor", MakeWrapLines(wide30), fake, 276))) == 276
        && WideFor(276, (wide30, "Body")) == 400,
        $"挂 Wrap {IOf(Try("WidthFor(挂 Wrap)", () => Call(formType, "WidthFor", MakeWrapLines(wide30), fake, 276)))}"
        + $" / 不挂 {WideFor(276, (wide30, "Body"))}", "挂 Wrap 的不开宽"));
    var fold25 = new string('衣', 25);
    var folded = Fold(MakeWrapLines(fold25), 236).Cast<object>().Select(TextOf).ToArray();
    need.Add(("折行那把算式: 25 字进 236 的行盒折成 19+6, 拼回去一字不差(折丢了就是板上少半句)",
        folded.Length == 2 && folded[0].Length == 19 && folded[1].Length == 6 && string.Join("", folded) == fold25,
        string.Join(" + ", folded.Select(f => $"{f.Length} 字")), "19 + 6, 合起来还是那 25 字"));
    var uncut = Fold(MakeLines((fold25, "Body")), 236).Cast<object>().Select(TextOf).ToArray();
    need.Add(("折行只折许它折的那几行(读数那四行和报错理由一个字都不许被切开)",
        uncut.Length == 1 && uncut[0] == fold25,
        $"{uncut.Length} 行「{string.Join("|", uncut.Select(t => $"{t.Length} 字"))}」", "原样一行 25 字"));
    // 行表直接用产品 LinesOf 出来的那五行、再照 Apply 那样过一遍折行来排：判据不自己抄一份行表，抄的那份迟早和板上对不上
    // 假尺子一格 12 px(19 字才断行), 真机那把是 17 px/字(13 字就断) —— 所以这里故意拿窄行盒逼出那一刀, 量的是板子容不容得下六行
    var cardSpots = Try("Arrange", () => formType.GetMethod("Arrange", shared)!
        .Invoke(null, new object[] { Fold(hersLines, 100), 276 }))!;
    Rectangle CRect(string name) => (Rectangle)spotsType.GetProperty(name)!.GetValue(cardSpots)!;
    var cardRows = (Rectangle[])spotsType.GetProperty("Rows")!.GetValue(cardSpots)!;
    var cardPanel = CRect("Panel");
    need.Add(("六行的盒子按各自字号占高(只有当前读数那一格 44, 其余 30), 行与行只留一个 Gap",
        cardRows.Select(r => r.Height).SequenceEqual(new[] { 30, 44, 30, 30, 30, 30 })
        && cardRows.Zip(cardRows.Skip(1)).All(p => p.Second.Top - p.First.Bottom == ConstInt(formType, "Gap")),
        string.Join("/", cardRows.Select(r => r.Height)), "30/44/30/30/30/30"));
    // 用户 2026-11-03 拍：三扇小框整体长度一致 —— 这张板不许按行数出来的数收，跟着番茄钟那张板的高走；
    // 填完那句建议还填不满的一截就留在底下（不许把板子拉长, 也不许把行摊开去填满）
    var presetCardH = PresetPanelHeight(asm, 276);
    var lineStackH = cardRows[^1].Bottom + ConstInt(formType, "PadY");
    need.Add(("面板高跟番茄钟那张板同一个数(不跟着六行缩), 宽还是纸的原宽",
        cardPanel.Width == 276 && presetCardH > 0 && cardPanel.Height == presetCardH && lineStackH < presetCardH,
        $"({cardPanel.Width},{cardPanel.Height}) 番茄钟 {presetCardH} 六行数出来 {lineStackH}", "(276,和番茄钟同高)"));
    // 板上字多字少都不许改板子大小：读取中→读到→读不到 之间整张板一跳，摆位和字号看着就像换了扇窗
    Array One() => MakeLines(("读取中…", "Body"));
    Array Two() => MakeLines(("读不到天气", "Body"), ("路上不通", "Body"));
    object? SpotsOf(Array src) => Try("Arrange", () => formType.GetMethod("Arrange", shared)!
        .Invoke(null, new object[] { src, 276 }));
    Size PanelOf(object? s) => s is null ? Size.Empty
        : ((Rectangle)spotsType.GetProperty("Panel")!.GetValue(s)!).Size;
    var stackStates = new[] { PanelOf(SpotsOf(One())), PanelOf(SpotsOf(Two())), PanelOf(cardSpots) };
    need.Add(("三种状态同一张板(一行「读取中…」和两行报错都不许撑成小票)",
        stackStates.All(p => p == cardPanel.Size) && cardPanel.Height == presetCardH,
        string.Join("/", stackStates.Select(p => $"{p.Width}x{p.Height}")), $"三张都 {cardPanel.Width}x{presetCardH}"));
    need.Add(("每一行都按纸面中线居中(左边那 20 格是抹完碎片留下的空白, 照整幅宽居就顶到纸边)",
        cardRows.All(r => r.X == 30 && r.X + r.Width / 2 == (cardPanel.Width + 20) / 2)
        && cardRows.All(r => r.Width == cardPanel.Width - 40),
        $"x={cardRows[0].X} 宽={cardRows[0].Width} 中线={cardRows[0].X + cardRows[0].Width / 2}",
        "x=30 宽=236 中线=148"));
    need.Add(("× 在右上角、不压任何一行, 六行都在板里",
        CRect("Close").Right <= cardPanel.Right && CRect("Close").Top >= 0
        && cardRows.All(r => !r.IntersectsWith(CRect("Close")))
        && cardRows.All(r => r.Bottom <= cardPanel.Bottom),
        $"× {CRect("Close")} 最后一行底 {cardRows[^1].Bottom}", "都在板里且不相压"));
    // 和番茄钟等长那一条量的是板子大小, 这一条量的是行的落点: 板子对得上但整块往下坠, 空白就跑到顶上来了
    need.Add(("六行从标题底下开始一行挨一行, 多出来的空白只许留在底下",
        cardRows[0].Top == ConstInt(formType, "TitleY") + ConstInt(formType, "TitleH") + ConstInt(formType, "Gap"),
        $"第一行顶 {cardRows[0].Top}(该是 {ConstInt(formType, "TitleY")}+{ConstInt(formType, "TitleH")}"
        + $"+{ConstInt(formType, "Gap")}={ConstInt(formType, "TitleY") + ConstInt(formType, "TitleH") + ConstInt(formType, "Gap")})",
        "第一行紧跟着标题, 空白在底下"));

    // —— 7) 四端点与超时: 这是桌宠第一次主动联网, 这一格记的是「出门的规矩」 ——
    var endpoints = ((Array)svc.GetField("IpUrls", shared)!.GetValue(null)!).Cast<object>()
        .Concat(new[] { (string)svc.GetField("NameUrlFormat", shared)!.GetValue(null)!,
                        (string)svc.GetField("ForecastUrlFormat", shared)!.GetValue(null)! })
        .Select(u => u.ToString()!).ToArray();
    need.Add(("四个端点全 HTTPS(免费档只给 http 那家已经弃用: 明文带着大致位置出门不该)",
        endpoints.All(u => u.StartsWith("https://")),
        $"{endpoints.Length} 个: {string.Join(" ", endpoints.Select(Host))}", "四个都 https"));
    need.Add(("拿英文名换中文名那一条要带着 language=zh(不带就换回来一串拼音)",
        endpoints[2].Contains("language=zh") && endpoints[2].Contains("format=json"),
        Host(endpoints[2]), "geocoding 那家 + language=zh"));
    need.Add(("取数那一条问的就是卡片要的那六项, 还带 timezone=auto(「今日」得按当地日子算)",
        endpoints[^1].Contains("temperature_2m,weather_code,wind_speed_10m,wind_direction_10m")
        && endpoints[^1].Contains("temperature_2m_max") && endpoints[^1].Contains("temperature_2m_min")
        && endpoints[^1].Contains("timezone=auto") && endpoints[^1].Contains("forecast_days=1"),
        "current 四项 + daily 两项", "六项 + 本地日子"));
    need.Add(("每一跳都设了超时(小窗只有一行「读取中…」, 没人应它就得自己收口, 不能永远挂着)",
        ConstInt(svc, "TimeoutSeconds") is > 0 and <= 20
        && ConstInt(svc, "ReadingTtlMinutes") < ConstInt(svc, "LocationTtlMinutes"),
        $"{ConstInt(svc, "TimeoutSeconds")} 秒超时, 读数缓存 {ConstInt(svc, "ReadingTtlMinutes")} 分, 位置缓存 {ConstInt(svc, "LocationTtlMinutes")} 分",
        "超时 >0, 读数比位置短"));

    // —— 8) 真拿 GDI+ 量一遍: 那五行折成几行、放不放得进板子(算式对了字太大照样挤) ——
    var paperFile = Path.Combine(Path.GetDirectoryName(asm.Location)!, @"res\image\focus_ui\bg_tips_3.png");
    var paperW = File.Exists(paperFile) ? ReadPaperWidth(paperFile) : 276;
    var fitNote = "";
    if (card is null || threw.Count > 0) fitNote = "前面那一跳没出卡片, 这一腿没得量";
    else
    {
        var sta2 = new Thread(() =>
        {
            try
            {
                // 不 Show、也不泵消息: Apply 跑不到 → EnsureFetching 开不了网络那一趟。
                // 三支笔在实例字段上, 窗口一 Dispose 就跟着没, 所以照第十层那样量完再关
                var window = Activator.CreateInstance(formType)!;
                var measure = formType.GetMethod("MeasureLine", member)!;
                var realMeasure = Delegate.CreateDelegate(
                    typeof(Func<,>).MakeGenericType(lineType, typeof(Size)), window, measure);
                var hero = (Font)formType.GetField("heroFont", member)!.GetValue(window)!;
                var body = (Font)formType.GetField("bodyFont", member)!.GetValue(window)!;
                Size SizeOf(object line) => (Size)measure.Invoke(window, new[] { line })!;
                // 板宽 = 真量出来的读数那四行(第五行挂着许它折的标记, 不参与开宽), 行盒 = 板宽减两头纸边距
                var realLines = AsArray(Call(formType, "LinesOf", Box(MakeOutcome(card, null)), "不知火"));
                var width = IOf(Call(formType, "WidthFor", realLines, realMeasure, paperW));
                var foldedReal = AsArray(Call(formType, "WrapRows", realLines, realMeasure, width - 40));
                var boxes = (Rectangle[])spotsType.GetProperty("Rows")!.GetValue(
                    formType.GetMethod("Arrange", shared)!.Invoke(null, new object[] { foldedReal, width })!)!;
                var sizes = foldedReal.Cast<object>().Select(SizeOf).ToArray();
                var tight = sizes.Zip(boxes, (s, b) => (s, b)).Where(p =>
                    p.s.Width > p.b.Width + 0.5 || p.s.Height > p.b.Height + 0.5).ToArray();
                var rowH = ConstInt(formType, "LineHeight");
                need.Add(("板子按真 GDI+ 量出来的那五行开宽、那句建议按行盒折完, 每一行都放得下(挤字就红在这)",
                    tight.Length == 0 && width == 276 && foldedReal.Length is >= 5 and <= 6
                    && foldedReal.Cast<object>().Skip(4).Select(TextOf).All(t => t.Length > 0)
                    && string.Join("", foldedReal.Cast<object>().Skip(4).Select(TextOf)) == Hers(card)
                    && rowH == boxes[4].Height,
                    tight.Length == 0
                        ? $"宽 {width}, 折完 {foldedReal.Length} 行(第五行起 {string.Join(" + ", sizes.Skip(4).Select(s => s.Width))} px), 行盒 {boxes[0].Width}"
                        : $"{tight.Length} 行放不下: {string.Join(" ", tight.Select(p => $"{p.s.Width}x{p.s.Height} 进 {p.b.Width}x{p.b.Height}"))}",
                    "0 行越界, 宽 276, 那句折成一两行且拼得回原句"));
                // 十五句 × 两档全用真 GDI+ 折一遍：假尺子一格 12 px(19 字才断)、真机那把 17 px(13 字就断),
                // 「装得下」只能由这一腿说, 而且板子高度不许跟着句子长
                var allSents = noteNames.SelectMany(nm => new[]
                {
                    (Which: "中性", Text: NoteText("NeutralNote", nm)),
                    (Which: "她那档", Text: NoteText("HerNote", nm)),
                }).ToArray();
                var foldBad = new List<string>();
                // 板子高度这一腿: 顶上那四行读数照旧的这一张卡片, 底下换成折开的这句 —— 交给产品自己的 Arrange 量整板高
                Array BoardOf(string[] pieces)
                {
                    var a = Array.CreateInstance(lineType, 4 + pieces.Length);
                    for (int i = 0; i < 4; i++) a.SetValue(realLines.GetValue(i), i);
                    for (int i = 0; i < pieces.Length; i++) a.SetValue(MakeLine(pieces[i], "Body", true), 4 + i);
                    return a;
                }
                int BoardHeight(string[] pieces) => ((Rectangle)spotsType.GetProperty("Panel")!.GetValue(
                    formType.GetMethod("Arrange", shared)!.Invoke(null, new object[] { BoardOf(pieces), 276 })!)!).Height;
                foreach (var s in allSents)
                {
                    var pieces = AsArray(Call(formType, "WrapRows", MakeWrapLines(s.Text), realMeasure, 236))
                        .Cast<object>().Select(TextOf).ToArray();
                    var ws = pieces.Select(p => SizeOf(MakeLine(p, "Body")).Width).ToArray();
                    var h = BoardHeight(pieces);
                    if (pieces.Length > 2 || ws.Any(w => w > 236) || string.Join("", pieces) != s.Text || h != presetCardH)
                        foldBad.Add($"{s.Which}「{s.Text}」→{pieces.Length} 行({string.Join("/", ws)} px) 板高 {h}");
                }
                need.Add(("十五句 × 两档都真拿 GDI+ 折过(中性 ≤1 行、她 ≤2 行、拼回去一字不差, 板子还是那张 276×418)",
                    foldBad.Count == 0 && allSents.Length == 30,
                    foldBad.Count == 0
                        ? $"{allSents.Length} 句全折进 236 的行盒, 最长那句 {allSents.Max(s => s.Text.Length)} 字"
                        : string.Join(" ", foldBad.Take(4)),
                    "0 句越界、0 句把板子拉长"));
                need.Add(("当前读数那一行确实大一号也真粗(「一眼要看的那一行」是这一行)",
                    hero.Size > body.Size && hero.Bold,
                    $"{hero.FontFamily.Name} 大 {hero.Size:F0}px {(hero.Bold ? "粗" : "常规")} / 正文 {body.Size:F0}px",
                    "比正文大且加粗"));
                need.Add(("标题那四个字是「今日天气」, 行表里第一行才是城名(别把标题当一行排进去)",
                    ConstStr("Caption") == "今日天气" && TextsOf(realLines)[0] != ConstStr("Caption"),
                    $"标题「{ConstStr("Caption")}」, 第一行「{TextsOf(realLines)[0]}」", "标题「今日天气」+ 城名分开"));
            }
            catch (Exception ex) { fitNote = $"{ex.GetBaseException().GetType().Name}: {ex.GetBaseException().Message}"; }
        });
        sta2.SetApartmentState(ApartmentState.STA);
        sta2.Start();
        sta2.Join();
    }
    // 这一格不许悄悄缺席: 前面哪一跳断了没出卡片, 这里就点名说「这一腿没得量」
    if (fitNote.Length > 0) need.Add(("真拿 GDI+ 量那一腿跑得下来(出不了卡片就没得量, 那条不能悄悄少一条)",
        false, fitNote, "不抛、且量得到"));

    return Criteria("天气卡片(三份真回包→板上读数四行+一句建议(按谁在屏幕上换腔、折两行)/缺字段点名/换算表/缓存新鲜度/版面)", need.ToArray());
}

/// <summary>
/// 往上找仓库根: 这一层要比源文件、读 csproj 和 resx、看 .gitignore，都得从根上走
/// </summary>
static string FindRepoRoot()
{
    for (var dir = new DirectoryInfo(Directory.GetCurrentDirectory()); dir is not null; dir = dir.Parent)
        if (Directory.Exists(Path.Combine(dir.FullName, "deskspine")) && Directory.Exists(Path.Combine(dir.FullName, "bwp-assets")))
            return dir.FullName;
    throw new DirectoryNotFoundException("找不到仓库根(要同时有 deskspine/ 和 bwp-assets/ 两个目录)");
}

/// <summary>
/// 第二十五层: 应用图标换成了不知火。它落在三个地方(托盘、两张标题栏、exe 文件图标)，而那张图按裁定是版权衍生件、
/// 不进版本库 —— 所以这层量的是「链子」不是长相: 装机那张在不在且六帧齐、和源图是不是逐字节同一张、
/// 代码那三处有没有真过 AppIcon.Resolve、干净克隆上没这张时退不退得回占位、resx 里有没有被偷偷塞进衍生图(版权门)、
/// csproj 那两条条件 ApplicationIcon、正式产物里那颗 PE 图标是不是它，最后带上整点报时那颗并表达摩的默认值活不活得过 Load。
/// 「认不认得出是不知火」量不到 —— 肉眼活，只能标 SKIP 交用户复验。
/// A/B/H 在干净克隆上会红: 那是「本机衍生件没装机」不是代码坏了，和番茄钟达摩那几条同一个道理。
/// </summary>
static bool AppIconChain(Assembly asm)
{
    var need = new List<(string What, bool Ok, string Got, string Want)>();
    var all = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static;
    var dir = Path.GetDirectoryName(asm.Location)!;
    var res = Path.Combine(dir, "res");
    var installed = Path.Combine(res, @"image\appicon_buzhihuo.ico");
    var repo = FindRepoRoot();
    string Repo(string rel) => Path.Combine(repo, rel);
    var src = Repo(@"deskspine\DeskSpine\res\image\appicon_buzhihuo.ico");
    var dark = Repo(@"deskspine\DeskSpine\appicon_dark.ico");

    // ICO 的头: 2 处类型(=1)、4 处帧数，每张目录项 16 字节、第 0 字节是宽(0 表示 256)
    static int[] Frames(string path)
    {
        var b = File.ReadAllBytes(path);
        if (b.Length < 6 || BitConverter.ToUInt16(b, 2) != 1) return Array.Empty<int>();
        var n = BitConverter.ToUInt16(b, 4);
        return Enumerable.Range(0, n).Select(i => b[6 + 16 * i] == 0 ? 256 : b[6 + 16 * i]).OrderBy(x => x).ToArray();
    }
    // 源码接线按字节数: ConfigForm.cs 是 GBK，解码反而引入新坑，而这些锚全是纯 ASCII
    static int Count(byte[] hay, string needle)
    {
        var n = System.Text.Encoding.UTF8.GetBytes(needle);
        var span = hay.AsSpan();
        int c = 0, at;
        while ((at = span.IndexOf(n)) >= 0) { c++; span = span[(at + n.Length)..]; }
        return c;
    }
    // resx 里那几枚 icon 的载荷是裸 ICO 字节(不是 .NET 序列化框)，所以能直接和文件比
    static (string Name, byte[] Bytes)[] IconBlobs(string resxFile)
    {
        var text = File.ReadAllText(resxFile, System.Text.Encoding.UTF8);
        var list = new List<(string, byte[])>();
        int at = -1;
        while ((at = text.IndexOf("<data name=\"", at + 1, StringComparison.Ordinal)) >= 0)
        {
            var end = text.IndexOf('"', at + 12);
            var gt = text.IndexOf('>', end);
            if (end < 0 || gt < 0 || !text.Substring(end, gt - end).Contains("System.Drawing.Icon")) continue;
            var open = text.IndexOf("<value>", gt, StringComparison.Ordinal);
            var close = text.IndexOf("</value>", open, StringComparison.Ordinal);
            if (open < 0 || close < 0) continue;
            try
            {
                var b64 = new string(text.AsSpan(open + 7, close - open - 7).ToArray().Where(c => !char.IsWhiteSpace(c)).ToArray());
                list.Add((text[(at + 12)..end], Convert.FromBase64String(b64)));
            }
            catch { list.Add((text[(at + 12)..end], Array.Empty<byte>())); }
        }
        return list.ToArray();
    }

    // A 装机那张在不在、六帧齐不齐(托盘要 16、标题栏要 32、资源管理器铺图标时要 256)
    var want6 = new[] { 16, 32, 48, 64, 128, 256 };
    var got6 = File.Exists(installed) ? Frames(installed) : Array.Empty<int>();
    need.Add(("装机 res\\image\\appicon_buzhihuo.ico 在且六帧齐", got6.SequenceEqual(want6),
        File.Exists(installed) ? $"{new FileInfo(installed).Length} B / 帧 {string.Join("/", got6)}" : "(没装机)",
        "帧 16/32/48/64/128/256"));

    // B 装机那张 == 源图逐字节: 重打图忘了重装，这条就得红(上一轮「跑的是旧产物」踩过)
    var sameBytes = File.Exists(installed) && File.Exists(src)
        && File.ReadAllBytes(installed).SequenceEqual(File.ReadAllBytes(src));
    string IcoBytes(string p) => File.Exists(p) ? $"{new FileInfo(p).Length} B" : "(不在)";
    need.Add(("装机那张和仓库旁源图逐字节同一张(防「改了源图没重装」)", sameBytes,
        $"{IcoBytes(src)} vs {IcoBytes(installed)}", "两边字节一模一样"));

    // C+D 运行时那颗到底取没取上。AppIcon 只探一次就缓存，所以每一跳之前都要把静态字段复位(等价于生产进程刚起来)
    var appIcon = asm.GetType("DeskSpine.AppIcon")!;
    var resolve = appIcon.GetMethod("Resolve", all)!;
    void ResetProbe()
    {
        appIcon.GetField("probed", all)!.SetValue(null, false);
        appIcon.GetField("derived", all)!.SetValue(null, null);
    }
    var placeholder = SystemIcons.Application;   // 故意挑一枚跟两张占位图都不相干的，「退回了」才看得出来
    Icon picked = null;
    var probeErr = "";
    try
    {
        ResetProbe();
        picked = resolve.Invoke(null, new object[] { placeholder, res }) as Icon;
    }
    catch (Exception ex) { probeErr = $"{ex.GetBaseException().GetType().Name}: {ex.GetBaseException().Message}"; }
    need.Add(("装机那张真被取上(回来的不是占位那枚)", picked is not null && !ReferenceEquals(picked, placeholder),
        probeErr.Length > 0 ? probeErr : picked is null ? "(空)" : ReferenceEquals(picked, placeholder) ? "拿回的就是占位那枚" : $"衍生那张, new Icon 选中 {picked.Width}x{picked.Height}",
        "不是占位、且不空"));

    // D 干净克隆上没这张 → 退回调用方给的占位、且不抛(这条红了就是「克隆下来起得来的样子变了」)
    var empty = Path.Combine(Path.GetTempPath(), $"bwp-noicon-{Guid.NewGuid():N}");
    Directory.CreateDirectory(empty);
    string fellBack = "(没跑)";
    try
    {
        ResetProbe();
        fellBack = ReferenceEquals(resolve.Invoke(null, new object[] { placeholder, empty }), placeholder) ? "退回占位了" : "没退回";
    }
    catch (Exception ex) { fellBack = $"抛 {ex.GetBaseException().GetType().Name}"; }
    finally { ResetProbe(); Directory.Delete(empty, true); }
    need.Add(("没那张衍生图时退回占位、不抛(干净克隆照样起得来)", fellBack == "退回占位了", fellBack, "退回占位、不抛"));

    // E 三个落点都得过 AppIcon.Resolve(设置窗构造里托盘一枚 + 标题栏一枚、换主题时托盘再重挂一枚、关于窗一枚)；
    // 报时那颗的默认值不许写回 Config() 构造函数(整段换掉会被冲)
    var wiring = new (string Where, string Needle, int Want, string Why)[]
    {
        (Repo(@"deskspine\DeskSpine\src\ConfigForm.cs"), "AppIcon.Resolve(", 3, "托盘 + 标题栏 + 换主题重挂托盘"),
        (Repo(@"deskspine\DeskSpine\src\AboutForm.Designer.cs"), "AppIcon.Resolve(", 1, "关于窗标题栏"),
        (Repo(@"deskspine\DeskSpine\src\AppIcon.cs"), "resDir ?? Program.ProgramResourceDirectory", 1, "默认还是装机那个 res"),
        (Repo(@"deskspine\DeskSpine\src\Config.cs"), "SystemConfig.BalloonIconPath", 0, "默认值只写在属性初始化器上"),
        (Repo(@"deskspine\DeskSpine\src\ConfigForm.cs"), "if (Visible && File.Exists(value))", 1, "报时那颗读不到时不许弹窗——启动会被模态框卡在 InitFromConfig 里"),
    };
    foreach (var (file, needle, want, why) in wiring)
    {
        var got = File.Exists(file) ? Count(File.ReadAllBytes(file), needle) : -1;
        need.Add(($"{Path.GetFileName(file)} 里「{needle.TrimEnd('(')}」有 {want} 处({why})", got == want,
            got < 0 ? "(文件不在)" : $"{got} 处", $"{want} 处"));
    }

    // F 版权门: 衍生图不许混进 resx(那是会进仓库的)。占位那两枚必须是上游的 appicon_dark.ico
    var derivedBytes = File.Exists(src) ? File.ReadAllBytes(src) : Array.Empty<byte>();
    var darkBytes = File.Exists(dark) ? File.ReadAllBytes(dark) : Array.Empty<byte>();
    var smuggled = new List<string>();
    var resxNote = new List<string>();
    var thisIconOk = false;
    foreach (var rel in new[] { @"deskspine\DeskSpine\src\ConfigForm.resx", @"deskspine\DeskSpine\src\AboutForm.resx" })
    {
        foreach (var (name, bytes) in IconBlobs(Repo(rel)))
        {
            resxNote.Add($"{Path.GetFileName(rel)}/{name} {bytes.Length}B");
            if (derivedBytes.Length > 0 && bytes.SequenceEqual(derivedBytes)) smuggled.Add($"{rel} 的「{name}」装的就是衍生那张");
            if (Path.GetFileName(rel) == "ConfigForm.resx" && name == "$this.Icon")
                thisIconOk = bytes.SequenceEqual(darkBytes);
        }
    }
    need.Add(("两张 resx 里没有任何一枚 icon 是衍生那张(版权件不进仓库)", smuggled.Count == 0 && derivedBytes.Length > 0,
        derivedBytes.Length == 0 ? "(源图不在, 没法比)" : smuggled.Count == 0 ? $"{resxNote.Count} 枚 icon 载荷都不等于那张 {derivedBytes.Length} B 的衍生图" : string.Join(" ", smuggled),
        "0 枚等于衍生那张"));
    need.Add(("ConfigForm.resx 的占位就是上游 appicon_dark.ico(退回去退的是它的图, 不是我打的)", thisIconOk,
        thisIconOk ? "逐字节相同" : "(不一样或没找到)", "与 appicon_dark.ico 逐字节相同"));
    var ignored = File.Exists(Repo("deskspine\\.gitignore"))
        && File.ReadAllLines(Repo("deskspine\\.gitignore"), System.Text.Encoding.UTF8)
             .Any(l => l.Trim() == "DeskSpine/res/image/appicon_buzhihuo.ico");
    need.Add(("deskspine/.gitignore 挡着那张衍生 ico", ignored, ignored ? "那一行在" : "(没那一行)", "一行 DeskSpine/res/image/appicon_buzhihuo.ico"));

    // G csproj 那两条条件 ApplicationIcon: 有那张就用它，没那张也能建起来
    var proj = File.Exists(Repo(@"deskspine\DeskSpine\DeskSpine.csproj"))
        ? File.ReadAllText(Repo(@"deskspine\DeskSpine\DeskSpine.csproj"), System.Text.Encoding.UTF8) : "";
    var bothCond = proj.Contains(@"Condition=""Exists('res\image\appicon_buzhihuo.ico')""")
        && proj.Contains(@"Condition=""!Exists('res\image\appicon_buzhihuo.ico')""");
    need.Add(("csproj 里两条条件 ApplicationIcon 都在(有图用图, 没图退回 appicon_dark.ico)", bothCond,
        bothCond ? "两条都在" : "(缺条)", "Exists 一条 + !Exists 一条"));

    // H 正式产物 exe 上那颗 PE 图标 == 装机 ico 的对应那一帧。条件式没生效时，这条是唯一会替我看一眼的红
    var exe = Path.ChangeExtension(asm.Location, ".exe");
    var peNote = "(没跑)";
    var peBad = 0;
    try
    {
        using var assoc = Icon.ExtractAssociatedIcon(exe);
        using var assocBmp = assoc.ToBitmap();
        using var wantIco = new Icon(installed, new Size(assocBmp.Width, assocBmp.Height));
        using var wantBmp = wantIco.ToBitmap();
        peNote = $"{Path.GetFileName(exe)} 里 {assocBmp.Width}x{assocBmp.Height} / 装机那帧 {wantBmp.Width}x{wantBmp.Height}";
        for (var y = 0; y < assocBmp.Height && y < wantBmp.Height; y++)
            for (var x = 0; x < assocBmp.Width && x < wantBmp.Width; x++)
                if (assocBmp.GetPixel(x, y) != wantBmp.GetPixel(x, y)) peBad++;
    }
    catch (Exception ex) { peNote = $"抛 {ex.GetBaseException().GetType().Name}: {ex.GetBaseException().Message}"; peBad = -1; }
    need.Add(("exe 文件图标抠出来和装机 ico 那一帧逐像素一样(条件 ApplicationIcon 真生效)", peBad == 0,
        peBad < 0 ? peNote : $"{peNote}, 差异 {peBad} 格", "0 格差异"));

    // I 整点报时那颗并表达摩: 默认值必须写在属性初始化器上。Load 是整段换掉 SystemConfig 的 ——
    // 有这一段但没这个键时拿到的是新 new 的对象，写在 Config() 构造函数里的那份会被冲掉(番茄钟那颗踩过)
    var sysType = asm.GetType("DeskSpine.SystemConfig")!;
    var balProp = sysType.GetProperty("BalloonIconPath")!;
    var fresh = balProp.GetValue(Activator.CreateInstance(sysType)) as string;
    var legacyJson = Path.Combine(Path.GetTempPath(), $"bwp-hourly-{Guid.NewGuid():N}.json");
    File.WriteAllText(legacyJson, "{\"SystemConfig\":{\"Visible\":true,\"HourlyChime\":true}}");
    string loaded;
    try
    {
        var back = Activator.CreateInstance(asm.GetType("DeskSpine.Config")!)!;
        asm.GetType("DeskSpine.Config")!.GetMethod("Load", new[] { typeof(string) })!
           .Invoke(back, new object[] { legacyJson });
        loaded = balProp.GetValue(asm.GetType("DeskSpine.Config")!.GetProperty("SystemConfig")!.GetValue(back)) as string ?? "(空)";
    }
    catch (Exception ex) { loaded = $"抛 {ex.GetBaseException().GetType().Name}"; }
    finally { File.Delete(legacyJson); }
    // 只比文件名: 默认值按「exe 旁边那个 res 目录」算，判据进程是 bwp-animator-test，它指到测试自己的 bin 里去了
    var damoSays = (fresh is not null && Path.GetFileName(fresh) == "focus_damo.ico")
        && Path.GetFileName(loaded) == "focus_damo.ico" && Equals(fresh, loaded);
    need.Add(("报时那颗默认和番茄钟同一张, 且活过 Load 整段换掉", damoSays,
        $"新建 {Path.GetFileName(fresh ?? "(空)")} / 旧配置 Load 回来 {Path.GetFileName(loaded)}", "两头都 focus_damo.ico"));
    need.Add(("旧的 hourlychime.ico 还在装机里(用户手动还能选回去)",
        File.Exists(Path.Combine(res, @"image\hourlychime.ico")),
        File.Exists(Path.Combine(res, @"image\hourlychime.ico")) ? "在" : "(没装机)", "res\\image\\hourlychime.ico 在"));

    // 这一层验不了的那半: 图上认不认得出是不知火、托盘那颗小不小 —— 桌面抓屏被安全策略挡着，只有肉眼能判
    Console.WriteLine("  这层不验长相: 托盘那颗和 exe 文件图标好不好认，只能用户在桌面上看(SKIP)");
    Console.WriteLine($"  resx 里的 icon 载荷: {string.Join(" ", resxNote)}");

    return Criteria("应用图标链(装机六帧/源图同字节/三处接线/占位兜底/版权门/csproj 条件/exe PE 图标/报时并表达摩)", need.ToArray());
}

/// <summary>
/// 第二十六层: 对外可见的那一层整体换成了 BwpDesktopPet + 百闻牌桌宠, 而内层那一半(命名空间、目录、数据目录名、
/// 单实例 Mutex 名、注册表自启值名)按裁定一个都不许跟着动 —— 动了等于把用户已有的配置和开机自启弄丢。
/// 所以两头都量: 「该换的」从装配出来的 dll/exe 名一路读到真建出来的那两扇窗(托盘 tooltip、关于窗标题),
/// 「不该换的」对着 Program.cs 的字节数 Mutex/注册表/数据目录还挂着 ProgramName。
/// MSI 本机建不出来(要 VS 的 Installer Projects 扩展), 安装包那半只验字符串, 装出来的样子标 SKIP 交用户看一眼。
/// </summary>
static bool VisibleNameChain(Assembly asm)
{
    var need = new List<(string What, bool Ok, string Got, string Want)>();
    var all = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Static;
    var member = BindingFlags.NonPublic | BindingFlags.Public | BindingFlags.Instance;
    var repo = FindRepoRoot();
    string Repo(string rel) => Path.Combine(repo, rel);
    string Src(string file) => Repo(Path.Combine(@"deskspine\DeskSpine\src", file));
    // 源码锚按字节数且只用 ASCII: Program.cs / ConfigForm.cs 是 GBK, 拿 UTF-8 编锚或整体解码都会读歪
    int Count(string file, string needle)
    {
        if (!File.Exists(file)) return -1;
        var span = File.ReadAllBytes(file).AsSpan();
        var n = System.Text.Encoding.ASCII.GetBytes(needle);
        int c = 0, at;
        while ((at = span.IndexOf(n)) >= 0) { c++; span = span[(at + n.Length)..]; }
        return c;
    }
    string Text(string file) => File.Exists(file) ? File.ReadAllText(file, System.Text.Encoding.UTF8) : "";

    var programType = asm.GetType("DeskSpine.Program")!;
    // ProgramName / DisplayName 是 const, ProgramDataDirectory 是 static readonly —— 三个都是字段, 没有属性
    string FieldValue(string name) => programType.GetField(name, all)!.GetValue(null) as string ?? "(空)";

    // 该换的那头: 装配名 / exe 名 / 那个中文常量
    var dllName = Path.GetFileName(asm.Location);
    var asmName = asm.GetName().Name ?? "(空)";
    need.Add(("装配出来的就叫 BwpDesktopPet(命名空间那半故意没跟着改)", dllName == "BwpDesktopPet.dll" && asmName == "BwpDesktopPet",
        $"{dllName} / 简单名 {asmName}", "BwpDesktopPet.dll / BwpDesktopPet"));
    var exePath = Path.ChangeExtension(asm.Location, ".exe");
    // 比的是名字不是「有没有个兄弟文件」: AssemblyName 那条整个没了时, 旁边躺着的是 DeskSpine.exe, 只查存在就假绿了(反向验 a/b 抓出来的)
    need.Add(("同目录那个原生壳 exe 就叫 BwpDesktopPet.exe(用户双击的是它)",
        File.Exists(exePath) && Path.GetFileName(exePath) == "BwpDesktopPet.exe",
        File.Exists(exePath) ? Path.GetFileName(exePath) : $"(没找到 {Path.GetFileName(exePath)})", "BwpDesktopPet.exe 在"));
    var display = FieldValue("DisplayName");
    need.Add(("Program.DisplayName 是那几个中文", display == "百闻牌桌宠", $"「{display}」", "「百闻牌桌宠」"));

    // 真建两扇窗读那两串字: 托盘 tooltip 只有构造完才在, 关于窗标题只有那条赋值跑过才变
    string trayNote = "(没跑)", aboutNote = "(没跑)";
    var sta = new Thread(() =>
    {
        try
        {
            var form = Activator.CreateInstance(asm.GetType("DeskSpine.ConfigForm")!)!;
            var tray = form.GetType().GetField("notifyIcon", member)!.GetValue(form)!;
            trayNote = (string)tray.GetType().GetProperty("Text")!.GetValue(tray)!;
        }
        catch (Exception ex) { trayNote = $"抛 {ex.GetBaseException().GetType().Name}: {ex.GetBaseException().Message}"; }
        try
        {
            var about = Activator.CreateInstance(asm.GetType("DeskSpine.AboutForm")!)!;
            aboutNote = (string)about.GetType().GetProperty("Text")!.GetValue(about)!;
        }
        catch (Exception ex) { aboutNote = $"抛 {ex.GetBaseException().GetType().Name}: {ex.GetBaseException().Message}"; }
    });
    sta.SetApartmentState(ApartmentState.STA);
    sta.Start();
    sta.Join();
    need.Add(("真建一扇设置窗, 托盘 tooltip 是中文那几个字", trayNote == "百闻牌桌宠", $"「{trayNote}」", "「百闻牌桌宠」"));
    need.Add(("真建一扇关于窗, 标题是「关于 百闻牌桌宠」", aboutNote == "关于 百闻牌桌宠", $"「{aboutNote}」", "「关于 百闻牌桌宠」"));

    // 不许动的那头: 数据目录名、单实例 Mutex 名、注册表自启值名都还挂着 ProgramName
    var progFile = Src("Program.cs");
    var keep = new (string Needle, string Why)[]
    {
        ("ProgramName = \"DeskSpine\";", "Release 那一支的常量还是它"),
        ("Path.Combine(SystemValue.LocalAppdataDirectory, ProgramName)", "配置目录名跟着它走"),
        ("new Mutex(true, ProgramName", "单实例名跟着它走"),
        ("runKey.SetValue(ProgramName", "开机自启那条值名跟着它走"),
        ("runKey.GetValue(ProgramName", "开机自启那条值名跟着它走"),
        ("runKey.DeleteValue(ProgramName", "开机自启那条值名跟着它走"),
    };
    foreach (var (needle, why) in keep)
    {
        var got = Count(progFile, needle);
        need.Add(("Program.cs 里「" + needle + "」还在(没跟着改名) " + why, got == 1,
            got < 0 ? "(文件不在)" : $"{got} 处", "1 处"));
    }
    var runtimeProgramName = FieldValue("ProgramName");
    var dataDir = FieldValue("ProgramDataDirectory");
    need.Add(("跑起来算出来的数据目录仍是 %LOCALAPPDATA%\\DeskSpine(用户已有配置不丢)",
        runtimeProgramName == "DeskSpine" && dataDir.EndsWith(@"\DeskSpine"),
        $"ProgramName={runtimeProgramName} 目录={dataDir}", "DeskSpine + 以 \\DeskSpine 结尾"));

    // 重复启动那个框: 标题走显示名, 但正文和 Mutex 那句不许混为一谈
    var boxTitle = Count(progFile, ", DisplayName, MessageBoxButtons.OK");
    var staleTitle = Count(progFile, ", ProgramName, MessageBoxButtons");
    need.Add(("重复启动那个框的标题用 DisplayName(不再露出 ProgramName)", boxTitle == 1 && staleTitle == 0,
        $"{boxTitle} 处用 DisplayName / {staleTitle} 处还用 ProgramName", "1 处 + 0 处"));
    // 设置窗还会弹两框: 打不开文件夹、SpineTool 起不来 —— 那两块标题栏也是用户会读到的字
    var errShown = Count(Src("ConfigForm.cs"), ", Program.DisplayName, MessageBoxButtons");
    var errStale = Count(Src("ConfigForm.cs"), ", Program.ProgramName, MessageBoxButtons");
    need.Add(("设置窗那两弹错误框的标题也用 DisplayName", errShown == 2 && errStale == 0,
        $"{errShown} 处用 DisplayName / {errStale} 处还用 ProgramName", "2 处 + 0 处"));

    // csproj 与安装包那几串: 只有字符串可查, MSI 本机建不出来
    var proj = Text(Repo(@"deskspine\DeskSpine\DeskSpine.csproj"));
    need.Add(("csproj 里 AssemblyName 就是它(且没留着旧的)",
        proj.Contains("<AssemblyName>BwpDesktopPet</AssemblyName>") && !proj.Contains("<AssemblyName>DeskSpine<"),
        proj.Contains("<AssemblyName>BwpDesktopPet</AssemblyName>") ? "BwpDesktopPet" : "(没有那条)", "一条 <AssemblyName>BwpDesktopPet</AssemblyName>"));
    var vd = Text(Repo(@"deskspine\Setup\Setup.vdproj"));
    var vdWants = new (string Needle, string Why)[]
    {
        ("\"ProductName\" = \"8:BwpDesktopPet\"", "卸载列表和安装文件夹那一格"),
        ("\"Title\" = \"8:BwpDesktopPet Setup\"", "安装向导标题栏"),
        ("\"8:Release\\\\BwpDesktopPetSetup.msi\"", "产物文件名"),
        ("\"Name\" = \"8:百闻牌桌宠\"", "开始菜单/桌面快捷方式那行字"),
    };
    var vdMiss = vdWants.Where(w => !vd.Contains(w.Needle)).Select(w => w.Why).ToArray();
    int shortcuts = vd.Split(new[] { "\"Name\" = \"8:百闻牌桌宠\"" }, StringSplitOptions.None).Length - 1;
    need.Add(("Setup.vdproj 四条对外字符串都换了(快捷方式两行都算)", vdMiss.Length == 0 && shortcuts == 2,
        vdMiss.Length == 0 ? $"四条都在, 快捷方式那行 {shortcuts} 处" : string.Join(" ", vdMiss), "四条都在 + 快捷方式 2 处"));
    var vdOld = new[] { "8:DeskSpine\"", "DeskSpineSetup.msi", "8:DeskSpine Setup" }.Where(vd.Contains).ToArray();
    need.Add(("vdproj 里对外的旧名清干净了(只剩上游仓库链接和 apphost 那条路径)", vdOld.Length == 0,
        vdOld.Length == 0 ? "没有残留" : $"残留 {string.Join(" ", vdOld)}", "0 处残留"));

    // 工具侧: 改名之后那几把量尺要是还按旧进程名找人，就会「桌宠明明在跑、脚本说没找到」—— 和「跑的是旧产物」同一类自己骗自己
    var tools = new[] { "check-pet-window.ps1", "check-bubble-window.ps1", "hitmap.ps1", "pet-hitmap.ps1", "probe-jitter.ps1", "setup_pet.py" };
    var stale = tools.Where(f => Count(Path.Combine(repo, @"bwp-assets", f), "DeskSpine.exe") > 0
        || Count(Path.Combine(repo, @"bwp-assets", f), "Get-Process DeskSpine") > 0).ToArray();
    var gone = tools.Where(f => !File.Exists(Path.Combine(repo, @"bwp-assets", f))).ToArray();
    need.Add(("bwp-assets 那几把尺子按新进程名找人(不然桌宠在跑也说没找到)", stale.Length == 0 && gone.Length == 0,
        gone.Length > 0 ? $"这几个文件不在: {string.Join(" ", gone)}" : stale.Length == 0 ? $"{tools.Length} 把都对着新名" : $"还按旧名: {string.Join(" ", stale)}",
        "6 把都在且 0 处旧进程名"));

    // 这一层验不了的那半: 安装包得在 VS 里建, 装完那一刻开始菜单/卸载列表/快捷方式叫什么只有肉眼能判
    Console.WriteLine("  这层不验装机样子: MSI 本机建不出来(要 VS Installer Projects 扩展), 快捷方式和卸载列表那几行字装完请用户看一眼(SKIP)");

    return Criteria("对外名字链(dll/exe 名/中文显示名/托盘 tooltip/关于窗标题/ProgramName 那半没动/重复启动框/csproj/vdproj)", need.ToArray());
}

/// <summary>
/// 第二十七层: 随 release 附件一起发过去的素材, 首启得自己能登记进名册。
/// 配置只认 %LOCALAPPDATA%\DeskSpine\config.json, 骨架路径又是按绝对路径解析的, 所以「文件躺在包里」和
/// 「桌宠在桌上」中间差的就是这一步。这里在临时目录造一棵假的 res\spine(骨架是空文件 —— 这条量的是认路的链子,
/// 不是素材本身), 验四件事: 认得出可用骨架、缺同名 .atlas 的那只不许登记、已有配置的用户一个字节都不许被覆盖、
/// 包内没这目录时(自己从源码建的那类人)静默不写文件。
/// </summary>
/// <summary>
/// 把「解压就能用」那句话跑在附件里的真素材上 —— 第 27 层那棵 res\spine 是合成假骨架(空字节),
/// 量的只是认路的链子; 这里拿建出来的那份 dll 对着包里那四只真骨骼登记一遍:
/// 配置写到临时目录(先撞上本机那一份就拒绝跑，用户的数据不许碰)，量四件事 ——
/// 真登记得上几只、名册里那几条路径真在场且落在包内、托盘显示得出中文名而不是拼音目录名、
/// 已有配置的那一份再调一次回 0 且一个字节不动。渲染那半条只有肉眼能量，这里不装。
/// </summary>
int SeedProbe(string[] args)
{
    if (args.Length < 3)
    {
        Console.WriteLine("usage: seed <BwpDesktopPet.dll> <包里的 res\\spine 目录> <临时目录>");
        return 2;
    }
    var dll = Path.GetFullPath(args[0]);
    var bundle = Path.GetFullPath(args[1]);
    var work = Path.GetFullPath(args[2]);
    if (!File.Exists(dll) || !Directory.Exists(bundle))
    {
        Console.WriteLine($"  找不到产物({File.Exists(dll)})或包内素材({Directory.Exists(bundle)})");
        return 1;
    }
    var cfgPath = Path.Combine(work, "config.json");
    var live = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                            "DeskSpine", "config.json");
    if (string.Equals(cfgPath, live, StringComparison.OrdinalIgnoreCase))
    {
        Console.WriteLine("  临时目录就是本机那份真配置，拒绝跑(这条判据不许碰用户的数据)");
        return 1;
    }

    var asm = Assembly.LoadFrom(dll);
    var seed = asm.GetType("DeskSpine.BundledRoster")!.GetMethod("Seed", BindingFlags.Static | BindingFlags.Public)!;
    var cfgType = asm.GetType("DeskSpine.Config")!;
    var load = cfgType.GetMethod("Load", new[] { typeof(string) })!;
    var display = asm.GetType("DeskSpine.PetNames")!.GetMethod("Display", new[] { typeof(string) })!;
    object Spine(object cfg) => cfgType.GetProperty("SpineConfig")!.GetValue(cfg)!;
    int Slot(object cfg, string name) => Convert.ToInt32(Spine(cfg).GetType().GetProperty(name)!.GetValue(Spine(cfg))!);
    string Skel(object cfg, int i) => (string)Spine(cfg).GetType().GetMethod("GetSkelPath")!
        .Invoke(Spine(cfg), new object[] { i })!;
    bool FlagAt(object cfg, string section, string name)
    {
        var p = cfgType.GetProperty(section)!.GetValue(cfg)!;
        return (bool)p.GetType().GetProperty(name)!.GetValue(p)!;
    }
    object Reload()
    {
        var o = Activator.CreateInstance(cfgType)!;
        load.Invoke(o, new object[] { cfgPath });
        return o;
    }

    if (Directory.Exists(work)) Directory.Delete(work, true);
    Directory.CreateDirectory(work);

    // 「应该登记几只」自己按同一条规则数一遍(有 .skel 且同名 .atlas)，不抄死一个 4
    var usable = Directory.GetDirectories(bundle).OrderBy(d => d, StringComparer.Ordinal)
        .Where(d => Directory.GetFiles(d, "*.skel").Any(s => File.Exists(Path.ChangeExtension(s, ".atlas"))))
        .Take(SpineSlotCount(asm)).ToList();

    var n = (int)seed.Invoke(null, new object[] { bundle, cfgPath })!;
    var wrote = File.Exists(cfgPath);          // 一只都没登记上时产品是不写配置文件的(源码党那条守卫)
    var cfg = wrote ? Reload() : null;
    var got = new List<string>();
    if (wrote) for (var i = 0; i < usable.Count; i++) got.Add(Skel(cfg!, i));
    var names = got.Select(p => (string)display.Invoke(null, new object[] { p })!).ToList();
    var han = new System.Text.RegularExpressions.Regex("[一-鿿]");
    int Num(string name) => cfg is null ? -1 : Slot(cfg, name);
    bool On(string section, string name) => cfg is not null && FlagAt(cfg, section, name);

    // 第二次首启: 上面那份就当是用户自己改过的配置，再登记一次必须回 0 且一个字节不许动
    var before = wrote ? File.ReadAllBytes(cfgPath) : Array.Empty<byte>();
    var again = (int)seed.Invoke(null, new object[] { bundle, cfgPath })!;
    var after = wrote ? File.ReadAllBytes(cfgPath) : Array.Empty<byte>();

    var cases = new[]
    {
        ("附件里那几只真登记得上", n == usable.Count && usable.Count > 0,
            $"回 {n} 只(包内可用 {usable.Count} 只)", "两者相等且不为 0"),
        ("名册里那几条路径真在场、且就在包里", wrote && got.Count == usable.Count && got.All(p => p != null
            && File.Exists(p) && p!.StartsWith(bundle + Path.DirectorySeparatorChar, StringComparison.OrdinalIgnoreCase)),
            wrote ? string.Join("|", got.Select(p => p is null ? "空" : Path.GetFileName(Path.GetDirectoryName(p)))) : "配置文件根本没写出来",
            "每格都是包内 res\\spine 下真存在的骨架"),
        ("托盘显示得出中文名(不是拼音骨架名)", wrote && names.Count > 0
            && names.All(s => han.IsMatch(s) && !s.Contains("_")) && names.Distinct().Count() == names.Count,
            wrote ? string.Join("、", names) : "(没配置可读)", "每只都是中文名、不重样"),
        ("V306/模式5/出场0/PMA/可见 落对(真配置读回来)", cfg is not null && Num("SpineVersion") == 0x0306
            && Num("InteractMode") == 5 && Num("ActiveSlot") == 0
            && On("BasicConfig", "SpineUsePMA") && On("SystemConfig", "Visible"),
            cfg is null ? "(没配置可读)"
                : $"V{Num("SpineVersion"):X} 模式{Num("InteractMode")} 出场{Num("ActiveSlot")} PMA{On("BasicConfig", "SpineUsePMA")} 可见{On("SystemConfig", "Visible")}",
            "V306 模式5 出场0 PMATrue 可见True"),
        ("已经有配置了再首启: 回 0 且一个字节不动", !wrote || (again == 0 && before.SequenceEqual(after)),
            wrote ? $"回 {again}, 文件{(before.SequenceEqual(after) ? "没动" : "被改了")}" : "(这一轮根本没写配置，看上面那条)",
            "回 0 且文件原样"),
    };
    var ok = Criteria("附件真素材首启登记(跑在这份产物上)", cases);
    Console.WriteLine($"  临时配置写在 {Path.GetFileName(work)} 里，量完删掉；本机那份没动过");
    Directory.Delete(work, true);
    Console.WriteLine(ok ? "SEED OK" : "SEED FAIL");
    return ok ? 0 : 1;
}

/// <summary>
/// 「首启真的会登记」这条链子接上了没 —— 不看源码里的字，看 Program 那个类型的 IL 里
/// 有没有一条 call 指向 BundledRoster.SeedIfFirstRun。Seed 写得再对、没人调它，
/// 附件里那四只照样躺在 res\spine 里没人认，而这层就假绿了。
/// </summary>
static bool CallsSeedIfFirstRun(Assembly asm)
{
    var owner = asm.GetType("DeskSpine.Program");
    var target = asm.GetType("DeskSpine.BundledRoster")?.GetMethod("SeedIfFirstRun", BindingFlags.Static | BindingFlags.Public);
    if (owner is null || target is null) return false;
    foreach (var m in owner.GetMethods(BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic))
    {
        byte[] il;
        try { il = m.GetMethodBody()?.GetILAsByteArray(); } catch { continue; }
        if (il is null) continue;
        for (var i = 0; i + 4 < il.Length; i++)
        {
            if (il[i] != 0x28) continue;          // call
            MethodBase mb;
            try { mb = m.Module.ResolveMethod(BitConverter.ToInt32(il, i + 1)); } catch { continue; }
            if (mb == target) return true;
        }
    }
    return false;
}

static bool BundledSeed(Assembly asm)
{
    var type = asm.GetType("DeskSpine.BundledRoster");
    var seed = type?.GetMethod("Seed", BindingFlags.Static | BindingFlags.Public);
    if (seed is null)
        return Criteria("包内素材首启登记", new[]
        {
            ("DeskSpine.BundledRoster.Seed 在产物里", false, "找不到这个静态方法", "接在产品代码里, 且 Program.cs 首启调用它"),
        });

    var cfgType = asm.GetType("DeskSpine.Config")!;
    var load = cfgType.GetMethod("Load", new[] { typeof(string) })!;
    var spineCfg = cfgType.GetProperty("SpineConfig")!.PropertyType;
    var getSkel = spineCfg.GetMethod("GetSkelPath")!;
    var display = asm.GetType("DeskSpine.PetNames")!.GetMethod("Display", new[] { typeof(string) })!;

    object Fresh() => Activator.CreateInstance(cfgType)!;
    string SkelAt(object cfg, int i)
        => (string)getSkel.Invoke(cfgType.GetProperty("SpineConfig")!.GetValue(cfg)!, new object[] { i })!;
    int Num(object cfg, string section, string name)
    {
        var p = cfgType.GetProperty(section)!.GetValue(cfg)!;
        return Convert.ToInt32(p.GetType().GetProperty(name)!.GetValue(p)!);
    }
    bool Flag(object cfg, string section, string name)
    {
        var p = cfgType.GetProperty(section)!.GetValue(cfg)!;
        return (bool)p.GetType().GetProperty(name)!.GetValue(p)!;
    }

    var tmp = Path.Combine(Path.GetTempPath(), "bwp-bundle-seed");
    static void Clear(string dir)
    {
        if (!Directory.Exists(dir)) return;
        foreach (var f in Directory.GetFiles(dir, "*", SearchOption.AllDirectories))
            File.SetAttributes(f, FileAttributes.Normal);
        Directory.Delete(dir, true);
    }
    Clear(tmp);

    // 产品那边抛了要红得看得见，不能把整轮 desk 带崩（守卫被拆掉的那条 bug 就是这么抓的）
    (bool, int) Call(string bundleRoot, string configPath)
    {
        try { return (true, (int)seed.Invoke(null, new object[] { bundleRoot, configPath })!); }
        catch { return (false, -1); }
    }

    string Make(string bundle, string pet, bool withAtlas)
    {
        var d = Path.Combine(bundle, pet);
        Directory.CreateDirectory(d);
        var skel = Path.Combine(d, pet + ".skel");
        File.WriteAllBytes(skel, new byte[] { 0x00 });
        if (withAtlas) File.WriteAllText(Path.ChangeExtension(skel, ".atlas"), $"{pet}\nsize: 1,1\n");
        return skel;
    }

    var cases = new List<(string, bool, string, string)>();
    var wired = CallsSeedIfFirstRun(asm);
    cases.Add(("首启真的会调它(Program 那一头接上了)", wired,
        wired ? "Main 的 IL 里有一条 call 指到 SeedIfFirstRun" : "Program 里没人调它(附件里那四只没人登记)",
        "产品入口的 IL 里有一处调用"));

    // 一、能用: 不知火(有图集) + 千姬(有图集) + 蟹姬(缺图集, 不许登记)
    var bundle = Path.Combine(tmp, "res", "spine");
    var a = Make(bundle, "buzhihuo_1127", true);
    var b = Make(bundle, "qianji_0552", true);
    var c = Make(bundle, "xieji_0481", false);
    var cfg1 = Path.Combine(tmp, "cfg1.json");
    var (ok1, n1) = Call(bundle, cfg1);
    var cfgObj = Fresh();
    load.Invoke(cfgObj, new object[] { cfg1 });
    var s0 = SkelAt(cfgObj, 0);
    var s1 = SkelAt(cfgObj, 1);
    var s2 = SkelAt(cfgObj, 2);
    string Pet(string? p) => p is null ? "空" : Path.GetFileNameWithoutExtension(p);
    string Back(bool ok, int n) => ok ? $"回 {n} 只" : "Seed 直接抛了(守卫没了)";
    cases.Add(("登记了几只", ok1 && n1 == 2 && s0 == Path.GetFullPath(a) && s1 == Path.GetFullPath(b) && s2 is null,
        $"{Back(ok1, n1)}, 名册[{Pet(s0)}|{Pet(s1)}|{Pet(s2)}] 应为 2 只 不知火|千姬|空",
        "2 只, 按目录名序排, 缺 .atlas 那只不收"));
    cases.Add(("版本/模式/PMA/出场格 落对", Num(cfgObj, "SpineConfig", "SpineVersion") == 0x0306
        && Num(cfgObj, "SpineConfig", "InteractMode") == 5 && Num(cfgObj, "SpineConfig", "ActiveSlot") == 0
        && Flag(cfgObj, "BasicConfig", "SpineUsePMA") && Flag(cfgObj, "SystemConfig", "Visible"),
        $"V{Num(cfgObj, "SpineConfig", "SpineVersion"):X} 模式{Num(cfgObj, "SpineConfig", "InteractMode")} 出场{Num(cfgObj, "SpineConfig", "ActiveSlot")} PMA{Flag(cfgObj, "BasicConfig", "SpineUsePMA")} 可见{Flag(cfgObj, "SystemConfig", "Visible")}",
        "V306(3.6) 模式5(BwpHero) 出场0 PMA真 可见真"));
    cases.Add(("登记上的路径托盘里显示得出中文名", (string)display.Invoke(null, new object[] { s0! }!) == "不知火",
        (string)display.Invoke(null, new object[] { s0! }!)!, "不知火"));

    // 二、已经有配置的人: 一个字节都不许动(用户在设置窗里改的那份不能被包里那份覆盖)
    var keep = "# 用户自己写的一行, 不是合法 JSON\n";
    File.WriteAllText(cfg1, keep);
    var (ok2, n2) = Call(bundle, cfg1);
    cases.Add(("已有配置不许覆盖", ok2 && n2 == 0 && File.ReadAllText(cfg1) == keep,
        $"{Back(ok2, n2)}, 文件{(File.ReadAllText(cfg1) == keep ? "没动" : "被改了")}", "回 0 且文件原样"));

    // 三、名册只有十格
    var bundle2 = Path.Combine(tmp, "twelve", "res", "spine");
    for (var i = 0; i < 12; i++) Make(bundle2, $"p{i:00}", true);
    var cfg3 = Path.Combine(tmp, "cfg3.json");
    var (ok3, n3) = Call(bundle2, cfg3);
    var cfgObj3 = Fresh();
    load.Invoke(cfgObj3, new object[] { cfg3 });
    cases.Add(("超过十格只收前十格", ok3 && n3 == SpineSlotCount(asm) && SkelAt(cfgObj3, 9)!.EndsWith("p09.skel") && SkelAt(cfgObj3, 0)!.EndsWith("p00.skel"),
        $"{Back(ok3, n3)}, 第0格{Pet(SkelAt(cfgObj3, 0))}, 第9格{Pet(SkelAt(cfgObj3, 9))}", "收 10 只, p00..p09"));

    // 四、自己从源码建的包: 没这目录就该静默, 连配置文件都不许造
    var cfg4 = Path.Combine(tmp, "cfg4.json");
    var (ok4, n4) = Call(Path.Combine(tmp, "no-such-dir"), cfg4);
    cases.Add(("包内没素材时静默(源码党不受影响)", ok4 && n4 == 0 && !File.Exists(cfg4),
        $"{Back(ok4, n4)}, 配置文件{(File.Exists(cfg4) ? "被造出来了" : "没造")}", "回 0 且不写文件"));

    Clear(tmp);
    return Criteria("包内素材首启登记(链子, 不碰真素材)", cases.ToArray());
}

/// <summary>产品里那格数只从 SpineConfig.SlotCount 拿, 判据不抄数(抄了改一处就假绿)</summary>
static int SpineSlotCount(Assembly asm)
    => (int)asm.GetType("DeskSpine.SpineConfig")!.GetField("SlotCount")!.GetValue(null)!;

/// <summary>装机那张纸的原宽: 产品里 WidthFor 喂的就是它, 判据照同一个数, 别自己钉一个会漂的</summary>
static int ReadPaperWidth(string file)
{
    using var probe = new Bitmap(new MemoryStream(File.ReadAllBytes(file)));
    return probe.Width;
}

/// <summary>
/// 番茄钟那张板在这个宽度下有多高 —— 三扇小框对齐用的就是这把尺。
/// 让产品自己报数: 判据里抄一个 418，Presets 那一表改了行高这边就假绿/假红。
/// 方法没接上（回滚成「各自数各自的行」那版）就当 0 交回去，让那条判据红，而不是把这层炸掉
/// </summary>
static int PresetPanelHeight(Assembly asm, int width)
{
    var m = asm.GetType("DeskSpine.FocusPresetForm")?
        .GetMethod("PanelHeight", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
    return m is null ? 0 : (int)m.Invoke(null, new object[] { width })!;
}

static bool Criteria(string title, (string What, bool Ok, string Got, string Want)[] cases)
{
    var ok = cases.All(c => c.Ok);
    var detail = string.Join("  ", cases.Select(c => c.Got.Length == 0 ? (c.Ok ? c.What : $"✗{c.What}") : $"{c.What}={c.Got}"));
    Console.WriteLine($"  {title}: {(ok ? "是" : "否")}  {detail}");
    foreach (var c in cases.Where(c => !c.Ok && c.Want.Length > 0))
        Console.WriteLine($"    ✗ {c.What}: 得到 {c.Got} 应为 {c.Want}");
    return ok;
}

/// <summary>
/// 无头验桌宠语音: 让 Speaker 真去读骨架旁边的 voice/_manifest.tsv, 再把每个表情连播「池大小+1」遍。
/// 多出的那一遍会撞上空队列并重洗, 所以「剩 n-1」同时验到了读包、挑句、一轮播完才重洗。会真出声。
/// </summary>
static int Voice(string[] args)
{
    if (args.Length < 1)
    {
        Console.Error.WriteLine("usage: bwp-animator-test voice <skel> [<skel2> ...]");
        return 2;
    }

    var type = typeof(TinyEngine.Speaker);
    var packsField = type.GetField("packs", BindingFlags.NonPublic | BindingFlags.Instance)!;
    var rotField = type.GetField("rotating", BindingFlags.NonPublic | BindingFlags.Instance)!;
    var speaker = new TinyEngine.Speaker();
    int bad = 0;

    foreach (var path in args)
    {
        var full = Path.GetFullPath(path);
        var dir = Path.GetDirectoryName(full)!;
        var tag = Path.GetFileName(dir);

        // 这个动画名对不上任何表情, 只用来把包读进缓存 —— 免得它混进下面「连播 n+1 遍」的计数里
        speaker.Say("_load_", full);
        var packs = (System.Collections.IDictionary)packsField.GetValue(speaker)!;
        if (!packs.Contains(dir))
        {
            Console.Error.WriteLine($"  FAIL: {tag} 的包没被缓存");
            bad++;
            continue;
        }

        var pool = (System.Collections.IDictionary)packs[dir]!;
        if (pool.Count == 0)
        {
            Console.WriteLine($"--- {tag}: 没有语音包, 全程静音(不算失败)");
            continue;
        }

        Console.WriteLine($"--- {tag}: {pool.Count} 个表情有句池 ---");
        var rot = (System.Collections.IDictionary)rotField.GetValue(speaker)!;
        int total = 0;
        foreach (var mood in pool.Keys.Cast<string>())
        {
            int n = ((System.Collections.ICollection)pool[mood]!).Count;
            total += n;
            for (int i = 0; i < n + 1; i++) speaker.Say(mood, full);
            int left = ((System.Collections.ICollection)rot[$"{full}|{mood}"]!).Count;
            Console.WriteLine($"  {mood}: {n} 句, 连播 {n + 1} 遍后队列剩 {left}" + (left == n - 1 ? "" : $" (应为 {n - 1})"));
            if (n == 0 || left != n - 1) bad++;
        }
        Console.WriteLine($"  合计 {total} 句");
    }

    speaker.Stop();
    Console.WriteLine(bad == 0 ? $"VOICE OK: {args.Length} 个骨架, 问题 0" : $"VOICE FAIL: {bad} 个问题");
    return bad == 0 ? 0 : 1;
}

/// <summary>
/// 无头验番茄钟: 时间源换成假时钟快进, 不用真等四小时。判四件事——
/// 整轮 4×(25+5)+15 的每个边界都换到预期那张脸、只有专注那 100 分钟不许睡、
/// 窗口藏着时 Update 一帧不跑也不丢时间(按挂钟逐段补, 一次只交最新那张脸)、开始/暂停/跳过/中止语义对得上。
/// 切脸走的是 PlayOnce, 所以这套判据跑起来会真出声。
/// </summary>
int Pomo(string[] skels)
{
    if (skels.Length < 1)
    {
        Console.Error.WriteLine("usage: bwp-animator-test pomodoro <skel> [<skel> ...]");
        return 2;
    }

    using var slot = new TinyEngine.SpineSlot(skels.Length);
    slot.Version = Spine.SpineVersion.V36;
    slot.AnimatorType = TinyEngine.AnimatorType.BwpHero;
    slot.UsePremultipliedAlpha = true;
    for (int i = 0; i < skels.Length; i++) slot.SetSpine(skels[i], i);
    slot.ActiveSlot = 0;

    var sp = SlotSpine(slot, 0);
    var t = ActionsType();
    var a = NewActions(t, sp.AnimationNames);
    var idle = Field(a, t, "Idle");
    var attack = Field(a, t, "Attack");
    var cast = Field(a, t, "Cast");
    var entrance = Field(a, t, "Entrance") ?? idle;
    Console.WriteLine($"脸谱: 开工={cast}  到点休息={attack}  回来/做完一整轮={entrance}  待机={idle}");

    int bad = 0;
    void Check(string label, bool ok, string got, string want)
    {
        Console.WriteLine($"  {(ok ? "✓" : "✗")} {label}: {got}" + (ok ? "" : $"  (应为 {want})"));
        if (!ok) bad++;
    }
    string Left(TinyEngine.Pomodoro p) => $"{p.Phase} 剩 {p.Remaining.TotalMinutes:0.#} 分";
    var Working = TinyEngine.PomodoroPhase.Working;
    var ShortBreak = TinyEngine.PomodoroPhase.ShortBreak;
    var LongBreak = TinyEngine.PomodoroPhase.LongBreak;
    var Off = TinyEngine.PomodoroPhase.Off;

    // —— 整一轮: 一秒一格推满 135 分钟, 边界换脸和「专注期间不许睡」一起判 ——
    var now = new DateTime(2026, 10, 29, 9, 0, 0);
    // 第二只钟: 只计「机器醒着」过了多久。这里由假挂钟推出来, 所以只动 now 就等于全程醒着(差值恒为 0);
    // 要模拟合盖就 Nap —— 挂钟和 slept 一起涨, 单调钟原地不动, 两者之差就是睡了多久
    var boot = now;
    TimeSpan slept = TimeSpan.Zero;
    TimeSpan Awake() => (now - boot) - slept;
    void Nap(TimeSpan away) { now = now.Add(away); slept += away; }
    var pomo = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    pomo.Start();
    Check("剩余就是整段", pomo.Remaining == TimeSpan.FromMinutes(25), Left(pomo), "Working 剩 25 分");
    pomo.Update(1f);    // 开始是应用线程下的命令, 脸要等渲染线程走一帧才换得上
    Check("开工就换沉思脸", sp.CurrentAnimation == cast, sp.CurrentAnimation, cast);

    var trace = new List<(int Min, TinyEngine.PomodoroPhase Phase, string Face)>();
    var sleepAt = new Dictionary<int, bool>();
    var roundAt = new Dictionary<int, int>();
    int last = pomo.TransitionId;
    for (int s = 0; s < 135 * 60; s++)
    {
        now = now.AddSeconds(1);
        pomo.Update(1f);
        if (pomo.TransitionId != last)
        {
            last = pomo.TransitionId;
            trace.Add((s / 60, pomo.Phase, sp.CurrentAnimation));
        }
        if (s % 60 == 30)
        {
            sleepAt[s / 60] = pomo.BlockingSleep;
            roundAt[s / 60] = pomo.WorkRoundNumber;
        }
        slot.Update(1f);
    }
    Console.WriteLine("  边界: " + string.Join("  ", trace.Select(x => $"{x.Min}m→{x.Phase}/{x.Face}")));
    var wantTrace = new (int, TinyEngine.PomodoroPhase, string)[]
    {
        (25, ShortBreak, attack), (30, Working, entrance), (55, ShortBreak, attack), (60, Working, entrance),
        (85, ShortBreak, attack), (90, Working, entrance), (115, LongBreak, entrance), (130, Working, entrance),
    };
    var traceOk = trace.Count == wantTrace.Length && trace.Zip(wantTrace).All(
        x => x.First.Min == x.Second.Item1 && x.First.Phase == x.Second.Item2 && x.First.Face == x.Second.Item3);
    Check("每个边界换对阶段也换对脸", traceOk, $"{trace.Count} 个边界", $"{wantTrace.Length} 个且逐个对得上");
    Check("做完一轮记了几个番茄", pomo.CompletedToday == 4, pomo.CompletedToday.ToString(), "4");
    bool SleepWants(int m) => m < 25 || m >= 130 || (m >= 30 && m < 55) || (m >= 60 && m < 85) || (m >= 90 && m < 115);
    var awakeBad = sleepAt.Where(kv => kv.Value != SleepWants(kv.Key)).Select(kv => $"{kv.Key}m={kv.Value}").ToArray();
    Check("只有四段专注顶掉入睡", awakeBad.Length == 0,
          awakeBad.Length == 0 ? $"105 个采样分钟全对" : string.Join(",", awakeBad), "工作段不许睡, 休息段该允许睡");
    // 轮内序号: 专注段念「这是第几段」, 休息段念「刚做完那一段是第几段」, 长假就是封顶那一档 4/4。
    // 长假之后是新的一轮, 所以第 130 分钟那个开工又回到 1/4 —— 不是接着数出 5 来
    int WantRound(int m) => m < 30 ? 1 : m < 60 ? 2 : m < 90 ? 3 : m < 130 ? 4 : 1;
    var roundBad = roundAt.Where(kv => kv.Value != WantRound(kv.Key)).Select(kv => $"{kv.Key}m={kv.Value}").ToArray();
    Check("整轮轮内序号逐分钟对得上", roundBad.Length == 0,
          roundBad.Length == 0 ? $"{roundAt.Count} 个采样分钟全对 (长假那格 {roundAt[120]}/4, 长假后回到 {roundAt[134]}/4)"
                               : string.Join(",", roundBad),
          "1、1、2、2、3、3、4、4(长假), 下一轮从 1 重新数");
    pomo.Abort();

    // —— 窗口藏着不跑帧: 欠了 60 分钟就按挂钟逐段补, 但一次只交最新那张脸 ——
    now = new DateTime(2026, 10, 29, 10, 0, 0);
    var hidden = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    hidden.Start();
    for (int m = 0; m < 30; m++) { now = now.AddMinutes(1); hidden.Update(60f); }
    var bumps = hidden.TransitionId;
    now = now.AddMinutes(60);
    hidden.Update(60f);
    bumps = hidden.TransitionId - bumps;
    Console.WriteLine($"  藏 60 分钟后一帧补完: {Left(hidden)}  今日 {hidden.CompletedToday}  补了 {bumps} 段  脸={sp.CurrentAnimation}");
    Check("补挂不丢时间(阶段)", hidden.Phase == ShortBreak, hidden.Phase.ToString(), "ShortBreak");
    Check("补挂不丢番茄(计数)", hidden.CompletedToday == 3, hidden.CompletedToday.ToString(), "3");
    Check("补挂只交一张脸", bumps == 4 && sp.CurrentAnimation == attack, $"{bumps} 段/脸 {sp.CurrentAnimation}", "4 段且脸是 attack");
    now = now.AddMinutes(1);
    hidden.Update(60f);
    Check("下一帧接回专注", hidden.Phase == Working && hidden.Remaining == TimeSpan.FromMinutes(24), Left(hidden), "Working 剩 24 分");
    hidden.Abort();

    // —— 控制项: 暂停冻住剩余、跳过只推进不记数、中止归位且不出声 ——
    now = new DateTime(2026, 10, 29, 12, 0, 0);
    var ctrl = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    ctrl.Start();
    now = now.AddMinutes(10);
    ctrl.Update(60f);
    ctrl.Pause();
    var left = ctrl.Remaining;
    now = now.AddMinutes(20);
    ctrl.Update(60f);
    Check("暂停后挂钟推着不走", ctrl.Remaining == left && ctrl.Phase == Working && !ctrl.BlockingSleep, Left(ctrl), "Working 剩 15 分, 可以睡");
    ctrl.Start();
    Check("再点开始就接上", ctrl.Remaining == left && ctrl.BlockingSleep, Left(ctrl), "接着跑 15 分, 不许睡");
    ctrl.Skip();
    ctrl.Update(60f);
    var skipFace = sp.CurrentAnimation;
    Check("跳过当段直接进休息", ctrl.Phase == ShortBreak && ctrl.Remaining == TimeSpan.FromMinutes(5) && !ctrl.BlockingSleep,
          Left(ctrl), "ShortBreak 剩 5 分, 可以睡");
    Check("跳过的那一段不算一个番茄", ctrl.CompletedToday == 0, ctrl.CompletedToday.ToString(), "0");
    Check("跳过照样往前走轮内位置", ctrl.WorkRoundNumber == 1 && ctrl.RoundsPerLongBreak == 4,
          $"{ctrl.WorkRoundNumber}/{ctrl.RoundsPerLongBreak}", "1/4");
    Check("跳过也换脸", skipFace == attack, skipFace, attack);
    var tid = ctrl.TransitionId;
    ctrl.Abort();
    ctrl.Update(60f);
    Check("中止归位且不再换脸", ctrl.Phase == Off && ctrl.Remaining == TimeSpan.Zero &&
                               ctrl.TransitionId == tid && sp.CurrentAnimation == skipFace,
          $"{ctrl.Phase} 剩 {ctrl.Remaining.TotalMinutes:0.#} 分 脸 {sp.CurrentAnimation}", "Off、脸不动");

    // 同一个位置两种走法: 自然跑满才记数, 跳过不记 —— 新语义的分界就判这一对
    now = new DateTime(2026, 10, 29, 15, 0, 0);
    var full = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    Check("自动开始默认按老规矩开着", full.AutoStartWork && full.AutoStartBreak,
          $"{full.AutoStartWork}/{full.AutoStartBreak}", "两个都 true(到点自己串下一段)");
    full.Start();
    now = now.AddMinutes(25).AddSeconds(1);
    full.Update(60f);
    Check("跑满一段才记一个", full.CompletedToday == 1 && full.Phase == ShortBreak && full.WorkRoundNumber == 1,
          $"{Left(full)} 今日 {full.CompletedToday} 轮内 {full.WorkRoundNumber}", "ShortBreak、今日 1、轮内 1/4");
    full.Abort();
    Check("中止不清今日计数", full.CompletedToday == 1, full.CompletedToday.ToString(), "1");
    full.Start();
    full.Update(60f);
    Check("中止后重新从第 1 段数", full.WorkRoundNumber == 1, $"{full.WorkRoundNumber}/4", "1/4");
    full.Abort();

    // —— 自动开始关着: 到点照样换脸、照样记数, 但下一段「装好不走」等用户点一下 ——
    now = new DateTime(2026, 10, 29, 18, 0, 0);
    var held = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake, AutoStartBreak = false };
    held.Start();
    var heldTid = held.TransitionId;
    now = now.AddMinutes(25).AddSeconds(1);
    held.Update(60f);
    Check("不自动接休息就停在待开始", held.Phase == ShortBreak && held.IsPaused &&
                                    held.Remaining == TimeSpan.FromMinutes(5) && held.CompletedToday == 1,
          $"{Left(held)} 今日 {held.CompletedToday}", "ShortBreak 剩整段 5 分、已暂停、仍记 1");
    Check("停住那一下照样换对脸", held.TransitionId == heldTid + 1 && sp.CurrentAnimation == attack,
          $"{held.TransitionId - heldTid} 次切换 脸 {sp.CurrentAnimation}", "换 1 次且是 attack");
    held.Start();
    Check("点一下就从整段开头接上", !held.IsPaused && held.Remaining == TimeSpan.FromMinutes(5), Left(held), "ShortBreak 剩 5 分且在走");
    held.AutoStartWork = false;
    now = now.AddMinutes(5).AddSeconds(1);
    held.Update(60f);
    Check("不自动开专注也停在待开始", held.Phase == Working && held.IsPaused &&
                                   held.Remaining == TimeSpan.FromMinutes(25) && !held.BlockingSleep &&
                                   sp.CurrentAnimation == entrance,
          $"{Left(held)} 脸 {sp.CurrentAnimation}", "Working 剩整段 25 分、已暂停、可以睡、脸是「回来」那张");
    held.Abort();

    // —— 跨零点: 今日归零, 暂停中的那段不会被补跑 ——
    now = new DateTime(2026, 10, 29, 22, 0, 0);
    var day = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    day.Start();
    now = now.AddMinutes(25).AddSeconds(1);     // 得自然跑满, 跳过不进计数(见上)
    day.Update(60f);
    day.Pause();
    day.Update(60f);
    Check("跨点前今日有数", day.CompletedToday == 1, day.CompletedToday.ToString(), "1");
    now = new DateTime(2026, 10, 30, 0, 5, 0);
    day.Update(60f);
    Check("过零点今日归零", day.CompletedToday == 0 && day.Phase == ShortBreak,
          $"今日 {day.CompletedToday} {Left(day)}", "今日 0 且仍停在 ShortBreak");
    day.Abort();

    // —— 专注段闭嘴: 换脸照旧但不配音; 「开工」和「到点」那两句是提醒, 必须还出得了声 ——
    // rotating 的键只在真抽到一句时才建, 所以「这句脸出过声没有」读得到, 不用竖着耳朵听
    var talker = new TinyEngine.Speaker();
    slot.Speaker = talker;
    var rotating = (System.Collections.IDictionary)typeof(TinyEngine.Speaker)
        .GetField("rotating", BindingFlags.NonPublic | BindingFlags.Instance)!.GetValue(talker)!;
    bool Spoken(string mood) => rotating.Keys.Cast<string>().Any(k => k.EndsWith($"|{mood}"));

    now = new DateTime(2026, 10, 30, 9, 0, 0);
    var quiet = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    quiet.Start();
    quiet.Update(1f);
    Check("开工那句还出声", Spoken(cast) && sp.CurrentAnimation == cast && slot.Muted,
          $"脸 {sp.CurrentAnimation} 出声 {Spoken(cast)} 已静音 {slot.Muted}", "thinking 出过声, 之后闭嘴");
    slot.HourlyChime();
    slot.Update(1f);
    Check("专注段里连报时都闭嘴", sp.CurrentAnimation == entrance && !Spoken(entrance),
          $"脸 {sp.CurrentAnimation} 出声 {Spoken(entrance)}", "脸照换但一句不抽");

    now = now.AddMinutes(25).AddSeconds(1);   // 补挂是「now > phaseEnd」, 正好压线不算过点
    quiet.Update(1f);
    Check("到点提醒没被上一段的静默吃掉", quiet.Phase == ShortBreak && sp.CurrentAnimation == attack && Spoken(attack) && !slot.Muted,
          $"{quiet.Phase} 脸 {sp.CurrentAnimation} 出声 {Spoken(attack)} 已静音 {slot.Muted}", "happy 出过声且不再静音");

    quiet.Abort();
    quiet.Update(1f);
    slot.HourlyChime();
    slot.Update(1f);
    Check("中止后彻底放开", !slot.Muted && Spoken(entrance), $"已静音 {slot.Muted} 出声 {Spoken(entrance)}", "不静音且抽得出句");
    slot.Speaker = null;

    // —— 休眠平移 deadline: 合盖六小时回来只停在原来那一段, 不许补出一串番茄 ——
    // 先确认这台机器上那只「只计工作状态」的钟真读得到: 读不到会静默退回挂钟, 上面几条照样全绿但功能等于没开。
    // 醒着的时间不该长过开机时间, 而退回值是公元 1 年起算的 tick —— 大得离谱, 一眼就能分开
    var win32 = typeof(TinyEngine.Pomodoro).Assembly.GetType("TinyEngine.Win32")!;
    var unbiased = (TimeSpan)win32.GetMethod("GetUnbiasedElapsedTime", BindingFlags.Public | BindingFlags.Static)!
        .Invoke(null, null)!;
    var uptime = TimeSpan.FromMilliseconds(Environment.TickCount64);
    Check("这台机器读得到工作状态钟", unbiased > TimeSpan.Zero && unbiased <= uptime,
          $"醒着 {unbiased.TotalHours:0.#} 小时 / 开机 {uptime.TotalHours:0.#} 小时", "醒着那段应小于等于开机时长且大于 0");

    now = new DateTime(2026, 10, 31, 9, 0, 0);
    var napped = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    napped.Start();
    for (int m = 0; m < 7; m++) { now = now.AddMinutes(1); napped.Update(1f); }
    Check("睡前往这一段里已经走掉 7 分钟", napped.Phase == Working && napped.Remaining == TimeSpan.FromMinutes(18), Left(napped), "Working 剩 18 分");
    var nappedTid = napped.TransitionId;
    Nap(TimeSpan.FromHours(6));      // 挂钟涨了六小时, 单调钟原地不动
    napped.Update(1f);
    Check("合盖六小时不补出一串番茄", napped.Phase == Working && napped.CompletedToday == 0 && napped.TransitionId == nappedTid,
          $"{napped.Phase} 今日 {napped.CompletedToday} 换了 {napped.TransitionId - nappedTid} 次脸", "还停在 Working、今日 0、一次脸都不换");
    Check("醒来剩下的还是睡前的 18 分钟", napped.Remaining == TimeSpan.FromMinutes(18), Left(napped), "Working 剩 18 分");
    now = now.AddMinutes(18).AddSeconds(1);
    napped.Update(1f);
    Check("醒来把剩下的跑完才算一个", napped.Phase == ShortBreak && napped.CompletedToday == 1,
          $"{napped.Phase} 今日 {napped.CompletedToday}", "ShortBreak 今日 1");

    // 暂停中那一段压根不吃时间, 所以睡觉不该去动冻住的剩余
    now = now.AddMinutes(2);
    napped.Update(1f);
    napped.Pause();
    var frozen = napped.Remaining;
    Nap(TimeSpan.FromHours(3));
    napped.Update(1f);
    Check("暂停里睡三小时也不动冻住的剩余", napped.Phase == ShortBreak && napped.Remaining == frozen,
          $"{napped.Phase} 剩 {napped.Remaining}", $"仍是暂停那一刻的 {frozen}");
    napped.Abort();

    // —— 挂钟被往回拨: 既不能说漏「剩一小时」, 也不能倒着数出负数 ——
    now = new DateTime(2026, 11, 2, 9, 0, 0);
    var rewound = new TinyEngine.Pomodoro { Target = slot, Clock = () => now, Mono = Awake };
    rewound.Start();
    now = now.AddMinutes(5);
    rewound.Update(1f);
    now = now.AddHours(-1);          // 改时区、NTP 对时、手动调表都会这样
    rewound.Update(1f);
    Check("表拨回去也不说漏一小时", rewound.Remaining == TimeSpan.FromMinutes(25), Left(rewound), "Working 剩 25 分(封顶在这一段本身)");
    now = now.AddMinutes(30);
    rewound.Update(1f);
    Check("拨回去以后仍按新表走, 不出负数", rewound.Phase == ShortBreak && rewound.Remaining == TimeSpan.Zero,
          Left(rewound), "ShortBreak 剩 0 分");
    rewound.Abort();

    Console.WriteLine(bad == 0 ? "POMODORO OK" : $"POMODORO FAIL: {bad} 项不符");
    return bad == 0 ? 0 : 1;
}

/// <summary>第 15 条要自己开一扇分层窗、读窗口矩形。TinyEngine 那个 Win32 是 internal 的，够不着，只能自己钉三个</summary>
internal static class Win32Probe
{
    public const int GWL_EXSTYLE = -20;
    public const int WS_EX_LAYERED = 0x80000;

    [System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern int GetWindowLong(IntPtr hWnd, int nIndex);

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
}

/// <summary>
/// 天气卡那层的假尺子。产品里 WidthFor 的 measure 是从外头递进来的: 真机用 GDI+ 量, 判据换这把
/// 「按字数乘字号」的尺, 才能把「板子该多宽」对成一串对得住的常数(真那把会随字体和 DPI 漂)。
/// 两档字各给一个格宽 —— 大号/正文要是读串了档, 量出来的宽就跟着串, 「谁是大号」这一格才抓得住
/// </summary>
internal static class HarnessRuler
{
    public const int HeroPerChar = 20;
    public const int BodyPerChar = 12;

    public static Size MeasureByChar<T>(T line)
    {
        var type = typeof(T);
        var text = (string)type.GetProperty("Text")!.GetValue(line)!;
        var hero = type.GetProperty("Face")!.GetValue(line)!.ToString() == "Hero";
        return new Size((hero ? HeroPerChar : BodyPerChar) * text.Length, hero ? 44 : 30);
    }
}
