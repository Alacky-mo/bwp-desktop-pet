param([Parameter(Mandatory = $true)][int]$X, [Parameter(Mandatory = $true)][int]$Y,
      [ValidateSet('Right', 'Left')][string]$Button = 'Right', [switch]$NoClick)

# 把真光标放到某个物理像素点上，再点一下。抓不了屏、又想把「右键宠物」这种手势自己验通的时候用。
# 三个坑都在这脚本里防掉了，改之前先读 docs/番茄钟界面方案.md §8：
#   1) INPUT 的 type 鼠标事件是 0（写成 1 会变键盘事件：SendInput 说发了，实际什么都没点）
#   2) PS 5.1 不认 DPI，不先 SetProcessDpiAwarenessContext 的话 2560 宽读成 1280，坐标差一半
#   3) 移完先回读 GetCursorPos，落在目标 2 px 以内才点 —— 不然点的是别人家的窗口
Add-Type -Namespace Win -Name Inj -MemberDefinition @'
[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct POINT { public int X; public int Y; }

[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct MOUSEINPUT {
    public int dx; public int dy; public uint mouseData; public uint dwFlags; public uint time;
    public System.IntPtr dwExtraInfo;
}

[System.Runtime.InteropServices.StructLayout(System.Runtime.InteropServices.LayoutKind.Sequential)]
public struct INPUT { public uint type; public MOUSEINPUT mi; }

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool SetProcessDpiAwarenessContext(System.IntPtr v);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern int GetSystemMetrics(int which);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool GetCursorPos(out POINT p);

[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern uint SendInput(uint n, INPUT[] p, int cbSize);

[System.Runtime.InteropServices.DllImport("kernel32.dll")]
public static extern int GetLastError();

public static void Aware() { SetProcessDpiAwarenessContext(new System.IntPtr(-4)); }
public static int Met(int which) { return GetSystemMetrics(which); }
public static POINT Cur() { POINT p; GetCursorPos(out p); return p; }

public static uint Move(int x, int y) {
    int left = Met(76), top = Met(77), w = Met(78), h = Met(79);
    var a = new INPUT[1];
    a[0].type = 0;
    a[0].mi.dx = (int)((x - left) * 65536.0 / w);
    a[0].mi.dy = (int)((y - top) * 65536.0 / h);
    a[0].mi.dwFlags = 0x0001u | 0x8000u | 0x4000u;    // MOVE | ABSOLUTE | VIRTUALDESK
    var n = SendInput(1u, a, System.Runtime.InteropServices.Marshal.SizeOf(typeof(INPUT)));
    return n == 1u ? 0u : (uint)GetLastError();
}

public static uint Click(string button) {
    uint down = button == "Left" ? 0x0002u : 0x0008u, up = button == "Left" ? 0x0004u : 0x0010u;
    var a = new INPUT[2];
    a[0].type = 0; a[0].mi.dwFlags = down;
    a[1].type = 0; a[1].mi.dwFlags = up;
    var n = SendInput(2u, a, System.Runtime.InteropServices.Marshal.SizeOf(typeof(INPUT)));
    return n == 2u ? 0u : (uint)GetLastError();
}
'@

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Win.Inj]::Aware() | Out-Null
$screen = "$([Win.Inj]::Met(78))x$([Win.Inj]::Met(79)) @ $([Win.Inj]::Met(76)),$([Win.Inj]::Met(77))"
$err = [Win.Inj]::Move($X, $Y)
Start-Sleep -Milliseconds 120
$at = [Win.Inj]::Cur()
Write-Host ("虚拟桌面 {0}; 移动 err={1}; 光标现在 {2},{3}（要去 {4},{5}）" -f $screen, $err, $at.X, $at.Y, $X, $Y)
if ($err -ne 0 -or [Math]::Abs($at.X - $X) -gt 2 -or [Math]::Abs($at.Y - $Y) -gt 2) {
    Write-Host '光标没落到位，这一下不点了'
    exit 2
}
if ($NoClick) { exit 0 }
$err = [Win.Inj]::Click($Button)
Write-Host ("{0} 键点下去了, err={1}" -f $Button, $err)
exit ($err -ne 0)
