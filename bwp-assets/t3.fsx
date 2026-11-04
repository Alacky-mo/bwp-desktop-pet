#r @"C:\Program Files\DeskSpine\SpineRuntime36.dll"
open SpineRuntime36
open System.Reflection
let f = BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.DeclaredOnly
let dump (t: System.Type) =
    printfn "== %s" t.FullName
    for c in t.GetConstructors() do printfn "   .ctor(%s)" (System.String.Concat(", ", [| for a in c.GetParameters() -> a.ParameterType.Name |]))
    for m in t.GetMethods(f) do
        if not m.IsSpecialName then printfn "   M %s(%s) -> %s" m.Name (System.String.Concat(", ", [| for a in m.GetParameters() -> a.ParameterType.Name |])) m.ReturnType.Name
List.iter dump [typeof<Skeleton>; typeof<Animation>; typeof<Skin>; typeof<SkeletonBinary>]
for e in [typeof<MixPose>; typeof<MixDirection>] do
    printfn "== %s : %A" e.FullName (System.Enum.GetNames e)
