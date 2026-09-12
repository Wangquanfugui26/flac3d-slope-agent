# -*- coding: utf-8 -*-
"""把今晚的根因发现与续做清单追加到项目记忆。一次性脚本。"""
import io
import os

MEM = r"C:/Users/wangfugui26/WorkBuddy AI/2026-09-11-15-12-22/.workbuddy-ai/memory/2026-09-11.md"

NOTE = u"""

---

## ★★ 重大根因发现：非共形网格导致上部坡体成为悬浮孤立体（2026-09-11 晚，收工存档）

**用户指令**：先只重跑 3 个关键算例验证；暂时搁置 bracket 收敛，优先把论文写完；
22:2x 用户要关机，明日继续。

### 一、真正的根因（推翻了此前两个错误假设）

**症状**：t60（theta=60）的 model solve 中 ratio-local 恒为 1.00000e+00，
200000 步 / 242 s 毫不下降，`***` 计数为 0（完全静默）。
其 gravity.sav 是无效应力态，SSR 从它出发必然报
"Model is unstable at maximum specified Factor of Safety"，
无论 bracket 下限压到多低（实测 0.8 / 0.3 / 0.05 全部 Not Valid）。

**根因**：FLAC3D 的 zone create brick 不会自动缝合非共形界面。
- 下部整块是 size 30 10 6，x 向单元尺寸恰好 1.0 m。
- 上部条带若单元尺寸 != 1.0 m，网格节点与下部块错位，两块不连通，
  上部坡体成为自由悬浮体 -> 力传不上去 -> ratio 恒为 1.0。

**实测对照（关键）**：

| xr（条带右边界） | nx（段数） | 单元尺寸 | 共形性 | 结果 |
|---|---|---|---|---|
| 19.0000 | 19 | 1.0000 m | 共形 | 收敛（base45，4342 步）|
| 18.8453 | 19 | 0.9919 m | 错位 | ratio 恒 1.0（t60 失败）|
| 19.0000 | 18 | 1.0556 m | 错位 | ratio 恒 1.0（失败）|

**注意**：把段数"减一"同样破坏共形性 —— 我一度误以为要 nx <= 宽度，
结果把 base45 也搞坏了。**段数必须与右边界坐标严格相等**。

**正确修法（已写入 gen_param_case2.py 的"修正 6"）**：
把条带右边界吸附到整数，令 nx == xr_snapped：

    nx = max(1, min(int(round(xr)), int(TOE_X)))
    xr = float(nx)

代价：阶梯在 x 向被量化为 1 m（可接受的几何近似）。
验证：theta=45 的网格与原始 base45 完全一致（1.685 结果不受影响）；
theta=60 的 10 层全部为 1.0 m 共形单元。

**论文归属**：属 C6 认知错误 / C2 隐性约束（软件不报错、不提示，静默产出无效模型）。

### 二、已验证的可信数据（可直接用于论文）

| 算例 | 参数 | FLAC3D FOS | Bishop | 偏差 | 状态 |
|---|---|---|---|---|---|
| base45 | c=30 phi=25 H=10 th=45 | 1.685 | 1.5778 | +6.8% | 两次运行逐位一致 |
| c10p15 | c=10 phi=15 H=10 th=45 | 0.75 | ~0.70 | +7.1% | 需 bracket 下限 0.3 |
| t60 | c=30 phi=25 H=10 th=60 | 待验证 | ~0.99 | — | 共形网格修复后待重跑 |

### 三、已确认的两条数值规律（论文核心方法论贡献）

**规律 1：不存在统一的收敛判据（自平衡 vs 强度折减是两个不同问题）**

| 自平衡判据 | 耗时 | 末步 | 末 ratio | *** | .sav |
|---|---|---|---|---|---|
| ratio-local 1e-5 | 421 s | 135738 | 0.990 | 0 | 无 |
| ratio-average 1e-4 | 902 s | 280186 | 1.84e-3 | 0 | 无 |
| cycles 3000 | 9 s | 3000 | — | 0 | 有 |

低强度边坡在重力下持续塑性流动，"力平衡"目标在物理上不存在。
**解法（已写入修正 4）**：model solve ratio-local 1e-5 cycles 20000（双判据取先到者）。
稳定算例仍按 1e-5 提前收敛（base45 仍 4342 步），不稳定算例由 20000 步兜底。

**规律 2：bracket 下限必须低于真实 FOS**
区间未覆盖时 FLAC3D 只回定性判断（Factor of Safety Not Valid），不报错。
**解法（已写入修正 5）**：下限放宽到 0.3。

### 四、论文当前状态

- 文件：D:/Flac3d/论文素材/论文全文_基于LLM_Agent的岩土数值模拟自动化.md
- **§5 已完整重写**（2693 -> 4730 字）：新增 L1/L2/L3 三层验证框架、
  三算例对照表、§5.4"不存在统一收敛判据"的完整论证、三态位移层级、
  zone.state 位掩码语义说明、fos-Unstable 是总崩溃而非滑面的提醒。
- **已删除**原先无效的自指式论证（"存档 AI 无法伪造"）。
- §1-4、§6-7 仍是旧版，待按国际期刊风格重写（用户的请求 b）。

### 五、明日续做清单（按优先级）

1. **跑完 t60 验证**（共形网格修复后）：stage1 + stage2，约 5 分钟。
   脚本已写好：D:/Flac3d/FLAC3D边坡模拟/脚本/_cf_run.py（若无则重建，
   逻辑同今晚 eZp4fj 任务：gen_param_case2 生成 -> 清旧产物 -> stage1 -> stage2）。
2. **重跑 26 算例参数化批次**（run_batch2.py，已含 .sav 校验）——
   论文"大工作量循环分析"那一章的数据基础。
   注意：所有算例都要用修正 4/5/6 重新生成。
3. **论文按国际期刊风格重写**（用户请求 b），七章骨架已设计：
   1 Intro / 2 Reproducible protocol / 3 Validation of the agent /
   4 Failure taxonomy / 5 Parametric study / 6 Mechanism analysis / 7 Discussion & limits
4. **机理分析章节**（用户请求 a）：机制工具链已存在
   （mech_analysis_v2.py / mech_slip_v3.py / mech_slip_v4.py / plot_mechanism.py，产出 M1-M6 六图），
   但尚未写成正式章节。
5. 补参考文献 [7][8][9]；英文摘要。

### 六、工具链现状（全部可用，勿重复造轮子）

| 脚本 | 作用 |
|---|---|
| flac_console_driver4.py | 唯一可用的驱动。-b 模式 + 末尾仅加 exit + 二进制 LF 写入 + 线程读 stdout + 超时兜底 |
| gen_param_case2.py | 算例生成器，已含修正 1-6（引号 group / large-strain off / sigma_yy / 双判据 / bracket 0.3 / 共形网格）|
| run_batch2.py | 批量编排，校验 .sav 存在性 + 无 *** 才记录 |
| probe_console.py | 读活动进程控制台屏幕（9001 行缓冲区需分段读，整块读返回 0 字符）|
| diag_snap.py | 采样 CPU/内存，区分"在算"与"挂住" |
| procs.py / kill_pids.py | 进程列举/终止（GBK 解码，ctypes 终止，绕开被禁的 wmic/cmd）|

**FLAC3D -b 模式的硬约束（血泪教训，逐条实测）**：
1. -b 不会自动退出，脚本末尾必须加 exit（加 return 会挂死）。
2. group 名必须加引号：group lower（无引号）会让解析器无限挂起。
3. 脚本必须是 LF 换行（CRLF 会让解析器静默截断后续内容）。
4. 任何 *** 错误会令该行之后所有语句被静默跳过（C3 静默失败）。
5. 若 stdout 被管道接走，进程控制台屏幕为空，probe 读不到内容 —— 改读日志文件尾部。

**收工时的进程状态**：FLAC3D 已全部终止，无残留进程；无后台任务在跑。
"""

with io.open(MEM, "a", encoding="utf-8") as f:
    f.write(NOTE)

print("appended %d chars to %s" % (len(NOTE), os.path.basename(MEM)))
