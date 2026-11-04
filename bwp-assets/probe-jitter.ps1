# 摆位跳动的量尺（R5 用）：按秒采样桌宠进程每扇可见窗口的矩形，把「跳了一下」打成数字。
# 为什么要有它：面板和浮窗跟的是骨骼**当前姿势**的包围盒，换表情/换角色时那个盒会变，
# 窗口就可能当场挪一下。挪多少只有肉眼判得「碍事/无所谓」，但肉眼数不清跳了几次 —— 所以数交给我，判交给你。
#
# 两个坑（都在 click-at.ps1 那边踩过，这里同样防）：
#   1) PS 5.1 不认 DPI，GetWindowRect 读到的是「一半的数」（2560 宽读成 1280）。
#      这里第一件事就是 SetProcessDpiAwarenessContext(-4)，所以打印的**全是物理像素**。
#   2) 桌宠那三扇窗口都是常驻的（藏起来是 Hide，不是销毁），所以按句柄认人不会认错。
#
# 用法（默认盯 90 秒，200 ms 采一次，位移超过 2 px 才算跳）:
#   powershell -NoProfile -ExecutionPolicy Bypass -File probe-jitter.ps1
#   ... -Seconds 180 -EveryMs 100 -Min 6
# 跑的时候该做的动作写在 docs/番茄钟复验单.md 的 R5。

param([int]$Seconds = 90, [int]$EveryMs = 200, [int]$Min = 2)

Add-Type -Namespace Jit -Name W -MemberDefinition @'
[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct RECT { public int Left, Top, Right, Bottom; }

public delegate bool EnumProc(System.IntPtr h, System.IntPtr l);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool SetProcessDpiAwarenessContext(System.IntPtr v);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool EnumWindows(EnumProc p, System.IntPtr l);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern uint GetWindowThreadProcessId(System.IntPtr h, out uint pid);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool IsWindowVisible(System.IntPtr h);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool GetWindowRect(System.IntPtr h, out RECT r);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern int GetClassName(System.IntPtr h, System.Text.StringBuilder s, int n);
'@

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[void][Jit.W]::SetProcessDpiAwarenessContext([System.IntPtr](-4))

$targets = @(Get-Process BwpDesktopPet -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
if ($targets.Count -eq 0) { Write-Host '没找到 BwpDesktopPet 进程，先把桌宠起来再跑'; exit 1 }

# 一次采样：句柄 → 矩形（只收可见且非零大小的）。
# 累加器必须挂 $script: —— 回调是从非托管代码里调起来的，函数局部变量不一定够得着，
# 挂错的症状是「一声不吭什么都没采到」（check-pet-window.ps1 也是这么防的）
function Sample {
    $script:found = @{}
    $cb = [Jit.W+EnumProc] {
        param($h, $l)
        $pid2 = 0
        [void][Jit.W]::GetWindowThreadProcessId($h, [ref]$pid2)
        if ($targets -contains $pid2 -and [Jit.W]::IsWindowVisible($h)) {
            $r = New-Object Jit.W+RECT
            [void][Jit.W]::GetWindowRect($h, [ref]$r)
            if (($r.Right - $r.Left) -gt 0 -and ($r.Bottom - $r.Top) -gt 0) {
                $cls = New-Object System.Text.StringBuilder 256
                [void][Jit.W]::GetClassName($h, $cls, 256)
                $script:found[$h.ToInt64()] = [pscustomobject]@{
                    Class = $cls.ToString(); X = $r.Left; Y = $r.Top
                    W = ($r.Right - $r.Left); H = ($r.Bottom - $r.Top)
                }
            }
        }
        return $true
    }
    [void][Jit.W]::EnumWindows($cb, [IntPtr]::Zero)
    return $script:found
}

# 认人：句柄固定，但尺寸会变，所以名字在第一次见到时就钉死（宠物主窗是 SFML_Window，另两扇是 WinForms）
$name = @{}
function Label($h, $cur) {
    if (-not $name.ContainsKey($h)) {
        $n = if ($cur.Class -like '*SFML*') { '宠物主窗' }
             elseif ($cur.W -ge 1000) { '宠物主窗?' }
             else { "分层窗 $($cur.W)x$($cur.H)" }
        $name[$h] = $n
    }
    return $name[$h]
}

$prev = @{}
$moves = @{}
$starts = @{}
$clock = Get-Date
Write-Host ("盯 {0} 秒，每 {1} ms 采一次；位移 >= {2} 物理 px 算一次跳。Ctrl+C 随时中断，中断前已经打印的照样算数" -f $Seconds, $EveryMs, $Min)

$deadline = $clock.AddSeconds($Seconds)
while ((Get-Date) -lt $deadline) {
    $now = Sample
    $t = ('{0,6:0.0}s' -f ((Get-Date) - $clock).TotalSeconds)
    foreach ($h in $now.Keys) {
        $cur = $now[$h]
        $who = Label $h $cur
        if (-not $prev.ContainsKey($h)) {
            $starts[$h] = $cur
            Write-Host ("{0}  {1,-12} 出现  {2}x{3} @ {4},{5}" -f $t, $who, $cur.W, $cur.H, $cur.X, $cur.Y)
            $moves[$h] = 0
        } elseif ($cur.W -ne $prev[$h].W -or $cur.H -ne $prev[$h].H `
                 -or [Math]::Abs($cur.X - $prev[$h].X) -ge $Min -or [Math]::Abs($cur.Y - $prev[$h].Y) -ge $Min) {
            $p = $prev[$h]
            $dx = $cur.X - $p.X; $dy = $cur.Y - $p.Y
            $d = [Math]::Max([Math]::Abs($dx), [Math]::Abs($dy))
            $tag = if ($cur.W -ne $p.W -or $cur.H -ne $p.H) { '尺寸也变了' } else { '' }
            if ($d -ge $Min) {
                Write-Host ("{0}  {1,-12} 跳 {2,5} px  Δx={3,5} Δy={4,5}  ({5},{6})→({7},{8})  {9}x{10}→{11}x{12} {13}" -f `
                    $t, $who, $d, $dx, $dy, $p.X, $p.Y, $cur.X, $cur.Y, $p.W, $p.H, $cur.W, $cur.H, $tag)
                $moves[$h] = $moves[$h] + 1
            }
        }
        $prev[$h] = $cur
    }
    foreach ($h in @($prev.Keys)) {
        if (-not $now.ContainsKey($h)) {
            Write-Host ("{0}  {1,-12} 收起/没了" -f $t, (Label $h $prev[$h]))
            $prev.Remove($h) | Out-Null
        }
    }
    Start-Sleep -Milliseconds $EveryMs
}

Write-Host ''
Write-Host '== 小结（物理像素；要看逻辑像素自己除缩放，这台机器是 200%）=='
foreach ($h in $starts.Keys) {
    $s = $starts[$h]
    Write-Host ("  {0,-12} 起手 {1}x{2} @ {3},{4}   跳 {5} 次" -f (Label $h $s), $s.W, $s.H, $s.X, $s.Y, $moves[$h])
}
Write-Host '回我：哪一扇跳了、跳几次、最大那一下多少 px、当时你正在做什么（换表情/换角色/什么都没干）。'
