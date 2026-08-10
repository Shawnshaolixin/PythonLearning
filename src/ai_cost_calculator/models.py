"""数据模型模块 —— 用 dataclass 定义结构化数据。

为什么用 dataclass?
- 普通类要写一大堆 __init__ 样板代码；dataclass 自动生成 __init__/__repr__/__eq__
- 类似 C# 的 record，简洁且自带类型标注
"""

from dataclasses import dataclass


@dataclass
class Model:
    """一个 LLM 模型的价格配置。"""

    name: str
    input_price_per_1m: float   # 每 100 万输入 token 的价格（元）
    output_price_per_1m: float  # 每 100 万输出 token 的价格（元）


@dataclass
class CallRecord:
    """一次 LLM API 调用的记录。"""

    call_id: int     # 调用编号
    model: str       # 使用的模型名（对应 Model.name）
    input_tokens: int   # 本次调用消耗的输入 token 数
    output_tokens: int  # 本次调用消耗的输出 token 数


@dataclass
class CostSummary:
    """按模型汇总后的统计结果。"""

    model: str
    call_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost: float
