# -*- coding: utf-8 -*-
"""进程查询/管理小工具（全部二进制解码，避免 GBK/UTF-8 报错）。

命令：
  python procs.py list                 列出 python/flac3d 进程
  python procs.py killflac             杀掉所有 flac3d700_console.exe
  python procs.py kill <pid> [...]     杀指定 pid
  python procs.py clean                杀掉所有 flac3d + driver/python 批跑进程
"""
import ctypes
import subprocess
import sys
import time

PROCESS_TERMINATE = 0x0001
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
kernel32.TerminateProcess.restype = ctypes.c_int
kernel32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]


def kill(pid):
    h = kernel32.OpenProcess(PROCESS_TERMINATE, 0, pid)
    if not h:
        return False
    kernel32.TerminateProcess(h, 1)
    kernel32.CloseHandle(h)
    return True


def ps_lines():
    """返回 [(name, pid, memKB)]，安全解码。"""
    raw = subprocess.run(["tasklist", "/FO", "CSV", "/NH"],
                         capture_output=True).stdout
    txt = raw.decode("gbk", errors="replace")
    rows = []
    for ln in txt.splitlines():
        p = [x.strip('"') for x in ln.split('","')]
        if len(p) >= 5:
            rows.append((p[0], p[1], p[4]))
    return rows


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"

    if cmd == "list":
        for n, pid, mem in ps_lines():
            nl = n.lower()
            if "python" in nl or "flac" in nl:
                print("%-28s pid=%-8s %s" % (n, pid, mem))
        return 0

    if cmd == "killflac":
        n = 0
        for name, pid, _ in ps_lines():
            if name.lower().startswith("flac3d"):
                if kill(int(pid)):
                    n += 1
        print("killed flac3d: %d" % n)
        return 0

    if cmd == "kill":
        for a in sys.argv[2:]:
            print("pid=%s killed=%s" % (a, kill(int(a))))
        return 0

    if cmd == "clean":
        n = 0
        for name, pid, _ in ps_lines():
            nl = name.lower()
            if nl.startswith("flac3d") or nl == "python.exe":
                if kill(int(pid)):
                    n += 1
        print("killed: %d" % n)
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
