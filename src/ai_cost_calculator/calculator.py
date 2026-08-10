"""核心计算模块 —— 负责读 JSON、解析数据、计算费用。

本模块练习的知识点：
- 文件读写 + JSON 序列化
- 异常处理（try/except）
- 列表推导式 / 字典推导式
- typing 类型标注
"""

import json
from pathlib import Path
from typing import List

try:
    from .models import CallRecord, CostSummary, Model
except ImportError:
    from models import CallRecord, CostSummary, Model  # type: ignore[no-redef]


def load_config(path: str) -> dict:
    """读取 JSON 配置文件并返回 dict。

    参数:
        path: JSON 文件路径
    返回:
        dict: 解析后的配置内容
    异常:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 格式错误
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 简单校验结构，防止后续 KeyError
    if "models" not in data or "calls" not in data:
        raise ValueError("配置文件缺少 models 或 calls 字段")
    return data


def parse_models(raw_models: List[dict]) -> List[Model]:
    """把原始 dict 列表转成 Model 对象列表（列表推导式 + **kwargs 展开）。"""
    return [Model(**m) for m in raw_models]


def parse_calls(raw_calls: List[dict]) -> List[CallRecord]:
    """把原始 dict 列表转成 CallRecord 对象列表。"""
    return [CallRecord(**c) for c in raw_calls]


def calc_call_cost(call: CallRecord, model: Model) -> float:
    """计算单次调用的费用。

    费用 = 输入token数/1e6 * 输入单价 + 输出token数/1e6 * 输出单价
    """
    return (
        call.input_tokens / 1_000_000 * model.input_price_per_1m
        + call.output_tokens / 1_000_000 * model.output_price_per_1m
    )


def summarize_by_model(
    calls: List[CallRecord], models: List[Model]
) -> List[CostSummary]:
    """按模型汇总所有调用的 token 数与费用。

    返回按调用次数降序排列的 CostSummary 列表。
    """
    # 先建一个 模型名 -> Model 的查找表（字典推导式），便于快速查找价格
    model_map: dict = {m.name: m for m in models}

    # 用 dict 按模型名累加
    # 注意：这里不能用 {m.name: 0 for m in models} 的简单版本，
    # 因为要给每个模型累计所有字段
    agg: dict[str, dict] = {}
    for c in calls:
        bucket = agg.setdefault(
            c.model, {"count": 0, "in": 0, "out": 0, "cost": 0.0}
        )
        bucket["count"] += 1
        bucket["in"] += c.input_tokens
        bucket["out"] += c.output_tokens
        if c.model in model_map:
            bucket["cost"] += calc_call_cost(c, model_map[c.model])

    # 转成 CostSummary 列表（列表推导式）
    result = [
        CostSummary(
            model=name,
            call_count=v["count"],
            total_input_tokens=v["in"],
            total_output_tokens=v["out"],
            total_cost=v["cost"],
        )
        for name, v in agg.items()
    ]

    # 按调用次数降序排序
    result.sort(key=lambda s: s.call_count, reverse=True)
    return result


def total_cost(summaries: List[CostSummary]) -> float:
    """所有模型的总费用。"""
    return sum(s.total_cost for s in summaries)
