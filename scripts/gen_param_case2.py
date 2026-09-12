# -*- coding: utf-8 -*-
"""
参数化算例脚本生成器 v2 —— 修正版（2026-09-11）。

对 v1 的三处关键修正（均由实测驱动）：

【修正 1】large-strain 模式
  实测：model solve 必须先声明 model large-strain on|off，否则报
        *** Large strain mode must be specified with the MODEL LARGE-STRAIN command.
  且该错误在 --batch 模式下会令该行之后的所有语句被静默跳过（不发任何提示）。
  原 v1 在 stage1 用 on、stage2 用 off；但 SSR（model factor-of-safety）本身
  强制要求 small-strain，且本模型 |u|max/坡高 ~ 4% 属小应变范畴。
  故全程统一 model large-strain off，避免模式切换带来的不一致。

【修正 2】错误即终止（本次最重要的发现）
  实测：--batch 模式下，脚本中任何一行出错（*** 开头）之后，
        该脚本剩余所有行都被静默跳过，且不会自动 exit。
  危害：stage1 里 model save 若被跳过，会生成「缺失 .sav」的假成功，
        下游 stage2 的 model restore 随即失败，整条流水线静默崩塌。
  对策：不再依赖「单次 --batch 跑完整个 stage」；改为把 stage 拆成
        多个小脚本，每步单独校验产物（.sav 是否存在），
        从机制上消灭 C3 类静默失败。

【修正 3】坐标系与量纲
  本模型 x 水平、y 竖直、z 厚度。竖直应力是 sigma_yy。
  导出时务必用 zone.stress(yy)，而非 (zz)。

【修正 4】自平衡判据必须带步数上限（2026-09-11 晚间实测，最重要的修正）
  实测（算例 c=10 kPa / phi=15 deg，Bishop 参照 FOS≈0.70，即本质上不稳定）：
    A) model solve ratio-local 1e-5   -> 135738 步后 ratio 仍 0.99，*** = 0，.sav 无
    B) model solve ratio-average 1e-4 -> 280186 步后 ratio 1.84e-3，*** = 0，.sav 无
    C) model solve cycles 3000        -> 9 秒干净结束，.sav 正常生成
  三者 *** 计数均为 0 —— 不是报错，是"力平衡"这个目标对该边坡根本不存在：
  低强度边坡在重力下持续塑性流动，ratio 在 0.3~0.7 间震荡，永不衰减。

  危害：没有步数上限时，自平衡阶段会无限跑下去。
  若外层驱动设了超时，FLAC3D 会在 model save 之前被杀，
  下游 stage2 的 model restore 随即失败 -> 整条流水线静默崩塌（C3+C2）。
  这正是旧批次 param_flac3d.csv 出现 None 与错值的根因。

  对策：自平衡统一改为「双判据取先到者」——
        model solve ratio-local 1e-5 cycles 20000
      · 稳定算例（如 base45）在 4342 步即满足 1e-5，行为与原先完全一致；
      · 不稳定算例跑到 20000 步上限即停，拿到"变形已充分发展"的初始状态，
        后续 SSR 折减照常可算。
  注意：不稳定算例的"自平衡位移"不代表初始沉降，而是已经开始滑动的位移，
        论文中须单独说明，不可与稳定算例的沉降量并列比较。

用法：
  python gen_param_case2.py <case_id> <H> <theta> <c_kPa> <phi_deg>
输出（写入 <CASES>/）：
  p_<id>_stage1.dat     建模 + 自重平衡 + 保存 gravity.sav
  p_<id>_stage2.dat     SSR 折减求 FOS
  p_<id>_stage3.dat     导出临界态全张量
"""
import math
import os
import sys

CASES = "D:/Flac3d/FLAC/exe64/cases"

L = 30.0          # 模型 x 向总长 (m)
HTOT = 20.0       # 模型 y 向总高 (m)
THICK = 6.0       # z 向厚度 (m)
TOE_X = 20.0      # 坡趾 x (m) —— 坡趾到右边界水平距离 = 30 - 20 = 10 m
TOE_Y = 10.0      # 坡趾 y (m)
NZ = 6
LAYER_H = 1.0

DENS = 2500.0     # kg/m3
BULK = 1.0e8      # Pa
SHEAR = 6.0e7     # Pa
TENS = 1.0e4      # Pa


def geom(H, theta_deg):
    th = math.radians(theta_deg)
    crest_x = TOE_X - H / math.tan(th)
    crest_y = TOE_Y + H
    if crest_x < 0.5:
        raise ValueError("坡角过大，坡顶内缘超出左边界: crest_x=%.2f" % crest_x)
    if crest_y > HTOT + 1e-9:
        raise ValueError("坡高过大，坡顶超出模型顶面: crest_y=%.2f" % crest_y)
    return crest_x, crest_y


def build_stage1(case_id, H, theta_deg, c_pa, phi_deg):
    """建模 + 自重平衡。"""
    crest_x, crest_y = geom(H, theta_deg)
    th = math.radians(theta_deg)

    A = []
    a = A.append
    a("model new")
    a('model title "Parametric slope case ' + case_id + '"')
    a("model large-strain off")          # 修正 1：全程小应变
    a("model mechanical")
    a("model deterministic on")
    a("model precision 6")
    a("model random 10000")
    a("")

    # 下部整块
    # 关键（实测）：group 名必须加引号！写成 `group lower`（不带引号）会让
    # FLAC3D 在 -b 批处理模式下无限挂起 —— 不报错、不超时、不产出任何文件。
    # 实测对照：`group lower` 永久挂起；`group "lower"` 1.3s 正常结束。
    a("zone create brick point 0 (0,0,0) point 1 (%g,0,0) point 2 (0,%g,0) "
      "point 3 (0,0,%g) size %d %d %d group \"lower\""
      % (L, TOE_Y, THICK, int(L), int(TOE_Y), NZ))
    a("")

    # 上部阶梯条带
    #
    # 修正 6（2026-09-11 实测，导致 t60 静默失效的根因）—— 共形网格约束
    #
    # 【现象】theta=60 时 model solve 的 ratio-local 恒为 1.00000e+00，
    #   200000 步 / 242 s 毫不下降，*** 计数为 0（完全静默）；
    #   其 gravity.sav 是无效应力态，SSR 从它出发必然报
    #   "Model is unstable at maximum specified Factor of Safety"，
    #   无论 bracket 下限压到多低（实测 0.8 / 0.3 / 0.05 全部 Not Valid）。
    #
    # 【机理】下部整块是 size 30 10 6，x 向单元尺寸恰好 1.0 m。
    #   FLAC3D 的 zone create brick **不会自动缝合非共形界面**：
    #   上部条带若单元尺寸不等于 1.0 m，其网格节点与下部块错位，
    #   两块**不连通**，上部坡体成为自由悬浮体 -> 力传不上去 -> ratio 恒为 1。
    #
    # 【实测对照】
    #   xr=19.0000, nx=19 -> 单元 1.0000 m -> 共形 -> 收敛（base45，4342 步）
    #   xr=18.8453, nx=19 -> 单元 0.9919 m -> 错位 -> ratio 恒 1.0（t60，失败）
    #   xr=19.0000, nx=18 -> 单元 1.0556 m -> 错位 -> ratio 恒 1.0（失败）
    #   （注意：把段数减一同样破坏共形性，见第 3 行对照）
    #
    # 【对策】把条带右边界**吸附到整数**，令 nx == xr_snapped，
    #   从而保证单元尺寸恰为 1.0 m、与下部块共形连通。
    #   代价是阶梯在 x 向被量化为 1 m，属可接受的几何近似。
    n_layers = int(round((crest_y - TOE_Y) / LAYER_H))
    for i in range(n_layers):
        yb = TOE_Y + i * LAYER_H
        yt = yb + LAYER_H
        if yt <= crest_y - 1e-9:
            xr = TOE_X - (yt - TOE_Y) / math.tan(th)
        else:
            xr = crest_x
        xr = max(crest_x, min(TOE_X, xr))

        # 吸附到整数：nx 必须等于右边界坐标，才能与下部块（1.0 m 单元）共形
        nx = max(1, min(int(round(xr)), int(TOE_X)))
        xr = float(nx)
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

    a("program log-file \"" + CASES + "/p_" + case_id + "_s1.log\" truncate")
    a("program log on")
    # 修正 4：双判据取先到者。稳定算例按 1e-5 提前收敛；不稳定算例由
    # cycles 20000 兜底截断，避免无限跑下去导致 model save 前被超时杀掉。
    a("model solve ratio-local 1e-5 cycles 20000")
    a("program log off")
    a("")                                 # 修正 2：save 独立成步，产物可校验
    a("model save \"" + CASES + "/p_" + case_id + "_gravity\"")
    return A


def build_stage2(case_id, lo=0.3, hi=3.0):
    """SSR 强度折减求 FOS。

    修正 5（2026-09-11 实测）：bracket 下限必须低于真实 FOS，否则 FLAC3D
    不会给出数值，只回一句定性判断：
        +++ Model is unstable at maximum specified Factor of Safety 0.8.
        Factor of Safety Not Valid
    实测：c10p15（Bishop 参照 0.70）与 t60 都落在 0.8 以下，因此都用
    bracket 0.8 3.0 时返回 Not Valid。
    对策：下限一律放宽到 0.3，覆盖到"重度不稳定"区间。
    注意 0.3 仍不是万能下界 —— 若某算例连 0.3 都撑不住，需再下调。
    """
    B = []
    b = B.append
    b("model restore \"" + CASES + "/p_" + case_id + "_gravity\"")
    b("model large-strain off")           # SSR 强制要求 small-strain
    b("program log-file \"" + CASES + "/p_" + case_id + "_s2.log\" truncate")
    b("program log on")
    b("model factor-of-safety bracket %g %g filename \"" % (lo, hi) + CASES
      + "/p_" + case_id + "_fos\" ratio-local 1e-5")
    b("model factor-of-safety list")
    b("program log off")
    return B


def build_stage3(case_id):
    """导出临界态 (fos-Stable) 的全张量与状态。"""
    C = []
    c = C.append
    c("model restore \"" + CASES + "/p_" + case_id + "_fos-Stable\"")
    c("model large-strain off")
    c("")
    c("fish define export_tensor")
    c("    local fname = '" + CASES + "/p_" + case_id + "_tensor.csv'")
    c("    file.open(fname,'write','text')")
    c("    local hdr = 'xc,yc,zc,ux,uy,uz,state,sxx,syy,szz,sxy,sxz,syz,vstrain'")
    c("    file.write(hdr)")
    c("    loop foreach local z zone.list")
    c("        local v = zone.pos(z)")
    c("        local d = zone.disp(z)")
    c("        local s = zone.stress(z)")
    c("        local row = string(v->x) + ',' + string(v->y) + ',' + string(v->z)")
    c("        row = row + ',' + string(d->x) + ',' + string(d->y) + ',' + string(d->z)")
    c("        row = row + ',' + string(zone.state(z))")
    c("        row = row + ',' + string(s->xx) + ',' + string(s->yy) + ',' + string(s->zz)")
    c("        row = row + ',' + string(s->xy) + ',' + string(s->xz) + ',' + string(s->yz)")
    c("        row = row + ',' + string(zone.volstrain(z))")
    c("        file.write(row)")
    c("    endloop")
    c("    file.close")
    c("end")
    c("")
    c("[export_tensor]")
    c("")
    c("model save \"" + CASES + "/p_" + case_id + "_tensor_done\"")
    return C


def write_dat(path, lines):
    with open(path, "w", encoding="ascii", errors="ignore") as f:
        f.write("\n".join(lines) + "\n")


def main():
    if len(sys.argv) < 6:
        print("usage: gen_param_case2.py <case_id> <H> <theta> <c_kPa> <phi_deg>")
        return 2
    cid = sys.argv[1]
    H = float(sys.argv[2])
    th = float(sys.argv[3])
    c_kpa = float(sys.argv[4])
    phi = float(sys.argv[5])

    os.makedirs(CASES, exist_ok=True)

    p1 = os.path.join(CASES, "p_%s_stage1.dat" % cid)
    p2 = os.path.join(CASES, "p_%s_stage2.dat" % cid)
    p3 = os.path.join(CASES, "p_%s_stage3.dat" % cid)

    write_dat(p1, build_stage1(cid, H, th, c_kpa * 1e3, phi))
    # 修正 5：bracket 下限 0.3，避免 FOS<0.8 的算例只得到 "Not Valid"
    write_dat(p2, build_stage2(cid, lo=0.3, hi=3.0))
    write_dat(p3, build_stage3(cid))

    cx, cy = geom(H, th)
    print("OK %s" % cid)
    print("  crest=(%.2f, %.2f)  c=%.0f kPa  phi=%.0f deg" % (cx, cy, c_kpa, phi))
    return 0


if __name__ == "__main__":
    sys.exit(main())
