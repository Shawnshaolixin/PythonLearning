# ai-cost-calculator

读取 JSON 配置、统计 LLM API 调用费用的命令行工具。

> Week 1 练习项目：Python 工程环境 + 基础语法（dataclass / typing / 推导式 / JSON / 异常处理）。

## 环境要求

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)（推荐）

## 快速开始

```bash
# 创建虚拟环境并安装项目
uv sync

# 运行：统计费用（表格输出）
uv run ai-cost-calculator --config config.json

# 运行：JSON 结构化输出
uv run ai-cost-calculator --config config.json --json
```

## 项目结构

```
src/ai_cost_calculator/   # Week 1: 费用统计器（函数式）
  models.py      数据模型（dataclass）
  calculator.py  读 JSON + 计算逻辑
  cli.py         命令行入口（argparse）
src/cost_reporter/        # Week 2: 账单报告生成器（面向对象）
  errors.py      自定义异常体系
  report.py      CostReport 类（@property / 魔术方法）
  formatters.py  格式化器（抽象基类 + 继承多态）
  cli.py         命令行入口（--format 参数）
src/call_streamer/        # Week 3: 大日志流费用分析器（生成器与迭代器）
  generators.py  知识点教学（迭代协议 / yield / 惰性求值 / yield from）
  pipeline.py    流式管道（读行 → 解析 → 过滤 → 算费用 → 聚合）
  cli.py         命令行入口（--log / --model / --top / --head）
  sample_gen.py  示例日志生成器（--lines 100000）
config.json      示例配置文件
```

## 配置格式

```json
{
  "models": [
    { "name": "模型名", "input_price_per_1m": 输入单价, "output_price_per_1m": 输出单价 }
  ],
  "calls": [
    { "call_id": 1, "model": "模型名", "input_tokens": 1200, "output_tokens": 350 }
  ]
}
```

费用公式：`输入token/1e6 * 输入单价 + 输出token/1e6 * 输出单价`

---

## Week 2：账单报告生成器（面向对象进阶）

> 在 Week 1 基础上重构扩展，练习 Python 类体系 vs C# 的差异：
> `class`/`self`（构造函数/`this`）、`@property`（get-only 属性）、魔术方法（`ToString`/`Equals`）、
> 自定义异常、继承 + 抽象方法（`abstract class`/`override`）。

### 运行

```bash
# 文本表格（默认）
uv run cost-reporter --config config.json

# Markdown 表格
uv run cost-reporter --config config.json --format markdown

# JSON
uv run cost-reporter --config config.json --format json
```

### 与 Week 1 的关系

- **复用**：`CostReport` 类的解析/汇总逻辑直接调用 Week 1 的 `calculator.py`（类做编排，函数做计算）
- **新增**：未知模型会通过 `validate()` 抛 `UnknownModelError`（Week 1 是静默计 0 费用）—— fail-fast
- **测试**：复用 Week 1 conftest.py 的 fixture

---

## Week 3：大日志流费用分析器（生成器与迭代器）

> 场景：生产环境每天几十万行 LLM 调用日志（JSONL），内存装不下 → 用生成器搭"水管"，
> 数据流式经过，内存占用 O(1)。这是 **LLM 流式输出（SSE）的底层机制**，Week 5 会用到。

### 知识点（C# 对照主线）

| Python | C# 等价 |
|--------|---------|
| 迭代协议 `__iter__` / `__next__` / `StopIteration` | `IEnumerable<T>` / `IEnumerator<T>` + `MoveNext()` |
| 生成器函数（函数体含 `yield`） | 迭代器方法（含 `yield return`） |
| 惰性求值（用到才执行） | LINQ 延迟执行（不 `ToList()` 时） |
| 生成器表达式 `(x for x in xs)` | `xs.Select(...)` 不 ToList |
| `yield from sub` | `foreach (var x in sub) yield return x;` |
| `itertools.islice` / `takewhile` | LINQ `.Take(n)` / `.TakeWhile(...)` |
| 无限序列（`while True: yield`） | LINQ 无法用 List 表达，IEnumerable 可以 |
| `next(g, default)` | `enumerator.MoveNext() ? Current : default` |

**最核心一句话：先搭管道、后放水。** 构建管道时什么都不算，只有 for 消费时才逐个求值。

### 运行

```bash
# 1. 生成 10 万行示例日志（固定随机种子，可复现）
uv run call-streamer-gen --lines 100000 --out calls.jsonl

# 2. 全量分析：汇总 + Top-3 模型（10 万行约 0.6 秒）
uv run call-streamer --log calls.jsonl --config config.json

# 3. 只统计某个模型
uv run call-streamer --log calls.jsonl --config config.json --model qwen-max

# 4. JSON 输出
uv run call-streamer --log calls.jsonl --config config.json --top 2 --json

# 5. 惰性演示：只读取前 3 行（islice 短路）
uv run call-streamer --log calls.jsonl --config config.json --head 3
```

### 管道结构（对比 LINQ 链）

```
iter_lines → parse_records → filter_by_model → with_cost
     ↓                        ↓                   ↓
File.ReadLines          .Select(Deserialize)  .Select(c => (c, cost))
     ↓
summarize（全量汇总）/ top_models（Top-K 聚合）
```

两个关键设计决策：
1. **生成器一次性**：同一个流只能消费一次 → 汇总和 Top-K 各自重新搭一遍管道（文件重读）
2. **内存与日志行数无关**：聚合用 dict 按模型累加，内存只与模型种类数相关

### 观察

跑一次 10 万行示例：`deepseek-v4-flash` 调用最多（6 万次）但费用最低（29 元），
`deepseek-v4-pro` 调用少（3 万次）却花掉大头（108 元）—— 贵模型省着用，这就是成本控制。

### 测试

`tests/test_call_streamer.py` 共 28 个用例，重点验证"惰性"：
- 副作用计数证明函数体在 `next()` 前不执行
- 无限序列 + `islice` 能跑完（急切实现会死循环）
- `iter_lines` 传不存在的文件不报错，`list()` 消费时才抛
- 大文件（5 万行）流式处理正确性
