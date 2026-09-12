# -*- coding: utf-8 -*-
"""probe_console.py <pid>  —— 只读地抓取某个 FLAC3D 控制台的真实屏幕内容。

背景：本次会话中我（AI）一度根据不可靠的 shell 输出做出错误判断。此脚本
直接 AttachConsole 到目标进程、用 ReadConsoleOutputCharacterW 读它的屏幕
缓冲区，是**唯一可靠**的"FLAC3D 现在到底在干什么"的观测手段，且写入目标
进程的 CONOUT$ 时只读不写，不会干扰它。

用法：
    python probe_console.py 32348            # 抓当前屏幕
    python probe_console.py 32348 60         # 抓屏幕最右 60 列
"""
import ctypes
import sys
from ctypes import wintypes

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
ATTACH_PARENT_PROCESS = -1

COORD = ctypes.c_short * 2
SMALL_RECT = ctypes.c_short * 4


class CHAR_INFO(ctypes.Structure):
    _fields_ = [("UnicodeChar", ctypes.c_wchar), ("Attributes", ctypes.c_ushort)]


class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", COORD),
        ("dwCursorPosition", COORD),
        ("wAttributes", ctypes.c_ushort),
        ("srWindow", SMALL_RECT),
        ("dwMaximumWindowSize", COORD),
    ]


class CONSOLE_SCREEN_BUFFER_INFOEX(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.ULONG),
        ("dwSize", COORD),
        ("dwCursorPosition", COORD),
        ("wAttributes", ctypes.c_ushort),
        ("srWindow", SMALL_RECT),
        ("dwMaximumWindowSize", COORD),
        ("nFont", wintypes.ULONG),
        ("dwFontSize", COORD),
        ("uFontFamily", wintypes.ULONG),
        ("uFontWeight", wintypes.ULONG),
        ("FaceName", ctypes.c_wchar * 32),
    ]


def free():
    k32.FreeConsole()


def attach(pid):
    if not k32.AttachConsole(wintypes.DWORD(pid)):
        err = ctypes.get_last_error()
        raise OSError("AttachConsole(%d) failed: err=%d" % (pid, err))


def open_conout():
    h = k32.CreateFileW(
        "CONOUT$",
        GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        0,
        None,
    )
    if h == -1 or h == 0xFFFFFFFFFFFFFFFF:
        err = ctypes.get_last_error()
        raise OSError("CreateFileW(CONOUT$) failed: err=%d" % err)
    return h


def screen_text(pid, width=None):
    """返回 (cols, rows, [每行字符串])。"""
    free()
    attach(pid)
    h = open_conout()
    try:
        info = CONSOLE_SCREEN_BUFFER_INFO()
        if not k32.GetConsoleScreenBufferInfo(h, ctypes.byref(info)):
            err = ctypes.get_last_error()
            raise OSError("GetConsoleScreenBufferInfo failed: err=%d" % err)
        cols = info.dwSize[0]
        rows = info.dwSize[1]
        left = info.srWindow[0]
        top = info.srWindow[1]
        right = info.srWindow[2]
        bottom = info.srWindow[3]
        vis_cols = right - left + 1
        vis_rows = bottom - top + 1

        def read_rows(y0, count):
            """只读 count 行（从 y0 开始）。整块读 9001 行会失败/被截断。"""
            cnt = max(1, min(count, rows - y0))
            n = cols * cnt
            buf = (ctypes.c_wchar * n)()
            got = wintypes.DWORD(0)
            origin = COORD(0, y0)
            ok = k32.ReadConsoleOutputCharacterW(
                h, buf, n, origin, ctypes.byref(got)
            )
            if not ok:
                err = ctypes.get_last_error()
                raise OSError("ReadConsoleOutputCharacterW failed: err=%d" % err)
            raw = "".join(buf[i] for i in range(got.value))
            out = []
            for r in range(cnt):
                out.append(raw[r * cols : (r + 1) * cols].rstrip())
            return out

        # 可见窗口（优先），失败则退回整个缓冲区
        try:
            lines = read_rows(top, vis_rows)
        except OSError:
            lines = read_rows(0, min(rows, 200))
            vis_rows = len(lines)
        if width:
            lines = [ln[:width] for ln in lines]
        return cols, rows, vis_rows, lines
    finally:
        try:
            k32.CloseHandle(h)
        except Exception:
            pass
        free()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    pid = int(sys.argv[1])
    width = int(sys.argv[2]) if len(sys.argv) > 2 else None
    cols, rows, vrows, lines = screen_text(pid, width)
    print("[probe] pid=%d buffer=%dx%d visible_rows=%d" % (pid, cols, rows, vrows))
    print("-" * 60)
    # 只打印非空行，并保留行号方便定位
    for i, ln in enumerate(lines):
        if ln.strip():
            print("%4d | %s" % (i, ln))
    print("-" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
