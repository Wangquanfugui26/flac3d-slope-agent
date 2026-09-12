# -*- coding: utf-8 -*-
"""三算例 Bishop 参照 —— 与 FLAC3D SSR 的独立交叉校核。

FLAC3D 值来自修复后管道（网格共形 + 双判据自平衡 + bracket 下限 0.3）：
    base45  1.685   （与早期手工交互运行逐位一致，L1 复现性通过）
    c10p15  0.75    （bracket 下限由 0.8 放宽至 0.3 后解出）
    t60     1.32    （网格共形修复后解出）

Bishop 简化法为条分法，与 FLAC3D 的连续介质有限差分在数学结构上完全独立，
故二者吻合具有真实的校核意义。
"""
import contextlib
import io
import sys

sys.path.insert(0, r"D:/Flac3d/FLAC3D边坡模拟/脚本")
import bishop_final as B  # noqa: E402

# (id, H, theta, c_kPa, phi_deg, FLAC3D_FOS)
CASES = [
    ("base45", 10, 45, 30, 25, 1.685),
    ("c10p15", 10, 45, 10, 15, 0.75),
    ("t60",    10, 60, 30, 25, 1.32),
]


def main():
    print("=" * 68)
    print("三算例验证：FLAC3D SSR  vs  Bishop 简化法（独立方法交叉）")
    print("=" * 68)
    print("%-9s %-8s %-6s %-10s %-10s %s"
          % ("case", "c(kPa)", "phi", "FLAC3D", "Bishop", "偏差"))
    rows = []
    for cid, H, th, c, phi, fl in CASES:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = B.fos_bishop(H=H, theta_deg=th, c=c * 1e3, phi_deg=phi,
                             verbose=False)
        # fos_bishop 返回 dict（键 F 为 FOS，另含临界滑面参数 xc/yc/R/xe/xi/n）
        f = r["F"] if isinstance(r, dict) else r
        dev = (fl - f) / f * 100.0
        rows.append((cid, c, phi, fl, f, dev))
        print("%-9s %-8s %-6s %-10.3f %-10.4f %+7.2f%%"
              % (cid, c, phi, fl, f, dev))

    devs = [r[5] for r in rows]
    print()
    print("偏差范围: %+.2f%% ~ %+.2f%%    均值 %+.2f%%"
          % (min(devs), max(devs), sum(devs) / len(devs)))
    print("判据: FLAC3D 应略高于 Bishop，方向与量级一致（文献典型 5%~15%）。")
    ok = all(0 < d < 15 for d in devs)
    print("结论: %s" % ("三例全部通过" if ok else "存在异常，需复核"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
