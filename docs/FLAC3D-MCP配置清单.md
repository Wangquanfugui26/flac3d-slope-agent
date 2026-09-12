# FLAC3D MCP 连接配置与启动清单

生成时间：2026-09-11
适用环境：FLAC3D 7.00（D:\Flac3d\FLAC\），Windows

---

## 一、配置文件（已完成）

已创建：`C:\Users\wangfugui26\.workbuddy-ai\mcp.json`

```json
{
  "mcpServers": {
    "itasca-mcp": {
      "type": "stdio",
      "command": "C:\\Users\\wangfugui26\\AppData\\Roaming\\Python\\Python39\\Scripts\\uvx.exe",
      "args": [
        "itasca-mcp"
      ]
    }
  }
}
```

备用 uvx 路径（若上面那个启动报错时替换）：

```
C:\Users\wangfugui26\.local\bin\uvx.exe
```

注意：`software` / `version` 是工具调用时传的参数，**不要**写进 args。

---

## 二、启用步骤（必须做，否则不生效）

1. 打开**连接器管理页面**
2. 点右上角的 **「自定义连接器」** 入口
3. 找到 `itasca-mcp`，点 **「信任」**
4. 信任后才会真正加载

新写入的 MCP 配置**不会自动生效**，这一步不能跳。

---

## 三、启动 bridge（执行类工具必需）

10 个工具中只有 5 个文档查询工具无需 bridge；跑仿真、执行代码这 5 个必须先在 FLAC3D 里启动 bridge。

**首次 / 每次会话**：

1. 打开 FLAC3D GUI：
   ```
   D:\Flac3d\FLAC\exe64\flac3d700_gui.exe
   ```
2. 在 GUI 内的 **IPython 控制台**执行 `D:\Flac3d\addon.py` 的内容
   （或直接从 GUI 里打开该文件执行）
3. 脚本会自动从 PyPI 安装/升级 `itasca-mcp-bridge`，然后启动服务

**之后每次新开 FLAC 会话，只需跑一句**：

```python
import itasca_mcp_bridge
itasca_mcp_bridge.start()
```

脚本是幂等的，重复执行安全。PyPI 连不上但本地已装时会跳过升级直接启动。

---

## 四、验证

### 已验证通过（2026-09-11）

**组件 1：MCP Server（itasca-mcp）**

命令：

```bash
uvx --from itasca-mcp itasca-mcp --help
```

结果：**EXIT=0，正常启动**。依赖全部安装成功（72 个包）。

**组件 2：Bridge（itasca-mcp-bridge）**

命令：

```bash
uvx --from itasca-mcp-bridge python -c "import itasca_mcp_bridge; print('OK')"
```

结果：**安装并导入成功**（1 个包，164ms）。说明 bridge 包在 PyPI 可用、
本机网络可达，FLAC3D 内执行 addon.py 时的安装步骤有保障。

**组件 3：地址对齐（已确认）**

- `addon.py` 启动 bridge 后监听 `http://localhost:9001`
- `itasca-mcp` 的 `--bridge-url` 默认值正是 `http://localhost:9001`
- `bridge.start()` 签名实测为 `start(host='localhost', port=9001, mode='auto', auto_upgrade=True)`

三者完全对齐，**无需任何额外参数配置**。

**组件 4：bridge 必须在 FLAC3D 进程内启动（重要约束，已实测）**

在普通 Python 环境里直接调用 `bridge.start()` 会报错：

```
RuntimeError: itasca module not available;
run bridge inside an ITASCA product GUI (PFC, FLAC3D, ...)
```

**结论：bridge 不能独立运行，必须从 FLAC3D 内部启动。**
这印证了 `addon.py` 注释里 "Run this *inside* FLAC's embedded Python" 的要求。

bridge 其余实测信息：

| 项 | 值 |
|---|---|
| bridge 版本 | 0.5.2 |
| `VALID_RUNTIME_MODES` | `('auto', 'gui', 'console')` |
| `DEFAULT_TIMER_INTERVAL_MS` | 20 |
| `DEFAULT_MAX_TASKS_PER_TICK` | 1 |
| 对外接口 | `start` / `upgrade` / `announce` / `runtime` / `whats_new` |

注意 `console` 模式的存在 —— 说明 bridge 也支持从 FLAC3D **控制台版**启动，
如果 GUI 路线有问题，可以改走 `flac3d700_console.exe`。

`itasca-mcp` 支持的启动参数：

| 参数 | 说明 | 默认值 |
|---|---|---|
| `--transport` | 传输协议，可选 stdio / http / sse | `stdio` |
| `--bridge-url` | bridge 的 HTTP 地址 | `http://localhost:9001` |
| `--bridge-port` | bridge 端口（`--bridge-url` 的简写） | `9001` |
| `--log-level` | 日志级别 | `warning` |

已确认它会自动选择 Python 3.12 解释器运行（拉取的是 cp312 wheel），
所以 hosts Python 3.9 不影响使用。

### 还需你做的验证

1. 在「自定义连接器」点信任后，测**文档类工具**（无需 bridge）→ 确认 MCP 通了
2. 在 FLAC3D 里启动 bridge 后，测**执行类工具** → 确认 bridge 通了

### 排查记录：uv 缓存锁卡住

首次启动时若超时中断，会残留 uvx.exe / uv.exe 进程占着缓存锁，
导致后续报 `Failed to acquire lock on the client cache`。

处理：先查进程再强杀。

```powershell
Get-Process | Where-Object { $_.ProcessName -match 'uv' } | Select-Object Id, ProcessName
Stop-Process -Id <PID> -Force
```

（Git Bash 下 `taskkill //PID` 参数写法会报错，直接用 PowerShell 的 Stop-Process。）

---

## 五、排查要点

| 症状 | 排查方向 |
|---|---|
| MCP 完全没加载 | 是否已在「自定义连接器」点了信任 |
| uvx 启动失败、报 Python 版本错误 | 换成 `.local\bin\uvx.exe`（配 Python 3.12） |
| 文档工具能用、执行工具报错 | bridge 没启动，回到第三步 |
| 首次启动很慢 / 超时 | 首次要从 PyPI 拉 fastmcp 等依赖，属正常现象 |

---

## 附：环境事实

- FLAC3D 7.00，Itasca Code Framework，revision 52581
- 绿色解压版，非标准安装（`C:\Program Files\Itasca` 为空）
- 可执行文件目录：`D:\Flac3d\FLAC\exe64\`
  - `flac3d700_gui.exe` / `flac3d700_console.exe`
  - `flac2d700_gui.exe` / `flac2d700_console.exe`
- 工程目录：`D:\Flac3d\project\project2026-7-14`、`project2026-7-15`
- bridge 脚本：`D:\Flac3d\addon.py`（Python 3.6+ 兼容，适配 FLAC 7 内嵌 Python 3.6）
- MCP 包：`itasca-mcp` 0.8.0，要求 Python >=3.10
- 已弃用：`flac-mcp`（0.5.2，冻结，勿再使用）
