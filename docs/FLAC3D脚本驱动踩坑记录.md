# FLAC3D 7.0 脚本驱动踩坑记录

通过 Windows 控制台 API 驱动 `flac3d700_console.exe` 时的实测经验。
所有结论均为实测，非文档推测。

---

## 一、控制台驱动机制

### 1.1 console 不读 stdin

`flac3d700_console.exe` 通过 Windows 控制台 API 读键盘，
**管道 / 重定向 / subprocess stdin 全部无效**。

正确做法（见 `flac_console_driver2.py`）：

```python
# 1. 以新控制台启动
proc = subprocess.Popen([exe], cwd=exe_dir, creationflags=CREATE_NEW_CONSOLE)
time.sleep(8)

# 2. 必须先脱离，否则 AttachConsole 报错 5 (ACCESS_DENIED)
kernel32.FreeConsole()
kernel32.AttachConsole(proc.pid)

# 3. 拿 CONIN$ / CONOUT$ 句柄，用 WriteConsoleInputW 注入按键
```

**关键点**：`FreeConsole()` 不能省，否则 `AttachConsole` 失败。

### 1.2 抓取输出用屏幕缓冲区

`program log-file` 只能记录命令回显和有 `---` 前缀的输出，
**不包含 FISH 的报错细节**。用 `ReadConsoleOutputCharacterW`
读屏幕缓冲区才能看到完整反馈：

```python
kernel32.ReadConsoleOutputCharacterW(h_out, buf, n, COORD(0,0), byref(got))
```

注意 `ctypes.wintypes` **没有** `COORD`，要自己定义结构体。

---

## 二、FLAC3D 语法陷阱

### 2.1 字符串参数必须加引号

```
zone create ... group lower          # ✗ Bad conversion
zone create ... group "lower"        # ✓
program log-file D:/path/x.log       # ✗ Bad conversion
program log-file "D:/path/x.log"     # ✓
call _file.dat                       # ✗ Bad conversion
call "_file.dat"                     # ✓
```

报错特征：`*** Bad conversion of parameter number N` +
`NOTE: String tokens must be surrounded by " or ' characters.`

### 2.2 FISH 索引循环必须用括号

```
loop local i = 0 3        # ✗ Syntax error
loop local i (0, 3)       # ✓
endloop                   # 必须显式 endloop
```

四种合法形式：
- `loop local var (expr1, expr2, <expr3>)`  — 索引
- `loop while exprtest`
- `loop for (init, test, modify)`
- `loop foreach local var expr`

### 2.3 command 块内不能用 FISH 变量插值（静默失败！）

```fish
fish define bad
    local yb = 12.0
    command
        zone create brick point 0 (0,[yb],0) ...   # ✗ [yb] 不替换！
    endcommand
end
```

**实测：不报错，但 `[yb]` 原样传给命令**，导致几何错误。
最危险的是它"看起来执行成功了"。

**规避**：由 Python 生成完整 .dat 文件，所有坐标为字面数值。

### 2.4 函数名对照（实测）

| 用途 | ✗ 错误 | ✓ 正确 |
|---|---|---|
| 单元删除 | `zone.delete(z)` (FISH) | `zone delete` (命令, 配 command/endcommand) |
| 单元位移 | `zone.disp(z)` | `gp.disp.x(zone.gp(z,j))` 取 8 角点平均 |
| 网格点位移 | — | `gp.disp.x(g)` / `.y` / `.z` |
| 网格点数 | — | `zone.gp.num(z)` 返回 8 |
| 取网格点 | — | `zone.gp(z, i)` i=1..8 |
| 单元质心 | `zone.pos(z)` ✓ | 返回 vector，用 `p->x` |
| 单元应力 | `zone.stress(z)` ✓ | 用 `st->yy`、`st->xy` |
| 单元状态 | `zone.state(z)` ✓ | 返回**整数位编码** |

### 2.5 zone.state 是位编码，不是字符串

| 值 | 标签 |
|---|---|
| 1 | shear-n（当前剪切破坏）|
| 2 | tension-n |
| 4 | shear-p |
| 8 | tension-p |
| 16/32/64/128 | 节理相关 |

判断用位运算：`(state & 1) != 0` 即 shear-n。

### 2.6 string.build 多参数拼接会报类型错误

```fish
file.write(fid, string.build("%1,...,%9", a,b,c,d,e,f,g,h,i))
# ✗ Unable to convert parameter type from Integer to List
```

**规避**：用 `+=` 逐段拼接字符串。

### 2.7 model factor-of-safety 需要大应变模式

```
model factor-of-safety ...
*** Large strain mode must be specified with the MODEL LARGE-STRAIN command.
```

必须先：`model large-strain on`

注意：官方在线文档**没有**写这个要求（文档与实际版本有差异），以实测为准。

### 2.8 读取 FOS 结果

```
model factor-of-safety bracket 1.0 3.0 filename "prefix"
model factor-of-safety list        # 显示上次结果
```

会生成三个文件：`prefix-Init.f3sav` / `-Stable.f3sav` / `-Unstable.f3sav`。

### 2.9 续行符

`&` 可作续行符，实测可用：

```
zone create brick point 0 (0,0,0) point 1 (30,0,0) &
                  point 2 (0,10,0) point 3 (0,0,6) &
                  size 30 10 6 group "lower"
```

### 2.10 禁止中文注释

.dat 文件里写中文注释会因编码问题导致解析异常。
生成 .dat 时用 `encoding="ascii"` 并只写英文注释。

---

## 三、工作目录

FLAC3D 默认工作目录：

```
C:\Users\<user>\Documents\Itasca\flac3d700\My Projects\
```

相对路径的文件都相对这里解析。**建议一律用绝对路径 + 引号**。

---

## 四、文件编码

FLAC3D 读 .dat 文件按本地 ANSI 代码页处理。生成脚本时用纯 ASCII 最稳。
日志文件的中文日期会显示为乱码（如 `ÖÜÎå`），不影响解析。
