# 附录 A：FISH file I/O 十步反推实验记录

> 说明：本附录完整记录 AI 为确定 FLAC3D FISH 语言 `file.write` 语义所进行的 10 次受控实验。
> 每次实验均包含：假设 → 代码 → 观测结果 → 结论修正。
> 这是"AI 通过实验反推非文档化 API 语义"的方法论范例。

---

## 实验背景

**目标**：将 2670 个单元的计算结果导出为 CSV，供 Python 绘图。

**初始假设**（源自常规编程经验）：
`file.write(文件句柄, 数据)` —— 与 C/Python 的 `f.write()` 语义一致。

**该假设是错误的。** 以下为逐步逼近真相的过程。

---
## 实验 1（16:59）`_probe_io.dat`

**假设**：`file.write(fid, list(...))` 可用，fid 为 `file.open` 的返回值。

```fish
local fid = file.open(".../_io_out.csv", "write", "text")
file.write(fid, list("a,b,c"))
loop foreach local zz zone.list
    ...
    file.write(fid, list(line))
endloop
file.close(fid)
```

**观测**：`_io_out.csv` **0 字节**，无报错。

**结论**：写入静默失败。FISH 文件 IO 语义与常规语言不同，需重新假设。

---

## 实验 2（17:01）`_probe_io2.dat`

**假设**：分离变量声明可避免问题。

```fish
local fid = file.open(".../_io2.csv", "write", "text")
local lst = list("a,b,c")
file.write(fid, lst)
...
file.close(fid)
```

**观测**：`_io2.csv` **207 字节**，写入成功。但内容为：
```
a
,
b
,
c
0
.
5
```
即**每个字符占一行**。

**结论**：
1. `file.write(fid, data)` 双参数形式**语法合法**（与实验 1 的差异在于 list 的构造方式）
2. 但字符串被**逐字符拆分**输出
3. `file.close(fid)` 能正常 flush

**新假设**：`file.write` 把第二个参数当作"列表"，列表的每个元素输出为一行；而字符串本身被当作字符列表。

---

## 实验 3（17:02）`_probe_io3.dat`

**假设**：提供多个元素的列表，可让每个元素各占一行。

```fish
file.write(fid, list("xc","yc","dx"))
```

**观测**：**报错**
```
*** Too many arguments to intrinsic (1 accepted).
    While compiling line 18 column 21
```

**结论**：★ **`file.write` 只接受 1 个参数！**
先前 `file.write(fid, lst)` 之所以"不报错"，是因为……【待实验 4 确认】

---

## 实验 4（17:09）`_probe_io4.dat`

**假设**：验证参数个数限制，排除偶发。

```fish
file.write(fid, list("a","b","c"))
file.write(fid, "d")
```

**观测**：**同样报错** `Too many arguments to intrinsic (1 accepted).`

**结论**：确证 `file.write` **签名只有 1 个参数**。
结合实验 2 的表象，推断真实语义为：**`file.open` 设置"当前文件"，`file.write(列表)` 写入该文件**——即 FISH 采用**全局当前文件**模型，而非传递句柄。

**新假设**：
```fish
file.open(path, "write", "text")   ; 不接收返回值
file.write(L)                       ; L 是列表，逐元素成行
file.close                          ; 无参数
```

---

## 实验 5（17:10）`_probe_io5.dat`

**假设**：验证上述新语义。

```fish
local L = list("x,y,z")
L = list.append(L, string(p->x))
file.open(fname, "write", "text")
file.write(L)
file.close
```

**观测**：✅ **执行成功，无报错**。`_io5.csv` 内容（`cat -A` 显示 `\r\n`）：
```
x^M$
,^M$
y^M$
,^M$
z^M$
1.5^M$
```

**关键分析**：
- `list("x,y,z")` 产生 `['x', ',', 'y', ',', 'z']`（**按字符拆分？不——只有 5 个元素却有 6 行输出**）
- `list.append` 追加的 `"1.5"` 完整输出为一行（4 字符未拆分）
- **推断**：`list("x,y,z")` 实际按 **`list()` 无参数构造空表 + 字符串作为首元素再加入**……需进一步验证

**结论**：
1. ✅ **`file.open` 不接收返回值 + `file.write(单参数)` + `file.close` 无参** —— 核心语义确认
2. ❓ `list("...")` 的行为仍不明确，需专项实验
3. ✅ `file.write` 对列表元素逐行输出；对**字符串元素**则逐字符拆分

---

## 实验 6（17:14）`_probe_io6.dat`

**假设**：用嵌套列表（内层列表 = 一行的各字段）实现 CSV。

```fish
local L = list()
L = list.append(L, list('a','b','c'))
L = list.append(L, list('1','2','3'))
```

**观测**：**报错** `Too many arguments to intrinsic (1 accepted).`

**结论**：`list.append` 同样只接受 1 个参数？→ 说明 FISH 中 `list.append` 的调用形式特异，
可能是 **方法式调用** 或 **单参数累积** 语义。

---

## 实验 7（17:15）`_probe_io7.dat`

**假设**：改用索引赋值构造列表。

```fish
local L = list('h1,h2,h3')
L(2) = 'r1,r2,r3'
L(3) = 'a,b,c'
file.open(".../_io7.csv", "write", "text")
file.write(L)
file.close
```

**观测**：✅ 执行成功。`_io7.csv` 输出 8 行：
```
h          ← list('h1,h2,h3') 的第1个元素是 'h'
r1,r2,r3   ← 索引赋值，整串输出为一行 ★
a,b,c      ← 同上 ★
h
2
,
h
3
```

**关键结论**：
1. ★★ **`L(n) = '字符串'` 赋值后，该字符串作为整体输出为一行** —— 这正是需要的 CSV 行行为！
2. ★★★ **`list('h1,h2,h3')` 按逗号拆分为 `['h1','h2','h3']`**（首元素 'h1' 输出为 `h`/`2`/`3` 拆行？）—— 实际输出首行只有 `h`，说明拆分方式是按字符

**修正假设**：`list(字符串)` 的行为是**按字符拆分**。
故**绝不能**用 `list('a,b,c')` 构造一个元素，必须用 `list.append`。

---

## 实验 8（17:16）`_probe_io8.dat`

**假设**：动态索引增长列表。

```fish
local L = list
L(1) = 'hdr1,hdr2,hdr3'
local cnt = 1
loop foreach local zz zone.list
    cnt += 1
    L(cnt) = row
endloop
```

**观测**：**报错** `*** Index 1 out of range (1,0)`

**结论**：`list`（裸标识符）构造的是**空表**，不能用索引赋值扩张。
必须用 `list.append` 增长。

---

## 实验 9（17:16）`_probe_io9.dat`

**假设**：用 `list.append` 逐行追加。

```fish
local L = list('hdr1,hdr2,hdr3')
loop foreach local zz zone.list
    ...
    L = list.append(L, row)
endloop
file.open(".../_io9.csv", "write", "text")
file.write(L)
file.close
```

**观测**：✅ 成功，`list.size(L) = 15`（1 表头 + 14 单元）。
但表头仍逐字符拆行（因 `list('hdr1,...')` 的字符拆分问题）。

**结论**：`list.append(L, x)` **确实可用且返回新列表**（必须 `L = list.append(L, x)` 重新赋值）。
剩余唯一问题：表头的构造方式。

---

## 实验 10（17:17）`_probe_io10.dat` ★★★ 成功

**假设**：空列表 + 每次 append 一个完整字符串行。

```fish
local L = list
L = list.append(L, 'xc,yc,zc')          ; 表头也用 append
loop foreach local zz zone.list
    local p = zone.pos(zz)
    local row = string(p->x) + ',' + string(p->y) + ',' + string(p->z)
    L = list.append(L, row)
endloop
file.open(".../_io10.csv", "write", "text")
file.write(L)
file.close
```

**观测**：✅✅ **完全正确的 CSV！**
```
xc,yc,zc
0.75,0.75,0.5
2.25,0.75,0.5
0.75,2.25,0.5
2.25,2.25,0.5
```

**最终结论 —— FISH 文件 IO 的正确语义**：

| 项目 | 正确用法 | 关键点 |
|---|---|---|
| 打开文件 | `file.open(路径, "write", "text")` | 不接收返回值；模式与类型**必须是字符串** |
| 写入 | `file.write(列表)` | **只接受 1 个参数**；列表每个元素输出为**一行** |
| 列表构造 | `local L = list` 然后 `L = list.append(L, 字符串)` | **禁止用 `list(长字符串)`**（会逐字符拆分） |
| 关闭 | `file.close` | 无参数 |

---

## 方法论总结

| 步骤 | 探针数 | 认知进展 |
|---|---|---|
| 初始错误假设 | 1 | `file.write(handle, data)` |
| 发现语法可行但输出异常 | 1 | 字符串逐字符拆分 |
| 发现参数个数限制 | 2 | ★ 只接受 1 个参数 |
| 提出全局当前文件模型 | 1 | ✅ 核心语义确认 |
| 排除列表构造干扰项 | 3 | `list(str)` 字符拆分、索引赋值限制 |
| 收敛到正确解 | 2 | ✅ 完整配方 |

**总耗时**：18 分钟（16:59 – 17:17），10 次受控实验。

**方法论启示**：
1. 面对**非文档化 API**，AI 的常规编程先验（"句柄式 IO"）会**系统性误导**
2. 有效策略是**单变量受控实验**——每次只改一个假设点
3. **异常输出（逐字符成行）比报错更有信息量**——它揭示了底层数据模型
4. AI 能在无人工干预下完成这一过程，但**必须能设计并解释实验**
