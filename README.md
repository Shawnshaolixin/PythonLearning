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
src/ai_cost_calculator/
  models.py      数据模型（dataclass）
  calculator.py  读 JSON + 计算逻辑
  cli.py         命令行入口（argparse）
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
