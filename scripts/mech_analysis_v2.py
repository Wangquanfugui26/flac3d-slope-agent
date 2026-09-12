# -*- coding: utf-8 -*-
"""
机理分析 v2 —— 基于修正后的认知：

认知修正 1：zone.state 是【屈服历史记忆】，shear-p 不代表当前塑性。
            shear-n/tension-n 才是"当前屈服"。
认知修正 2：fos-Unstable 是全模型崩溃态（2670/2670 全破坏），
            不能用于滑面识别。滑面应从 fos-Stable（临界态）的
            屈服带（shear-p 带）提取。
认知修正 3：FLAC3D 里 y 是竖向（模型设置 y 为竖直），σyy 是竖向应力；
            σzz 是厚度方向应力。原 CSV 导出的是 szz，用错了分量。

分析内容：
  A. 滑面几何定量识别（从稳定态屈服带）+ 圆/对数螺旋拟合对比
  B. 强度发挥度 mob 分布（用完整张量）
  C. 张量 vs 稳定态的一致性核验
"""
import csv, os, math
import numpy as np

DATA = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据"
KEYS = ("x","y","z","ux","uy","uz","state","sxx","syy","szz","sxy","sxz","syz")
C0, PHI0 = 30e3, 25.0
PHI = math.radians(PHI0)


def load(path):
    cols = {k: [] for k in KEYS}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        rd = csv.reader(f); next(rd, None)
        for r in rd:
            if len(r) < 13:
                continue
            try:
                v = [float(t) for t in r[:13]]
            except ValueError:
                continue
            for k, vv in zip(KEYS, v):
                cols[k].append(vv)
    return {k: np.array(v) for k, v in cols.items()}


def layer(d, z=0.5):
    m = np.isclose(d["z"], z)
    return {k: v[m] for k, v in d.items()}


print("=" * 72)
print("机理分析 v2 —— 修正认知后的重做")
print("=" * 72)

d_st = layer(load(r"D:/Flac3d/FLAC/exe64/tensor_base45.csv"))
d_un = layer(load(r"D:/Flac3d/FLAC/exe64/tensor_unstable.csv"))

for nm, dd in (("临界稳定态 (fos-Stable)", d_st), ("崩溃态 (fos-Unstable)", d_un)):
    st = dd["state"].astype(int)
    print("\n[%s]  代表层单元数 = %d" % (nm, len(st)))
    for bit, lab in ((1, "shear-n"), (2, "tension-n"), (4, "shear-p"), (8, "tension-p")):
        print("    %-10s = %4d" % (lab, ((st & bit) != 0).sum()))
    print("    %-10s = %4d" % ("elastic", (st == 0).sum()))

# ---------- A. 从临界态提取滑面 ----------
print("\n" + "=" * 72)
print("A. 滑面几何识别（基于临界稳定态的屈服带 shear-p）")
print("=" * 72)

st = d_st["state"].astype(int)
x, y = d_st["x"], d_st["y"]
yielded = (st & 4) != 0          # 曾剪切屈服 = 滑面候选带

# 排除模型边界附近的伪屈服（角点应力集中）
interior = (x > 1.5) & (x < 28.5) & (y > 1.5)
band = yielded & interior
print("屈服带单元数 = %d" % band.sum())

# 沿 x 取屈服带的 y 中位数作为滑面轨迹
bins = np.arange(2.0, 28.0, 1.0)
traj = []
for xb in bins:
    m = band & (np.abs(x - xb) < 0.5)
    if m.sum() >= 1:
        traj.append((xb, float(np.median(y[m])), int(m.sum())))
traj = np.array(traj)
print("\n滑面轨迹：")
for t in traj:
    print("   x=%5.1f  y=%6.2f  n=%d" % (t[0], t[1], int(t[2])))

if len(traj) >= 4:
    xx, yy = traj[:, 0], traj[:, 1]
    # 圆拟合
    A = np.c_[xx, yy, np.ones(len(xx))]
    b = -(xx**2 + yy**2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    D, E, F = sol
    xc, yc = -D/2, -E/2
    R = math.sqrt(max(xc**2 + yc**2 - F, 0))
    res = np.sqrt((xx-xc)**2 + (yy-yc)**2) - R
    print("\n【圆拟合】圆心=(%.2f, %.2f)  R=%.2f  RMS残差=%.3f m  最大残差=%.3f m"
          % (xc, yc, R, np.sqrt((res**2).mean()), np.abs(res).max()))

    print("\n【与 Bishop 临界滑面对照】")
    print("  Bishop 搜索: 圆心=(19.98, 23.55)  R=13.55  FOS=1.5778")
    print("  FLAC3D 提取: 圆心=(%.2f, %.2f)  R=%.2f" % (xc, yc, R))
    d_c = math.hypot(xc-19.98, yc-23.55)
    print("  圆心距离 = %.2f m  半径差 = %.2f m" % (d_c, abs(R-13.55)))

# ---------- B. 强度发挥度 ----------
print("\n" + "=" * 72)
print("B. 强度发挥度 mob（用完整张量，平面应变）")
print("=" * 72)


def mobility(dd):
    sxx, syy, sxy = dd["sxx"], dd["syy"], dd["sxy"]
    tau = np.sqrt(((syy - sxx) / 2.0) ** 2 + sxy ** 2)
    sign = (sxx + syy) / 2.0
    sn = -sign
    tauf = C0 + sn * np.tan(PHI)
    mob = np.where(tauf > 1.0, tau / tauf, 0.0)
    return tau, sn, tauf, mob


for nm, dd in (("临界稳定态", d_st), ("崩溃态", d_un)):
    tau, sn, tauf, mob = mobility(dd)
    stt = dd["state"].astype(int)
    print("\n[%s]" % nm)
    print("  tau_max:  mean=%.1f  max=%.1f kPa" % (tau.mean()/1e3, tau.max()/1e3))
    print("  sigma_n:  mean=%.1f kPa" % (sn.mean()/1e3))
    print("  tau_f:    mean=%.1f kPa" % (tauf.mean()/1e3))
    print("  mob:      mean=%.3f  p95=%.3f  max=%.3f"
          % (mob.mean(), np.percentile(mob, 95), mob.max()))
    m = (stt & 4) != 0
    if m.sum():
        print("  屈服带内 mob: mean=%.3f  max=%.3f" % (mob[m].mean(), mob[m].max()))
    m2 = (stt & 1) != 0
    if m2.sum():
        print("  当前剪切破坏区 mob: mean=%.3f  max=%.3f" % (mob[m2].mean(), mob[m2].max()))

# ---------- C. 竖向应力的物理合理性 ----------
print("\n" + "=" * 72)
print("C. 竖向应力 σyy 的物理合理性核验")
print("=" * 72)
syy = d_st["syy"]
print("  理论：自重竖向应力 σv = -ρg·h，ρg = %.1f kPa/m" % (2500*9.81/1e3))
print("  %6s %12s %12s %10s" % ("y(m)", "σyy实测", "σv理论", "比值"))
for yb in (1.0, 3.0, 5.0, 7.0, 9.0):
    m = np.abs(d_st["y"] - yb) < 0.6
    if m.sum():
        meas = syy[m].mean() / 1e3
        theo = -2500 * 9.81 * (20.0 - yb) / 1e3
        print("  %6.1f %12.1f %12.1f %10.2f" % (yb, meas, theo, meas/theo))

np.save(os.path.join(DATA, "_slip_traj_v2.npy"), traj if len(traj) else np.array([]))
print("\n轨迹已保存")
