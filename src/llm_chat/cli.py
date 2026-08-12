"""命令行入口 —— llm-chat 聊天工具（Week 5 实战）。

用法示例：
  uv run llm-chat                                    # 默认 deepseek-chat，流式
  uv run llm-chat --model deepseek-reasoner          # 切换模型（多模型演示）
  uv run llm-chat --no-stream                        # 非流式（一次等完整回复）
  uv run llm-chat --system "你是 Python 老师" --temperature 0.5
  uv run llm-chat --load history.json                # 加载历史继续聊
  uv run llm-chat --save history.json                # 退出时保存历史

环境变量：
  DEEPSEEK_API_KEY   必填（DeepSeek 开放平台申请，https://platform.deepseek.com）
  DEEPSEEK_BASE_URL  默认 https://api.deepseek.com（换成其他 OpenAI 兼容服务即可）

聊天中的命令：
  /exit /quit   退出        /clear   清空历史（保留 system）
  /help         帮助        /save 路径   保存历史
                             /load 路径   加载历史

C# 对照主线：
  整体结构 ≈ HelloWorld 示例 1 的 .NET 聊天循环（Console.ReadLine + 循环）
"""

import argparse  # C#: System.CommandLine / 手动解析 args
import os  # C#: using System.Environment;
import sys  # C#: Environment.Exit

from openai import APIError  # C#: OpenAI SDK 的 ApiException（401 密钥错等都会抛它）

try:
    from .chat import (
        DEFAULT_MODEL,
        build_client,
        consume_stream,
        load_history,
        non_stream_reply,
        save_history,
        stream_reply,
        system_message,
        trim_history,
    )
    from .cost import usage_cost
except ImportError:
    # 直接运行本文件时（python cli.py）—— 与 Week 2/3 相同的回退模式
    from chat import (  # type: ignore[no-redef]
        DEFAULT_MODEL,
        build_client,
        consume_stream,
        load_history,
        non_stream_reply,
        save_history,
        stream_reply,
        system_message,
        trim_history,
    )
    from cost import usage_cost  # type: ignore[no-redef]

# 常见退出命令集合 —— C#: HashSet<string> exitCommands = new() { "/exit", "/quit" };
_EXIT_COMMANDS = {"/exit", "/quit"}  # 集合字面量 —— C#: HashSet 初始化器


def _print_stats(reply, config_path: str, model: str) -> None:
    """打印一次回复的 token 用量 + 费用（复用 Week 1 计费公式）。

    C#: 提取成私有方法 —— 保持主循环整洁。
    """
    cost = usage_cost(model, reply.prompt_tokens, reply.completion_tokens, config_path)
    # cost 为 None 表示价格未配置 —— 提示如何补，而不是报错
    cost_text = (
        f"{cost:.6f} 元" if cost is not None else "未配置价格（可在 config.json 的 models 里添加）"
    )
    # f-string 千分位 + 宽度 —— C#: $"{reply.PromptTokens:N0}"
    print(f"    ⏱ 输入 {reply.prompt_tokens:,} · 输出 {reply.completion_tokens:,} token · 费用 {cost_text}")


def main() -> None:  # C#: public static void Main(string[] args)
    parser = argparse.ArgumentParser(
        description="LLM 命令行聊天工具（Week 5: LLM API 调用 + 流式输出）"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LLM_CHAT_MODEL", DEFAULT_MODEL),  # 环境变量可覆盖默认值
        help=f"模型名（默认 {DEFAULT_MODEL}，也可用 LLM_CHAT_MODEL 环境变量）",
    )
    parser.add_argument(
        "--stream", dest="stream", action="store_true", default=True, help="流式输出（默认开启）"
    )
    parser.add_argument(
        "--no-stream", dest="stream", action="store_false", help="非流式输出（一次等完整回复）"
    )
    parser.add_argument(
        "--system", default="你是乐于助人的 AI 助手", help="System Prompt（助手的人设/规则）"
    )
    parser.add_argument(
        "--temperature", type=float, default=1.0, help="采样温度 0-2（越高越随机，默认 1.0）"
    )
    parser.add_argument(
        "--config", default="config.json", help="价格配置文件（费用统计用，Week 1 的格式）"
    )
    parser.add_argument("--save", default=None, help="退出时保存历史到 JSON 文件")
    parser.add_argument("--load", default=None, help="启动时加载历史 JSON 文件")
    parser.add_argument(
        "--history", type=int, default=20,
        help="上下文窗口：保留 system + 最近 N 条消息（0=不限，默认 20）",
    )
    args = parser.parse_args()  # C#: 手动解析 args 或 System.CommandLine

    # 密钥检查 —— 绝不把 key 硬编码在代码/配置文件里（C#: 环境变量或 User Secrets）
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:  # C#: string.IsNullOrEmpty(apiKey)
        print("错误: 未设置 DEEPSEEK_API_KEY 环境变量")
        print("  在 DeepSeek 开放平台申请: https://platform.deepseek.com")
        sys.exit(1)  # C#: Environment.Exit(1)

    # 创建客户端 —— base_url 默认 DeepSeek，可用 DEEPSEEK_BASE_URL 换成别的兼容服务
    base_url = os.environ.get("DEEPSEEK_BASE_URL", None)  # C#: Configuration["DEEPSEEK_BASE_URL"]
    client = build_client(api_key, base_url) if base_url else build_client(api_key)

    # 加载历史（--load 或 /load 命令）；没有历史时注入 system 消息
    messages = load_history(args.load) if args.load else []  # C#: 加载 List<ChatMessage>
    if not any(m["role"] == "system" for m in messages):  # C#: !messages.Any(m => m.Role == System)
        messages.insert(0, system_message(args.system))  # C#: messages.Insert(0, systemMsg)

    # 欢迎信息
    mode = "流式" if args.stream else "非流式"  # C#: args.Stream ? "Streaming" : "Non-streaming"
    print(f"llm-chat（Week 5） 模型: {args.model}  ·  模式: {mode}  ·  温度: {args.temperature}")
    print(f"System Prompt: {args.system}")
    print("命令: /exit 退出 · /clear 清空历史 · /help 帮助（/save 路径 保存 · /load 路径 加载）")
    print("-" * 60)

    try:
        while True:  # C#: while (true) —— 聊天循环（HelloWorld 示例 1 同款结构）
            try:
                user_input = input("你> ").strip()  # C#: Console.ReadLine()
            except EOFError:  # 输入流被关闭（管道/重定向输入结束时）—— C#: ReadLine() 返回 null
                print()
                break
            if not user_input:  # 空输入跳过 —— C#: string.IsNullOrWhiteSpace
                continue
            if not user_input:  # 空输入跳过 —— C#: string.IsNullOrWhiteSpace
                continue

            # --- 命令处理 ---
            if user_input in _EXIT_COMMANDS:  # C#: exitCommands.Contains(input)
                break
            if user_input == "/clear":
                messages = [m for m in messages if m["role"] == "system"]  # 保留 system
                print("[已清空历史]")
                continue
            if user_input == "/help":
                print("命令: /exit 退出 · /clear 清空历史 · /save 路径 保存 · /load 路径 加载")
                continue
            if user_input.startswith("/save "):
                save_history(messages, user_input[len("/save "):].strip())
                print("[已保存历史]")
                continue
            if user_input.startswith("/load "):
                messages = load_history(user_input[len("/load "):].strip())
                if not any(m["role"] == "system" for m in messages):
                    messages.insert(0, system_message(args.system))
                print("[已加载历史]")
                continue

            # --- 普通对话 ---
            messages.append({"role": "user", "content": user_input})  # C#: messages.Add(userMsg)

            if args.stream:  # 流式：边收边打印（Week 3 生成器实战）
                print("AI> ", end="", flush=True)  # flush=True 立即刷出（不积攒在缓冲区）
                gen = stream_reply(client, messages, args.model, args.temperature)
                # consume_stream 逐块消费：on_piece 回调负责打印（end="" 不换行），
                # 迭代结束后取出生成器 return 的汇总结果（token 用量）
                # C#: await foreach 拿流，统计则来自流末尾的 usage 对象
                reply = consume_stream(
                    gen, on_piece=lambda p: print(p, end="", flush=True)
                )
                print()  # 回复结束换行
            else:  # 非流式：一次等完整回复
                reply = non_stream_reply(client, messages, args.model, args.temperature)
                print(f"AI> {reply.content}")

            messages.append({"role": "assistant", "content": reply.content})  # C#: messages.Add(assistantMsg)
            # 上下文窗口管理：裁剪到 system + 最近 N 条 —— C#: messages = TrimHistory(messages, N)
            messages = trim_history(messages, args.history)

            _print_stats(reply, args.config, args.model)  # 每轮打印 token + 费用
    except KeyboardInterrupt:  # Ctrl+C —— C#: Console.CancelKeyPress 事件
        print("\n[已退出]")
    except APIError as e:  # C#: catch (ApiException) —— API 层错误（401 密钥错 / 余额不足等）
        print(f"\nAPI 错误: {e}")
        print("  检查: DEEPSEEK_API_KEY 是否正确 · 账户余额是否充足 · 模型名是否有效")
    except Exception as e:  # C#: catch (Exception) —— 兜底，不让堆栈直接崩给用户
        print(f"\n发生错误: {e}")
    finally:
        if args.save:  # --save 指定时退出自动保存 —— C#: finally 块里做收尾
            save_history(messages, args.save)
            print(f"[已保存历史到 {args.save}]")


if __name__ == "__main__":  # C#: Main() 入口方法
    main()
