# -*- coding: utf-8 -*-
"""test_loose.py —— 验证"宽松自平衡判据"能否治住低强度算例。

背景（2026-09-11 实测）：
  c10p15 (c=10 kPa, phi=15 deg) 是本质上不稳定的边坡（Bishop 参照 FOS≈0.70）。
  用 model solve ratio-local 1e-5 做重力自平衡时，ratio 长期在 0.3~0.7 震荡，
  111577 步后仍不收敛 —— 因为不稳定边坡在重力下会持续塑性流动，
  "力平衡"这个目标本身不存在。

本测试对同一算例依次尝试三种判据，比较耗时与收敛情况：
  A) ratio-local 1e-5   （原判据，预期永不收敛 —— 作为对照）
  B) ratio-average 1e-4 （平均不平衡力，对局部震荡不敏感）
  C) cycles 3000        （硬性截断，不看收敛）

判据：B 或 C 能在可接受时间内结束并正常 save，即说明解耦方案可行。
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

# 复用生成器建模，但把 solve 那一行替换掉
CID = "loose_c10p15"


def build_variant(solve_line):
    """用 gen_param_case2 生成基础脚本，再把 solve 行换成 solve_line。"""
    r = subprocess.run([PY, GEN, CID, "10", "45", "10", "15"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("gen failed: " + (r.stderr or "")[-400:])
    base = os.path.join(CASES, "p_%s_stage1.dat" % CID)

    # 注意：生成器里 solve 行是 'model solve ratio-local 1e-5'
    src = open(base, "rb").read().decode("ascii", errors="replace")
    src = src.replace("model solve ratio-local 1e-5", solve_line)
    # 日志文件重命名，避免互相覆盖
    tag = re.sub(r"[^a-z0-9]+", "_", solve_line.lower())[-24:]
    src = src.replace("p_%s_s1.log" % CID, "p_%s_%s_s1.log" % (CID, tag))
    out = os.path.join(CASES, "p_%s_%s_stage1.dat" % (CID, tag))
    open(out, "wb").write(src.encode("ascii"))
    return out, tag


def run(dat, timeout):
    of = os.path.join(LOG, "loose_" + os.path.basename(dat).replace(".dat", "") + ".txt")
    if os.path.exists(of):
        os.remove(of)
    t0 = time.time()
    subprocess.run([PY, DRV, dat, str(timeout), of], capture_output=True)
    el = time.time() - t0
    txt = open(of, "rb").read().decode("gbk", errors="replace") if os.path.exists(of) else ""
    rows = re.findall(r"(\d+)\s+(\d+)\s+1\.00000e\+00\s+([\d.eE+-]+)", txt)
    ncyc = int(rows[-1][1]) if rows else 0
    lastratio = rows[-1][2] if rows else "-"
    nerr = sum(1 for ln in txt.splitlines() if ln.strip().startswith("***"))
    saved = "Model saved to file" in txt
    return el, ncyc, lastratio, nerr, saved


def main():
    print("=" * 74)
    print("宽松自平衡判据测试 —— 算例 c=10 kPa, phi=15 deg (本质不稳定)")
    print("=" * 74)
    tests = [
        ("A) ratio-local 1e-5（对照，预期失败）", "model solve ratio-local 1e-5", 420),
        ("B) ratio-average 1e-4", "model solve ratio-average 1e-4", 900),
        ("C) cycles 3000（硬截断）", "model solve cycles 3000", 900),
    ]
    for label, line, to in tests:
        dat, tag = build_variant(line)
        print("\n--- %s ---" % label)
        el, ncyc, lr, nerr, saved = run(dat, to)
        print("  耗时=%.0fs  末步号=%d  末ratio=%s  ***=%d  .sav=%s"
              % (el, ncyc, lr, nerr, "有" if saved else "无"))
        verdict = "收敛/正常结束" if saved else "未收敛（被超时截断）"
        print("  判定: " + verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
