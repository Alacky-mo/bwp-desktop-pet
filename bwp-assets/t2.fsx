#r @"C:\Program Files\DeskSpine\SpineRuntime36.dll"
open SpineRuntime36
open System.Reflection
let dump (t: System.Type) =
    printfn "== %s" t.Name
    for p in t.GetProperties(BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.DeclaredOnly) do printfn "   P %s : %s" p.Name p.PropertyType.Name
    for f in t.GetFields(BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.DeclaredOnly) do printfn "   F %s : %s" f.Name f.FieldType.Name
    for m in t.GetMethods(BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.DeclaredOnly) do
        if not m.IsSpecialName then printfn "   M %s(%s)" m.Name (System.String.Concat(",", [| for a in m.GetParameters() -> a.ParameterType.Name |]))
dump (typeof<Atlas>); dump (typeof<AttachmentTimeline>); dump (typeof<SkeletonData>); dump (typeof<SlotData>); dump (typeof<BoneData>)
