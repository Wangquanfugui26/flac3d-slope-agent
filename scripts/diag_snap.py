# -*- coding: utf-8 -*-
"""diag_snap.py <pid> [n] [interval]

在 n 次采样、每次间隔 interval 秒，记录目标进程的：
  - CPU 时间（kernel32 GetProcessTimes）
  - 工作集内存（psapi GetProcessMemoryInfo）
  - 控制台屏幕最后几行（probe_console）

用途：区分 FLAC3D 是"在算"还是"挂住了"。
   在算 → CPU 时间持续增长、屏幕 cycling 行号递增
   挂住 → CPU 时间停滞、屏幕不变
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe_console  # noqa: E402

k32 = ctypes.WinDLL("kernel32", use_last_error=True)
psapi = ctypes.WinDLL("psapi", use_last_error=True)

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010


class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def cpu_and_mem(pid):
    h = k32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
    if not h:
        return None, None
    try:
        c, e, k, u = (wintypes.FILETIME() for _ in range(4))
        if not k32.GetProcessTimes(h, ctypes.byref(c), ctypes.byref(e),
                                  ctypes.byref(k), ctypes.byref(u)):
            return None, None
        def ft(f):
            return (f.dwHighDateTime << 32) | f.dwLowDateTime
        cpu = (ft(k) + ft(u)) / 1e7
        pmc = PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(pmc)
        psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb)
        return cpu, pmc.WorkingSetSize / 1024.0
    finally:
        k32.CloseHandle(h)


def last_lines(pid, k=6):
    try:
        cols, rows, vrows, lines = probe_console.screen_text(pid)
    except OSError as ex:
        return ["<probe failed: %s>" % ex]
    return [ln.rstrip()[-100:] for ln in lines if ln.strip()][-k:]


def main():
    pid = int(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    interval = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
    prev = None
    for i in range(n):
        cpu, mem = cpu_and_mem(pid)
        d = "" if prev is None else "   dCPU=%+.2fs" % (cpu - prev)
        print("[%2d] t=%6.1fs  cpu=%9.2fs  mem=%9.1f K%s"
              % (i, i * interval, cpu if cpu else -1, mem if mem else -1, d))
        for ln in last_lines(pid, 4):
            print("        | " + ln)
        prev = cpu
        if i < n - 1:
            time.sleep(interval)
    return 0


if __name__ == "__main__":
    sys.exit(main())
