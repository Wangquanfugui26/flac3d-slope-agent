# -*- coding: utf-8 -*-
"""
Bishop 简化法（最终版）—— 作为 SSR 结果的独立验证基准 + 参数研究对照解。

要点：
  1. 进出口点参数化，滑面圆心由两出露点与半径唯一确定（凹向上）
  2. alpha 取"下滑为正"的驱动角
  3. 三级细化搜索：粗搜 -> 中搜 -> 精搜
  4. 支持批量参数（c, phi, 坡角, 坡高）以配合参数研究

几何参数化后可支持坡角/坡高变化，与 FLAC3D 参数研究保持一致。
"""
import numpy as np
import math

GAMMA = 2500.0 * 9.81


class SlopeGeometry(object):
    """由坡角 theta、坡高 H 反推坡面线。模型 x in [0, L]，y in [0, Htot]。"""

    def __init__(self, H=10.0, theta_deg=45.0, L=30.0, Htot=20.0,
                 toe_x=None, toe_y=None):
        self.H = float(H)
        self.theta = math.radians(theta_deg)
        self.L = float(L)
        self.Htot = float(Htot)
        self.toe_y = float(toe_y) if toe_y is not None else (Htot - H)
        self.toe_x = float(toe_x) if toe_x is not None else (L - 10.0)
        self.crest_y = self.toe_y + H
        self.crest_x = self.toe_x - H / math.tan(self.theta)

    def surface_y(self, x):
        if x <= self.crest_x:
            return self.crest_y
        if x >= self.toe_x:
            return self.toe_y
        return self.toe_y + (self.toe_x - x) * math.tan(self.theta)

    def describe(self):
        return ("H=%.1f m, theta=%.1f deg, toe=(%.2f,%.2f), crest=(%.2f,%.2f)"
                % (self.H, math.degrees(self.theta), self.toe_x, self.toe_y,
                   self.crest_x, self.crest_y))


def circle_from_points(x1, y1, x2, y2, R):
    dx, dy = x2 - x1, y2 - y1
    d = math.hypot(dx, dy)
    if d < 1e-9 or R < d / 2 - 1e-9:
        return None
    mx, my = 0.5 * (x1 + x2), 0.5 * (y1 + y2)
    h = math.sqrt(max(R * R - (d / 2) ** 2, 0.0))
    ux, uy = -dy / d, dx / d
    c1 = (mx + h * ux, my + h * uy)
    c2 = (mx - h * ux, my - h * uy)
    return c1 if c1[1] > c2[1] else c2


def circle_ys(x, xc, yc, R):
    t = R * R - (x - xc) ** 2
    if t < 0:
        return None
    return yc - math.sqrt(t)


def fos_circle(geo, xc, yc, R, phi_deg, c, dx=0.25):
    """给定滑面，用 Bishop 简化法求 FOS。"""
    xs = np.arange(0.0, geo.L + 1e-9, 0.05)
    cover = []
    for x in xs:
        yb = circle_ys(x, xc, yc, R)
        if yb is None or yb < -1e-6:
            continue
        if geo.surface_y(x) - yb < -1e-6:
            continue
        cover.append(x)
    if len(cover) < 6:
        return None, 0
    x_lo, x_hi = cover[0], cover[-1]
    if x_hi - x_lo < 2.0:
        return None, 0

    edges = np.arange(x_lo, x_hi + dx, dx)
    if len(edges) < 5:
        return None, 0

    Ws, alphas, bs = [], [], []
    for i in range(len(edges) - 1):
        xm = 0.5 * (edges[i] + edges[i + 1])
        yb = circle_ys(xm, xc, yc, R)
        if yb is None:
            continue
        h = geo.surface_y(xm) - yb
        if h <= 1e-6:
            continue
        b = edges[i + 1] - edges[i]
        Ws.append(GAMMA * h * b)
        dydx = -(xm - xc) / (yb - yc)
        alphas.append(math.atan(-dydx))
        bs.append(b)
    if len(Ws) < 5:
        return None, 0

    W = np.array(Ws); a = np.array(alphas); b = np.array(bs)
    den = np.sum(W * np.sin(a))
    if den <= 1e-6:
        return None, 0

    phi = math.radians(phi_deg)
    F = 1.0
    for _ in range(100):
        ma = np.cos(a) + np.sin(a) * math.tan(phi) / F
        ma = np.where(np.abs(ma) < 0.2, 0.2, ma)
        num = np.sum((c * b + W * math.tan(phi)) / ma)
        F_new = num / den
        if not np.isfinite(F_new):
            return None, 0
        if abs(F_new - F) < 1e-8:
            F = F_new
            break
        F = F_new
    if not np.isfinite(F) or F <= 0.05 or F > 30:
        return None, 0
    return F, len(Ws)


def search(geo, phi_deg, c, coarse=1.0):
    """三级细化搜索临界滑面。"""
    xe_lo, xe_hi = geo.crest_x + 1.0, geo.toe_x + 5.0
    xi_lo, xi_hi = max(0.0, geo.crest_x - 12.0), geo.toe_x - 2.0
    m = geo.H

    best = None

    def trial(xe, xi, R):
        nonlocal best
        if xi >= xe - 1.2:
            return
        ye, yi = geo.surface_y(xe), geo.surface_y(xi)
        d = math.hypot(xe - xi, ye - yi)
        if R < d / 2 * 1.001:
            return
        cc = circle_from_points(xi, yi, xe, ye, R)
        if cc is None:
            return
        F, n = fos_circle(geo, cc[0], cc[1], R, phi_deg, c)
        if F is None:
            return
        if best is None or F < best[0]:
            best = (F, xe, xi, R, n, cc)

    for xe in np.arange(xe_lo, xe_hi + 1e-9, coarse):
        for xi in np.arange(xi_lo, xi_hi + 1e-9, coarse):
            for R in np.arange(0.6 * m, 3.0 * m, coarse):
                trial(xe, xi, R)
    if best is None:
        return None

    for step in (0.25, 0.05):
        F0, xe0, xi0, R0, _, _ = best
        for xe in np.arange(xe0 - 2 * step, xe0 + 2 * step + 1e-9, step):
            for xi in np.arange(xi0 - 2 * step, xi0 + 2 * step + 1e-9, step):
                for R in np.arange(R0 - 2 * step, R0 + 2 * step + 1e-9, step):
                    trial(xe, xi, R)

    F, xe, xi, R, n, cc = best
    return dict(F=float(F), xe=float(xe), xi=float(xi), R=float(R),
                n=int(n), xc=float(cc[0]), yc=float(cc[1]))


def fos_bishop(H=10.0, theta_deg=45.0, c=30e3, phi_deg=25.0, verbose=True):
    geo = SlopeGeometry(H=H, theta_deg=theta_deg)
    r = search(geo, phi_deg, c)
    if r is None:
        return None
    if verbose:
        print("  Bishop: H=%.1f theta=%.0f c=%.1f kPa phi=%.1f -> FOS=%.4f "
              "(xc=%.2f yc=%.2f R=%.2f n=%d)"
              % (H, theta_deg, c / 1e3, phi_deg, r["F"],
                 r["xc"], r["yc"], r["R"], r["n"]))
    return r


if __name__ == "__main__":
    print("=== Bishop 简化法（最终版）===")
    print("几何：" + SlopeGeometry().describe())
    r = fos_bishop()
    if r:
        print("\n临界滑面：FOS_Bishop = %.4f" % r["F"])
        print("  圆心 = (%.2f, %.2f) m   半径 = %.2f m" % (r["xc"], r["yc"], r["R"]))
        print("  出口 x = %.2f   入口 x = %.2f   分条数 = %d" % (r["xe"], r["xi"], r["n"]))
        print("\n对照 FLAC3D SSR (FOS = 1.685)：")
        print("  绝对偏差 = %+.4f   相对偏差 = %+.2f%%"
              % (r["F"] - 1.685, (r["F"] - 1.685) / 1.685 * 100))
