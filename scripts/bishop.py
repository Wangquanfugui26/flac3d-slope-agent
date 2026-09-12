# -*- coding: utf-8 -*-
"""
Bishop 简化法独立实现 —— SSR 结果的独立验证基准。

几何（与 FLAC3D 模型严格一致，坡趾 y=10 假设）：
   坡面自坡趾 (20,10) 升至坡顶内缘 (10,20)，坡角 45 度
   坡顶平台 y=20，x in [0,10]
   坡脚平台 y=10，x in [20,30]
   模型 x in [0,30]，y in [0,20]

改进点（相比首版）：
   1. 滑面必须以坡面为滑动边界，出入点需落在坡面或平台上
   2. 限定圆心在坡顶线以上（yc >= 20），保证滑面为凹向上圆弧
   3. 增加分条数下限，剔除退化解
   4. 搜索后输出滑面几何供人工核对
"""
import numpy as np
import math

C0 = 30e3
PHI0 = 25.0
GAMMA = 2500.0 * 9.81

TOE_X, TOE_Y = 20.0, 10.0
CREST_X, CREST_Y = 10.0, 20.0


def surface_y(x):
    """坡面线（边坡的上部自由边界）。"""
    if x <= CREST_X:
        return CREST_Y
    if x >= TOE_X:
        return TOE_Y
    return TOE_Y + (TOE_X - x) * (CREST_Y - TOE_Y) / (TOE_X - CREST_X)


def circle_ys(x, xc, yc, R):
    t = R * R - (x - xc) ** 2
    if t < 0:
        return None
    return yc - math.sqrt(t)


def slice_bishop(xc, yc, R, dx=0.5, phi_deg=PHI0, c=C0, gamma=GAMMA,
                 min_slices=8):
    """对给定圆弧执行 Bishop 简化法。返回 (F, n_slices, info) 或 (None,0,None)。"""
    # 滑面必须为凹向上：圆心须在滑面之上
    if yc <= 0:
        return None, 0, None

    # 建立分条 x 范围：滑面与坡面之间的滑体
    xs = np.arange(0.0, 30.0 + 1e-9, 0.05)
    cover = []
    for x in xs:
        yb = circle_ys(x, xc, yc, R)
        if yb is None:
            continue
        yt = surface_y(x)
        if yt - yb <= 0.05:      # 需要有一定厚度才算滑体
            continue
        if yb < 0:               # 滑面不应穿出模型底面
            continue
        cover.append(x)
    if len(cover) < 20:
        return None, 0, None
    x_lo, x_hi = cover[0], cover[-1]
    # 滑面跨度不应超过模型宽度
    if x_hi - x_lo > 29.0:
        return None, 0, None

    edges = np.arange(x_lo, x_hi + dx, dx)
    if len(edges) < min_slices:
        return None, 0, None

    Ws, alphas, bs = [], [], []
    for i in range(len(edges) - 1):
        xm = 0.5 * (edges[i] + edges[i + 1])
        yb = circle_ys(xm, xc, yc, R)
        if yb is None:
            continue
        yt = surface_y(xm)
        h = yt - yb
        if h <= 0.05:
            continue
        b = edges[i + 1] - edges[i]
        W = gamma * h * b
        dydx = -(xm - xc) / (yb - yc)
        alpha = math.atan(dydx)
        Ws.append(W)
        alphas.append(alpha)
        bs.append(b)

    if len(Ws) < min_slices:
        return None, 0, None

    W = np.array(Ws)
    a = np.array(alphas)
    b = np.array(bs)

    phi = math.radians(phi_deg)
    F = 1.0
    for _ in range(80):
        ma = np.cos(a) + np.sin(a) * math.tan(phi) / F
        ma = np.where(np.abs(ma) < 0.2, 0.2, ma)
        num = np.sum((c * b + W * math.tan(phi)) / ma)
        den = np.sum(W * np.sin(a))
        if abs(den) < 1e-6:
            return None, 0, None
        F_new = num / den
        if abs(F_new - F) < 1e-7:
            F = F_new
            break
        F = F_new

    if not np.isfinite(F) or F <= 0.05 or F > 30:
        return None, 0, None
    info = dict(x_lo=x_lo, x_hi=x_hi, n=len(Ws), xc=xc, yc=yc, R=R)
    return F, len(Ws), info


def search_critical(phi_deg=PHI0, c=C0, gamma=GAMMA, verbose=False):
    """
    系统搜索临界滑面。
    圆心限定在坡顶线以上（yc >= CREST_Y - 2），符合凹向上圆弧的物理约束。
    以标准网格粗搜 + 局部细化。
    """
    best = None

    def try_one(xc, yc, R):
        nonlocal best
        F, n, info = slice_bishop(xc, yc, R, phi_deg=phi_deg, c=c, gamma=gamma)
        if F is None:
            return
        if best is None or F < best[0]:
            best = (F, xc, yc, R, n)
            if verbose:
                print("  best F=%.4f  xc=%.2f yc=%.2f R=%.2f n=%d" % (F, xc, yc, R, n))

    # 粗搜：圆心在坡顶线附近及以上
    for xc in np.arange(-2.0, 24.0, 1.0):
        for yc in np.arange(19.0, 45.0, 1.0):
            for R in np.arange(8.0, 34.0, 1.0):
                try_one(xc, yc, R)

    if best is None:
        return None, None

    F0, xc0, yc0, R0, _ = best
    for step, span in ((0.25, 1.0),):
        for xc in np.arange(xc0 - span, xc0 + span + 1e-9, step):
            for yc in np.arange(yc0 - span, yc0 + span + 1e-9, step):
                for R in np.arange(R0 - span, R0 + span + 1e-9, step):
                    try_one(xc, yc, R)

    F, xc, yc, R, n = best
    _, _, info = slice_bishop(xc, yc, R, phi_deg=phi_deg, c=c, gamma=gamma)
    return F, info


def report(phi_deg=PHI0, c=C0, gamma=GAMMA, label="base"):
    print("\n=== Bishop 简化法：%s ===" % label)
    print("  c = %.2f kPa, phi = %.1f deg, gamma = %.1f kN/m3"
          % (c / 1e3, phi_deg, gamma / 1e3))
    F, info = search_critical(phi_deg=phi_deg, c=c, gamma=gamma)
    if F is None:
        print("  搜索失败：无有效滑面")
        return None, None
    print("  临界滑面 FOS_Bishop = %.4f" % F)
    print("    圆心 = (%.2f, %.2f) m" % (info["xc"], info["yc"]))
    print("    半径 = %.2f m" % info["R"])
    print("    滑面 x 范围 = [%.2f, %.2f] m" % (info["x_lo"], info["x_hi"]))
    print("    分条数 = %d" % info["n"])
    return F, info


if __name__ == "__main__":
    F, info = report()
    if F is not None:
        print("\n  与 FLAC3D SSR (FOS=1.685) 对照：")
        print("    相对偏差 = %+.2f%%" % ((F - 1.685) / 1.685 * 100))
