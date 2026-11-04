open System
open System.Reflection
let asm = Assembly.LoadFrom(@"C:\Program Files\DeskSpine\SpineRuntime36.dll")
let show n =
    let t = asm.GetType("SpineRuntime36." + n)
    printfn "== %s" t.FullName
    for m in t.GetMethods(BindingFlags.Public ||| BindingFlags.Instance ||| BindingFlags.Static ||| BindingFlags.DeclaredOnly) do
        printfn "   %s %s(%s)" m.ReturnType.Name m.Name (String.Concat(", ", [| for p in m.GetParameters() -> p.ParameterType.Name + " " + p.Name |]))
    for c in t.GetConstructors() do
        printfn "   .ctor(%s)" (String.Concat(", ", [| for p in c.GetParameters() -> p.ParameterType.Name + " " + p.Name |]))
    for p in t.GetProperties() do printfn "   prop %s %s" p.PropertyType.Name p.Name
    for f in t.GetFields() do printfn "   field %s %s" f.FieldType.Name f.Name
show "TextureLoader"; show "Atlas"; show "SkeletonBinary"; show "SkeletonData"; show "Animation"
