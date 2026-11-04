using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using SpineRuntime36;

namespace BwpProbe;

internal sealed class Quiet : TextureLoader
{
    public void Load(AtlasPage page, string path) => page.rendererObject = path;
    public void Unload(object texture) { }
}

internal sealed class Quiet38 : SpineRuntime38.TextureLoader
{
    public void Load(SpineRuntime38.AtlasPage page, string path) => page.rendererObject = path;
    public void Unload(object texture) { }
}

/// Census over the 3.8 runtime, to tell whether blobs the 3.6 reader rejects are newer exports.
internal sealed class Census38 : SpineRuntime38.AttachmentLoader
{
    private readonly SpineRuntime38.Atlas[] atlases;
    private readonly SpineRuntime38.AtlasAttachmentLoader inner;

    public Census38(SpineRuntime38.Atlas[] atlases)
    {
        this.atlases = atlases;
        inner = new SpineRuntime38.AtlasAttachmentLoader(atlases);
    }

    private bool Has(string name)
    {
        if (name == null) return false;
        foreach (var a in atlases)
            if (a.FindRegion(name) != null) return true;
        return false;
    }

    public SpineRuntime38.RegionAttachment NewRegionAttachment(SpineRuntime38.Skin s, string name, string path)
        => Has(path) ? inner.NewRegionAttachment(s, name, path) : new SpineRuntime38.RegionAttachment(name);
    public SpineRuntime38.MeshAttachment NewMeshAttachment(SpineRuntime38.Skin s, string name, string path)
        => Has(path) ? inner.NewMeshAttachment(s, name, path) : new SpineRuntime38.MeshAttachment(name);
    public SpineRuntime38.BoundingBoxAttachment NewBoundingBoxAttachment(SpineRuntime38.Skin s, string name)
        => Has(name) ? inner.NewBoundingBoxAttachment(s, name) : new SpineRuntime38.BoundingBoxAttachment(name);
    public SpineRuntime38.PathAttachment NewPathAttachment(SpineRuntime38.Skin s, string name)
        => Has(name) ? inner.NewPathAttachment(s, name) : new SpineRuntime38.PathAttachment(name);
    public SpineRuntime38.PointAttachment NewPointAttachment(SpineRuntime38.Skin s, string name)
        => Has(name) ? inner.NewPointAttachment(s, name) : new SpineRuntime38.PointAttachment(name);
    public SpineRuntime38.ClippingAttachment NewClippingAttachment(SpineRuntime38.Skin s, string name)
        => Has(name) ? inner.NewClippingAttachment(s, name) : new SpineRuntime38.ClippingAttachment(name);
}

/// Records every region an skeleton references, without needing the page textures.
/// Delegates to the real AtlasAttachmentLoader when the region exists somewhere in the package,
/// so nothing throws and the census is complete; otherwise a plain attachment stands in.
internal sealed class Census : AttachmentLoader
{
    private readonly Atlas[] atlases;
    private readonly AtlasAttachmentLoader inner;
    public readonly List<string> Regions = new();
    public readonly List<string> Missing = new();

    public Census(Atlas[] atlases)
    {
        this.atlases = atlases;
        inner = new AtlasAttachmentLoader(atlases);
    }

    private AtlasRegion Find(string name)
    {
        foreach (var a in atlases)
        {
            var r = a.FindRegion(name);
            if (r != null) return r;
        }
        return null;
    }

    private bool Has(string name)
    {
        if (name == null) return false;
        var hit = Find(name) != null;
        if (hit) { if (!Regions.Contains(name)) Regions.Add(name); }
        else if (!Missing.Contains(name)) Missing.Add(name);
        return hit;
    }

    public RegionAttachment NewRegionAttachment(Skin skin, string name, string path)
        => Has(path) ? inner.NewRegionAttachment(skin, name, path) : new RegionAttachment(name);

    public MeshAttachment NewMeshAttachment(Skin skin, string name, string path)
        => Has(path) ? inner.NewMeshAttachment(skin, name, path) : new MeshAttachment(name);

    public BoundingBoxAttachment NewBoundingBoxAttachment(Skin skin, string name)
        => Has(name) ? inner.NewBoundingBoxAttachment(skin, name) : new BoundingBoxAttachment(name);

    public PathAttachment NewPathAttachment(Skin skin, string name)
        => Has(name) ? inner.NewPathAttachment(skin, name) : new PathAttachment(name);

    public PointAttachment NewPointAttachment(Skin skin, string name)
        => Has(name) ? inner.NewPointAttachment(skin, name) : new PointAttachment(name);

    public ClippingAttachment NewClippingAttachment(Skin skin, string name)
        => Has(name) ? inner.NewClippingAttachment(skin, name) : new ClippingAttachment(name);
}

internal static class Program
{
    private const string Sep = "\t";
    private static readonly Quiet Loader = new();

    private static string F(float v) => v.ToString("0.###", CultureInfo.InvariantCulture);

    private static string Row(string file, SkeletonData sd, Census census, string err)
    {
        var anims = sd == null
            ? new List<string>()
            : sd.Animations.Select(a => a.Name + ":" + F(a.Duration)).ToList();
        var kinds = sd == null
            ? new List<string>()
            : sd.Animations.SelectMany(a => a.Timelines)
                .GroupBy(t => t.GetType().Name)
                .OrderByDescending(g => g.Count())
                .Select(g => g.Key + "x" + g.Count()).ToList();
        var skins = sd == null
            ? new List<string>()
            : sd.Skins.Select(s => s.Name).ToList();
        var cols = new List<string>
        {
            file,
            err ?? "ok",
            sd?.Version,
            sd?.Name,
            sd?.ImagesPath,
            sd?.Hash,
            sd == null ? null : F(sd.Fps),
            sd == null ? null : F(sd.Width) + "x" + F(sd.Height),
            sd == null ? "0" : sd.Bones.Count.ToString(),
            sd == null ? "0" : sd.Slots.Count.ToString(),
            sd == null ? "0" : skins.Count.ToString(),
            sd == null ? "0" : anims.Count.ToString(),
            sd == null ? "0" : sd.Events.Count.ToString(),
            sd == null ? "0" : sd.IkConstraints.Count.ToString(),
            sd == null ? "0" : sd.PathConstraints.Count.ToString(),
            sd == null ? "0" : sd.TransformConstraints.Count.ToString(),
            string.Join(";", skins),
            string.Join(";", anims),
            string.Join(";", kinds),
            census == null ? "" : string.Join(";", census.Regions),
            census == null ? "" : string.Join(";", census.Missing),
        };
        return string.Join(Sep, cols.Select(c => (c ?? "").Replace("\t", " ").Replace("\n", " ")));
    }

    private static int Main(string[] args)
    {
        if (args.Length < 1)
        {
            Console.Error.WriteLine("usage: bwp-probe census <dumpDir> <out.tsv> | strict <modelRoot> [out.tsv] | peek <skel> <atlas>");
            return 2;
        }
        switch (args[0])
        {
            case "census": return Census_(args[1], args[2]);
            case "try38": return Try38(args[1]);
            case "colors": return Colors(args[1]);
            case "blend": return Blend(args[1]);
            case "strict": return Strict(args[1], args.Length > 2 ? args[2] : null);
            case "peek": return Peek(args[1], args[2]);
            case "slots": return Slots(args[1], args[2]);
            case "slotkeys": return SlotKeys(args[1], args[2], args.Skip(3).ToArray());
            default: return 2;
        }
    }

    private static Atlas[] LoadAtlases(string dir)
    {
        var list = new List<Atlas>();
        foreach (var path in Directory.GetFiles(dir, "*.atlas").Concat(Directory.GetFiles(dir, "*.txt")).Distinct())
        {
            try { list.Add(new Atlas(path, Loader)); }
            catch (Exception e) { Console.Error.WriteLine($"  atlas {Path.GetFileName(path)}: {e.Message}"); }
        }
        return list.ToArray();
    }

    private static int Census_(string dumpDir, string outTsv)
    {
        var atlases = LoadAtlases(dumpDir);
        Console.Error.WriteLine($"{atlases.Length} atlases parsed from {dumpDir}");
        var heads = new[]
        {
            "skel", "err", "version", "skel_name", "images_path", "hash", "fps", "size", "bones", "slots", "skins", "anims", "events",
            "ik", "pathc", "transformc", "skin_names", "animations", "timeline_kinds", "regions", "missing_regions"
        };
        var sb = new StringBuilder(string.Join(Sep, heads) + "\n");
        var files = Directory.GetFiles(dumpDir, "*.bin").Concat(Directory.GetFiles(dumpDir, "*.skel")).ToArray();
        int ok = 0, bad = 0;
        for (int i = 0; i < files.Length; i++)
        {
            var f = files[i];
            var census = new Census(atlases);
            SkeletonData sd = null;
            string err = null;
            try
            {
                sd = new SkeletonBinary((AttachmentLoader)census).ReadSkeletonData(f);
                ok++;
            }
            catch (Exception e)
            {
                err = e.GetType().Name + ": " + e.Message.Split('\n')[0];
                bad++;
            }
            sb.Append(Row(Path.GetFileName(f), sd, census, err)).Append('\n');
            if ((i + 1) % 50 == 0) Console.Error.Write($"\r  {i + 1}/{files.Length} ({bad} not skeletons/anomalies)");
        }
        Console.Error.WriteLine();
        File.WriteAllText(outTsv, sb.ToString(), new UTF8Encoding(false));
        Console.WriteLine($"census: {ok} skeletons, {bad} rejected -> {outTsv}");
        return 0;
    }

    private static int Try38(string dumpDir)
    {
        var atlases = new List<SpineRuntime38.Atlas>();
        foreach (var path in Directory.GetFiles(dumpDir, "*.atlas"))
            try { atlases.Add(new SpineRuntime38.Atlas(path, new Quiet38())); } catch { }
        Console.Error.WriteLine($"3.8 runtime: {atlases.Count} atlases parsed");
        foreach (var f in Directory.GetFiles(dumpDir, "*.bin"))
        {
            string info;
            try
            {
                var sd = new SpineRuntime38.SkeletonBinary(
                    (SpineRuntime38.AttachmentLoader)new Census38(atlases.ToArray())).ReadSkeletonData(f);
                info = $"OK v{sd.Version} bones={sd.Bones.Count} slots={sd.Slots.Count} " +
                       $"anims=[{string.Join(",", sd.Animations.Select(a => a.Name))}]";
            }
            catch (Exception e)
            {
                info = e.GetType().Name + ": " + e.Message.Split('\n')[0];
            }
            Console.WriteLine($"{Path.GetFileName(f)}\t{info}");
        }
        return 0;
    }

    /// Setup-pose slot colours vs the colours ColorTimelines actually animate to.
    private static int Colors(string dumpDir)
    {
        var atlases = LoadAtlases(dumpDir);
        var setup = new Dictionary<string, int>();
        var keys = new Dictionary<string, int>();
        int slots = 0, tinted = 0, warm = 0, cool = 0, white = 0;
        bool diag = true;
        foreach (var f in Directory.GetFiles(dumpDir, "*.bin"))
        {
            SkeletonData sd;
            try { sd = new SkeletonBinary((AttachmentLoader)new Census(atlases)).ReadSkeletonData(f); }
            catch { continue; }
            foreach (var s in sd.Slots)
            {
                slots++;
                if (s.R > 0.98f && s.G > 0.98f && s.B > 0.98f) { white++; continue; }
                tinted++;
                setup[Bucket(s.R, s.G, s.B)] = setup.GetValueOrDefault(Bucket(s.R, s.G, s.B)) + 1;
            }
            foreach (var a in sd.Animations)
                foreach (var t in a.Timelines)
                    if (t is ColorTimeline ct)
                    {
                        var fr = ct.Frames;
                        int stride = fr.Length / Math.Max(1, ct.FrameCount);
                        if (diag)
                        {
                            Console.WriteLine("  diag FrameCount=" + ct.FrameCount + " len=" + fr.Length +
                                              " stride=" + stride + " first=" +
                                              string.Join(" ", fr.Take(stride * 2).Select(x => x.ToString("0.###"))));
                            diag = false;
                        }
                        for (int i = 0; i + stride <= fr.Length; i += stride)
                        {
                            float r = fr[i + 1], g = fr[i + 2], b = fr[i + 3];
                            if (r > 0.98f && g > 0.98f && b > 0.98f) { white++; continue; }
                            keys[Bucket(r, g, b)] = keys.GetValueOrDefault(Bucket(r, g, b)) + 1;
                            if (r > b + 0.04f) warm++; else if (b > r + 0.04f) cool++;
                        }
                    }
        }
        Console.WriteLine($"{dumpDir}: slots={slots} setupTinted={tinted} whiteKeys+whiteSetup={white} " +
                          $"animated colour keys: warm={warm} cool={cool}  ({100.0 * warm / Math.Max(1, warm + cool):0}% warm)");
        Console.WriteLine("  top setup slot colours      " + Top(setup));
        Console.WriteLine("  top animated colour keys   " + Top(keys));
        return 0;
    }

    /// How many slots are drawn with a non-normal (additive-ish) blend mode.
    private static int Blend(string dumpDir)
    {
        var atlases = LoadAtlases(dumpDir);
        var kinds = new Dictionary<string, int>();
        int skels = 0, withNonNormal = 0, slots = 0, nonNormal = 0;
        foreach (var f in Directory.GetFiles(dumpDir, "*.bin"))
        {
            SkeletonData sd;
            try { sd = new SkeletonBinary((AttachmentLoader)new Census(atlases)).ReadSkeletonData(f); }
            catch { continue; }
            skels++;
            bool seen = false;
            foreach (var s in sd.Slots)
            {
                slots++;
                string k = s.BlendMode.ToString();
                kinds[k] = kinds.GetValueOrDefault(k) + 1;
                if (k != "Normal") { nonNormal++; seen = true; }
            }
            if (seen) withNonNormal++;
        }
        Console.WriteLine($"{dumpDir}: skels={skels} containing non-normal blend={withNonNormal}  " +
                          $"slots={slots} nonNormal={nonNormal} ({100.0 * nonNormal / Math.Max(1, slots):0.0}%)");
        Console.WriteLine("  blend modes " + Top(kinds));
        return 0;
    }

    private static string Bucket(float r, float g, float b) =>
        $"{(int)(r * 4) * 64},{(int)(g * 4) * 64},{(int)(b * 4) * 64}";

    private static string Top(Dictionary<string, int> d) =>
        string.Join("  ", d.OrderByDescending(kv => kv.Value).Take(6)
            .Select(kv => $"rgb({kv.Key})x{kv.Value}"));

    private static int Peek(string skel, string atlas)
    {
        var a = new Atlas(atlas, Loader);
        var sd = new SkeletonBinary(new[] { a }).ReadSkeletonData(skel);
        Report(sd);
        PlayAll(sd);
        return 0;
    }

    private static void Report(SkeletonData sd)
    {
        Console.WriteLine($"  version={sd.Version} fps={F(sd.Fps)} size={F(sd.Width)}x{F(sd.Height)} " +
                          $"bones={sd.Bones.Count} slots={sd.Slots.Count} skins={sd.Skins.Count} anims={sd.Animations.Count}");
        foreach (var a in sd.Animations)
            Console.WriteLine($"    {a.Name,-28} {F(a.Duration),6}s  " +
                              string.Join(",", a.Timelines.Select(t => t.GetType().Name).Distinct()));
    }

    /// Drives every animation through AnimationState the way DeskSpine does; throws on broken data.
    private static int PlayAll(SkeletonData sd)
    {
        var skel = new Skeleton(sd);
        var data = new AnimationStateData(sd) { DefaultMix = 0f };
        int fail = 0;
        foreach (var a in sd.Animations)
        {
            try
            {
                var state = new AnimationState(data);
                state.SetAnimation(0, a.Name, true);
                float step = 1f / 30f, t = 0f;
                while (t < Math.Max(a.Duration, 0.05f))
                {
                    state.Update(step);
                    state.Apply(skel);
                    skel.UpdateWorldTransform();
                    t += step;
                }
            }
            catch (Exception e)
            {
                fail++;
                Console.WriteLine($"    !! {a.Name}: {e.GetType().Name}: {e.Message}");
            }
        }
        return fail;
    }

    /// Draw-order dump of every slot: blend, setup colour, and the regions it can show.
    /// Answers "what is that bright thing behind the character" without guessing.
    private static int Slots(string skel, string atlasPath)
    {
        var a = new Atlas(atlasPath, Loader);
        var sd = new SkeletonBinary(new[] { a }).ReadSkeletonData(skel);

        var perSlot = new Dictionary<int, List<(string att, string region, float w, float h)>>();
        foreach (var skin in sd.Skins)
            foreach (var kv in skin.Attachments)
            {
                string region = kv.Value switch
                {
                    RegionAttachment r => r.Path,
                    MeshAttachment m => m.Path,
                    _ => null
                };
                float w = kv.Value switch
                {
                    RegionAttachment r => r.Width,
                    MeshAttachment m => m.Width,
                    _ => 0f
                };
                float h = kv.Value switch
                {
                    RegionAttachment r => r.Height,
                    MeshAttachment m => m.Height,
                    _ => 0f
                };
                if (!perSlot.TryGetValue(kv.Key.slotIndex, out var list))
                    perSlot[kv.Key.slotIndex] = list = new List<(string, string, float, float)>();
                if (!list.Any(e => e.att == kv.Key.name))
                    list.Add((kv.Key.name, region ?? kv.Key.name, w, h));
            }

        Console.WriteLine($"# {Path.GetFileName(skel)}  slots={sd.Slots.Count} skins={sd.Skins.Count}");
        Console.WriteLine("idx  slot  bone  blend  setupRGBA  attachments(region WxH)");
        foreach (var s in sd.Slots.OrderBy(x => x.Index))
        {
            var atts = perSlot.TryGetValue(s.Index, out var l)
                ? string.Join(", ", l.Select(e =>
                    $"{e.att}->{e.region} {F(e.w)}x{F(e.h)}"))
                : "(none)";
            var col = $"{F(s.R)}{F(s.G)}{F(s.B)}{F(s.A)}";
            Console.WriteLine($"{s.Index,3}  {s.Name,-22} {s.BoneData.Name,-16} {s.BlendMode,-8} {col,-10} {atts}");
        }
        return 0;
    }

    /// Per-animation keyframe summary for the named slots: does the layer stay visible,
    /// how much alpha does it carry, and is its bone chain being moved.
    private static int SlotKeys(string skel, string atlasPath, string[] names)
    {
        var a = new Atlas(atlasPath, Loader);
        var sd = new SkeletonBinary(new[] { a }).ReadSkeletonData(skel);
        var boneName = new Dictionary<int, string>();
        for (int i = 0; i < sd.Bones.Count; i++) boneName[i] = sd.Bones.Items[i].Name;
        foreach (var raw in names)
        {
            var s = sd.Slots.FirstOrDefault(x => x.Name.StartsWith(raw, StringComparison.OrdinalIgnoreCase));
            if (s == null) { Console.WriteLine($"# {raw}: no such slot"); continue; }
            var chain = new HashSet<string>();
            for (var b = s.BoneData; b != null; b = b.Parent) chain.Add(b.Name);
            Console.WriteLine($"slot {s.Name} bone={s.BoneData.Name} blend={s.BlendMode} " +
                              $"setup={s.AttachmentName ?? "-"} chain={string.Join("<", chain)}");
            foreach (var an in sd.Animations)
            {
                var bits = new List<string>();
                foreach (var t in an.Timelines)
                    switch (t)
                    {
                        case ColorTimeline ct when ct.SlotIndex == s.Index:
                        {
                            int stride = ct.Frames.Length / Math.Max(1, ct.FrameCount);
                            var keys = Enumerable.Range(0, ct.FrameCount)
                                .Select(i => new[] { ct.Frames[i * stride + 1], ct.Frames[i * stride + 2],
                                                     ct.Frames[i * stride + 3], ct.Frames[i * stride + 4] }).ToList();
                            bits.Add($"colour n={ct.FrameCount} alpha {keys.Min(k => k[3]):0.00}-{keys.Max(k => k[3]):0.00} " +
                                     $"rgb {string.Join("/", keys.Select(k => $"{k[0]:0.00}-{k[1]:0.00}-{k[2]:0.00}").Distinct())}");
                            break;
                        }
                        case AttachmentTimeline at when at.SlotIndex == s.Index:
                            bits.Add($"attach [{string.Join(",", at.AttachmentNames.Select(x => x ?? "null").Distinct())}]");
                            break;
                    }
                var moved = an.Timelines.OfType<Timeline>()
                    .Where(t => t is RotateTimeline or TranslateTimeline or ScaleTimeline or ShearTimeline)
                    .Select(t => t switch
                    {
                        RotateTimeline r => boneName[r.BoneIndex],
                        TranslateTimeline r => boneName[r.BoneIndex],   // also covers Scale and Shear
                        _ => null
                    })
                    .Where(n => n != null && chain.Contains(n)).Distinct().ToList();
                Console.WriteLine($"  {an.Name,-14} {(moved.Any() ? "bones:" + string.Join(",", moved) + "  " : "")}" +
                                  $"{(bits.Any() ? string.Join("  ", bits) : "no key on this slot")}");
            }
        }
        return 0;
    }

    private static int Strict(string modelRoot, string outTsv)

    {
        var heads = new[] { "model", "skel", "version", "anims", "min", "max", "total_s", "animations", "play_failures", "error" };
        var sb = new StringBuilder(string.Join(Sep, heads) + "\n");
        var dirs = Directory.GetDirectories(modelRoot);
        int good = 0, bad = 0;
        foreach (var dir in dirs)
        {
            var skelFiles = Directory.GetFiles(dir, "*.skel");
            var atlasFiles = Directory.GetFiles(dir, "*.atlas");
            if (skelFiles.Length == 0 || atlasFiles.Length == 0) continue;
            var name = Path.GetFileName(dir);
            string err = null;
            SkeletonData sd = null;
            int fail = 0;
            try
            {
                var a = new Atlas(atlasFiles[0], Loader);
                sd = new SkeletonBinary(new[] { a }).ReadSkeletonData(skelFiles[0]);
                fail = PlayAll(sd);
                good++;
            }
            catch (Exception e)
            {
                err = e.GetType().Name + ": " + e.Message.Split('\n')[0];
                bad++;
            }
            if (sd != null)
            {
                var ds = sd.Animations.Select(x => x.Duration).ToList();
                sb.Append(string.Join(Sep, new[]
                {
                    name, Path.GetFileName(skelFiles[0]), sd.Version, sd.Animations.Count.ToString(),
                    F(ds.Min()), F(ds.Max()), F(ds.Sum()),
                    string.Join(";", sd.Animations.Select(x => x.Name + ":" + F(x.Duration))),
                    fail.ToString(), ""
                })).Append('\n');
            }
            else sb.Append(string.Join(Sep, new[] { name, Path.GetFileName(skelFiles[0]), "", "0", "", "", "", "", "", err })).Append('\n');
        }
        Console.WriteLine($"strict: {good} models load and play, {bad} broken  ({outTsv})");
        if (outTsv != null) File.WriteAllText(outTsv, sb.ToString(), new UTF8Encoding(false));
        return 0;
    }
}
