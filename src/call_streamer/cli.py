"""命令行入口 —— 大日志流费用分析器。

用法示例：
  uv run call-streamer --log calls.jsonl --config config.json
  uv run call-streamer --log calls.jsonl --config config.json --model deepseek-v4-pro
  uv run call-streamer --log calls.jsonl --config config.json --top 5 --json
  uv run call-streamer --log calls.jsonl --config config.json --head 3   # 惰性演示

知识点覆盖（呼应 generators.py 与 pipeline.py）：
  - 生成器管道：读行 → 解析 → 过滤 → 算费用 → 聚合（惰性求值）
  - islice 短路：--head 只读前 N 行就停止
  - Top-K 聚合：内存只与模型种类数相关，与日志行数无关
"""

import argparse  # C#: 命令行参数解析（沿用 Week 1 的模式）
import json  # C#: using System.Text.Json;
from itertools import islice  # C#: Enumerable.Take

try:
    from .pipeline import (
        analyze_log,
        head,
        iter_lines,
        parse_records,
    )
except ImportError:
    # 直接运行本文件时（python cli.py）—— 与 Week 2 相同的回退模式
    from pipeline import (  # type: ignore[no-redef]
        analyze_log,
        head,
        iter_lines,
        parse_records,
    )


def print_summary(summary: dict) -> None:
    """打印汇总信息（文本格式）。"""
    print(f"总调用次数 : {summary['calls']:,}")  # C#: $"{summary.Calls:N0}"
    print(f"输入 token : {summary['input_tokens']:,}")  # C#: $"{summary.InputTokens:N0}"
    print(f"输出 token : {summary['output_tokens']:,}")
    print(f"总费用     : {summary['total_cost']:.4f} 元")  # 不用 ¥ —— Windows GBK 控制台编码不了


def print_top(tops: list, json_output: bool) -> None:
    """打印 Top-K 模型表（text 或 json）。"""
    if json_output:  # C#: if (jsonOutput)
        print(json.dumps(tops, ensure_ascii=False, indent=2))  # C#: JsonSerializer.Serialize(...)
        return
    # 表头（C#: Console.WriteLine 逐行输出）
    print(f"\n{'模型':<22}{'调用次数':>12}{'费用':>14}")
    print("-" * 50)
    for name, count, cost in tops:  # C#: foreach (var (name, count, cost) in tops)
        print(f"{name:<22}{count:>12,}{cost:>14.4f}")


def main() -> None:  # C#: public static void Main(string[] args)
    parser = argparse.ArgumentParser(
        description="大日志流费用分析器（Week 3: 生成器与迭代器）"
    )
    parser.add_argument(
        "--log", type=str, default="calls.jsonl", help="调用日志文件（JSONL 格式）"
    )
    parser.add_argument(
        "--config", type=str, default="config.json", help="模型价格配置文件"
    )
    parser.add_argument(
        "--model", type=str, default=None, help="只统计指定模型（不指定则统计全部）"
    )
    parser.add_argument(
        "--top", type=int, default=3, help="显示费用最高的前 N 个模型（默认 3）"
    )
    parser.add_argument("--json", action="store_true", help="JSON 格式输出")
    parser.add_argument(
        "--head",
        type=int,
        default=None,
        help="只读取日志前 N 行（演示 islice 惰性短路）",
    )
    args = parser.parse_args()  # C#: 手动解析 args 或 System.CommandLine

    # --head 模式：演示惰性短路 —— 只解析前 N 行，第 N+1 行起永不读取
    # C#: File.ReadLines(path).Select(Deserialize).Take(n)  —— 同样的短路
    if args.head is not None:  # C#: if (args.Head != null)
        lines = iter_lines(args.log)  # 此刻文件尚未打开 —— 惰性（C#: ReadLines 同样惰性）
        sample = list(head(parse_records(lines), args.head))  # islice 短路点（C#: Take(n).ToList()）
        print(f"[惰性演示] islice 短路：{args.head} 条之后的日志行从未被读取")
        for record in sample:  # C#: foreach (var r in sample)
            print(f"  #{record.call_id}  {record.model:<20} in={record.input_tokens:,} out={record.output_tokens:,}")
        return

    # 完整分析：两次遍历管道（汇总 + Top-K），全程 O(1) 内存
    try:
        summary, tops = analyze_log(
            args.log,
            args.config,
            model_filter=args.model,
            top_k=args.top,
        )
    except FileNotFoundError as e:  # C#: catch (FileNotFoundException ex)
        print(f"错误: {e}")
        print("提示: 先运行 uv run call-streamer-gen --lines 100000 生成示例日志")
        return

    if args.json:  # C#: 结构化输出
        print(json.dumps({"summary": summary, "top_models": tops}, ensure_ascii=False, indent=2))
        return

    print_summary(summary)
    print_top(tops, json_output=False)


if __name__ == "__main__":
    main()
