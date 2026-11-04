#r @"C:\Program Files\DeskSpine\SpineRuntime36.dll"
open SpineRuntime36
open System
open System.Reflection
let psig (m: MethodInfo) = String.Join(", ", Array.map (fun (a: ParameterInfo) -> sprintf "%s %s" a.ParameterType.Name a.Name) m.GetParameters())
let dump (t: Type) (pick: string -> bool) =
    printfn "== %s" t.Name
    for c in t.GetConstructors() do printfn "   .ctor(%s)" (psig c)
    for m in t.GetMethods(BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.DeclaredOnly) do
        if pick m.Name then printfn "   %s(%s) -> %s" m.Name (psig m) m.ReturnType.Name
dump typeof<Animation> (fun n -> n = "Apply")
dump typeof<Skeleton> (fun n -> true)
dump typeof<SkeletonBinary> (fun n -> true)
dump typeof<Atlas> (fun n -> true)
dump typeof<Skin> (fun n -> true)
