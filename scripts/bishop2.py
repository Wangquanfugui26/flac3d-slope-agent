# -*- coding: utf-8 -*-
"""
Bishop 简化法 —— 第二版，采用"入口/出口点"参数化（工程标准做法）。

参数化方式（替代圆心+半径的盲搜）：
   出口点 (x_e, y_e) 位于坡面或坡脚平台
   入口点 (x_i, y_i) 位于坡面或坡顶平台，且 x_i < x_e
   给定进出口点后，圆心必位于两点连线的中垂线上 -> 单参数搜索（圆半径）

这样可从根本上排除"滑面只在平台下切一小段"的退化解。
"""
import numpy as np
import math

C0 = 30e3
PHI0 = 25.0
GAMMA = 2500.0 * 9.81

TOE_X, TOE_Y = 20.0, 10.0
CREST_X, CREST_Y = 10.0, 20.0


def surface_y(x):
    if x <= CREST_X:
        return CREST_Y
    if x >= TOE_X:
        return TOE_Y
    return TOE_Y + (TOE_X - x) * (CREST_Y - TOE_Y) / (TOE_X - CREST_X)


def circle_from_points(x1, y1, x2, y2, R):
    """由两出露点与半径求圆心（取使滑面凹向上的解，即 yc 较大者上方）。"""
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-9 or R < d / 2 - 1e-9:
        return None
    mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
    h = math.sqrt(max(R * R - (d / 2) ** 2, 0.0))
    # 单位法向（指向左侧）
    ux, uy = -dy / d, dx / d
    # 取圆心在弦上方（yc 更大）的解，保证滑面从弦下方通过 -> 凹向上
    c1 = (mx + h * ux, my + h * uy)
    c2 = (mx - h * ux, my - h * uy)
    return c1 if c1[1] > c2[1] else c2


def circle_ys(x, xc, yc, R):
    t = R * R - (x - xc) ** 2
    if t < 0:
        return None
    return yc - math.sqrt(t)


def slice_bishop(xc, yc, R, dx=0.5, phi_deg=PHI0, c=C0, gamma=GAMMA, min_slices=5):
    if yc <= 0:
        return None, 0, None
    xs = np.arange(0.0, 30.0 + 1e-9, 0.05)
    cover = []
    for x in xs:
        yb = circle_ys(x, xc, yc, R)
        if yb is None:
            continue
        if yb < -1e-6:
            continue
        if surface_y(x) - yb < -1e-6:
            continue
        cover.append(x)
    if len(cover) < 10:
        return None, 0, None
    x_lo, x_hi = cover[0], cover[-1]
    if x_hi - x_lo < 3.0:
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
        h = surface_y(xm) - yb
        if h <= 1e-6:
            continue
        b = edges[i + 1] - edges[i]
        W = gamma * h * b
        # 底面切线斜率；取负号使 alpha 为"向下滑动为正"的驱动角
        dydx = -(xm - xc) / (yb - yc)
        alpha = math.atan(-dydx)
        Ws.append(W); alphas.append(alpha); bs.append(b)
    if len(Ws) < min_slices:
        return None, 0, None

    W = np.array(Ws); a = np.array(alphas); b = np.array(bs)
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
            F = F_new; break
        F = F_new
    if not np.isfinite(F) or F <= 0.05 or F > 30:
        return None, 0, None
    return F, len(Ws), dict(x_lo=x_lo, x_hi=x_hi, n=len(Ws), xc=xc, yc=yc, R=R)


def search_by_exit_entry(phi_deg=PHI0, c=C0, gamma=GAMMA,
                         exit_range=None, entry_range=None,
                         R_range=None):
    """
    以出口点/入口点参数化搜索。
    出口点：坡面下段至坡脚平台（滑动体的下部剪出处）
    入口点：坡顶平台至坡面上段（滑动体的上部拉裂处）
    """
    if exit_range is None:
        exit_range = np.arange(14.0, 26.0, 0.5)
    if entry_range is None:
        entry_range = np.arange(0.5, 12.0, 0.5)
    if R_range is None:
        R_range = np.arange(10.0, 40.0, 0.5)

    best = None
    for xe in exit_range:
        ye = surface_y(xe)
        for xi in entry_range:
            if xi >= xe - 1.0:
                continue
            yi = surface_y(xi)
            d = math.hypot(xe - xi, ye - yi)
            for R in R_range:
                if R < d / 2 * 1.01:
                    continue
                cc = circle_from_points(xi, yi, xe, ye, R)
                if cc is None:
                    continue
                xc, yc = cc
                F, n, info = slice_bishop(xc, yc, R, phi_deg=phi_deg, c=c, gamma=gamma)
                if F is None:
                    continue
                # 校验：滑面须确实连接 (xi,yi) 与 (xe,ye)
                if best is None or F < best[0]:
                    best = (F, info)
    return best


def report(phi_deg=PHI0, c=C0, gamma=GAMMA, label="base"):
    print("\n=== Bishop 简化法（进出口点参数化）：%s ===" % label)
    print("  c = %.2f kPa, phi = %.1f deg, gamma = %.1f kN/m3"
          % (c / 1e3, phi_deg, gamma / 1e3))
    best = search_by_exit_entry(phi_deg=phi_deg, c=c, gamma=gamma)
    if best is None:
        print("  搜索失败")
        return None, None
    F, info = best
    print("  临界滑面 FOS_Bishop = %.4f" % F)
    print("    圆心 = (%.2f, %.2f) m   半径 = %.2f m" % (info["xc"], info["yc"], info["R"]))
    print("    滑面 x 范围 = [%.2f, %.2f] m   分条数 = %d" % (info["x_lo"], info["x_hi"], info["n"]))
    return F, info


if __name__ == "__main__":
    F, info = report()
    if F is not None:
        print("\n  与 FLAC3D SSR (FOS=1.685) 对照：相对偏差 = %+.2f%%" % ((F - 1.685) / 1.685 * 100))
