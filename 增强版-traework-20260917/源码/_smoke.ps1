param(
    [string]$SourcePath = "",
    [switch]$Exe,
    [string]$WindowTitle = "",
    [int]$Iter = 200,
    [switch]$SkipF11,
    [switch]$SkipSpace,
    [string]$DebugLog = ""
)
$ErrorActionPreference = "Stop"
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class SmokeWin {
  public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder sb, int max);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
}
'@

function Find-TkWindow([int]$procId, [string]$title) {
    $script:foundHandle = [IntPtr]::Zero
    $cb = [SmokeWin+EnumProc]{
        param($hWnd, $lParam)
        $wpid = 0
        [SmokeWin]::GetWindowThreadProcessId($hWnd, [ref]$wpid) | Out-Null
        $ok = $false
        if ($title) {
            $sb = New-Object System.Text.StringBuilder 256
            [SmokeWin]::GetWindowText($hWnd, $sb, 256) | Out-Null
            if ($sb.ToString() -eq $title) { $ok = $true }
        } else {
            if ($wpid -eq $procId) { $ok = $true }
        }
        if ($ok -and [SmokeWin]::IsWindowVisible($hWnd)) {
            $script:foundHandle = $hWnd
            return $false
        }
        return $true
    }
    [SmokeWin]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
    return $script:foundHandle
}

# Locate a pythonw/python interpreter:
#   1) $env:SMOKE_PY   2) LOCALAPPDATA pythoncore install   3) PATH
$py = $env:SMOKE_PY
if (-not $py) {
    $roots = @(
        (Join-Path $env:LOCALAPPDATA "Python"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python")
    )
    foreach ($root in $roots) {
        if (-not (Test-Path $root)) { continue }
        foreach ($exe in @("pythonw.exe", "python.exe")) {
            $hit = Get-ChildItem -Path $root -Filter $exe -Recurse -Depth 2 -ErrorAction SilentlyContinue |
                   Select-Object -First 1
            if ($hit) { $py = $hit.FullName; break }
        }
        if ($py) { break }
    }
}
if (-not $py) { $py = "pythonw.exe" }
$src = $SourcePath
if (-not $src) { $src = Join-Path (Split-Path $PSScriptRoot -Parent) "award_app.py" }
if (-not (Test-Path $src)) { Write-Host "src not found: $src"; exit 1 }

$psi = New-Object System.Diagnostics.ProcessStartInfo
if ($Exe) {
    $psi.FileName = $src
    $psi.Arguments = ""
} else {
    $psi.FileName = $py
    $psi.Arguments = '"' + $src + '"'
}
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
if ($DebugLog) {
    Remove-Item $DebugLog -ErrorAction SilentlyContinue
    $psi.EnvironmentVariables["AWARD_DEBUG"] = $DebugLog
}
$p = [System.Diagnostics.Process]::Start($psi)
Write-Host "started pid=$($p.Id), waiting for window..."
$h = [IntPtr]::Zero
for ($i = 0; $i -lt 150; $i++) {
    Start-Sleep -Milliseconds 100
    if ($p.HasExited) {
        Write-Host "EXITED early code=$($p.ExitCode)"
        Write-Host ("ERR: " + $p.StandardError.ReadToEnd())
        exit 1
    }
    $script:foundHandle = [IntPtr]::Zero
    $h = Find-TkWindow $p.Id $WindowTitle
    if ($h -ne [IntPtr]::Zero) { break }
}
if ($h -eq [IntPtr]::Zero) {
    Write-Host "NO WINDOW"; Stop-Process -Id $p.Id -Force; exit 1
}
Write-Host ("window found h=0x{0:X}. running stress ({1} iters)..." -f $h.ToInt64(), $Iter)

$bad = 0
$hangStart = -1
$w = 1280; $hh = 800
for ($i = 0; $i -lt $Iter; $i++) {
    $act = $i % 7
    switch ($act) {
        0 { $w = 960 + (Get-Random -Maximum 400); $hh = 600 + (Get-Random -Maximum 260) }
        1 { $w = 1100 + (Get-Random -Maximum 200); $hh = 640 + (Get-Random -Maximum 160) }
        2 { $hh -= 40 }
        3 { $hh += 40 }
        4 { $w += 50 }
        5 { $w -= 50 }
        6 { $w = 1280; $hh = 800 }
    }
    if ($w -lt 960) { $w = 960 }; if ($w -gt 1600) { $w = 1600 }
    if ($hh -lt 600) { $hh = 600 }; if ($hh -gt 1000) { $hh = 1000 }
    [SmokeWin]::SetWindowPos($h, [IntPtr]::Zero, 60, 40, $w, $hh, 0x0040) | Out-Null
    if (-not $SkipF11 -and $i % 20 -eq 0) {
        [SmokeWin]::PostMessage($h, 0x0100, [IntPtr]0x7A, [IntPtr]::Zero) | Out-Null
        [SmokeWin]::PostMessage($h, 0x0101, [IntPtr]0x7A, [IntPtr]::Zero) | Out-Null
    }
    if (-not $SkipSpace -and $i % 10 -eq 0) {
        [SmokeWin]::PostMessage($h, 0x0100, [IntPtr]0x20, [IntPtr]::Zero) | Out-Null
        [SmokeWin]::PostMessage($h, 0x0101, [IntPtr]0x20, [IntPtr]::Zero) | Out-Null
    }
    Start-Sleep -Milliseconds 25
    if ($p.HasExited) { Write-Host "EXITED during stress at iter $i"; exit 1 }
    if (-not $p.Responding) {
        $bad++
        if ($hangStart -lt 0) { $hangStart = $i }
    } else {
        $hangStart = -1
    }
}
Start-Sleep -Milliseconds 600
$p.Refresh()
$final = if ($p.HasExited) { "EXITED" } else { "alive" }
Write-Host ("done. not-responding samples: {0}/{1}, final={2}, Responding={3}, CPU={4:N1}s" -f $bad, $Iter, $final, $p.Responding, $p.CPU)
try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
if ($Exe) {
    $base = [System.IO.Path]::GetFileNameWithoutExtension($src)
    Get-Process | Where-Object { $_.ProcessName -eq $base } | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}
if ($bad -eq 0 -and $final -eq "alive") { exit 0 } else { exit 2 }
