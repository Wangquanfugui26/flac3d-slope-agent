# -*- coding: utf-8 -*-
"""数据可用性探针：确认三个 CSV 能支撑哪些机理分析。"""
import csv, os
import numpy as np

DATA = r"D:/Flac3d/FLAC3D边坡模拟/FLAC3D模型与数据"
KEYS = ("x","y","z","ux","uy","uz","state","szz","sxy")

def load(tag):
    p = os.path.join(DATA, f"slope_{tag}.csv")
    rows = []
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        rd = csv.reader(f)
        next(rd, None)
        for r in rd:
            if len(r) >= 9:
                try:
                    rows.append([float(v) for v in r[:9]])
                except ValueError:
                    pass
    a = np.array(rows)
    return {k: a[:, i] for i, k in enumerate(KEYS)}

for tag in ("gravity", "stable", "failure"):
    d = load(tag)
    n = len(d["x"])
    umag = np.sqrt(d["ux"]**2 + d["uy"]**2 + d["uz"]**2)
    st = d["state"].astype(int)
    print(f"\n===== {tag}  n={n} =====")
    print(f"  x range {d['x'].min():.2f} ~ {d['x'].max():.2f}")
    print(f"  y range {d['y'].min():.2f} ~ {d['y'].max():.2f}")
    print(f"  z range {d['z'].min():.2f} ~ {d['z'].max():.2f}")
    print(f"  |u| max  {umag.max():.6f} m   mean {umag.mean():.6f}")
    print(f"  ux range [{d['ux'].min():.4f}, {d['ux'].max():.4f}]")
    print(f"  uy range [{d['uy'].min():.4f}, {d['uy'].max():.4f}]")
    print(f"  szz    range [{d['szz'].min():.1f}, {d['szz'].max():.1f}] Pa")
    print(f"  sxy    range [{d['sxy'].min():.1f}, {d['sxy'].max():.1f}] Pa")
    vals, cnts = np.unique(st, return_counts=True)
    print(f"  state  {dict(zip(vals.tolist(), cnts.tolist()))}")
    # 按 z 分层核对是否模型为二维平面应变（同一 (x,y) 各 z 层应一致）
    zs = np.unique(np.round(d["z"], 3))
    print(f"  z layers: {zs.tolist()}")
