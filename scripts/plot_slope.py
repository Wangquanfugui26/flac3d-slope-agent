"""
Slope simulation result visualization.

Input CSV columns: xc,yc,zc,ux,uy,uz,state,szz,sxy[,sxz,syz]
  state is a bit mask:
    1 = shear-n   2 = tension-n
    4 = shear-p   8 = tension-p

Outputs (to D:\\Flac3d\\results):
  1. displacement cloud maps (total / vertical / horizontal)
  2. plastic zone distribution
  3. displacement vectors
  4. stress cloud maps
  5. FOS summary figure
"""

import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei", "SimHei", "DejaVu Sans"
]
plt.rcParams["axes.unicode_minus"] = False

# CSV 数据目录：优先使用本包的「FLAC3D模型与数据」目录，其次回退到 FLAC3D 工作目录
_PKG_DATA = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "FLAC3D模型与数据"
)
OUT_DIR = _PKG_DATA if os.path.isdir(_PKG_DATA) else r"D:\Flac3d\FLAC\exe64"
# 图片输出目录：默认写到本包的「结果图」目录（脚本位于 <包>\脚本\，故上溯一级）
FIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "结果图")

BIT_SHEAR_N = 1
BIT_TENSION_N = 2
BIT_SHEAR_P = 4
BIT_TENSION_P = 8

KEYS = ("x", "y", "z", "ux", "uy", "uz", "state", "szz", "sxy", "sxz", "syz")


def read_csv(path):
    cols = {k: [] for k in KEYS}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        rd = csv.reader(f)
        next(rd, None)
        for row in rd:
            if len(row) < 9:
                continue
            try:
                vals = [float(v) for v in row[:9]]
            except ValueError:
                continue
            for k, v in zip(KEYS, vals):
                cols[k].append(v)
            for k in KEYS[9:]:
                cols[k].append(0.0)
    return {k: np.array(v) for k, v in cols.items()}


def _frame(ax):
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal")
    ax.grid(alpha=0.25, linewidth=0.4)


def plot_displacement(d, tag, fos=None):
    xs, ys = d["x"], d["y"]
    umag = np.sqrt(d["ux"] ** 2 + d["uy"] ** 2 + d["uz"] ** 2)
    fig, axes = plt.subplots(1, 3, figsize=(19, 5.6))
    for ax, data, ttl, cm in [
        (axes[0], umag, "Total displacement |u| (m)", "turbo"),
        (axes[1], d["uy"], "Vertical displacement uy (m)", "RdBu_r"),
        (axes[2], d["ux"], "Horizontal displacement ux (m)", "RdBu_r"),
    ]:
        sc = ax.scatter(xs, ys, c=data, s=13, cmap=cm, marker="s")
        ax.set_title(ttl, fontsize=12)
        plt.colorbar(sc, ax=ax, fraction=0.046)
        _frame(ax)
    t = f"Slope displacement field - {tag}"
    if fos is not None:
        t += f"   (FOS = {fos:.3f})"
    fig.suptitle(t, fontsize=14)
    fig.tight_layout()
    p = os.path.join(FIG_DIR, f"displacement_{tag}.png")
    fig.savefig(p, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return p


def plot_plastic(d, tag, fos=None):
    xs, ys, st = d["x"], d["y"], d["state"].astype(int)
    fig, ax = plt.subplots(figsize=(10.5, 7))

    elastic = st == 0
    shear_n = (st & BIT_SHEAR_N) != 0
    tension_n = (st & BIT_TENSION_N) != 0
    # zones that only ever yielded in the past (no active failure)
    only_past = (~elastic) & (~shear_n) & (~tension_n)

    handles = []
    ax.scatter(xs[elastic], ys[elastic], c="#EBE9E2", s=14,
               marker="s", edgecolors="#C9C6BE", linewidths=0.3)
    handles.append(Patch(facecolor="#EBE9E2", edgecolor="#C9C6BE",
                         label=f"Elastic ({int(elastic.sum())})"))
    ax.scatter(xs[only_past], ys[only_past], c="#F09595", s=14,
               marker="s", edgecolors="none")
    handles.append(Patch(facecolor="#F09595",
                         label=f"Yielded in past only ({int(only_past.sum())})"))
    if tension_n.any():
        ax.scatter(xs[tension_n], ys[tension_n], c="#185FA5", s=20,
                   marker="s", edgecolors="none")
        handles.append(Patch(facecolor="#185FA5",
                             label=f"Tension failure now ({int(tension_n.sum())})"))
    ax.scatter(xs[shear_n], ys[shear_n], c="#E24B4A", s=20,
               marker="s", edgecolors="none")
    handles.append(Patch(facecolor="#E24B4A",
                         label=f"Shear failure now ({int(shear_n.sum())})"))

    ax.legend(handles=handles, loc="upper right", fontsize=9, framealpha=0.95)
    _frame(ax)
    t = f"Plastic zone distribution - {tag}"
    if fos is not None:
        t += f"   (FOS = {fos:.3f})"
    ax.set_title(t, fontsize=13)
    p = os.path.join(FIG_DIR, f"plastic_{tag}.png")
    fig.savefig(p, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return p, int(elastic.sum()), int(len(st) - elastic.sum())


def plot_vectors(d, tag, stride=5):
    xs, ys = d["x"], d["y"]
    umag = np.sqrt(d["ux"] ** 2 + d["uy"] ** 2)
    fig, ax = plt.subplots(figsize=(11, 7))
    sc = ax.scatter(xs, ys, c=umag, s=14, cmap="turbo", marker="s", alpha=0.75)
    plt.colorbar(sc, ax=ax, fraction=0.046, label="|u| (m)")
    umax = umag.max() if umag.max() > 0 else 1.0
    span = max(xs.max() - xs.min(), ys.max() - ys.min())

    # subsample so arrows stay legible
    keep = np.zeros(len(xs), dtype=bool)
    keep[::stride] = True
    keep &= (umag > umax * 0.004)
    q = ax.quiver(xs[keep], ys[keep], d["ux"][keep], d["uy"][keep],
                  color="#2C2C2A", scale=umax / (0.26 * span), width=0.0038,
                  headwidth=4.5, headlength=5.5, alpha=0.9)
    _frame(ax)
    ax.set_title(f"Displacement vectors - {tag}  (every {stride}th zone)", fontsize=13)
    p = os.path.join(FIG_DIR, f"vectors_{tag}.png")
    fig.savefig(p, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return p


def plot_magnitude(d, tag, fos=None):
    """Standalone total-displacement contour, the headline figure."""
    xs, ys = d["x"], d["y"]
    umag = np.sqrt(d["ux"] ** 2 + d["uy"] ** 2 + d["uz"] ** 2) * 1e3  # mm
    fig, ax = plt.subplots(figsize=(11, 6.8))
    sc = ax.scatter(xs, ys, c=umag, s=42, cmap="turbo", marker="s",
                    edgecolors="none")
    cb = plt.colorbar(sc, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("|u| (mm)", fontsize=11)
    _frame(ax)
    t = f"Total displacement magnitude - {tag}"
    if fos is not None:
        t += f"   (FOS = {fos:.3f})"
    ax.set_title(t, fontsize=13)
    fig.tight_layout()
    p = os.path.join(FIG_DIR, f"displacement_magnitude_{tag}.png")
    fig.savefig(p, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return p


def plot_stress(d, tag):
    xs, ys = d["x"], d["y"]
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    sc = axes[0].scatter(xs, ys, c=d["szz"] / 1e3, s=13, cmap="viridis", marker="s")
    axes[0].set_title("Vertical stress szz (kPa)", fontsize=12)
    plt.colorbar(sc, ax=axes[0], fraction=0.046)
    _frame(axes[0])

    sc1 = axes[1].scatter(xs, ys, c=d["sxy"] / 1e3, s=13, cmap="RdBu_r", marker="s")
    axes[1].set_title("Shear stress sxy (kPa)", fontsize=12)
    plt.colorbar(sc1, ax=axes[1], fraction=0.046)
    _frame(axes[1])

    fig.suptitle(f"Stress field - {tag}", fontsize=14)
    fig.tight_layout()
    p = os.path.join(FIG_DIR, f"stress_{tag}.png")
    fig.savefig(p, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return p


def plot_fos_summary(fos, fos_prev, n_elas, n_plas, tag):
    """FOS summary panel: the strength-reduction result plus context."""
    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(14, 5.6), gridspec_kw={"width_ratios": [1.15, 1]}
    )

    # -- left: gauge-style bar
    ax.barh(["Slope"], [fos], color="#E24B4A", height=0.4)
    ax.axvline(1.0, color="#2C2C2A", linestyle="--", linewidth=1.5)
    ax.axvline(fos, color="#185FA5", linewidth=1.5)
    ax.text(fos, 0.32, f"  FOS = {fos:.3f}", va="bottom", ha="left",
            fontsize=14, fontweight="bold", color="#185FA5")
    for x, lab in [(1.0, "1.0  limit"), (1.5, "1.5  acceptable")]:
        ax.axvline(x, color="#9A9790", linestyle=":", linewidth=1.0)
        ax.text(x, -0.42, lab, ha="center", fontsize=8.5, color="#6E6B64")
    ax.set_xlim(0, max(fos * 1.35, 2.0))
    ax.set_xlabel("Factor of Safety")
    ax.set_title("Strength reduction result", fontsize=12)
    ax.grid(axis="x", alpha=0.3)
    ax.set_yticks([])

    # -- right: plastic / elastic breakdown
    ax2.bar(["Elastic", "Plastic (any)"], [n_elas, n_plas],
            color=["#EBE9E2", "#E24B4A"], edgecolor="#C9C6BE", width=0.5)
    tot = max(n_elas + n_plas, 1)
    for i, v in enumerate([n_elas, n_plas]):
        ax2.text(i, v + tot * 0.015, f"{v}\n({v / tot * 100:.1f}%)",
                 ha="center", fontsize=10.5)
    ax2.set_ylim(0, tot * 1.22)
    ax2.set_ylabel("Number of zones")
    ax2.set_title("Zone state at failure", fontsize=12)
    ax2.grid(axis="y", alpha=0.3)

    fig.suptitle("Slope stability assessment - Factor of Safety",
                 fontsize=14, fontweight="bold")
    fig.tight_layout()
    p = os.path.join(FIG_DIR, "FOS_summary.png")
    fig.savefig(p, dpi=170, bbox_inches="tight")
    plt.close(fig)
    return p


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "gravity"
    fos = float(sys.argv[2]) if len(sys.argv) > 2 else None

    os.makedirs(FIG_DIR, exist_ok=True)
    csv_path = os.path.join(OUT_DIR, f"slope_{tag}.csv")
    if not os.path.exists(csv_path):
        csv_path = os.path.join(OUT_DIR, "slope_gravity.csv")

    print(f"reading: {csv_path}")
    d = read_csv(csv_path)
    n = len(d["x"])
    if n == 0:
        print("ERROR: no data rows")
        return 1
    print(f"zones: {n}")
    print(f"|u| max = {np.sqrt(d['ux']**2+d['uy']**2+d['uz']**2).max():.4e} m")
    print(f"uy  range = [{d['uy'].min():.4e}, {d['uy'].max():.4e}] m")
    print(f"ux  range = [{d['ux'].min():.4e}, {d['ux'].max():.4e}] m")
    st = d["state"].astype(int)
    print(f"plastic bitmask: shear-n={(st&BIT_SHEAR_N>0).sum()}, "
          f"tension-n={(st&BIT_TENSION_N>0).sum()}, "
          f"shear-p={(st&BIT_SHEAR_P>0).sum()}, "
          f"tension-p={(st&BIT_TENSION_P>0).sum()}")

    outs = [plot_magnitude(d, tag, fos)]
    outs.append(plot_displacement(d, tag, fos))
    p2, n_elas, n_plas = plot_plastic(d, tag, fos)
    outs.append(p2)
    outs.append(plot_vectors(d, tag))
    outs.append(plot_stress(d, tag))
    if fos is not None and tag == "failure":
        outs.append(plot_fos_summary(fos, 1.0, n_elas, n_plas, tag))
    print(f"elastic = {n_elas}, plastic = {n_plas}")
    for o in outs:
        print(f"saved: {o}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
