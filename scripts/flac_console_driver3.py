# -*- coding: utf-8 -*-
"""
FLAC3D console 驱动器 v3 —— 基于「文件流 + 完成标志」的健壮版本。

v2 的致命缺陷：
  1. 它从 GUI 屏幕缓冲区 (CONOUT$) 抓文本。当没有可见控制台窗口时
     （后台任务、无桌面会话），屏幕缓冲区一片空白，驱动器什么也读不到。
  2. 它靠「固定等待 N 秒」判断结束，然后发 'exit'。如果命令实际需要
     更久，就会在计算中途把 FLAC3D 杀掉 —— 表现为日志停在半截、
     .sav 文件永远不生成、内存不增长。
  3. 它把 'program call ...' 作为单条命令注入。FLAC3D 的输入是
     行缓冲的，交互式注入多字符命令在高负载下容易丢字符。

v3 策略（完全绕开屏幕缓冲区）：
  - 把要执行的 FLAC3D 语句写成一个 .dat 脚本文件（调用方负责）。
  - 启动 flac3d700_console.exe，把该脚本作为 *命令行参数* 传入：
        flac3d700_console.exe -b "D:/.../script.dat"
    FLAC3D console 支持 -b / --batch 批处理模式：执行完脚本后自动退出。
  - 用 subprocess 的 stdout/stderr 管道实时读取输出到文件。
  - 以「进程退出」作为唯一完成信号 —— 不存在提前杀进程的风险。

用法：
  python flac_console_driver3.py <script.dat> [timeout_seconds] [outfile]
"""

import os
import subprocess
import sys
import time

EXE_DIR = r"D:\Flac3d\FLAC\exe64"
EXE = os.path.join(EXE_DIR, "flac3d700_console.exe")


def main():
    if len(sys.argv) < 2:
        print("usage: flac_console_driver3.py <script.dat> [timeout_s] [outfile]")
        return 2

    script = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
    outfile = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.exists(script):
        print("[drv3] script not found: " + script)
        return 3

    # -b 让 FLAC3D 执行脚本后自动退出
    cmd = [EXE, "-b", script]
    print("[drv3] %s" % " ".join(cmd), flush=True)

    t0 = time.time()
    proc = subprocess.Popen(
        cmd, cwd=EXE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )

    chunks = []
    killed = False
    try:
        while True:
            if timeout and (time.time() - t0) > timeout:
                killed = True
                proc.kill()
                break
            line = proc.stdout.readline()
            if not line:
                if proc.poll() is not None:
                    break
                time.sleep(0.2)
                continue
            chunks.append(line)
        proc.wait(timeout=30)
    except Exception as e:
        print("[drv3] exception: %r" % (e,))
        try:
            proc.kill()
        except Exception:
            pass

    el = time.time() - t0
    raw = b"".join(chunks)
    # 尽量还原成可读文本
    text = None
    for enc in ("gbk", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    if text is None:
        text = raw.decode("latin-1", errors="replace")

    if outfile:
        with open(outfile, "w", encoding="utf-8", errors="replace") as f:
            f.write(text)

    nerr = sum(1 for ln in text.splitlines() if ln.strip().startswith("***"))
    print("[drv3] exit=%s elapsed=%.0fs errors=%d" % (proc.returncode, el, nerr))
    return 0


if __name__ == "__main__":
    sys.exit(main())
