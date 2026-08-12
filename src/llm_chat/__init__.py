"""llm_chat —— Week 5: LLM API 调用 + 流式输出（命令行聊天工具）。

把 HelloWorld 示例 1（.NET 聊天循环）用 Python + OpenAI SDK 重写，
并加上多模型切换 / 流式 / Token 费用统计 / 历史保存加载：
  chat.py   对话核心（SDK 调用 / 流式生成器 / 消息历史）
  cost.py   Token 用量 → 费用（复用 Week 1 计费公式）
  cli.py    命令行入口（uv run llm-chat）
"""
