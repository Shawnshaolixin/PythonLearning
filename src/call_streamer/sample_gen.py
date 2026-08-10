"""示例数据生成器 —— 生成大 JSONL 日志文件（用于演示流式分析）。

用法：
  uv run call-streamer-gen --lines 100000 --out calls.jsonl

设计：
  - random.seed 固定 → 每次生成的日志完全一致（可复现，测试友好）
  - 一行一条 JSON（JSONL 格式）—— 这是日志系统的标准格式之一
  - 权重分布：deepseek-v4-flash 占大头（便宜模型调用多），符合真实场景
"""

import argparse  # C#: 命令行参数解析
import json  # C#: using System.Text.Json;
import random  # C#: Random（注意：C# 的 Random 无种子时不可复现）
from pathlib import Path  # C#: System.IO.Path

# 模型名必须与 config.json 里的 models 一致（否则算不出价格 → 费用为 0）
# C#: 配置驱动的常量表 —— 也可以从 config.json 读，这里写死便于教学
MODEL_NAMES = ["deepseek-v4-flash", "deepseek-v4-pro", "qwen-max"]
# (模型名, 出现权重) —— 权重越大出现越多（C#: 加权随机通常手写，无标准库）
MODEL_WEIGHTS = [("deepseek-v4-flash", 0.6), ("deepseek-v4-pro", 0.3), ("qwen-max", 0.1)]


def make_record(call_id: int, rng: random.Random) -> dict:
    """生成一条调用记录 dict。C#: Dictionary<string, object> MakeRecord(...)

    random.Random(rng) 作为参数传入 —— 生成器可复现（C#: 传 Random 实例同理）。
    """
    model = rng.choices(  # C#: 加权随机 —— 需要自己实现或用手写比例判断
        [m for m, _ in MODEL_WEIGHTS],  # 模型名列表
        weights=[w for _, w in MODEL_WEIGHTS],  # 对应权重
        k=1,
    )[0]
    return {
        "call_id": call_id,
        "model": model,
        # token 数量按对数正态分布模拟真实负载（大多数调用很小，偶尔很大）
        "input_tokens": int(rng.lognormvariate(6.0, 1.2)),  # C#: 无直接等价，需手写分布
        "output_tokens": int(rng.lognormvariate(5.0, 1.0)),
    }


def generate(path: str, lines: int) -> None:
    """生成 lines 条调用记录写入 JSONL 文件。

    对比 Week 1 的 json.dump(整份数据)：
      这里逐行写、不构建大列表 —— 100 万行也不会占内存。
      C#: 用 StreamWriter 逐行 WriteLine（而不是把 List 序列化成一个文件）。
    """
    rng = random.Random(42)  # 固定种子 → 可复现（C#: new Random(42)）
    out = Path(path)  # C#: var out = new FileInfo(path);
    with open(out, "w", encoding="utf-8") as f:  # C#: using var writer = new StreamWriter(path);
        for call_id in range(1, lines + 1):  # C#: for (var i = 1; i <= lines; i++)
            line = json.dumps(make_record(call_id, rng), ensure_ascii=False)  # C#: JsonSerializer.Serialize(record)
            f.write(line + "\n")  # C#: writer.WriteLine(line);
    print(f"已生成 {lines:,} 条调用记录 → {path}")  # C#: $"...{lines:N0}...{path}"


def main() -> None:  # C#: public static void Main(string[] args)
    parser = argparse.ArgumentParser(description="生成 LLM 调用日志（JSONL 格式）")
    parser.add_argument("--lines", type=int, default=100_000, help="生成的记录条数")
    parser.add_argument("--out", type=str, default="calls.jsonl", help="输出文件路径")
    args = parser.parse_args()
    generate(args.out, args.lines)


if __name__ == "__main__":
    main()
