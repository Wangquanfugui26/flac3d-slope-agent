"""
生成 FLAC3D 边坡模拟的 .dat 脚本。

基于实测的 FISH API 约束：
  file.open(名字, "write", "text")   -- 模式与类型必须是字符串
  file.write(指针, 列表)              -- 参数是列表
  gp.disp.x(zone.gp(z,j))            -- 单元位移取 8 角点平均
  zone.state(z)                      -- 返回整数位编码

几何（m）：x 0~30，y 0~20，z 厚 0~6
  坡趾 (20,10)，坡顶内缘 (10,20)，坡角 45deg
"""

import os

OUT_DIR = r"D:\Flac3d\FLAC\exe64"

L = 30.0
H = 20.0
THICK = 6.0
TOE_X = 20.0
TOE_Y = 10.0
CREST_X = 10.0
CREST_Y = 20.0

NX_LOW = 30
NY_LOW = 10
NZ = 6
LAYER_H = 1.0

DENS = 2500.0
BULK = 1.0e8
SHEAR = 6.0e7
COH = 3.0e4
PHI = 25.0
TENS = 1.0e4

OUT = "D:/Flac3d/FLAC/exe64"


def gen_stage1(csv="slope_gravity.csv", log="s1.log", prefix="slope_gravity"):
    L_ = []
    a = L_.append

    a("model new")
    a('model title "3D Slope - Mohr-Coulomb"')
    a("model large-strain on")
    a("model mechanical")
    a("model deterministic on")
    a("model precision 6")
    a("model random 10000")
    a("")
    a(f'program log-file "{OUT}/{log}" truncate')
    a("program log on")
    a("")

    a(f"zone create brick point 0 (0,0,0) point 1 ({L},0,0) "
      f"point 2 (0,{TOE_Y},0) point 3 (0,0,{THICK}) "
      f'size {NX_LOW} {NY_LOW} {NZ} group "lower"')
    a("")

    n_layers = int(round((CREST_Y - TOE_Y) / LAYER_H))
    for i in range(n_layers):
        yb = TOE_Y + i * LAYER_H
        yt = yb + LAYER_H
        xr = max(CREST_X, min(TOE_X, L - yt))
        nx = int(round(xr))
        if nx < 1:
            continue
        a(f"zone create brick point 0 (0,{yb},0) point 1 ({xr},{yb},0) "
          f"point 2 (0,{yt},0) point 3 (0,{yb},{THICK}) "
          f'size {nx} 1 {NZ} group "upper"')
    a("")

    a("zone cmodel assign mohr-coulomb")
    a(f"zone property density {DENS} bulk {BULK} shear {SHEAR} "
      f"cohesion {COH} friction {PHI} tension {TENS}")
    a("")

    a("model gravity 0 -9.81 0")
    a("zone gridpoint fix velocity-x range position-x 0")
    a(f"zone gridpoint fix velocity-x range position-x {L}")
    a("zone gridpoint fix velocity-y range position-y 0")
    a("zone gridpoint fix velocity-z range position-z 0")
    a(f"zone gridpoint fix velocity-z range position-z {THICK}")
    a("")

    a("model solve ratio-local 1e-5")
    a("")

    a("fish define export_g")
    a("    local L = list")
    a("    L = list.append(L, 'xc,yc,zc,ux,uy,uz,state,szz,sxy')")
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
    a("        local line = string(p->x)")
    a("        line += ',' + string(p->y)")
    a("        line += ',' + string(p->z)")
    a("        line += ',' + string(sdx)")
    a("        line += ',' + string(sdy)")
    a("        line += ',' + string(sdz)")
    a("        line += ',' + string(zone.state(zz))")
    a("        line += ',' + string(st->yy)")
    a("        line += ',' + string(st->xy)")
    a("        L = list.append(L, line)")
    a("    endloop")
    a(f'    file.open("{OUT}/{csv}", "write", "text")')
    a("    file.write(L)")
    a("    file.close")
    a("    io.out('### CSV EXPORTED')")
    a("end")
    a("@export_g")
    a("")
    a(f'model save "{OUT}/{prefix}"')
    a("program log off")

    p = os.path.join(OUT_DIR, "stage1.dat")
    with open(p, "w", encoding="ascii", errors="ignore") as f:
        f.write("\n".join(L_))
    print(f"written: {p}  ({len(L_)} lines)")
    return p


if __name__ == "__main__":
    gen_stage1()
