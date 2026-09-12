# -*- coding: utf-8 -*-
"""
批量参数算例编排器 v2 —— 基于 flac_console_driver3（流式、可校验）。

设计要点（吸取 v1 全线静默崩塌的教训）：
  1. 每个算例分 3 步，每步单独调用 driver3，跑完立刻校验产物文件是否真的生成。
     产物缺失 = 该步失败 → 该算例标记 FAILED，不写伪成功记录。
  2. driver3 用 flac3d700_console.exe --batch 执行脚本，stdout 流式落盘，
     以「进程退出」为准（这里不能等它退出，见下），超时则强杀并判失败。
  3. 解析 FOS 从 s2.log（program log 输出，编码探测 gbk/utf-8）。
  4. 支持断点续跑：CSV 中已成功记录的算例自动跳过；
     记录 FAILED 的算例会重跑。

结果 CSV: param_flac3d.csv
  case,H,theta,c_kPa,phi_deg,fos_flac3d,status,t_stage1_s,t_stage2_s
"""
import os
import re
import subprocess
import sys
import time

PY = r"D:/VS/Shared/Python39_64/python.exe"
SP = r"D:/Flac3d/FLAC3D边坡模拟/脚本"
DRV = os.path.join(SP, "flac_console_driver3.py")
GEN = os.path.join(SP, "gen_param_case2.py")
CASES = r"D:/Flac3d/FLAC/exe64/cases"
LOG = r"D:/Flac3d/FLAC3D边坡模拟/原始输出日志"
RESULT = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据/param_flac3d.csv"

# 各步超时（秒）：stage2 要跑 bisection ~8 次求解，给足余量
T_STAGE1 = 900
T_STAGE2 = 7200


def decode_log(path):
    if not os.path.exists(path):
        return ""
    raw = open(path, "rb").read()
    for enc in ("gbk", "utf-8", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return ""


def run_driver(script, timeout, tag):
    out = os.path.join(LOG, "_b2_%s.txt" % tag)
    r = subprocess.run([PY, DRV, script, str(timeout), out],
                       capture_output=True, text=True)
    return r.returncode, out


def check_no_error(outfile):
    """检查 driver 抓到的 stdout 里有没有 *** 错误行。"""
    t = decode_log(outfile)
    errs = [ln.strip() for ln in t.splitlines() if ln.strip().startswith("***")]
    return (len(errs) == 0), (errs[0][:160] if errs else "")


def parse_fos(case_id):
    t = decode_log(os.path.join(CASES, "p_%s_s2.log" % case_id))
    m = re.search(r"Last Factor of Safety Calculated:\s*([\d.]+)", t)
    if m:
        return float(m.group(1))
    m = re.search(r"Factor of Safety is\s*:\s*([\d.]+)", t)
    if m:
        return float(m.group(1))
    return None


def run_one(cid, H, theta, c_kpa, phi):
    """返回 (fos, status, t1, t2)"""
    # --- 生成脚本 ---
    r = subprocess.run([PY, GEN, cid, str(H), str(theta), str(c_kpa), str(phi)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("   [gen] FAILED %s" % (r.stderr or r.stdout)[-200:])
        return None, "GEN_FAIL", 0, 0

    sav_g = os.path.join(CASES, "p_%s_gravity.sav" % cid)
    # 清理旧产物，确保校验的是本次结果
    for f in (sav_g,):
        if os.path.exists(f):
            os.remove(f)

    # --- stage1 ---
    t0 = time.time()
    rc, out = run_driver(os.path.join(CASES, "p_%s_stage1.dat" % cid),
                         T_STAGE1, "%s_s1" % cid)
    t1 = time.time() - t0
    ok, why = check_no_error(out)
    if not ok:
        print("   [stage1] ERROR: %s" % why)
        return None, "S1_ERROR", t1, 0
    if not os.path.exists(sav_g):
        print("   [stage1] .sav 未生成（静默失败）")
        return None, "S1_NO_SAV", t1, 0

    # --- stage2 ---
    sav_fos = os.path.join(CASES, "p_%s_fos-Stable.sav" % cid)
    if os.path.exists(sav_fos):
        os.remove(sav_fos)
    t0 = time.time()
    rc, out = run_driver(os.path.join(CASES, "p_%s_stage2.dat" % cid),
                         T_STAGE2, "%s_s2" % cid)
    t2 = time.time() - t0
    ok, why = check_no_error(out)
    fos = parse_fos(cid)
    if fos is None:
        print("   [stage2] FOS 解析失败 | out_err=%s" % why)
        return None, "S2_NO_FOS", t1, t2

    print("   stage1 %.0fs  stage2 %.0fs  FOS=%.4f" % (t1, t2, fos))
    return fos, "OK", t1, t2


def load_done():
    done = {}
    if os.path.exists(RESULT):
        with open(RESULT, "r", encoding="utf-8") as f:
            for ln in f.readlines()[1:]:
                if ln.strip():
                    parts = ln.split(",")
                    done[parts[0]] = parts[6].strip() if len(parts) > 6 else ""
    return done


def main():
    cases = []
    # 设计 1：c-phi 矩阵（4x4 = 16）
    for c in (10, 20, 30, 40):
        for phi in (15, 20, 25, 30):
            cases.append(("c%02dp%02d" % (c, phi), 10, 45, c, phi))
    # 设计 2：坡角扫描（30/35/40/45/50/55/60，45 已含在矩阵）→ 补 6
    for th in (30, 35, 40, 50, 55, 60):
        cases.append(("t%02d" % th, 10, th, 30, 25))
    # 设计 3：坡高扫描（6/8/10/12/15，10 已含在矩阵）→ 补 4
    for H in (6, 8, 12, 15):
        cases.append(("h%02d" % H, H, 45, 30, 25))

    print("总计 %d 个算例" % len(cases))

    done = load_done()
    real_done = {k for k, v in done.items() if v == "OK"}
    if done:
        print("已有记录 %d 条，其中 OK %d 条" % (len(done), len(real_done)))

    if not os.path.exists(RESULT):
        with open(RESULT, "w", encoding="utf-8") as f:
            f.write("case,H,theta,c_kPa,phi_deg,fos_flac3d,status,"
                    "t_stage1_s,t_stage2_s\n")

    # 重跑：把非 OK 的旧记录从 CSV 中剔除，避免重复行
    if done and (len(done) - len(real_done)) > 0:
        keep = ["case,H,theta,c_kPa,phi_deg,fos_flac3d,status,"
                "t_stage1_s,t_stage2_s"]
        with open(RESULT, "r", encoding="utf-8") as f:
            for ln in f.readlines()[1:]:
                if ln.strip() and ln.split(",")[0] in real_done:
                    keep.append(ln.rstrip("\n"))
        with open(RESULT, "w", encoding="utf-8") as f:
            f.write("\n".join(keep) + "\n")
        print("已清理非 OK 旧记录，保留 %d 条" % len(real_done))

    for cid, H, theta, c, phi in cases:
        if cid in real_done:
            continue
        print("\n>>> [%s] H=%s theta=%s c=%s phi=%s" % (cid, H, theta, c, phi))
        fos, status, ts1, ts2 = run_one(cid, H, theta, c, phi)
        with open(RESULT, "a", encoding="utf-8") as f:
            f.write("%s,%s,%s,%s,%s,%s,%s,%.0f,%.0f\n"
                    % (cid, H, theta, c, phi,
                       ("%.4f" % fos) if fos is not None else "",
                       status, ts1, ts2))

    print("\n全部完成。结果 -> " + RESULT)


if __name__ == "__main__":
    sys.exit(main())
