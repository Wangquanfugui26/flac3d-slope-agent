# -*- coding: utf-8 -*-
"""
生成完整导出脚本 gen_export_full.dat。

相对原 stage3.dat 的改进：
  1. 导出完整应力张量 (sxx,syy,szz,sxy,sxz,syz) -- 原仅 szz/sxy，导致强度发挥度无法计算
  2. 导出体积应变
  3. 分别从 fos-Stable 与显式折减破坏态导出，不再混用同一状态

FISH 语义约束（已实测）：
  file.open(路径,"write","text") 不接收返回值
  file.write(列表) 只接受 1 个参数
  list.append(L, str) 需重新赋值
"""
import os
import math

OUT = "D:/Flac3d/FLAC/exe64"
FOS = 1.685
RED = 1.30 * FOS
C0 = 30e3
PHI0 = 25.0
C_RED = C0 / RED
PHI_RED = math.degrees(math.atan(math.tan(math.radians(PHI0)) / RED))

HEADER = "xc,yc,zc,ux,uy,uz,state,sxx,syy,szz,sxy,sxz,syz,volstrain"


def export_block(fishname, csv, marker):
    L = []
    a = L.append
    a("fish define " + fishname)
    a("    local Lst = list")
    a("    Lst = list.append(Lst, '" + HEADER + "')")
    a("    loop foreach local zz zone.list")
    a("        local p = zone.pos(zz)")
    a("        local ngp = zone.gp.num(zz)")
    a("        local sdx = 0.0")
    a("        local sdy = 0.0")
    a("        local sdz = 0.0")
    a("        loop local j (1, ngp)")
    a("            local g = zone.gp(zz, j)")
    a("            sdx += gp.disp.x(g)")
    a("            sdy += gp.disp.y(g)")
    a("            sdz += gp.disp.z(g)")
    a("        endloop")
    a("        sdx /= ngp")
    a("        sdy /= ngp")
    a("        sdz /= ngp")
    a("        local st = zone.stress(zz)")
    a("        local vs = zone.prop(zz, 'volumetric-strain')")
    a("        local row = string(p->x) + ',' + string(p->y) + ',' + string(p->z)")
    a("        row += ',' + string(sdx) + ',' + string(sdy) + ',' + string(sdz)")
    a("        row += ',' + string(zone.state(zz))")
    a("        row += ',' + string(st->xx) + ',' + string(st->yy) + ',' + string(st->zz)")
    a("        row += ',' + string(st->xy) + ',' + string(st->xz) + ',' + string(st->yz)")
    a("        row += ',' + string(vs)")
    a("        Lst = list.append(Lst, row)")
    a("    endloop")
    a('    file.open("' + OUT + "/" + csv + '", "write", "text")')
    a("    file.write(Lst)")
    a("    file.close")
    a("    io.out('### " + marker + "')")
    a("end")
    a("@" + fishname)
    a("")
    return L


lines = []
lines.append('model restore "' + OUT + '/slope_gravity"')
lines.append('program log-file "' + OUT + '/s_export.log" truncate')
lines.append("program log on")
lines.append("")
lines.append("; --- state 1: gravity equilibrium ---")
lines += export_block("exp_gravity", "full_gravity.csv", "GRAVITY EXPORTED")
lines.append("")
lines.append("; --- state 2: critical state at FOS (restore from SSR output) ---")
lines.append('model restore "' + OUT + '/slope_fos-Stable"')
lines.append("model large-strain off")
lines += export_block("exp_stable", "full_stable.csv", "STABLE EXPORTED")
lines.append("")
lines.append("; --- state 3: true failure (explicit reduction by 1.30*FOS) ---")
lines.append('model restore "' + OUT + '/slope_gravity"')
lines.append("model large-strain off")
lines.append("zone property cohesion " + repr(C_RED) + " friction " + repr(PHI_RED))
lines.append("model solve ratio-local 1e-5")
lines += export_block("exp_broken", "full_broken.csv", "BROKEN EXPORTED")
lines.append('model save "' + OUT + '/slope_broken"')
lines.append("program log off")

p = os.path.join(OUT, "gen_export_full.dat")
with open(p, "w", encoding="ascii", errors="ignore") as f:
    f.write("\n".join(lines))
print("written: " + p + "  (" + str(len(lines)) + " lines)")
print("reduction factor = " + str(RED) + "  c_red = " + str(C_RED) + "  phi_red = " + str(PHI_RED))
