# R6 打靶的量尺（配合 docs/番茄钟复验单.md 的 R6）：
# 自己找到预设小窗那扇 276x406 的分层窗，把 13 个测试点的**屏幕绝对物理坐标**打印出来，
# 你照着点就行，不用自己加减。加 -Run N 才真的把光标挪过去点（会动你的鼠标，默认不动）。
#
# 为什么要它：面板那些盒子是 Arrange() 里的相对偏移，靠肉眼在 138x203 逻辑像素的小面板上
# 找「× 左上角往里 1~2 px」是找不到的，找错了还会把「点不动」记成失灵。
#
# 三个坑（和 probe-jitter.ps1 / click-at.ps1 同一套）：
#   1) PS 5.1 不认 DPI，不先 SetProcessDpiAwarenessContext(-4) 读到的矩形是真实值的一半。
#   2) 打印的偏移是**物理像素**，和 Arrange 那套数一一对应（这台机器分层窗没按 DPI 缩放）。
#   3) 面板会跟着宠物走，所以每次跑都重新量一遍，别用上一次的坐标。
#
# 用法：
#   powershell -NoProfile -ExecutionPolicy Bypass -File ./hitmap.ps1            # 只打印坐标和该发生什么
#   ... -Run 7                                                                    # 第 7 号：把光标移过去、真点一下
#   ... -Run 7 -DryMove                                                           # 只把光标放上去，不点

param([int]$Run = -1, [switch]$DryMove)

Add-Type -Namespace Hit -Name W -MemberDefinition @'
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
[void][Hit.W]::SetProcessDpiAwarenessContext([System.IntPtr](-4))

$ids = @(Get-Process BwpDesktopPet -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
if ($ids.Count -eq 0) { Write-Host '没找到 BwpDesktopPet 进程，先把桌宠起来'; exit 1 }

$script:wins = @()
$cb = [Hit.W+EnumProc] {
    param($h, $l)
    $p = 0
    [void][Hit.W]::GetWindowThreadProcessId($h, [ref]$p)
    if ($ids -contains $p -and [Hit.W]::IsWindowVisible($h)) {
        $r = New-Object Hit.W+RECT
        [void][Hit.W]::GetWindowRect($h, [ref]$r)
        $c = New-Object System.Text.StringBuilder 256
        [void][Hit.W]::GetClassName($h, $c, 256)
        $script:wins += [pscustomobject]@{
            Class = $c.ToString(); X = $r.Left; Y = $r.Top
            W = ($r.Right - $r.Left); H = ($r.Bottom - $r.Top)
        }
    }
    return $true
}
[void][Hit.W]::EnumWindows($cb, [IntPtr]::Zero)

# 认面板：只认 276x406 那扇（Arrange 出来的死尺寸，不随内容变）。宠物主窗是全屏的 SFML 窗，浮窗矮得多。
$panel = $script:wins | Where-Object { $_.W -eq 276 -and $_.H -eq 406 } | Select-Object -First 1
if (-not $panel) {
    Write-Host '没找到 276x406 的面板窗 —— 先把预设小窗开出来（右键宠物，或托盘 番茄钟 → 预设小窗）。'
    Write-Host ('现在可见的这些是：' + (($script:wins | ForEach-Object { "$($_.W)x$($_.H)@$($_.X),$($_.Y)" }) -join '  '))
    exit 2
}
$float = $script:wins | Where-Object { $_ -ne $panel -and $_.Class -notlike '*SFML*' } | Select-Object -First 1
Write-Host ('面板左上角（物理）= ' + "$($panel.X),$($panel.Y)   尺寸 $($panel.W)x$($panel.H)   " +
            $(if ($float) { "浮窗 $($float.W)x$($float.H) @ $($float.X),$($float.Y)" } else { '浮窗现在没露' }))

# 这些偏移全是 FocusPresetForm.Arrange(Presets, 276) 的数：PadX 14 / PadY 12 / Gap 8 / RowH 54 /
# RadioBox 54 / PlateW 104 / PlateH 44 / SummaryH 24 / CloseSize 44 / StartW 150 / StartH 66。
# 改了 Arrange 就要改这里 —— 所以脚本把面板死尺寸钉成 276x406，对不上就说明两边飘了。
$L, $T = $panel.X, $panel.Y
function P($dx, $dy) { return "$($L + $dx),$($T + $dy)" }

$steps = @(
    [pscustomobject]@{ N = 1;  在哪 = '× 正中';                         坐标 = (P 242 34);  该发生 = '面板收起；再右键宠物该开回来' },
    [pscustomobject]@{ N = 2;  在哪 = '× 左上角往里 1~2 px';            坐标 = (P 221 13);  该发生 = '同样该收（44x44 的盒子边角也得点得到）' },
    [pscustomobject]@{ N = 2;  在哪 = '× 右下角那一格';                 坐标 = (P 263 55);  该发生 = '同样该收' },
    [pscustomobject]@{ N = 3;  在哪 = '× 外面那一圈（标题最右端）';     坐标 = (P 210 34);  该发生 = '不该收。收了 = 盒子画大了' },
    [pscustomobject]@{ N = 4;  在哪 = '大按钮正中';                     坐标 = (P 138 361); 该发生 = '开始专注 → 先停一下 →（暂停后）继续 轮转' },
    [pscustomobject]@{ N = 5;  在哪 = '大按钮上边缘内 1 px';            坐标 = (P 138 329); 该发生 = '同样算一次点' },
    [pscustomobject]@{ N = 5;  在哪 = '大按钮下边缘内 1 px';            坐标 = (P 138 393); 该发生 = '同样算一次点' },
    [pscustomobject]@{ N = 6;  在哪 = '大按钮左边的空白';               坐标 = (P 40 361);  该发生 = '不该有反应（按钮没占满整行）' },
    [pscustomobject]@{ N = 6;  在哪 = '大按钮右边的空白';               坐标 = (P 240 361); 该发生 = '不该有反应' },
    [pscustomobject]@{ N = 7;  在哪 = '第1行 圆点上';                   坐标 = (P 82 91);   该发生 = '选中第1行（圆点变、摘要跟着变）' },
    [pscustomobject]@{ N = 7;  在哪 = '第2行 数字板上';                 坐标 = (P 169 145); 该发生 = '选中第2行 —— 整行 166 宽都算命中' },
    [pscustomobject]@{ N = 7;  在哪 = '第3行 行末「分」右边空白';       坐标 = (P 215 199); 该发生 = '选中第3行' },
    [pscustomobject]@{ N = 8;  在哪 = '摘要行正中';                     坐标 = (P 138 246); 该发生 = '什么都别变（设计，不是失灵）' },
    [pscustomobject]@{ N = 9;  在哪 = '缝：三行 → 摘要 (y226~234)';     坐标 = (P 138 230); 该发生 = '什么都别变' },
    [pscustomobject]@{ N = 9;  在哪 = '缝：摘要 → 开关 (y258~266)';     坐标 = (P 138 262); 该发生 = '什么都别变' },
    [pscustomobject]@{ N = 9;  在哪 = '缝：开关 → 按钮 (y320~328)';     坐标 = (P 138 324); 该发生 = '什么都别变' },
    [pscustomobject]@{ N = 10; 在哪 = '开关行 圆点';                    坐标 = (P 82 293);  该发生 = '「换阶段弹气泡」on/off 来回切' },
    [pscustomobject]@{ N = 10; 在哪 = '开关行 文字';                    坐标 = (P 140 293); 该发生 = '同样该切' },
    [pscustomobject]@{ N = 10; 在哪 = '开关行 右侧空白';                坐标 = (P 215 293); 该发生 = '同样该切' }
)

if ($Run -ge 0) {
    $s = @($steps | Where-Object { $_.N -eq $Run })
    if ($s.Count -eq 0) { Write-Host "第 $Run 号没有对应的点，看看上面那张表"; exit 2 }
    # 面板不吃右键（FocusPresetForm 的 OnMouseDown/Up 都只认 MouseButtons.Left），
    # 而且按下和抬起要落在同一块才算一次点 —— click-at.ps1 正是在同一点上 down+up。
    # 1/2 号一点就把面板收了，第二处会落到桌面上，所以那种编号一次只替你点第一处。
    $todo = if ($Run -eq 1 -or $Run -eq 2) { @($s[0]) } else { $s }
    foreach ($one in $todo) {
        $x, $y = $one.坐标.Split(',')
        Write-Host ('#{0} {1} → {2}   该发生：{3}' -f $one.N, $one.在哪, $one.坐标, $one.该发生)
        $a = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "$PSScriptRoot\click-at.ps1",
               '-X', $x, '-Y', $y, '-Button', 'Left')
        if ($DryMove) { & powershell @a -NoClick } else { & powershell @a }
    }
    if ($todo.Count -lt $s.Count) {
        Write-Host ('  这一号还剩：' + (($s | Select-Object -Skip $todo.Count | ForEach-Object { "$($_.在哪)=$($_.坐标)" }) -join '；') +
                    ' —— 面板已经收了，重新开一扇再跑一次 -Run ' + $Run)
    }
    Write-Host '回我：实际发生了什么（和「该发生」不一样就照实写）'
    exit 0
}

Write-Host ''
Write-Host '== 照着点的顺序（坐标 = 屏幕绝对物理像素，你自己的鼠标或 -Run N 都行）=='
$steps | Format-Table -AutoSize 'N', '在哪', '坐标', '该发生' | Out-String -Width 220

Write-Host '== 剩下三条不用点，是看 =='
Write-Host '  11 有没有哪一下要点两下才生效，或者按下没抬起就不换 → 报第几号'
Write-Host '  12 未选中的那行圆点（素材峰 α 133，深底上可能只剩一圈）→ 一眼分得出哪行没被选中吗'
Write-Host '  13 整扇面板 276x406 物理 = 逻辑 138x203，在你眼里是正好还是偏小 → 偏小要放大到几倍(1.5x/2x)'
Write-Host ''
Write-Host '回我：1~13 每条一个 ✓ / ✗ / 说不清，✗ 的补一句「点下去实际发生了什么」。'
Write-Host '想让我把光标放过去就别自己伸手：hitmap.ps1 -Run 7（真点）；-Run 7 -DryMove（只放过去不点）。'
