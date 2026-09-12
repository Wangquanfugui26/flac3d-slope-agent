# -*- coding: utf-8 -*-
"""
关键算例验证（3 例）—— 用修正后的管道重跑，并与 Bishop 解交叉校验。

三例设计意图：
  base45  : c=30 kPa, phi=25 deg, H=10, theta=45
            —— 与最初手工完成、已逐位复核的基准算例相同，
               已知 SSR 真值 FOS = 1.685。这是回溯检查（回溯检验管道正确性）。
  c10p15  : c=10 kPa, phi=15 deg, H=10, theta=45
            —— 验证「低强度 → 低 FOS」单侧极端。
  t60     : c=30 kPa, phi=25 deg, H=10, theta=60
            —— 验证「陡坡 → 低 FOS」，与 base45 共享强度参数，
               仅几何不同，是干净的几何敏感性对照。

判据：FLAC3D SSR 与 Bishop 简化法应为 FLAC3D 略高（+3%~+8%）。
若出现 |偏差| > 15% 或 FOS < 1，判为管道异常。
"""
import os
import re
import subprocess
import sys
import time

PY = r"D:/VS/Shared/Python39_64/python.exe"
SP = r"D:/Flac3d/FLAC3D边坡模拟/脚本"
DRV = os.path.join(SP, "flac_console_driver4.py")
GEN = os.path.join(SP, "gen_param_case2.py")
CASES = r"D:/Flac3d/FLAC/exe64/cases"
LOG = r"D:/Flac3d/FLAC3D边坡模拟/原始输出日志"

# 三例：(id, H, theta, c_kPa, phi_deg)
PICKS = [
    ("base45", 10, 45, 30, 25),   # 已知真值 1.685
    ("c10p15", 10, 45, 10, 15),   # 低强度极端
    ("t60",    10, 60, 30, 25),   # 陡坡极端
]

T_S1 = 1200
T_S2 = 10800


def dec(p):
    if not os.path.exists(p):
        return ""
    raw = open(p, "rb").read()
    for e in ("gbk", "utf-8", "latin-1"):
        try:
            return raw.decode(e)
        except Exception:
            pass
    return ""


def show(p, n, label):
    t = dec(p)
    lines = t.splitlines()
    print("----- %s (%d 行, 显示末 %d 行) -----" % (label, len(lines), n))
    for ln in lines[-n:]:
        print("  " + ln)


def run_step(cid, step, timeout):
    dat = os.path.join(CASES, "p_%s_%s.dat" % (cid, step))
    out = os.path.join(LOG, "v2_%s_%s.txt" % (cid, step))
    if os.path.exists(out):
        os.remove(out)
    t0 = time.time()
    r = subprocess.run([PY, DRV, dat, str(timeout), out],
                       capture_output=True, text=True)
    return time.time() - t0, out


def main():
    print("=" * 78)
    print("关键算例验证 —— 3 例")
    print("=" * 78)

    results = []
    for cid, H, th, c, phi in PICKS:
        print("\n" + "#" * 78)
        print("# [%s]  H=%s  theta=%s  c=%s kPa  phi=%s deg" % (cid, H, th, c, phi))
        print("#" * 78)

        r = subprocess.run([PY, GEN, cid, str(H), str(th), str(c), str(phi)],
                           capture_output=True, text=True)
        print(r.stdout.strip())
        if r.returncode != 0:
            print("生成失败: " + (r.stderr or "")[-300:])
            results.append((cid, None, "GEN_FAIL"))
            continue

        # 清旧产物
        for suf in ("_gravity.sav", "_fos-Stable.sav", "_fos-Unstable.sav",
                    "_fos-Init.sav"):
            f = os.path.join(CASES, "p_%s%s" % (cid, suf))
            if os.path.exists(f):
                os.remove(f)

        # --- stage1 ---
        el1, o1 = run_step(cid, "stage1", T_S1)
        sav = os.path.join(CASES, "p_%s_gravity.sav" % cid)
        ok1 = os.path.exists(sav)
        print("  [stage1] %.0fs  gravity.sav=%s" % (el1, "有" if ok1 else "【缺失】"))
        show(o1, 12, "stage1 输出")
        if not ok1:
            results.append((cid, None, "S1_NO_SAV"))
            continue

        # --- stage2 ---
        el2, o2 = run_step(cid, "stage2", T_S2)
        t2 = dec(os.path.join(CASES, "p_%s_s2.log" % cid))
        m = re.search(r"Last Factor of Safety Calculated:\s*([\d.]+)", t2)
        if not m:
            m = re.search(r"Factor of Safety is\s*:\s*([\d.]+)", t2)
        fos = float(m.group(1)) if m else None
        print("  [stage2] %.0fs  FOS=%s" % (el2, fos))
        show(o2, 14, "stage2 输出")
        results.append((cid, fos, "OK" if fos else "S2_NO_FOS"))

    # ---------------- 汇总 ----------------
    print("\n" + "=" * 78)
    print("汇总")
    print("=" * 78)
    print("%-10s %-12s %-12s %-10s %s" % ("case", "FLAC3D", "Bishop", "偏差", "状态"))
    for cid, fos, st in results:
        print("%-10s %-12s %-12s %-10s %s"
              % (cid, fos if fos else "-", "(待算)", "-", st))

    print("\n预期：base45 应 ≈ 1.685（已知真值）；三项均应 1.0~2.2，")
    print("     且 FLAC3D 略高于 Bishop 3%~8%。")


if __name__ == "__main__":
    sys.exit(main())
