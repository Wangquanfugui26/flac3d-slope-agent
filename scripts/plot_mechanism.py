# -*- coding: utf-8 -*-
"""
机理分析图表生成 —— 用于论文第 6 章。

输出 6 张图：
  M1 三状态位移场对比（自重 / 临界 / 崩溃）
  M2 滑面几何：位移梯度带 + 屈服带 + Bishop 圆弧 三判据对照
  M3 沿滑面应力路径（tau vs sigma_n + 强度包线）
  M4 强度发挥度空间分布
  M5 竖向应力剖面与理论对照
  M6 位移场运动学分解（矢量 + 转动中心）
"""
import csv, os, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch, Arc

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

DATA = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据"
FIG = r"D:/Flac3d/FLAC3D边坡模拟/结果图"
FLAC = r"D:/Flac3d/FLAC/exe64"
KEYS = ("x","y","z","ux","uy","uz","state","sxx","syy","szz","sxy","sxz","syz")
C0, PHI0 = 30e3, 25.0
PHI = math.radians(PHI0)
os.makedirs(FIG, exist_ok=True)


def load(path, z=0.5):
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
    d = {k: np.array(v) for k, v in cols.items()}
    m = np.isclose(d["z"], z)
    return {k: v[m] for k, v in d.items()}


def frame(ax):
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.25, linewidth=0.4)


def slope_line(ax):
    ax.plot([0, 10, 20, 30], [20, 20, 10, 10], "k-", linewidth=1.6, zorder=5)


st = load(os.path.join(FLAC, "tensor_base45.csv"))
un = load(os.path.join(FLAC, "tensor_unstable.csv"))
gr = load(os.path.join(DATA, "slope_gravity.csv")) if os.path.exists(
    os.path.join(DATA, "slope_gravity.csv")) else None

# ============ M1 三状态位移场对比 ============
fig, axes = plt.subplots(1, 3, figsize=(19, 5.8))
um_g = np.sqrt(gr["ux"]**2 + gr["uy"]**2) * 1e3 if gr is not None else None
um_s = np.sqrt(st["ux"]**2 + st["uy"]**2) * 1e3
um_u = np.sqrt(un["ux"]**2 + un["uy"]**2) * 1e3

panels = []
if gr is not None:
    panels.append((axes[0], gr, um_g, "Gravity equilibrium", 35.1))
panels.append((axes[1], st, um_s, "Critical state (FOS=1.685)", um_s.max()))
panels.append((axes[2], un, um_u, "Collapse state", um_u.max()))
panels = panels[:3]
if len(panels) < 3 and gr is None:
    pass

for ax, d, um, ttl, vmax in panels:
    sc = ax.scatter(d["x"], d["y"], c=um, s=26, cmap="turbo", marker="s",
                    vmin=0, vmax=vmax, edgecolors="none")
    cb = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("|u| (mm)", fontsize=10)
    slope_line(ax)
    frame(ax)
    ax.set_title("%s\nmax |u| = %.1f mm" % (ttl, vmax), fontsize=11)

fig.suptitle("Displacement field evolution across three states", fontsize=14)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "M1_three_states_displacement.png"), dpi=165, bbox_inches="tight")
plt.close(fig)
print("M1 saved")

# ============ M2 滑面几何三判据对照 ============
fig, ax = plt.subplots(figsize=(11.5, 7))
ax.scatter(un["x"], un["y"], c="#EBE9E2", s=22, marker="s",
           edgecolors="#C9C6BE", linewidths=0.3, zorder=1)

# 屈服带（临界态）
stt = st["state"].astype(int)
yb_mask = (stt & 4) != 0
ax.scatter(st["x"][yb_mask], st["y"][yb_mask], c="#F09595", s=30, marker="s",
           edgecolors="none", zorder=2, label="Yielded band (shear-p), critical state")

# 位移梯度带（崩溃态）
traj = np.load(os.path.join(DATA, "_slip_grad_unstable.npy"))
ax.plot(traj[:, 0], traj[:, 1], "o-", color="#185FA5", linewidth=2.2,
        markersize=6, zorder=6, label="Slip surface from |grad u| peak (kinematic)")

# Bishop 临界圆弧
xc, yc, R = 19.98, 23.55, 13.55
th = np.linspace(0, 2*math.pi, 400)
ax.plot(xc + R*np.cos(th), yc + R*np.sin(th), "--", color="#0F6E56",
        linewidth=2.0, zorder=5, label="Bishop critical circle (LEM, FOS=1.578)")

slope_line(ax)
frame(ax)
ax.set_xlim(-0.5, 30.5)
ax.set_ylim(-0.5, 25.5)
ax.legend(loc="lower left", fontsize=9, framealpha=0.95)
ax.set_title("Slip surface identification: three independent criteria", fontsize=13)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "M2_slip_surface_criteria.png"), dpi=165, bbox_inches="tight")
plt.close(fig)
print("M2 saved")

# ============ M3 应力路径 ============
def mobility(d):
    sxx, syy, sxy = d["sxx"], d["syy"], d["sxy"]
    tau = np.sqrt(((syy - sxx)/2.0)**2 + sxy**2)
    sn = -(sxx + syy)/2.0
    tauf = C0 + sn*np.tan(PHI)
    return tau, sn, tauf, np.where(tauf > 1, tau/tauf, 0.0)


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.2))

tau_s, sn_s, tauf_s, mob_s = mobility(st)
tau_u, sn_u, tauf_u, mob_u = mobility(un)

ax1.scatter(sn_s/1e3, tau_s/1e3, s=14, c="#185FA5", alpha=0.5,
            label="Critical state (FOS=1.685)")
ax1.scatter(sn_u/1e3, tau_u/1e3, s=14, c="#E24B4A", alpha=0.5,
            label="Collapse state")
sn_line = np.linspace(0, 400, 200)
ax1.plot(sn_line, (C0 + sn_line*1e3*np.tan(PHI))/1e3, "k-", linewidth=2.2,
         label="Mohr-Coulomb envelope (c=30 kPa, phi=25 deg)")
ax1.plot(sn_line, (C0/1.685 + sn_line*1e3*np.tan(PHI)/1.685)/1e3, "k--",
         linewidth=1.6, label="Reduced envelope (FOS=1.685)")
ax1.set_xlabel("Normal stress $\\sigma_n$ (kPa)", fontsize=11)
ax1.set_ylabel("Shear stress $\\tau$ (kPa)", fontsize=11)
ax1.set_title("Stress state vs. strength envelope", fontsize=12)
ax1.legend(fontsize=9, loc="upper left")
ax1.grid(alpha=0.3)
ax1.set_xlim(0, 420)

# 沿滑面 mob 分布（用梯度轨迹的 x 位置）
ax2.scatter(st["x"], mob_s, s=14, c="#185FA5", alpha=0.45, label="Critical state")
ax2.axhline(1.0, color="#E24B4A", linewidth=2.0, linestyle="--",
            label="Strength limit (mob = 1)")
ax2.axhline(mob_s.max(), color="#854F0B", linewidth=1.4, linestyle=":",
            label="Observed max = %.3f" % mob_s.max())
ax2.set_xlabel("x (m)", fontsize=11)
ax2.set_ylabel("Mobilization ratio $\\tau/\\tau_f$", fontsize=11)
ax2.set_title("Strength mobilization distribution", fontsize=12)
ax2.legend(fontsize=9, loc="upper right")
ax2.grid(alpha=0.3)
ax2.set_ylim(0, 1.15)

fig.suptitle("Mechanism analysis: stress path and strength mobilization", fontsize=14)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "M3_stress_path_mobilization.png"), dpi=165, bbox_inches="tight")
plt.close(fig)
print("M3 saved")

# ============ M4 mob 空间分布 ============
fig, ax = plt.subplots(figsize=(11.5, 7))
sc = ax.scatter(st["x"], st["y"], c=mob_s, s=34, cmap="YlOrRd", marker="s",
                vmin=0, vmax=1.0, edgecolors="none")
cb = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.03)
cb.set_label("Mobilization ratio $\\tau/\\tau_f$", fontsize=11)
slope_line(ax)
frame(ax)
ax.set_title("Spatial distribution of strength mobilization (critical state)", fontsize=13)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "M4_mobilization_map.png"), dpi=165, bbox_inches="tight")
plt.close(fig)
print("M4 saved")

# ============ M5 竖向应力剖面 ============
fig, ax = plt.subplots(figsize=(9.5, 6.5))
for d, lab, col in ((st, "Critical state (fos-Stable)", "#185FA5"),
                    (un, "Collapse state (fos-Unstable)", "#E24B4A")):
    ys, sv = [], []
    for yb in np.arange(0.5, 20.0, 0.5):
        m = np.abs(d["y"] - yb) < 0.4
        if m.sum() >= 2:
            ys.append(yb); sv.append(d["syy"][m].mean()/1e3)
    ax.plot(sv, ys, "o-", color=col, markersize=4, linewidth=1.6, label=lab)

yy = np.linspace(0, 20, 100)
ax.plot(-2500*9.81*(20-yy)/1e3, yy, "k--", linewidth=2.0,
        label="Theory: $\\sigma_v=-\\rho g h$")
ax.axhline(10.0, color="#888780", linestyle=":", linewidth=1.2)
ax.text(0.02, 10.2, "toe level y=10 m", fontsize=9, color="#5F5E5A",
        transform=ax.get_yaxis_transform())
ax.set_xlabel("Vertical stress $\\sigma_{yy}$ (kPa)", fontsize=11)
ax.set_ylabel("y (m)", fontsize=11)
ax.set_title("Vertical stress profile vs. self-weight theory", fontsize=13)
ax.legend(fontsize=9, loc="lower left")
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "M5_vertical_stress_profile.png"), dpi=165, bbox_inches="tight")
plt.close(fig)
print("M5 saved")

# ============ M6 运动学矢量 + 转动中心 ============
fig, ax = plt.subplots(figsize=(11.5, 7.5))
um = np.sqrt(un["ux"]**2 + un["uy"]**2)
sc = ax.scatter(un["x"], un["y"], c=um*1e3, s=26, cmap="turbo", marker="s",
                alpha=0.75, edgecolors="none")
plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.03, label="|u| (mm)")

keep = np.zeros(len(un["x"]), bool)
keep[::4] = True
keep &= (um > um.max()*0.01)
ax.quiver(un["x"][keep], un["y"][keep], un["ux"][keep], un["uy"][keep],
          color="#2C2C2A", scale=um.max()/(0.30*22), width=0.0035,
          headwidth=4.5, headlength=5.5, alpha=0.85, zorder=6)

# 由位移矢量反算瞬时转动中心（最小二乘）
# 对每点：v = omega x r  =>  v_perp 方向指向圆心
sel = um > um.max()*0.15
if sel.sum() >= 10:
    px, py = un["x"][sel], un["y"][sel]
    vx, vy = un["ux"][sel], un["uy"][sel]
    n = np.hypot(vx, vy)
    n[n < 1e-12] = 1e-12
    # 法线方向单位矢量 ((x-xc) 方向应与 v 垂直)
    nx, ny = -vy/n, vx/n
    # 解直线交点： (x-xc)*nx + (y-yc)*ny = 0  ->  nx*xc+ny*yc = nx*x+ny*y
    A = np.c_[nx, ny]
    b = nx*px + ny*py
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    cx, cy = sol
    ax.plot(cx, cy, "*", color="#A32D2D", markersize=20, zorder=8,
            markeredgecolor="white", markeredgewidth=1.2)
    ax.annotate("Rotation centre\n(%.1f, %.1f)" % (cx, cy),
                xy=(cx, cy), xytext=(cx-5, cy+3.5), fontsize=10, color="#501313",
                arrowprops=dict(arrowstyle="->", color="#A32D2D", lw=1.4))
    for px_, py_ in zip(px[::12], py[::12]):
        ax.plot([cx, px_], [cy, py_], color="#A32D2D", linewidth=0.5, alpha=0.3, zorder=3)

slope_line(ax)
frame(ax)
ax.set_title("Kinematics: displacement vectors and back-calculated rotation centre", fontsize=13)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "M6_kinematics_rotation.png"), dpi=165, bbox_inches="tight")
plt.close(fig)
print("M6 saved")

print("\n全部机理图已生成")
