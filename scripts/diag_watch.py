# -*- coding: utf-8 -*-
"""诊断：查看运行中 flac3d 进程的窗口标题/句柄信息，判断它是否卡住。

不依赖 GUI 抓屏，改用进程的可执行路径 + 命令行 + 内存增长趋势判断。
"""
import subprocess
import time


def snap():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq flac3d700_console.exe",
                          "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    rows = []
    for ln in out.splitlines():
        p = [x.strip('"') for x in ln.split('","')]
        if len(p) >= 5 and p[0].lower().startswith("flac3d"):
            rows.append((p[1], p[4]))
    return rows


def pyprocs():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq python.exe",
                          "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    rows = []
    for ln in out.splitlines():
        p = [x.strip('"') for x in ln.split('","')]
        if len(p) >= 5 and p[0].lower().startswith("python"):
            rows.append((p[1], p[4]))
    return rows


print("=== flac3d 内存采样（每10秒，共5次） ===")
for i in range(5):
    print("  t=%2ds  flac3d=%s  python=%s"
          % (i * 10, snap(), pyprocs()))
    time.sleep(10)
