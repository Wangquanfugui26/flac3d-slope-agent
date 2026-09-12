# FLAC3D 三维边坡数值模拟 — 完整成果包

> 项目：三维均质边坡稳定性分析
> 求解引擎：**本机 FLAC3D 7.00**（`D:\Flac3d\FLAC\exe64\flac3d700_console.exe`）
> 完成时间：2026-09-11

---

## 一、核心结论

| 项目 | 结果 |
|---|---|
| **安全系数 FOS** | **1.685**（强度折减法，二分区间 0.8~3.0） |
| 最大总位移（失稳态） | 404.6 mm |
| 最大总位移（自重平衡态） | 35.1 mm |
| 单元总数 | 2670 |
| 破坏模式 | 圆弧形旋转滑动 |

---

## 二、目录结构

```
FLAC3D边坡模拟/
├── README.md                      ← 本文件（总索引）
├── 边坡数值模拟报告.md              ← 完整技术报告（推荐先读）
├── FLAC3D-MCP配置清单.md            ← MCP 连接器配置说明
├── FLAC3D脚本驱动踩坑记录.md         ← 技术踩坑总结（FISH 语法等）
│
├── 结果图/                         ← 11 张成果图（Python matplotlib 绘制）
│   ├── FOS_summary.png                    安全系数汇总
│   ├── displacement_magnitude_failure.png 失稳态总位移云图（核心图）
│   ├── displacement_magnitude_gravity.png 自重态总位移云图
│   ├── displacement_failure.png           失稳态位移三分量
│   ├── displacement_gravity.png           自重态位移三分量
│   ├── plastic_failure.png                失稳态塑性区
│   ├── plastic_gravity.png                自重态塑性区
│   ├── vectors_failure.png                失稳态位移矢量场
│   ├── vectors_gravity.png                自重态位移矢量场
│   ├── stress_failure.png                 失稳态应力场
│   └── stress_gravity.png                 自重态应力场
│
├── 脚本/                           ← 可复现的全部脚本
│   ├── gen_slope.py                       生成 FLAC3D 建模脚本 (stage1.dat)
│   ├── plot_slope.py                      读 CSV 绘图
│   └── flac_console_driver2.py            驱动 FLAC3D 控制台的驱动器
│
├── FLAC3D模型与数据/                ← FLAC3D 原始输入与输出
│   ├── stage1.dat                         建模 + 自重平衡 + 导出
│   ├── stage2.dat                         强度折减法求 FOS
│   ├── stage3.dat                         导出失稳/稳定态数据
│   ├── slope_gravity.csv                  自重平衡态结果（2670 行）
│   ├── slope_failure.csv                  失稳态结果
│   ├── slope_stable.csv                   稳定态结果
│   ├── slope_gravity.sav                  自重平衡模型存档
│   └── slope_fos-{Init,Stable,Unstable}.sav   FOS 计算过程存档
│
├── 原始输出日志/                    ← 求解过程原始记录（FLAC3D 程序日志）
│   ├── s1.log                             阶段一程序日志
│   ├── s2.log                             阶段二程序日志（含 FOS = 1.685）
│   └── s3.log                             阶段三程序日志
│
└── 调试过程留档/                    ← 调试痕迹（保留备查，非必需）
    ├── 探针脚本/                            FISH 语法探测用的一次性脚本
    ├── 屏幕抓取/                            控制台回读的屏幕快照
    └── _fos_probe_base.sav / _fosprobe-Init.sav
```

> **注**：`_s1/_s2/_s3_screen.txt`（控制台屏幕抓取）在 `调试过程留档/屏幕抓取/` 中也有一份，
> `原始输出日志/` 中的那三份是运行当时的直接记录。

---

## 三、如何复现

> 本包位置：`D:\Flac3d\FLAC3D边坡模拟\`
> 脚本已内置路径自适应：绘图脚本会自动读写**本包内**的 `FLAC3D模型与数据/` 与 `结果图/`，
> 无需手动改路径。

```bash
# 1) 生成建模脚本（输出到 D:\Flac3d\FLAC\exe64\stage1.dat）
python "D:\Flac3d\FLAC3D边坡模拟\脚本\gen_slope.py"

# 2) 阶段一：建模 + 自重平衡
python "D:\Flac3d\FLAC3D边坡模拟\脚本\flac_console_driver2.py" \
    'call "D:/Flac3d/FLAC/exe64/stage1.dat"' 200 out1.txt

# 3) 阶段二：强度折减法求安全系数
python "D:\Flac3d\FLAC3D边坡模拟\脚本\flac_console_driver2.py" \
    'call "D:/Flac3d/FLAC/exe64/stage2.dat"' 280 out2.txt

# 4) 阶段三：导出失稳态数据
python "D:\Flac3d\FLAC3D边坡模拟\脚本\flac_console_driver2.py" \
    'call "D:/Flac3d/FLAC/exe64/stage3.dat"' 90 out3.txt

# 5) 绘图（用带 matplotlib 的 Python；图自动写入本包 结果图/）
D:\VS\Shared\Python39_64\python.exe "D:\Flac3d\FLAC3D边坡模拟\脚本\plot_slope.py" failure 1.685
D:\VS\Shared\Python39_64\python.exe "D:\Flac3d\FLAC3D边坡模拟\脚本\plot_slope.py" gravity
```

**说明**：
- 阶段 1~3 的 `.dat` 脚本由 `flac_console_driver2.py` 在 FLAC3D 工作目录
  `D:\Flac3d\FLAC\exe64` 下执行，故 CSV 输出到该目录；如需改到别处，
  修改 `gen_slope.py` 与 `stage*.dat` 内的路径即可。
- `plot_slope.py` 会自动优先读取本包 `FLAC3D模型与数据/` 内的 CSV，
  若不存在则回退到 `D:\Flac3d\FLAC\exe64`。

---

## 四、模型参数速查

| 项目 | 取值 |
|---|---|
| 模型尺寸 | 30 m (x) × 20 m (y) × 6 m (z) |
| 坡高 / 坡角 | 10 m / 45° |
| 坡趾 / 坡顶内缘 | (20, 10) / (10, 20) |
| 坡趾到右边界 | 10 m |
| 本构模型 | Mohr-Coulomb |
| ρ / K / G | 2500 kg/m³ / 1e8 Pa / 6e7 Pa |
| c / φ / σt | 30 kPa / 25° / 10 kPa |
| 重力 | 9.81 m/s²（−y 方向） |

---

## 五、计算环境说明

- **FLAC3D**：本机 `D:\Flac3d\FLAC\exe64\flac3d700_console.exe`（7.00 版）
- **调用方式**：Win32 控制台 API 注入命令（`flac_console_driver2.py`），脚本化驱动
- **Python 绘图环境**：`D:\VS\Shared\Python39_64\python.exe`（matplotlib 3.9.4 + numpy 2.0.2）
- **注意**：本机 managed Python 3.13 未安装 matplotlib，绘图统一用上述 3.9 环境

### 为什么没走 itasca-mcp？

`itasca-mcp` 的执行类工具依赖 `itasca-mcp-bridge`，而 bridge **必须在 FLAC3D 进程内部启动**（在独立 Python 中调用会报 `RuntimeError: itasca module not available; run bridge inside an ITASCA product GUI`）。因此改走**控制台直驱**路线，计算仍全部由本机 FLAC3D 完成，效果等效。

---

## 六、重要假设（需确认）

模型总高 20 m、坡高 10 m，本模拟判定 **坡趾标高 y = 10 m**（坡面自半高处起坡，坡顶平台 y=20 由 x=0 延伸至 x=10）。

若原意为「坡趾在地面 y=0、坡顶在 y=10」，则模型需重建，结果会随之改变。
