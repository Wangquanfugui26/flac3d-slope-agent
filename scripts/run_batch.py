# -*- coding: utf-8 -*-
"""
批量运行参数算例的编排器。

流程（每算例）：
  1. gen_param_case.py 生成 stage1.dat / stage2.dat
  2. 调 flac_console_driver2.py 跑 stage1（建模+自重，约 15s + 开销）
  3. 调 flac_console_driver2.py 跑 stage2（SSR，约 300s + 开销）
  4. 从 p_<id>_s2.log 解析 FOS，追加到结果 CSV

支持断点续跑：已完成的算例（结果已在 CSV 中）自动跳过。
"""
import os
import re
import subprocess
import sys
import time

PY = r"D:/VS/Shared/Python39_64/python.exe"
SP = r"D:/Flac3d/FLAC3D边坡模拟/脚本"
DRV = os.path.join(SP, "flac_console_driver2.py")
GEN = os.path.join(SP, "gen_param_case.py")
CASES = r"D:/Flac3d/FLAC/exe64/cases"
LOG = r"D:/Flac3d/FLAC3D边坡模拟/原始输出日志"
RESULT = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据/param_flac3d.csv"


def decode_log(path):
    raw = open(path, "rb").read()
    for enc in ("gbk", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return ""


def check_s1_ok(case_id):
    """校验 stage1 是否真正成功（防止 C2/C3 类静默失败被当成成功）。

    必须同时满足：
      - 日志里没有 '*** ' 开头的 FLAC3D 错误行
      - 日志里出现 'Model saved to file'（即走到了 model save）
    """
    p = os.path.join(CASES, "p_%s_s1.log" % case_id)
    if not os.path.exists(p):
        return False, "no log"
    t = decode_log(p)
    errs = [ln.strip() for ln in t.splitlines() if ln.strip().startswith("***")]
    if errs:
        return False, errs[0][:120]
    if "Model saved to file" not in t:
        return False, "no 'Model saved' marker"
    return True, "ok"


def parse_fos(case_id):
    p = os.path.join(CASES, "p_%s_s2.log" % case_id)
    if not os.path.exists(p):
        return None
    t = decode_log(p)
    m = re.search(r"Last Factor of Safety Calculated:\s*([\d.]+)", t)
    if m:
        return float(m.group(1))
    m = re.search(r"Factor of Safety is\s*:\s*([\d.]+)", t)
    if m:
        return float(m.group(1))
    return None


def run_one(case_id, H, theta, c_kpa, phi, retries=2):
    # 生成脚本
    r = subprocess.run([PY, GEN, case_id, str(H), str(theta),
                        str(c_kpa), str(phi)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("  [gen] FAILED: " + (r.stderr or "")[-300:])
        return None, -1, -1

    # stage 1（含重试：Illegal geometry 是非确定性故障）
    t1 = 0.0
    for attempt in range(retries + 1):
        t0 = time.time()
        o1 = os.path.join(LOG, "_batch_%s_s1.txt" % case_id)
        subprocess.run([PY, DRV,
                        'program call "%s/p_%s_stage1.dat"' % (CASES, case_id),
                        "150", o1], capture_output=True, text=True)
        t1 = time.time() - t0
        ok, why = check_s1_ok(case_id)
        if ok:
            break
        print("  [stage1 第%d次失败] %s" % (attempt + 1, why))
    else:
        return None, t1, -1

    # stage 2
    t0 = time.time()
    o2 = os.path.join(LOG, "_batch_%s_s2.txt" % case_id)
    subprocess.run([PY, DRV,
                    'program call "%s/p_%s_stage2.dat"' % (CASES, case_id),
                    "600", o2], capture_output=True, text=True)
    t2 = time.time() - t0

    fos = parse_fos(case_id)
    print("  stage1 %.0fs  stage2 %.0fs  FOS=%s" % (t1, t2, fos))
    return fos, t1, t2


def main():
    cases = []
    # ---- 设计 1：c-phi 矩阵（16 例）----
    for c in (10, 20, 30, 40):
        for phi in (15, 20, 25, 30):
            cases.append(("c%02dp%02d" % (c, phi), 10, 45, c, phi))
    # ---- 设计 2：坡角扫描（7 例，45 度与矩阵重复故只跑 6 个新值）----
    for th in (30, 35, 40, 50, 55, 60):
        cases.append(("t%02d" % th, 10, th, 30, 25))
    # ---- 设计 3：坡高扫描（5 例，H=10 与矩阵重复故只跑 4 个新值）----
    for H in (6, 8, 12, 15):
        cases.append(("h%02d" % H, H, 45, 30, 25))

    print("总计 %d 个算例待跑" % len(cases))

    done = set()
    if os.path.exists(RESULT):
        with open(RESULT, "r", encoding="utf-8") as f:
            for line in f.readlines()[1:]:
                if line.strip():
                    done.add(line.split(",")[0])
        print("已完成的算例：%d 个（跳过）" % len(done))

    if not os.path.exists(RESULT):
        with open(RESULT, "w", encoding="utf-8") as f:
            f.write("case,H,theta,c_kPa,phi_deg,fos_flac3d,t_stage1_s,t_stage2_s\n")

    for cid, H, theta, c, phi in cases:
        if cid in done:
            continue
        print("\n>>> [%s] H=%s theta=%s c=%s phi=%s" % (cid, H, theta, c, phi))
        t0 = time.time()
        fos, ts1, ts2 = run_one(cid, H, theta, c, phi)
        el = time.time() - t0
        with open(RESULT, "a", encoding="utf-8") as f:
            f.write("%s,%s,%s,%s,%s,%s,%.0f,%.0f\n"
                    % (cid, H, theta, c, phi, fos, ts1, ts2))
        print("  完成，用时 %.0f s" % el)


if __name__ == "__main__":
    main()
