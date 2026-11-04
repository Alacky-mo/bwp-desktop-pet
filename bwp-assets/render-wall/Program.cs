using System.Text;
using SFML.Graphics;
using SFML.System;

// Renders thumbnails of packed models so characters can be told apart without loading each one
// into DeskSpine by hand.
// usage: bwp-render-wall <modelRoot> <outDir> [viewHeight=1600] [seconds=0.6] [anims=first|all] [target=2048]
// anims=all writes one <model>@<animation>.png per animation, which is how the emotion rigs are
// compared side by side. If <modelRoot>/_frame.tsv exists ("stem  w  h", tab separated) each model
// is framed to its own canvas instead of the shared viewHeight, so a 112-unit chat head is not
// rendered at 1/20th scale inside a view sized for a 3000-unit battle stage.

Console.OutputEncoding = Encoding.UTF8;
if (args.Length < 2)
{
    Console.Error.WriteLine("usage: bwp-render-wall <modelRoot> <outDir> [viewHeight] [seconds] [anims] [target]");
    return 2;
}

string root = args[0], outDir = args[1];
float viewHeight = args.Length > 2 ? float.Parse(args[2]) : 1600f;
float seconds = args.Length > 3 ? float.Parse(args[3]) : 0.6f;
bool allAnims = args.Length > 4 && args[4] == "all";
int targetPx = args.Length > 5 ? int.Parse(args[5]) : 2048;
Directory.CreateDirectory(outDir);

var frames = new Dictionary<string, (float w, float h)>();
string frameTsv = Path.Combine(root, "_frame.tsv");
if (File.Exists(frameTsv))
    foreach (var line in File.ReadAllLines(frameTsv))
    {
        var c = line.Split('\t');
        if (c.Length >= 3 && float.TryParse(c[1], out float w) && float.TryParse(c[2], out float h))
            frames[c[0]] = (w, h);
    }

// Same scene-layer filter BwpHero installs: the battle backdrops and the big neutral-white
// additive glow would otherwise fill the frame and hide who the character is.
(string Prefix, float Alpha)[] sceneLayers =
[
    ("beijing", 0f), ("qianjing", 0f), ("bj", 0f), ("bg", 0f), ("guang", 0.25f),
];
string[] preferred = ["idle1", "idle", "battlestand", "born_break", "born"];

var target = new RenderTexture((uint)targetPx, (uint)targetPx, false);
var view = new View();
view.Center = new Vector2f(0, 30);
view.Size = new Vector2f(viewHeight, -viewHeight);   // SFML window y is down, Spine y is up

var report = new StringBuilder("model\tanimation\tduration\terror\n");
int ok = 0, failed = 0, dirs = Directory.GetDirectories(root).Length;
foreach (var dir in Directory.GetDirectories(root).OrderBy(x => x))
{
    var skel = Directory.GetFiles(dir, "*.skel").FirstOrDefault();
    var atlas = Directory.GetFiles(dir, "*.atlas").FirstOrDefault();
    if (skel is null || atlas is null) continue;
    string name = Path.GetFileName(dir);

    if (frames.TryGetValue(name, out var f))
    {
        float vh = MathF.Max(f.w, f.h) * 1.35f;
        view.Center = new Vector2f(0, f.h * 0.5f);
        view.Size = new Vector2f(vh, -vh);
    }
    else if (view.Size.X != viewHeight)
    {
        view.Center = new Vector2f(0, 30);
        view.Size = new Vector2f(viewHeight, -viewHeight);
    }

    try
    {
        using var spine = Spine.Spine.New(Spine.SpineVersion.V36, skel, atlas, defaultMix: 0.15f);
        foreach (var (prefix, alpha) in sceneLayers) spine.SlotAlphaScale[prefix] = alpha;
        spine.UsePremultipliedAlpha = true;

        IEnumerable<string> todo = allAnims ? spine.AnimationNames
            : new[] { preferred.FirstOrDefault(spine.AnimationNames.Contains) ?? spine.AnimationNames[0] };
        foreach (string anim in todo)
        {
            spine.CurrentAnimation = anim;
            for (int i = 0; i < (int)(seconds * 60); i++) spine.Update(1f / 60f);
            target.Clear(new Color(0, 0, 0, 0));
            target.SetView(view);
            spine.Draw(target, RenderStates.Default);
            target.Display();
            using var image = target.Texture.CopyToImage();
            image.SaveToFile(Path.Combine(outDir, allAnims ? $"{name}@{anim}.png" : name + ".png"));
            ok++;
            report.Append($"{name}\t{anim}\t{spine.GetAnimationDuration(anim):0.00}\t\n");
        }
    }
    catch (Exception e)
    {
        failed++;
        report.Append($"{name}\t\t\t{e.GetType().Name}: {e.Message.Split('\n')[0]}\n");
    }
    if ((ok + failed) % 50 == 0) Console.Error.WriteLine($"  {ok + failed}/{dirs}");
}

File.WriteAllText(Path.Combine(outDir, "_wall.tsv"), report.ToString(), new UTF8Encoding(false));
Console.WriteLine($"rendered {ok} thumbnails, {failed} failed -> {outDir}");
return 0;
