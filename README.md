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
