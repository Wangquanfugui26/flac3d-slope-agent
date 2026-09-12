# -*- coding: utf-8 -*-
"""
生成参数化算例的 FLAC3D 脚本（建模 + 自重平衡 + SSR 求 FOS）。

用法：
  python gen_param_case.py <case_id> <H> <theta> <c_kPa> <phi_deg>
输出：
  <OUT>/cases/p_<case_id>_stage1.dat   (建模+自重+导出)
  <OUT>/cases/p_<case_id>_stage2.dat   (SSR 求 FOS)
  <OUT>/cases/p_<case_id>_stage3.dat   (导出临界态)

建模策略：仍用"分层条带"法构造任意坡角坡面。
  坡脚 (toe_x, toe_y)，坡顶 (crest_x, crest_y)
  crest_x = toe_x - H/tan(theta)
  为保证坡顶平台宽度足够，模型 x 向范围自动扩展。

重要：所有坐标为字面数值，避免 FISH 插值静默失败（C3）。
"""
import os
import math
import sys

BASE = "D:/Flac3d/FLAC/exe64"
CASES = BASE + "/cases"

L = 30.0          # 模型 x 向总长
HTOT = 20.0       # 模型 y 向总高
THICK = 6.0       # z 向厚度
TOE_X = 20.0      # 坡趾 x
TOE_Y = 10.0      # 坡趾 y
NZ = 6
LAYER_H = 1.0

DENS = 2500.0
BULK = 1.0e8
SHEAR = 6.0e7
TENS = 1.0e4


def gen(case_id, H, theta_deg, c_pa, phi_deg):
    th = math.radians(theta_deg)
    crest_x = TOE_X - H / math.tan(th)
    crest_y = TOE_Y + H
    if crest_x < 0.5:
        raise ValueError("坡角过大导致坡顶内缘超出模型左边界: crest_x=%.2f" % crest_x)
    if crest_y > HTOT + 1e-9:
        raise ValueError("坡高过大导致坡顶超出模型顶面: crest_y=%.2f" % crest_y)

    os.makedirs(CASES, exist_ok=True)

    # ---------- stage 1：建模 + 自重平衡 ----------
    a = [].append
    A = []
    a = A.append
    a("model new")
    a('model title "Parametric slope case ' + case_id + '"')
    # 修正 (2026-09-11)：large-strain on 会让 45° 阶梯状坡面在自重下产生
    # 网格畸变，触发非确定性的 "*** Illegal geometry"，导致算例随机失败。
    # 本模型为小应变问题（|u|max/坡高 ~ 4%），且 SSR 本身强制要求 small-strain，
    # 因此全程使用小应变更自洽。原 base45 算例能跑通属于侥幸。
    a("model large-strain off")
    a("model mechanical")
    a("model deterministic on")
    a("model precision 6")
    a("model random 10000")
    a("")
    a('program log-file "' + CASES + '/p_' + case_id + '_s1.log" truncate')
    a("program log on")
    a("")

    # 下部整块：y 从 0 到 toe_y
    a("zone create brick point 0 (0,0,0) point 1 (%g,0,0) point 2 (0,%g,0) "
      "point 3 (0,0,%g) size %d %d %d group \"lower\""
      % (L, TOE_Y, THICK, int(L), int(TOE_Y), NZ))
    a("")

    # 上部条带：y 从 toe_y 到 crest_y，每层 1m
    n_layers = int(round((crest_y - TOE_Y) / LAYER_H))
    for i in range(n_layers):
        yb = TOE_Y + i * LAYER_H
        yt = yb + LAYER_H
        # 该层顶面对应的坡面 x 位置
        if yt <= crest_y - 1e-9:
            xr = TOE_X - (yt - TOE_Y) / math.tan(th)
        else:
            xr = crest_x
        xr = max(crest_x, min(TOE_X, xr))
        nx = max(1, int(round(xr)))
        a("zone create brick point 0 (0,%g,0) point 1 (%g,%g,0) point 2 (0,%g,0) "
          "point 3 (0,%g,%g) size %d 1 %d group \"upper\""
          % (yb, xr, yb, yt, yb, THICK, nx, NZ))
    a("")

    a("zone cmodel assign mohr-coulomb")
    a("zone property density %g bulk %g shear %g cohesion %g friction %g tension %g"
      % (DENS, BULK, SHEAR, c_pa, phi_deg, TENS))
    a("")

    a("model gravity 0 -9.81 0")
    a("zone gridpoint fix velocity-x range position-x 0")
    a("zone gridpoint fix velocity-x range position-x %g" % L)
    a("zone gridpoint fix velocity-y range position-y 0")
    a("zone gridpoint fix velocity-z range position-z 0")
    a("zone gridpoint fix velocity-z range position-z %g" % THICK)
    a("")
    a("model solve ratio-local 1e-5")
    a("")
    a('model save "' + CASES + '/p_' + case_id + '_gravity"')
    a("program log off")

    p1 = os.path.join(CASES, "p_" + case_id + "_stage1.dat")
    with open(p1, "w", encoding="ascii", errors="ignore") as f:
        f.write("\n".join(A))

    # ---------- stage 2：SSR 求 FOS ----------
    B = []
    b = B.append
    b('model restore "' + CASES + '/p_' + case_id + '_gravity"')
    b("model large-strain off")
    b('program log-file "' + CASES + '/p_' + case_id + '_s2.log" truncate')
    b("program log on")
    b('model factor-of-safety bracket 0.8 3.0 filename "' + CASES
      + '/p_' + case_id + '_fos" ratio-local 1e-5')
    b("model factor-of-safety list")
    b("program log off")

    p2 = os.path.join(CASES, "p_" + case_id + "_stage2.dat")
    with open(p2, "w", encoding="ascii", errors="ignore") as f:
        f.write("\n".join(B))

    return p1, p2, dict(case=case_id, H=H, theta=theta_deg, c=c_pa, phi=phi_deg,
                        crest_x=crest_x, crest_y=crest_y)


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("usage: gen_param_case.py <case_id> <H> <theta> <c_kPa> <phi_deg>")
        sys.exit(2)
    cid = sys.argv[1]
    H = float(sys.argv[2]); th = float(sys.argv[3])
    ck = float(sys.argv[4]); ph = float(sys.argv[5])
    p1, p2, info = gen(cid, H, th, ck * 1e3, ph)
    print("OK " + cid)
    print("  " + p1)
    print("  " + p2)
    print("  crest=(%.2f, %.2f)" % (info["crest_x"], info["crest_y"]))
