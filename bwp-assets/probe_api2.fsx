open System
open System.Reflection
let flags = BindingFlags.Public ||| BindingFlags.NonPublic ||| BindingFlags.Instance ||| BindingFlags.Static ||| BindingFlags.DeclaredOnly
let asm = Assembly.LoadFrom(@"C:\Program Files\DeskSpine\SpineRuntime36.dll")
let show (n: string) =
    let t = asm.GetType("SpineRuntime36." + n)
    printfn "== %s : %s" t.Name t.BaseType.Name
    for p in t.GetProperties(flags) do printfn "   P %-22s %s" p.Name p.PropertyType.Name
    for f in t.GetFields flags do printfn "   F %-22s %s" f.Name f.FieldType.Name
    for m in t.GetMethods flags do
        if not m.IsSpecialName then printfn "   M %-22s -> %s (%s)" m.Name m.ReturnType.Name (String.Concat(",", [| for a in m.GetParameters() -> a.ParameterType.Name |]))
List.iter show ["AtlasPage"; "AtlasRegion"; "Skin"; "Animation"; "ExposedList`1"; "Attachment"; "RegionAttachment"; "MeshAttachment"; "SkeletonData"; "Timeline"; "DeformTimeline"; "AttachmentTimeline"]
