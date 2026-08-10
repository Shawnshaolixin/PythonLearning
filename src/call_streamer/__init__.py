"""call_streamer —— Week 3: 生成器与迭代器（大日志流费用分析器）。

模块组成：
  generators.py   知识点教学（迭代协议 / yield / 惰性求值 / yield from）
  pipeline.py     流式管道（读行 → 解析 → 过滤 → 算费用 → 聚合）
  cli.py          命令行入口（uv run call-streamer）
  sample_gen.py   示例日志生成器（uv run call-streamer-gen）
"""
