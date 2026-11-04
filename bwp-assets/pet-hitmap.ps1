# 抓不了屏的时候用 WindowFromPoint「摸」出宠物身上能点的那块 —— 分层窗按逐像素 alpha 命中，
# 透明处 WindowFromPoint 根本不给这扇窗，所以扫出来的就是真能点到的剪影。
# 为什么需要它：宠物窗是一扇 2560x1599 的大透明窗，光看窗口矩形完全不知道身子在哪，
# 而右键要点中「不透明的那块」才开得出预设小窗（R6 全靠那扇窗）。
# 只读：不点任何东西、不挪鼠标。
#
# 用法: powershell -NoProfile -ExecutionPolicy Bypass -File ./pet-hitmap.ps1 [-Step 12] [-Preview 60]

param([int]$Step = 12, [int]$Preview = 60)

Add-Type -Namespace Pet -Name W -MemberDefinition @'
[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct RECT { public int Left, Top, Right, Bottom; }

// 别用 System.Drawing.Point —— PS 5.1 的 Add-Type 默认不引 System.Drawing，会编不过
[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct POINT { public int X; public int Y; }

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

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern System.IntPtr WindowFromPoint(POINT p);
'@

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[void][Pet.W]::SetProcessDpiAwarenessContext([System.IntPtr](-4))

$ids = @(Get-Process BwpDesktopPet -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
if ($ids.Count -eq 0) { Write-Host '没找到 BwpDesktopPet 进程'; exit 1 }

# 找出那扇最大的可见窗（= 宠物主窗 SFML_Window）
$script:pet = $null
$cb = [Pet.W+EnumProc] {
    param($h, $l)
    $p = 0
    [void][Pet.W]::GetWindowThreadProcessId($h, [ref]$p)
    if ($ids -contains $p -and [Pet.W]::IsWindowVisible($h)) {
        $r = New-Object Pet.W+RECT
        [void][Pet.W]::GetWindowRect($h, [ref]$r)
        $c = New-Object System.Text.StringBuilder 256
        [void][Pet.W]::GetClassName($h, $c, 256)
        if ($c.ToString() -like '*SFML*') {
            $script:pet = [pscustomobject]@{ Handle = $h; X = $r.Left; Y = $r.Top; W = ($r.Right - $r.Left); H = ($r.Bottom - $r.Top) }
        }
    }
    return $true
}
[void][Pet.W]::EnumWindows($cb, [IntPtr]::Zero)
if (-not $script:pet) { Write-Host '没找到可见的 SFML_Window（宠物是不是被「显示精灵」关了？）'; exit 1 }
$pet = $script:pet
Write-Host ("宠物窗 {0}x{1} @ {2},{3}   句柄 {4}" -f $pet.W, $pet.H, $pet.X, $pet.Y, $pet.Handle)

$hits = @()
$other = 0
for ($y = $pet.Y; $y -lt ($pet.Y + $pet.H); $y += $Step) {
    for ($x = $pet.X; $x -lt ($pet.X + $pet.W); $x += $Step) {
        $pt = New-Object Pet.W+POINT; $pt.X = $x; $pt.Y = $y
        $h = [Pet.W]::WindowFromPoint($pt)
        if ($h -eq $pet.Handle) { $hits += ,@($x, $y) } elseif ($h -ne [IntPtr]::Zero) { $other++ }
    }
}
if ($hits.Count -eq 0) { Write-Host '一个点都没摸到这扇窗 —— 全窗透明或被别窗压着，Step 调小点再试'; exit 2 }

$x0 = ($hits | ForEach-Object { $_[0] } | Measure-Object -Minimum).Minimum
$x1 = ($hits | ForEach-Object { $_[0] } | Measure-Object -Maximum).Maximum
$y0 = ($hits | ForEach-Object { $_[1] } | Measure-Object -Minimum).Minimum
$y1 = ($hits | ForEach-Object { $_[1] } | Measure-Object -Maximum).Maximum
$cxD = [int](($hits | ForEach-Object { $_[0] } | Measure-Object -Average).Average)
$cyD = [int](($hits | ForEach-Object { $_[1] } | Measure-Object -Average).Average)
$cyM = [int](($y0 + $y1) / 2)
Write-Host ''
Write-Host ('能点到的剪影：x ' + $x0 + '~' + $x1 + '（宽 ' + ($x1 - $x0 + 1) + '） y ' + $y0 + '~' + $y1 + '（高 ' + ($y1 - $y0 + 1) + '）' +
            '  命中 ' + $hits.Count + ' 点 / 扫 ' + [math]::Round(($pet.W / $Step) * ($pet.H / $Step)) + ' 点，' + $other + ' 点落到别的窗')
Write-Host ('  形心 ' + $cxD + ',' + $cyD + '   包围盒中心 ' + $cxD + ',' + $cyM + '   ← 右键点这个才开得出小窗')

# 粗 ASCII：把窗口矩形按 $Preview 列分格，实心=该格有 ≥1 个可点中心
$cols = $Preview
$rows = [math]::Max(1, [math]::Round($Preview * ($pet.H / $pet.W) * 0.5))
$grid = @{}
foreach ($pt in $hits) {
    $cx = [int][math]::Floor(($pt[0] - $pet.X) / ($pet.W / $cols))
    $cy = [int][math]::Floor(($pt[1] - $pet.Y) / ($pet.H / $rows))
    if ($cx -ge $cols) { $cx = $cols - 1 }
    if ($cy -ge $rows) { $cy = $rows - 1 }
    $grid["$cx,$cy"] = 1 + ($grid["$cx,$cy"])
}
$cellW = [math]::Round($pet.W / $cols); $cellH = [math]::Round($pet.H / $rows)
Write-Host ''
Write-Host ("可点区域大概长这样（每格约 {0}x{1} 物理 px，# 越多越实）：" -f $cellW, $cellH)
for ($r = 0; $r -lt $rows; $r++) {
    $line = ''
    for ($c = 0; $c -lt $cols; $c++) {
        $n = $grid["$c,$r"]
        if (-not $n) { $line += '.' } elseif ($n -lt 3) { $line += ':' } elseif ($n -lt 8) { $line += '+' } else { $line += '#' }
    }
    Write-Host ('  ' + $line)
}
