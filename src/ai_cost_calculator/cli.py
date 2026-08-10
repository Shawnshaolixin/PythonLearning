"""命令行入口模块。

练习知识点：
- argparse（命令行参数解析，类似 C# 的命令行参数）
- 结构化输出（表格 / JSON）
- main() 作为程序入口约定
"""

import argparse
import json
from pathlib import Path
from typing import List

from . import calculator
from .models import CostSummary


def format_table(summaries: List[CostSummary]) -> str:
    """把汇总结果格式化成简单的文本表格。"""
    lines = [
        f"{'模型':<24}{'次数':>6}{'输入token':>14}{'输出token':>14}{'费用(元)':>12}"
    ]
    lines.append("-" * 70)
    for s in summaries:
        lines.append(
            f"{s.model:<24}{s.call_count:>6}{s.total_input_tokens:>14}"
            f"{s.total_output_tokens:>14}{s.total_cost:>12.4f}"
        )
    lines.append("-" * 70)
    lines.append(f"{'合计':<24}{'':>6}{'':>14}{'':>14}{calculator.total_cost(summaries):>12.4f}")
    return "\n".join(lines)


def to_json_dict(summaries: List[CostSummary]) -> dict:
    """把结果转成可 JSON 序列化的 dict。"""
    return {
        "total_cost": round(calculator.total_cost(summaries), 4),
        "models": [
            {
                "model": s.model,
                "call_count": s.call_count,
                "input_tokens": s.total_input_tokens,
                "output_tokens": s.total_output_tokens,
                "cost": round(s.total_cost, 4),
            }
            for s in summaries
        ],
    }


def main() -> None:
    # 1. 解析命令行参数
    parser = argparse.ArgumentParser(
        description="统计 LLM API 调用费用的命令行工具"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="JSON 配置文件路径（默认: config.json）",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式输出（而非表格）",
    )
    args = parser.parse_args()

    # 2. 读取并处理数据（用 try/except 捕获可预期的错误）
    try:
        data = calculator.load_config(args.config)
        models = calculator.parse_models(data["models"])
        calls = calculator.parse_calls(data["calls"])
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as e:
        # 遇到错误给出友好提示，而不是抛出一大段堆栈
        print(f"错误: {e}")
        print("请检查配置文件路径和格式是否正确。")
        return

    # 3. 汇总计算
    summaries = calculator.summarize_by_model(calls, models)

    # 4. 输出
    if args.json:
        print(json.dumps(to_json_dict(summaries), ensure_ascii=False, indent=2))
    else:
        print(format_table(summaries))


# 只有直接运行本文件时才执行 main()；
# 被 import 时不执行 —— 这是 Python 的标准入口约定
if __name__ == "__main__":
    main()
