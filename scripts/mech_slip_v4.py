# -*- coding: utf-8 -*-
"""
滑面识别 v4 —— 改进的位移梯度法。

v3 的缺陷：|∇u| 在坡面自由边界处最大（位移不受约束），
          峰值搜索总是落到坡面上，无法识别内部滑面。

v4 的修正：
  1. 以坡面线为界，只在坡体内部（坡面以下 ≥ 2 m）搜索
  2. 使用【剪应变】的代理：不只用 |∇u|，而用位移场的
     旋转-剪切不变量，抑制自由边界的伪峰值
  3. 引入"滑体-滑床"位移突变（相对位移）判据：
     对每列 x，找 ux 沿 y 方向梯度最大处（滑体与滑床的水平错动）
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


def surface_y(x):
    if x <= 10.0:
        return 20.0
    if x >= 20.0:
        return 10.0
    return 10.0 + (20.0 - x)


print("=" * 74)
print("滑面识别 v4 —— 坡体内部搜索 + 水平错动判据")
print("=" * 74)

for tag, path, fname in (
        ("崩溃态 (fos-Unstable)", r"D:/Flac3d/FLAC/exe64/tensor_unstable.csv", "unstable"),
        ("临界态 (fos-Stable)", r"D:/Flac3d/FLAC/exe64/tensor_base45.csv", "stable")):
    d = load(path)
    x, y, ux, uy = d["x"], d["y"], d["ux"], d["uy"]
    um = np.sqrt(ux**2 + uy**2)
    print("\n[%s]  |u|max = %.4f m" % (tag, um.max()))

    # 按 x 列扫描，在坡面以下 2m 的范围内找 ux 沿 y 的梯度峰值
    traj = []
    for xv in np.arange(1.0, 29.0, 1.0):
        m = np.abs(x - xv) < 0.5
        if m.sum() < 3:
            continue
        yy = y[m]
        uu = ux[m]          # 水平位移是滑动的关键分量
        uv = uy[m]
        order = np.argsort(yy)
        yy, uu, uv = yy[order], uu[order], uv[order]
        # 去重
        uniq, idx = np.unique(np.round(yy, 2), return_index=True)
        yy, uu, uv = yy[idx], uu[idx], uv[idx]
        if len(yy) < 4:
            continue
        # 只用坡面以下 1.5m 以上的深度（排除自由边界）
        sy = surface_y(xv)
        keep = yy < sy - 1.5
        if keep.sum() < 4:
            continue
        yk, uk, vk = yy[keep], uu[keep], uv[keep]
        # ux 沿 y 的梯度
        g = np.gradient(uk, yk)
        # 同时也考虑 |u| 梯度
        gmag = np.gradient(np.sqrt(uk**2 + vk**2), yk)
        score = np.abs(g) + np.abs(gmag)
        k = int(np.argmax(score))
        traj.append((xv, float(yk[k]), float(score[k]), float(uk[k])))

    traj = np.array(traj)
    print("  提取点数 = %d" % len(traj))
    if len(traj) >= 5:
        print("  %6s %8s %12s %12s" % ("x", "y_slip", "score", "ux(m)"))
        for t in traj:
            print("  %6.1f %8.2f %12.5f %12.5f" % (t[0], t[1], t[2], t[3]))

        # 平滑后圆拟合
        from numpy.polynomial import polynomial as P
        xx, yyv = traj[:, 0], traj[:, 1]
        A = np.c_[xx, yyv, np.ones(len(xx))]
        b = -(xx**2 + yyv**2)
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        D, E, F = sol
        xc, yc = -D/2, -E/2
        R2 = xc**2 + yc**2 - F
        if R2 > 0:
            R = math.sqrt(R2)
            res = np.sqrt((xx-xc)**2 + (yyv-yc)**2) - R
            print("\n  【圆拟合】圆心=(%.2f, %.2f)  R=%.2f  RMS=%.3f m  max=%.3f m"
                  % (xc, yc, R, np.sqrt((res**2).mean()), np.abs(res).max()))
            print("  与 Bishop(19.98, 23.55, R=13.55) 圆心距 = %.2f m"
                  % math.hypot(xc-19.98, yc-23.55))
        np.save(os.path.join(DATA, "_slip_v4_%s.npy" % fname), traj)

        # 与屈服带的上包络比较
        stt = d["state"].astype(int)
        nfrac = (stt & 1) != 0
        print("  当前破坏(shear-n)单元数 = %d" % nfrac.sum())
print("\n完成")
