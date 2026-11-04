open System
open System.Reflection
let asm = Assembly.LoadFrom(@"C:\Program Files\DeskSpine\SpineRuntime36.dll")
printfn "assembly: %s" asm.FullName
let types = asm.GetExportedTypes() |> Array.sortBy (fun t -> t.FullName)
printfn "public types: %d" types.Length
for t in types do printfn "  %s" t.FullName
