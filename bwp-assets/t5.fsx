#r @"C:\Program Files\DeskSpine\SpineRuntime36.dll"
open SpineRuntime36
open System
open System.Reflection
let psig (c: MethodBase) = String.Join(", ", Array.map (fun (a: ParameterInfo) -> a.ParameterType.Name + " " + a.Name) (c.GetParameters()))
for t in [typeof<AttachmentLoader>; typeof<AtlasAttachmentLoader>; typeof<SkeletonBinary>] do
    printfn "== %s" t.FullName
    for m in t.GetMethods(BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.DeclaredOnly) do printfn "   %s %s(%s)" m.ReturnType.Name m.Name (psig m)
    for c in t.GetConstructors() do printfn "   .ctor(%s)" (psig c)
