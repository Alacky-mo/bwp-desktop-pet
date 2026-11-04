# 桌宠起没起来、窗口摆在哪 —— 抓屏被安全策略挡着时用它代替肉眼。
# 注意 DPI: 桌宠是 PerMonitorV2 感知, 而这里的 PowerShell 5.1 不是, 所以量到的宽高/坐标是「逻辑像素」,
#          200% 缩放下正好是 config.json 里那组数的一半 —— 对得上就行, 别当成窗口没被摆好。
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class W {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc p, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", SetLastError=true)] public static extern IntPtr GetWindowLongPtr(IntPtr h, int i);
  public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

$targets = Get-Process BwpDesktopPet -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id
Write-Output "PID: $($targets -join ',')"
$rows = @()
[void][W]::EnumWindows({
  param($h, $l)
  $pid2 = 0
  [void][W]::GetWindowThreadProcessId($h, [ref]$pid2)
  if ($targets -contains $pid2) {
    $r = New-Object W+RECT
    [void][W]::GetWindowRect($h, [ref]$r)
    $cls = New-Object System.Text.StringBuilder 256
    [void][W]::GetClassName($h, $cls, 256)
    $txt = New-Object System.Text.StringBuilder 256
    [void][W]::GetWindowText($h, $txt, 256)
    $style = [W]::GetWindowLongPtr($h, -16).ToInt64()
    $exstyle = [W]::GetWindowLongPtr($h, -20).ToInt64()
    $visible = [W]::IsWindowVisible($h)
    $topmost = ($exstyle -band 0x8) -ne 0
    $layered = ($exstyle -band 0x80000) -ne 0
    $popup = ($style -band 0x80000000) -ne 0
    $script:rows += [pscustomobject]@{
      Handle = $h.ToInt64(); Class = $cls.ToString(); Title = $txt.ToString();
      Visible = $visible; Topmost = $topmost; Layered = $layered; Popup = $popup;
      W = ($r.Right - $r.Left); H = ($r.Bottom - $r.Top); X = $r.Left; Y = $r.Top
    }
  }
  return $true
}, [IntPtr]::Zero)
$rows | Format-Table -AutoSize | Out-String -Width 200
