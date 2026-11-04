# 台词气泡那扇窗到底起没起来、是不是画布那个尺寸、露多久收多久 —— 抓屏被安全策略挡着时用它代替肉眼。
# 和 check-pet-window.ps1 的差别：这把尺自己声明成 DPI-aware，所以量到的是**物理像素**。
# 桌宠是 PerMonitorV2 感知的，气泡那张矩形由 UpdateLayeredWindow 直接给物理坐标，
# 所以 379x188 应当原样对得上；非感知的尺子会读到一半（200% 缩放下 190x94），那是尺子的锅不是窗口的锅。
#
# 用法：  powershell -NoProfile -File check-bubble-window.ps1
#        参数 -Seconds 采多久(默认 210 = 够走完两轮 15 露 + 60 收)、-Every 几秒采一次、
#        -CanvasW/-CanvasH 画布尺寸、-Find 头一条台词最多等多久(默认 90)
# 看什么：BUBBLE FOUND 那行的句柄、BUBBLE RUNS 那串的段长、最后一行 BUBBLE OK

param(
    [int]$Seconds = 210,
    [int]$Every = 2,
    [int]$CanvasW = 379,
    [int]$CanvasH = 188,
    [int]$Find = 90
)

Add-Type @"
using System; using System.Text; using System.Runtime.InteropServices;
public class BW {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern IntPtr GetWindowLongPtr(IntPtr h, int i);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern IntPtr SetProcessDpiAwarenessContext(IntPtr ctx);
  [DllImport("user32.dll")] public static extern uint GetDpiForSystem();
  [DllImport("user32.dll")] public static extern bool SystemParametersInfo(int a, int b, ref RECT r, int c);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

# PerMonitorV2(-4) 拿不到就退回系统级感知，两头都失败就只能按「读到一半」解释数字，脚本会把这点打出来
$ctx = [IntPtr](-4)
try { [void][BW]::SetProcessDpiAwarenessContext($ctx) } catch { }
[void][BW]::SetProcessDPIAware()
$dpi = [BW]::GetDpiForSystem()
Write-Output "DPI=$dpi (96=100%, 192=200%)  —— 尺子自己声明成感知了，量到的应是物理像素"

$work = New-Object BW+RECT
[void][BW]::SystemParametersInfo(0x30, 0, [ref]$work, 0)   # SPI_GETWORKAREA
Write-Output ("工作区 {0},{1}~{2},{3}" -f $work.Left, $work.Top, $work.Right, $work.Bottom)

function Get-Windows {
    $targets = Get-Process BwpDesktopPet -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id
    if (-not $targets) { return @() }
    # EnumWindows 的回调写的是 $script:rows(脚本作用域), 所以这里不能用函数里的局部同名变量, 不然拿到的是空表
    $script:rows = @()
    [void][BW]::EnumWindows({
        param($h, $l)
        $pid2 = 0
        [void][BW]::GetWindowThreadProcessId($h, [ref]$pid2)
        if ($targets -contains [int]$pid2) {
            $r = New-Object BW+RECT
            [void][BW]::GetWindowRect($h, [ref]$r)
            $cls = New-Object System.Text.StringBuilder 256
            [void][BW]::GetClassName($h, $cls, 256)
            $ex = [BW]::GetWindowLongPtr($h, -20).ToInt64()
            $script:rows += [pscustomobject]@{
                Handle = $h.ToInt64(); Class = $cls.ToString();
                Visible = [BW]::IsWindowVisible($h);
                Layered = ($ex -band 0x80000) -ne 0; Tool = ($ex -band 0x80) -ne 0;
                NoActivate = ($ex -band 0x8000000) -ne 0;
                W = ($r.Right - $r.Left); H = ($r.Bottom - $r.Top); X = $r.Left; Y = $r.Top
            }
        }
        return $true
    }, [IntPtr]::Zero)
    return $script:rows
}

function Find-Bubble {
    param($Rows)
    # 只有气泡那张是画布尺寸(±2 容差)，所以按尺寸认；句柄一旦认出来就一直跟同一扇
    $Rows | Where-Object { $_.Visible -and [Math]::Abs($_.W - $CanvasW) -le 2 -and [Math]::Abs($_.H - $CanvasH) -le 2 } |
        Select-Object -First 1
}

$deadline = (Get-Date).AddSeconds($Find)
$bubble = $null
Write-Output "找头一条台词冒出来的那扇窗(最多等 $Find 秒)..."
while (-not $bubble -and (Get-Date) -lt $deadline) {
    $rows = Get-Windows
    $bubble = Find-Bubble $rows
    if (-not $bubble) { Start-Sleep -Seconds $Every }
}
if (-not $bubble) {
    Write-Output "BUBBLE MISSING 等到现在没有一扇 $CanvasW x $CanvasH 的可见窗 —— 素材没装机/开关关了/节拍没接，看下面这张表"
    $all = @(Get-Windows)
    Write-Output ("BwpDesktopPet 的顶层窗 " + $all.Count + " 扇:")
    Write-Output (($all | Format-Table -AutoSize | Out-String -Width 200).TrimEnd())
    exit 1
}

Write-Output ("BUBBLE FOUND handle={0} {1}x{2} @({3},{4}) Layered={5} Tool={6} NoActivate={7} class={8}" -f
    $bubble.Handle, $bubble.W, $bubble.H, $bubble.X, $bubble.Y,
    $bubble.Layered, $bubble.Tool, $bubble.NoActivate, $bubble.Class)
Write-Output ("  贴边检查: 右边到 {0} (工作区右 {1}) 下边到 {2} (工作区下 {3})" -f
    ($bubble.X + $bubble.W), $work.Right, ($bubble.Y + $bubble.H), $work.Bottom)
$pet = (Get-Windows | Where-Object { $_.Class -like "*SFML*" } | Select-Object -First 1)
if ($pet) {
    Write-Output ("  宠物那扇(SFML): {0}x{1} @({2},{3})  —— 气泡看得见的那圈墨应坐在它右边界 +{4} 那一侧，塞不下就翻到左边(镜像)" -f
        $pet.W, $pet.H, $pet.X, $pet.Y, 4)
}

# 从这一刻起跟同一句柄数露/收的段长。头一段可能是「已经露了一会儿」的半截，所以标 head。
$end = (Get-Date).AddSeconds($Seconds)
$runs = @()
$last = $true
$t0 = Get-Date
while ((Get-Date) -lt $end) {
    $on = [BW]::IsWindowVisible([IntPtr]$bubble.Handle)
    if ($on -ne $last) {
        $runs += [pscustomobject]@{ On = $last; Sec = [int]((Get-Date) - $t0).TotalSeconds }
        $t0 = Get-Date
    }
    $last = $on
    Start-Sleep -Seconds $Every
}
$runs += [pscustomobject]@{ On = $last; Sec = [int]((Get-Date) - $t0).TotalSeconds }

$shown = ($runs | Where-Object { $_.On } | ForEach-Object { $_.Sec }) -join ','
$hid = ($runs | Where-Object { -not $_.On } | ForEach-Object { $_.Sec }) -join ','
Write-Output ("BUBBLE RUNS 露={0} 收={1} (采样 {2} 秒, 每 {3} 秒一次; 头尾两段可能被采样窗口切短)" -f
    $shown, $hid, $Seconds, $Every)

# 判据只看「走满的那一段」: 15 秒到点自己收、之后空到 60 秒再来一条。±5 秒是采样粒度和 UI 线程排队的余量
$firstFull = ($runs | Where-Object { $_.On } | Select-Object -Skip 1 -First 1)
$firstGap = ($runs | Where-Object { -not $_.On } | Select-Object -First 1)
$ok = $true
if ($null -eq $firstFull) {
    Write-Output "  露的那一段只采到一段(还是头一条), $Seconds 秒太短, 把 -Seconds 加到 180 再看"
    $ok = $false
} elseif ([Math]::Abs($firstFull.Sec - 15) -gt 5) {
    Write-Output ("  露了 {0} 秒, 对不上 15" -f $firstFull.Sec); $ok = $false
} else {
    Write-Output ("  露 {0} 秒 —— 对得上 ShowSeconds=15" -f $firstFull.Sec)
}
if ($null -ne $firstGap -and $firstGap.Sec -ge 12 -and [Math]::Abs($firstGap.Sec - 60) -gt 8) {
    Write-Output ("  收了 {0} 秒, 对不上 60" -f $firstGap.Sec); $ok = $false
} elseif ($null -ne $firstGap -and $firstGap.Sec -ge 12) {
    Write-Output ("  收 {0} 秒 —— 对得上 GapSeconds=60" -f $firstGap.Sec)
} else {
    Write-Output "  这趟没采到走满的收起段(那段 60 秒比 -Seconds 还长就正常, 加大 -Seconds 再看)"; $ok = $false
}
if ($ok) { Write-Output "BUBBLE OK" } else { Write-Output "BUBBLE SHORT 见上面那两行" }
