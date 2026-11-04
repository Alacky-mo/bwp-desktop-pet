#r @"C:\Program Files\DeskSpine\SpineRuntime36.dll"
open SpineRuntime36
type L() =
    interface TextureLoader with
        member _.Load(page: AtlasPage, path: string) = page.rendererObject <- box path
        member _.Unload(_t: obj) = ()
let asm = System.Reflection.Assembly.LoadFrom(@"C:\Program Files\DeskSpine\SpineRuntime36.dll")
for t in asm.GetTypes() |> Array.filter (fun t -> t.Name = "Timeline" || t.Name = "Atlas") do
    printfn "%s public=%b" t.FullName t.IsPublic
printfn "ok %A" (typeof<L>)
