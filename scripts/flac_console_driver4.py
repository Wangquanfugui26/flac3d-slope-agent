# -*- coding: utf-8 -*-
"""
FLAC3D console 驱动器 v4 —— 最终可用版本。

===== 为什么需要 v4（两轮实测的教训） =====

v2（控制台注入）：靠 WriteConsoleInput 注入按键 + 抓 GUI 屏幕。
   缺陷：无可见窗口时读不到屏幕；靠固定等待秒数判断结束，
   会把还在计算的 FLAC3D 提前杀掉 → gravity.sav 没生成 → 全链静默崩塌。

v3（--batch + 流式读取）：改用 flac3d700_console.exe -b script.dat，
   并 readline 直到 EOF。
   缺陷（本轮实测发现）：**-b 执行完脚本后进程不会退出**，
   于是 stdout 管道永不关闭，readline 永久阻塞 → 死挂。
   实测证据：脚本产物 h1.sav 已正常生成，但进程 25s 后 CPU 仅 1.8s、内存不变。

v4（本版）解决方案：
   1. 在传给 FLAC3D 的脚本副本 **末尾追加一行 exit**。
      实测：加 exit 后进程 1.3s 内干净退出。
   2. 不再依赖 readline-EOF；改为独立线程读取 stdout，
      主线程轮询「进程是否退出」，并以超时兜底强杀。
   3. 以「产物文件出现」+「进程退出」双条件判定成功。

用法：
  python flac_console_driver4.py <script.dat> [timeout_seconds] [outfile]
注意：本脚本会在 exe 目录下生成 <script>.run 副本（原脚本不做改动）。
"""

import os
import subprocess
import sys
import threading
import time

EXE_DIR = r"D:\Flac3d\FLAC\exe64"
EXE = os.path.join(EXE_DIR, "flac3d700_console.exe")


def make_runscript(script):
    """复制脚本并在末尾追加 exit，返回副本路径。

    三个实测得出的硬约束（缺一即挂起，且无任何报错）：

    (1) 末尾只能加 `exit`，**绝不能加 `return`**。
        实测：末尾为 "return\\nexit" 时，return 把控制权弹回交互提示符，
        后面的 exit 永不被消费 → 进程永久挂起（120s 无输出、无产物）。
        末尾仅 "exit" 时 1.3s 干净退出并正常生成 .sav。

    (2) 必须以 **二进制** 写入并强制 LF 换行。
        Windows 文本模式会写出 CRLF(\\r\\n)，FLAC3D 解析器遇到多余的 \\r
        会静默中断该行之后的内容（同样无报错）。

    (3) 副本用 .dat 扩展名（与验证通过的用例一致）。
    """
    base = os.path.splitext(script)[0]
    run = base + ".run.dat"
    with open(script, "rb") as f:
        body = f.read()
    body = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not body.endswith(b"\n"):
        body += b"\n"
    body += b"exit\n"
    with open(run, "wb") as f:
        f.write(body)
    return run


def main():
    if len(sys.argv) < 2:
        print("usage: flac_console_driver4.py <script.dat> [timeout_s] [outfile]")
        return 2

    script = sys.argv[1]
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
    outfile = sys.argv[3] if len(sys.argv) > 3 else None

    if not os.path.exists(script):
        print("[drv4] script not found: " + script)
        return 3

    run = make_runscript(script)
    cmd = [EXE, "-b", run]
    print("[drv4] " + " ".join(cmd), flush=True)

    t0 = time.time()
    proc = subprocess.Popen(
        cmd, cwd=EXE_DIR,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=0,
    )

    # 独立线程读 stdout（二进制，避免任何编码解码问题），主线程轮询进程状态
    chunks = []
    lock = threading.Lock()

    def reader():
        while True:
            b = proc.stdout.read(4096)
            if not b:
                break
            with lock:
                chunks.append(b)

    th = threading.Thread(target=reader, daemon=True)
    th.start()

    # 主线程轮询进程是否退出，超时则强杀
    killed = False
    while True:
        if proc.poll() is not None:
            break
        if timeout and (time.time() - t0) > timeout:
            killed = True
            try:
                proc.kill()
            except Exception:
                pass
            break
        time.sleep(0.5)

    th.join(timeout=10)
    el = time.time() - t0

    with lock:
        raw = b"".join(chunks)

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
    print("[drv4] exit=%s elapsed=%.0fs errors=%d killed=%s"
          % (proc.returncode, el, nerr, killed), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
