# -*- coding: utf-8 -*-
"""
滑面识别 v3 —— 用位移场运动学特征识别真滑面（而非屈服标记）。

原理：
  边坡滑动时，滑体刚体式位移，滑床基本不动。
  沿滑面存在【位移梯度最大】的区域（速度不连续面）。
  因此：对位移场求梯度，最大梯度带 = 真滑面。

方法：
  1. 对代表层位移场 (ux, uy) 做规则网格插值（原为散点）
  2. 计算每单元的 |∇u| = sqrt((dux/dx)^2+(dux/dy)^2+(duy/dx)^2+(duy/dy)^2)
  3. 沿 x 扫描，取 |∇u| 峰值位置作为滑面点
  4. 对提取点做圆弧拟合与对数螺旋拟合，比较优劣
"""
import csv, os, math
import numpy as np

DATA = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据"
KEYS = ("x","y","z","ux","uy","uz","state","sxx","syy","szz","sxy","sxz","syz")


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


def grid_from_scatter(x, y, vals, nx=None, ny=None, dx=1.0):
    """散点 -> 规则网格（最近邻填充）。"""
    xmin, xmax = x.min(), x.max()
    ymin, ymax = y.min(), y.max()
    if nx is None:
        nx = int(round((xmax - xmin) / dx)) + 1
    if ny is None:
        ny = int(round((ymax - ymin) / dx)) + 1
    gx = np.linspace(xmin, xmax, nx)
    gy = np.linspace(ymin, ymax, ny)
    G = np.full((ny, nx), np.nan)
    cnt = np.zeros((ny, nx))
    acc = np.zeros((ny, nx))
    ix = np.clip(np.round((x - xmin) / (xmax - xmin) * (nx - 1)).astype(int), 0, nx-1)
    iy = np.clip(np.round((y - ymin) / (ymax - ymin) * (ny - 1)).astype(int), 0, ny-1)
    np.add.at(acc, (iy, ix), vals)
    np.add.at(cnt, (iy, ix), 1.0)
    m = cnt > 0
    G[m] = acc[m] / cnt[m]
    return gx, gy, G


def gradient_magnitude(gx, gy, ux, uy):
    """在网格上求 |∇u|。"""
    hx = gx[1] - gx[0]
    hy = gy[1] - gy[0]
    ux_g = np.nan_to_num(ux, nan=0.0)
    uy_g = np.nan_to_num(uy, nan=0.0)
    dux_dx, dux_dy = np.gradient(ux_g, hy, hx)
    duy_dx, duy_dy = np.gradient(uy_g, hy, hx)
    mag = np.sqrt(dux_dx**2 + dux_dy**2 + duy_dx**2 + duy_dy**2)
    return mag


print("=" * 72)
print("滑面识别 v3 —— 位移场梯度法（运动学判据）")
print("=" * 72)

for tag, path in (("临界稳定态", r"D:/Flac3d/FLAC/exe64/tensor_base45.csv"),
                  ("崩溃态", r"D:/Flac3d/FLAC/exe64/tensor_unstable.csv")):
    d = load(path)
    x, y, ux, uy = d["x"], d["y"], d["ux"], d["uy"]
    umag = np.sqrt(ux**2 + uy**2)
    print("\n[%s]  |u| max = %.4f m  |u| mean = %.4f m" % (tag, umag.max(), umag.mean()))

    gx, gy, UX = grid_from_scatter(x, y, ux, dx=1.0)
    _, _, UY = grid_from_scatter(x, y, uy, dx=1.0)
    _, _, UM = grid_from_scatter(x, y, umag, dx=1.0)
    G = gradient_magnitude(gx, gy, UX, UY)
    print("  |∇u| max = %.4f  (= %.2f mm/m)" % (G.max(), G.max()*1e3))

    # 沿每列找 |∇u| 峰值
    traj = []
    for j, xv in enumerate(gx):
        col = G[:, j]
        if np.all(np.isnan(col)):
            continue
        k = int(np.nanargmax(col))
        if col[k] > 0.05 * np.nanmax(G):
            traj.append((float(xv), float(gy[k]), float(col[k])))
    traj = np.array(traj)
    print("  提取峰值点数 = %d" % len(traj))
    if len(traj) >= 5:
        print("  滑面轨迹（x, y, |∇u|）：")
        for t in traj[::3]:
            print("     x=%5.1f  y=%6.2f  |grad|=%.4f" % (t[0], t[1], t[2]))
        np.save(os.path.join(DATA, "_slip_grad_%s.npy" % ("stable" if "base45" in path else "unstable")), traj)

        # 圆弧拟合
        xx, yy = traj[:, 0], traj[:, 1]
        A = np.c_[xx, yy, np.ones(len(xx))]
        b = -(xx**2 + yy**2)
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        D, E, F = sol
        xc, yc = -D/2, -E/2
        R2 = xc**2 + yc**2 - F
        if R2 > 0:
            R = math.sqrt(R2)
            res = np.sqrt((xx-xc)**2 + (yy-yc)**2) - R
            print("  【圆拟合】圆心=(%.2f,%.2f) R=%.2f RMS=%.3f m" % (xc, yc, R, np.sqrt((res**2).mean())))
            print("            与 Bishop(19.98,23.55,R=13.55) 圆心距=%.2f m"
                  % math.hypot(xc-19.98, yc-23.55))

        # 对数螺旋拟合：r = a*exp(b*theta)
        theta = np.arctan2(yy - yy.mean(), xx - xx.mean())
        r = np.sqrt((xx-xx.mean())**2 + (yy-yy.mean())**2)
        good = r > 1e-6
        if good.sum() >= 4:
            lb = np.polyfit(theta[good], np.log(r[good]), 1)
            pred = lb[1] + lb[0]*theta[good]
            resid = np.log(r[good]) - pred
            print("  【对数螺旋】r=exp(%.3f+%.4f*theta)  RMS(log)=%.4f"
                  % (lb[1], lb[0], np.sqrt((resid**2).mean())))
