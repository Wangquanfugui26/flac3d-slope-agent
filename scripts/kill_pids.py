# -*- coding: utf-8 -*-
"""按 PID 终止进程（不依赖 cmd/wmic）。

用法：python kill_pids.py <pid> [pid ...]
"""
import ctypes
import sys

PROCESS_TERMINATE = 0x0001
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
kernel32.TerminateProcess.restype = ctypes.c_int
kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

rc_all = 0
for a in sys.argv[1:]:
    try:
        pid = int(a)
    except ValueError:
        print("bad pid: %s" % a)
        rc_all = 2
        continue
    h = kernel32.OpenProcess(PROCESS_TERMINATE, 0, pid)
    if not h:
        print("pid=%d open failed err=%d" % (pid, ctypes.get_last_error()))
        rc_all = 3
        continue
    ok = kernel32.TerminateProcess(h, 1)
    err = ctypes.get_last_error()
    kernel32.CloseHandle(h)
    print("pid=%d terminate=%s err=%d" % (pid, bool(ok), err))

sys.exit(rc_all)
