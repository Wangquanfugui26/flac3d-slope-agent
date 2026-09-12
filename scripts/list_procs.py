# -*- coding: utf-8 -*-
"""列出所有 python.exe / flac3d700_console.exe 进程及其命令行，用于识别残留批跑。"""
import subprocess
import sys

PS = (
    "$ps = Get-CimInstance Win32_Process | "
    "Where-Object { $_.Name -eq 'python.exe' -or $_.Name -eq 'flac3d700_console.exe' }; "
    "foreach ($p in $ps) { Write-Output ($p.ProcessId.ToString() + '|' + $p.Name + '|' + $p.CommandLine) }"
)

r = subprocess.run(["powershell", "-NoProfile", "-Command", PS],
                   capture_output=True, timeout=90)
out = r.stdout.decode("gbk", errors="replace")
print("STDOUT:")
print(out)
if r.stderr:
    print("STDERR:")
    print(r.stderr.decode("gbk", errors="replace")[:1000])
