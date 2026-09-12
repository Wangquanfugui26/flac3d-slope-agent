# -*- coding: utf-8 -*-
"""
机理分析 1：滑裂面几何的定量识别与强度发挥度分析。

思路：
  1. 取剪切破坏带（shear-n / shear-p）单元集合，按 x 分层求最大的 y 值，
     得到滑面在 x-y 平面上的轨迹（滑面是贯通带，取每列最深/最高的破坏点）
  2. 对滑面轨迹做圆拟合（最小二乘），求圆心与半径
  3. 计算每个单元的强度发挥度 tau/tau_f，绘制分布
  4. 沿滑面提取应力路径
"""
import csv, os
import numpy as np

DATA = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据"
FIG = r"D:/Flac3d/FLAC3D边坡模拟/结果图"
KEYS = ("x","y","z","ux","uy","uz","state","szz","sxy")

# 材料参数（与 stage1.dat 一致）
C0 = 30e3      # Pa
PHI = 25.0     # deg
TENS = 10e3

def load(tag):
    p = os.path.join(DATA, f"slope_{tag}.csv")
    rows = []
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        rd = csv.reader(f); next(rd, None)
        for r in rd:
            if len(r) >= 9:
                try: rows.append([float(v) for v in r[:9]])
                except ValueError: pass
    a = np.array(rows)
    return {k: a[:, i] for i, k in enumerate(KEYS)}

def collapse_z(d):
    """z 向 6 层数据在平面应变下近似相同，取 z=0.5 层作为代表。"""
    m = np.isclose(d["z"], 0.5)
    return {k: v[m] for k, v in d.items()}

d = collapse_z(load("failure"))
x, y = d["x"], d["y"]
st = d["state"].astype(int)
szz, sxy = d["szz"], d["sxy"]

print(f"代表层单元数 = {len(x)}")

BIT_SN, BIT_TN, BIT_SP, BIT_TP = 1, 2, 4, 8
shear_n = (st & BIT_SN) != 0
tension_n = (st & BIT_TN) != 0
anyfrac = shear_n | tension_n | ((st & BIT_SP) != 0) | ((st & BIT_TP) != 0)

print(f"剪切破坏 {shear_n.sum()}, 拉伸破坏 {tension_n.sum()}, 任意屈服 {anyfrac.sum()}")
print(f"弹性 {int((~anyfrac).sum())}")

# ---- 滑裂面轨迹提取：剪切破坏带的几何中心线 ----
# 对每个 x 区间，取剪切破坏单元 y 的中位数
xs_bins = np.arange(0.5, 30.0, 1.0)
traj = []
for xb in xs_bins:
    m = shear_n & (np.abs(x - xb) < 0.5)
    if m.sum() >= 1:
        traj.append((xb, np.median(y[m]), m.sum()))
traj = np.array(traj)
print("\n--- 剪切破坏带中心线（x, y_中位, 单元数）---")
for t in traj:
    print(f"  x={t[0]:5.1f}  y={t[1]:6.2f}  n={int(t[2])}")

# ---- 圆拟合 ----
# 圆方程 x^2+y^2 + D x + E y + F = 0，最小二乘
if len(traj) >= 3:
    xx, yy = traj[:, 0], traj[:, 1]
    A = np.c_[xx, yy, np.ones(len(xx))]
    b = -(xx**2 + yy**2)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    D, E, F = sol
    xc, yc = -D/2, -E/2
    R = np.sqrt(xc**2 + yc**2 - F)
    resid = np.sqrt((xx - xc)**2 + (yy - yc)**2) - R
    print(f"\n--- 圆拟合结果 ---")
    print(f"  圆心 = ({xc:.2f}, {yc:.2f}) m")
    print(f"  半径 = {R:.2f} m")
    print(f"  残差 RMS = {np.sqrt((resid**2).mean()):.3f} m, max = {np.abs(resid).max():.3f} m")
    print(f"  滑面张角 = {np.degrees(np.arctan2(np.abs(yy-yc), np.abs(xx-xc))).max():.1f} deg (从圆心看)")

# ---- 强度发挥度 ----
# 用平面应变近似：p = -(szz+sxx)/2，q = ...，仅用 szz/sxy 做简化估计
# 更严谨需 sxx。这里用 sv=szz（竖直）, sh 未知 -> 采用 FLAC3D 常见做法
# 由于 CSV 只导出了 szz 与 sxy，这里以 tau_max = |sxy| 与
# tau_f = c + sigma_n * tan(phi) 的比值给出"剪应力发挥度"的下界估计，
# 并对沿 45deg 坡面附近的单元给出更细的讨论。
phi_r = np.radians(PHI)
sigma_n_est = -szz   # 正应力近似取竖向应力（压为正）
tau_est = np.abs(sxy)
tau_f = C0 + sigma_n_est * np.tan(phi_r)
mob = np.where(tau_f > 0, tau_est / tau_f, 0.0)

print(f"\n--- 强度发挥度 mob = |sxy| / (c + sigma_n tan phi) ---")
print(f"  （注意：仅为剪应力发挥度的近似，未含 sxx）")
for label, m in [("全域", np.ones_like(mob, bool)),
                 ("剪切带", shear_n),
                 ("弹性区", ~anyfrac)]:
    if m.sum():
        print(f"  {label:8s}: mean={mob[m].mean():.3f}  p95={np.percentile(mob[m],95):.3f}  max={mob[m].max():.3f}")

# 存滑面轨迹供绘图
np.save(os.path.join(DATA, "_slip_traj.npy"), traj)
print("\n轨迹已存: _slip_traj.npy")
