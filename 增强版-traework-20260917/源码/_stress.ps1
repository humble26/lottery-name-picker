param([int]$PidArg)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Stress2 {
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
}
"@
$proc = Get-Process -Id $PidArg -ErrorAction Stop
$h = $proc.MainWindowHandle
$bad = 0
$start = Get-Date
$w = 1280; $hh = 800
for ($i = 0; $i -lt 200; $i++) {
    $act = $i % 6
    switch ($act) {
        0 { $w = 960 + (Get-Random -Maximum 340); $hh = 600 + (Get-Random -Maximum 220) }
        1 { $w = 1100 + (Get-Random -Maximum 200); $hh = 640 + (Get-Random -Maximum 160) }
        2 { $hh = $hh - 30 }
        3 { $hh = $hh + 30 }
        4 { $w = $w + 40 }
        5 { $w = $w - 40 }
    }
    if ($w -lt 960) { $w = 960 }; if ($w -gt 1500) { $w = 1500 }
    if ($hh -lt 600) { $hh = 600 }; if ($hh -gt 900) { $hh = 900 }
    [Stress2]::SetWindowPos($h, [IntPtr]::Zero, 80, 60, $w, $hh, 0x0040) | Out-Null
    if ($i % 20 -eq 0) { [Stress2]::PostMessage($h, 0x0100, [IntPtr]0x7A, [IntPtr]::Zero) | Out-Null; [Stress2]::PostMessage($h, 0x0101, [IntPtr]0x7A, [IntPtr]::Zero) | Out-Null }
    if ($i % 15 -eq 0) { [Stress2]::PostMessage($h, 0x0100, [IntPtr]0x20, [IntPtr]::Zero) | Out-Null; [Stress2]::PostMessage($h, 0x0101, [IntPtr]0x20, [IntPtr]::Zero) | Out-Null }
    Start-Sleep -Milliseconds 30
    $p = Get-Process -Id $PidArg -ErrorAction SilentlyContinue
    if (-not $p.Responding) { $bad++; Write-Host ("t={0}s NOT RESPONDING (iter {1})" -f [int]((Get-Date)-$start).TotalSeconds, $i) }
}
$p = Get-Process -Id $PidArg
Write-Host ("done. not-responding samples: {0}, total CPU: {1:N1}s, Responding={2}" -f $bad, $p.CPU, $p.Responding)
