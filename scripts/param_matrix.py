# -*- coding: utf-8 -*-
"""
参数研究设计 + Bishop 对照解批量计算。

设计：c-phi 二维矩阵（4x4 = 16）+ 坡角扫描（7 档）+ 坡高扫描（5 档）
Bishop 解析对照解可立即算出，FLAC3D 数值解需驱动软件跑。
"""
import sys, os, json, math, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bishop_final import fos_bishop, SlopeGeometry

OUT = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据"

# ---------- 设计 1：c-phi 二维矩阵 ----------
C_LEVELS = [10e3, 20e3, 30e3, 40e3]     # kPa
PHI_LEVELS = [15.0, 20.0, 25.0, 30.0]   # deg

# ---------- 设计 2：坡角扫描 ----------
THETA_LEVELS = [30.0, 35.0, 40.0, 45.0, 50.0, 55.0, 60.0]

# ---------- 设计 3：坡高扫描 ----------
H_LEVELS = [6.0, 8.0, 10.0, 12.0, 15.0]


def run_cphi():
    print("\n" + "=" * 70)
    print("设计 1：c-phi 二维矩阵（Bishop 解析对照解）")
    print("=" * 70)
    res = []
    print("c(kPa) \\ phi(deg)  " + "".join("%10.1f" % p for p in PHI_LEVELS))
    for c in C_LEVELS:
        row = []
        for phi in PHI_LEVELS:
            r = fos_bishop(H=10.0, theta_deg=45.0, c=c, phi_deg=phi, verbose=False)
            row.append(r["F"] if r else None)
            res.append(dict(H=10.0, theta=45.0, c=c, phi=phi,
                            fos_bishop=r["F"] if r else None,
                            xc=r["xc"] if r else None, yc=r["yc"] if r else None,
                            R=r["R"] if r else None))
        print("%8.1f         " % (c / 1e3) + "".join(
            ("%10.4f" % v) if v else "         -" for v in row))
    return res


def run_theta():
    print("\n" + "=" * 70)
    print("设计 2：坡角扫描（Bishop 解析对照解）")
    print("=" * 70)
    res = []
    print("%8s %12s %10s %10s" % ("theta", "FOS_Bishop", "xc", "R"))
    for th in THETA_LEVELS:
        r = fos_bishop(H=10.0, theta_deg=th, c=30e3, phi_deg=25.0, verbose=False)
        if r:
            print("%8.1f %12.4f %10.2f %10.2f" % (th, r["F"], r["xc"], r["R"]))
            res.append(dict(H=10.0, theta=th, c=30e3, phi=25.0, fos_bishop=r["F"]))
        else:
            print("%8.1f %12s" % (th, "infeasible"))
            res.append(dict(H=10.0, theta=th, c=30e3, phi=25.0, fos_bishop=None))
    return res


def run_height():
    print("\n" + "=" * 70)
    print("设计 3：坡高扫描（Bishop 解析对照解）")
    print("=" * 70)
    res = []
    print("%8s %12s %10s %10s" % ("H", "FOS_Bishop", "xc", "R"))
    for H in H_LEVELS:
        r = fos_bishop(H=H, theta_deg=45.0, c=30e3, phi_deg=25.0, verbose=False)
        if r:
            print("%8.1f %12.4f %10.2f %10.2f" % (H, r["F"], r["xc"], r["R"]))
            res.append(dict(H=H, theta=45.0, c=30e3, phi=25.0, fos_bishop=r["F"]))
        else:
            print("%8.1f %12s" % (H, "infeasible"))
            res.append(dict(H=H, theta=45.0, c=30e3, phi=25.0, fos_bishop=None))
    return res


if __name__ == "__main__":
    t0 = time.time()
    all_res = {}
    all_res["cphi"] = run_cphi()
    all_res["theta"] = run_theta()
    all_res["height"] = run_height()
    p = os.path.join(OUT, "param_bishop.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(all_res, f, ensure_ascii=False, indent=2)
    print("\n已保存: " + p)
    print("总耗时 %.1f 秒" % (time.time() - t0))
