open System
open System.Reflection
let asm = Assembly.LoadFrom(@"C:\Program Files\DeskSpine\SpineRuntime38.dll")
printfn "assembly %s" asm.FullName
for t in asm.GetExportedTypes() |> Array.filter (fun t -> t.Name = "SkeletonBinary" || t.Name = "TextureLoader" || t.Name="Atlas") do
    printfn "== %s" t.FullName
    for m in t.GetMethods(BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.Static ||| BindingFlags.DeclaredOnly) do printfn "   M %s arity=%d" m.Name (m.GetParameters().Length)
    for c in t.GetConstructors() do printfn "   .ctor arity=%d" (c.GetParameters().Length)
    for f in t.GetFields(BindingFlags.Public ||| BindingFlags.Instance) do printfn "   F %s" f.Name
