"""
FLAC3D console 驱动器 v2：附加到 console 后，读取其屏幕缓冲区内容。

关键改进：用 ReadConsoleOutputCharacterW 抓取控制台屏幕文本，
可以看到 FLAC3D 的真实输出，不依赖 program log-file。
"""

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time
import os

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
OPEN_EXISTING = 3
CREATE_NEW_CONSOLE = 0x00000010
KEY_EVENT = 0x0001
VK_RETURN = 0x0D

kernel32.CreateFileW.restype = wt.HANDLE
kernel32.CreateFileW.argtypes = [
    wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p,
    wt.DWORD, wt.DWORD, wt.HANDLE,
]
kernel32.WriteConsoleInputW.restype = wt.BOOL
kernel32.WriteConsoleInputW.argtypes = [
    wt.HANDLE, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD),
]


class COORD(ctypes.Structure):
    _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]


kernel32.ReadConsoleOutputCharacterW.restype = wt.BOOL
kernel32.ReadConsoleOutputCharacterW.argtypes = [
    wt.HANDLE, wt.LPWSTR, wt.DWORD, COORD, ctypes.POINTER(wt.DWORD),
]
kernel32.GetConsoleScreenBufferInfo.restype = wt.BOOL
kernel32.GetConsoleScreenBufferInfo.argtypes = [wt.HANDLE, ctypes.c_void_p]
kernel32.FreeConsole.restype = wt.BOOL
kernel32.AttachConsole.restype = wt.BOOL
kernel32.AttachConsole.argtypes = [wt.DWORD]
kernel32.SetConsoleCursorPosition.restype = wt.BOOL
kernel32.SetConsoleCursorPosition.argtypes = [wt.HANDLE, COORD]


class SMALL_RECT(ctypes.Structure):
    _fields_ = [
        ("Left", ctypes.c_short), ("Top", ctypes.c_short),
        ("Right", ctypes.c_short), ("Bottom", ctypes.c_short),
    ]


class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
    _fields_ = [
        ("dwSize", COORD), ("dwCursorPosition", COORD),
        ("wAttributes", wt.WORD), ("srWindow", SMALL_RECT),
        ("dwMaximumWindowSize", COORD),
    ]


class CHAR_UNION(ctypes.Union):
    _fields_ = [("UnicodeChar", ctypes.c_wchar), ("AsciiChar", ctypes.c_char)]


class KEY_EVENT_RECORD(ctypes.Structure):
    _fields_ = [
        ("bKeyDown", wt.BOOL), ("wRepeatCount", wt.WORD),
        ("wVirtualKeyCode", wt.WORD), ("wVirtualScanCode", wt.WORD),
        ("uChar", CHAR_UNION), ("dwControlKeyState", wt.DWORD),
    ]


class EVENT_UNION(ctypes.Union):
    _fields_ = [("KeyEvent", KEY_EVENT_RECORD), ("pad", ctypes.c_byte * 16)]


class INPUT_RECORD(ctypes.Structure):
    _fields_ = [("EventType", wt.WORD), ("Event", EVENT_UNION)]


def _char_rec(ch, down):
    r = INPUT_RECORD()
    r.EventType = KEY_EVENT
    k = r.Event.KeyEvent
    k.bKeyDown = down
    k.wRepeatCount = 1
    k.uChar.UnicodeChar = ch
    return r


def send_line(handle, text):
    recs = []
    for ch in text:
        recs.append(_char_rec(ch, True))
        recs.append(_char_rec(ch, False))
    r = INPUT_RECORD()
    r.EventType = KEY_EVENT
    k = r.Event.KeyEvent
    k.bKeyDown = True
    k.wRepeatCount = 1
    k.wVirtualKeyCode = VK_RETURN
    k.wVirtualScanCode = 0x1C
    k.uChar.UnicodeChar = "\r"
    recs.append(r)
    r2 = INPUT_RECORD()
    r2.EventType = KEY_EVENT
    k2 = r2.Event.KeyEvent
    k2.bKeyDown = False
    k2.wRepeatCount = 1
    k2.wVirtualKeyCode = VK_RETURN
    k2.wVirtualScanCode = 0x1C
    k2.uChar.UnicodeChar = "\r"
    recs.append(r2)
    arr = (INPUT_RECORD * len(recs))(*recs)
    written = wt.DWORD(0)
    return kernel32.WriteConsoleInputW(
        handle, ctypes.byref(arr), len(recs), ctypes.byref(written)
    )


def read_screen(h_out, max_lines=200):
    """读取控制台屏幕缓冲区文本。"""
    info = CONSOLE_SCREEN_BUFFER_INFO()
    if not kernel32.GetConsoleScreenBufferInfo(h_out, ctypes.byref(info)):
        return None
    width = info.dwSize.X
    height = info.dwSize.Y
    n = width * height
    buf = ctypes.create_unicode_buffer(n + 1)
    got = wt.DWORD(0)
    origin = COORD(0, 0)
    if not kernel32.ReadConsoleOutputCharacterW(
        h_out, buf, n, origin, ctypes.byref(got)
    ):
        return None
    text = buf[: got.value]
    lines = []
    for i in range(0, len(text), width):
        lines.append(text[i:i + width].rstrip())
    # 去掉尾部空行
    while lines and not lines[-1]:
        lines.pop()
    return lines[-max_lines:]


def main():
    exe_dir = r"D:\Flac3d\FLAC\exe64"
    exe = os.path.join(exe_dir, "flac3d700_console.exe")

    if len(sys.argv) < 2:
        print("usage: flac_console_driver2.py <command> [wait_seconds] [outfile]")
        return 2

    cmd = sys.argv[1]
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    outfile = sys.argv[3] if len(sys.argv) > 3 else None

    proc = subprocess.Popen([exe], cwd=exe_dir, creationflags=CREATE_NEW_CONSOLE)
    print(f"[drv] pid={proc.pid}", flush=True)
    time.sleep(8)

    kernel32.FreeConsole()
    time.sleep(0.5)
    if not kernel32.AttachConsole(proc.pid):
        print(f"[drv] AttachConsole failed: {ctypes.get_last_error()}", flush=True)
        proc.kill()
        return 1

    h_in = kernel32.CreateFileW(
        "CONIN$", GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None,
    )
    h_out = kernel32.CreateFileW(
        "CONOUT$", GENERIC_READ | GENERIC_WRITE,
        FILE_SHARE_READ | FILE_SHARE_WRITE, None, OPEN_EXISTING, 0, None,
    )
    print("[drv] attached", flush=True)

    print(f"[drv] sending: {cmd!r}", flush=True)
    send_line(h_in, cmd)

    # 轮询屏幕，直到出现完成标志或超时
    deadline = time.time() + wait
    last_snapshot = []
    while time.time() < deadline:
        time.sleep(4)
        snap = read_screen(h_out)
        if snap:
            last_snapshot = snap
        if proc.poll() is not None:
            break

    text = "\n".join(last_snapshot)
    print("=" * 60)
    print("[drv] SCREEN OUTPUT:")
    print(text)
    print("=" * 60)

    if outfile:
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(text)

    if proc.poll() is None:
        send_line(h_in, "exit")
        time.sleep(3)
        if proc.poll() is None:
            proc.kill()

    kernel32.FreeConsole()
    print("[drv] done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
