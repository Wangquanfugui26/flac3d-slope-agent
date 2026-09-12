# -*- coding: utf-8 -*-
"""
机理分析 A：沿滑面的应力路径 + 强度发挥度

物理背景：
  边坡失稳的本质是滑面上某点的剪应力达到 Mohr-Coulomb 强度。
  定义强度发挥度（mobilization ratio）：
      mob = tau_max / tau_f
      tau_max = sqrt( ((syy-sxx)/2)^2 + sxy^2 )     （平面应变最大剪应力）
      tau_f   = c + sigma_n * tan(phi)
      sigma_n = (sxx+syy)/2                          （滑面法向应力近似）
  mob -> 1 表示该点达到强度极限。

  同时计算安全裕度 1-mob，并沿滑面给出分布曲线。
"""
import csv, os
import numpy as np

DATA = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据"
C0 = 30e3
PHI0 = 25.0
PHI = np.radians(PHI0)


def load_tensor(path):
    cols = {k: [] for k in ("x", "y", "z", "ux", "uy", "uz", "state",
                            "sxx", "syy", "szz", "sxy", "sxz", "syz")}
    keys = list(cols.keys())
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        rd = csv.reader(f)
        next(rd, None)
        for r in rd:
            if len(r) < 13:
                continue
            try:
                v = [float(t) for t in r[:13]]
            except ValueError:
                continue
            for k, vv in zip(keys, v):
                cols[k].append(vv)
    return {k: np.array(v) for k, v in cols.items()}


def compute(d):
    """计算每个单元的 tau_max, sigma_n, tau_f, mob。"""
    sxx, syy, sxy = d["sxx"], d["syy"], d["sxy"]
    # 平面应变最大剪应力（在 x-y 平面内）
    taumax = np.sqrt(((syy - sxx) / 2.0) ** 2 + sxy ** 2)
    # 平均正应力
    sig_n = (sxx + syy) / 2.0
    # 压为正
    sn_pos = -sig_n
    tau_f = C0 + sn_pos * np.tan(PHI)
    mob = np.where(tau_f > 1.0, taumax / tau_f, 0.0)
    return taumax, sig_n, tau_f, mob


def main():
    p = os.path.join(DATA, "slope_gravity.csv")
    print("注意：原始 CSV 仅含 szz/sxy，不足以算完整张量。")
    print("      需使用新导出的 tensor_base45.csv（含完整 6 分量）。")
    print("")
    print("本脚本用于 tensor_base45.csv：")

    pt = r"D:/Flac3d/FLAC/exe64/tensor_base45.csv"
    if not os.path.exists(pt):
        print("  未找到 " + pt)
        return
    d = load_tensor(pt)
    print("  载入 %d 个单元" % len(d["x"]))

    taumax, sig_n, tau_f, mob = compute(d)
    st = d["state"].astype(int)
    BIT_SN, BIT_TN, BIT_SP, BIT_TP = 1, 2, 4, 8
    shear_n = (st & BIT_SN) != 0
    tension_n = (st & BIT_TN) != 0
    anyp = (st != 0)

    print("\n=== 强度发挥度 mob = tau_max / tau_f ===")
    for label, m in [("全域", np.ones_like(mob, bool)),
                     ("剪切破坏", shear_n),
                     ("拉伸破坏", tension_n),
                     ("任意屈服", anyp)]:
        if m.sum():
            print("  %-8s n=%5d  mean=%.3f  p50=%.3f  p95=%.3f  max=%.3f"
                  % (label, m.sum(), mob[m].mean(),
                     np.percentile(mob[m], 50), np.percentile(mob[m], 95),
                     mob[m].max()))

    print("\n=== 关键物理检验：mob 是否在剪切破坏区接近 1.0 ===")
    if shear_n.sum():
        print("  剪切破坏单元的 mob：%.3f ~ %.3f (均值 %.3f)"
              % (mob[shear_n].min(), mob[shear_n].max(), mob[shear_n].mean()))
        print("  预期：应接近或等于 1.0（已达强度极限）")

    print("\n=== 沿滑面（剪切带）的应力路径 ===")
    # 按 x 分箱，取剪切带的平均应力状态
    x = d["x"]
    bins = np.arange(0.5, 30.0, 2.0)
    print("  x(m)   n   sig_n(kPa)  tau_max(kPa)  tau_f(kPa)   mob")
    for xb in bins:
        m = shear_n & (np.abs(x - xb) < 1.0)
        if m.sum() >= 2:
            print("  %5.1f %4d  %10.1f  %12.1f  %10.1f  %6.3f"
                  % (xb, m.sum(), -sig_n[m].mean() / 1e3,
                     taumax[m].mean() / 1e3, tau_f[m].mean() / 1e3,
                     mob[m].mean()))

    np.save(os.path.join(DATA, "_mob_taumax.npy"), taumax)
    np.save(os.path.join(DATA, "_mob_sigman.npy"), sig_n)
    np.save(os.path.join(DATA, "_mob_ratio.npy"), mob)
    print("\n已保存中间量供绘图")


if __name__ == "__main__":
    main()
