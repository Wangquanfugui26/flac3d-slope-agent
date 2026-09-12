# -*- coding: utf-8 -*-
"""读取 flac3d 进程的线程状态与 IO 计数，判断是否死锁/挂起。"""
import subprocess
import sys

PS = r"""
$p = Get-Process -Id %PID% -ErrorAction SilentlyContinue
if ($p) {
  Write-Output ("Threads=" + $p.Threads.Count)
  Write-Output ("CPU=" + $p.CPU)
  Write-Output ("WS=" + $p.WorkingSet64)
  Write-Output ("Responding=" + $p.Responding)
  Write-Output ("MainWindowTitle=" + $p.MainWindowTitle)
  Write-Output ("HandleCount=" + $p.HandleCount)
} else { Write-Output "no such process" }
"""

pid = sys.argv[1] if len(sys.argv) > 1 else "20972"
r = subprocess.run(["powershell", "-NoProfile", "-Command",
                    PS.replace("%PID%", pid)],
                   capture_output=True, timeout=90)
print(r.stdout.decode("gbk", errors="replace"))
e = r.stderr.decode("gbk", errors="replace")
if e.strip():
    print("STDERR:", e[:800])
