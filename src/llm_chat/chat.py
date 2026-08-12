"""对话核心 —— OpenAI SDK 调用 + 流式输出 + 消息历史管理（Week 5）。

C# 对照主线：
  OpenAI Python SDK     ≈ OpenAI NuGet 包（和 .NET 版是同一套 API 设计）
  client.chat.completions.create(...)  ≈ await client.Chat.Completions.CreateAsync(...)
  messages 列表（role/content 字典）   ≈ List<ChatMessage>（system / user / assistant）
  stream=True 返回可迭代对象           ≈ .NET 的流式响应（IAsyncEnumerable<ChatCompletionStreamingUpdate>）
  resp.usage                          ≈ ChatCompletion.Usage（prompt/completion tokens）

与 HelloWorld 示例 1 的关系：同样的聊天循环，只是换语言 ——
对比阅读能直观感受"同样的逻辑，两种语言的写法差异"。
"""

import json  # C#: using System.Text.Json;
import os  # C#: using System.Environment;
from dataclasses import dataclass  # C#: record
from typing import Iterator, List, Optional

from openai import OpenAI  # C#: using OpenAI; —— SDK 内部处理 HTTP（类似 .NET 的 HttpClient 封装）

# DeepSeek 的 OpenAI 兼容端点（换其他服务商只改这里 + 环境变量）
DEFAULT_BASE_URL = "https://api.deepseek.com"  # C#: const string DefaultBaseUrl = "...";
DEFAULT_MODEL = "deepseek-chat"  # DeepSeek 通用对话模型（--model 可覆盖）


@dataclass
class ReplyResult:
    """一次回复的完整结果：内容 + token 用量 + 费用。

    C#: public record ReplyResult(string Content, int PromptTokens, int CompletionTokens, double? Cost);
    cost 为 None 表示 config.json 里没有该模型的价格（费用未知，不影响对话）。
    """

    content: str  # C#: string Content
    prompt_tokens: int  # C#: int PromptTokens
    completion_tokens: int  # C#: int CompletionTokens
    cost: Optional[float] = None  # C#: double? Cost


# ============================================================
# 客户端工厂：环境变量驱动（不把 key 写进代码）
# ============================================================

def build_client(api_key: str, base_url: str = DEFAULT_BASE_URL) -> OpenAI:
    """按 api_key + base_url 创建 OpenAI 客户端。

    C#: var client = new OpenAIClient(apiKey, new OpenAIClientOptions { Endpoint = baseUrl });
    教学点：DeepSeek / 通义千问 / 其他兼容服务 —— 客户端代码完全不用改，
    只换 base_url 和 key —— 这是"OpenAI 兼容协议"生态的意义。
    """
    return OpenAI(api_key=api_key, base_url=base_url)


# ============================================================
# 消息结构（对应 C# 的 ChatMessage 角色）
# ============================================================

def system_message(content: str) -> dict:
    """构造 system 角色消息（设定助手人设/规则）。

    C#: new ChatMessage(ChatRole.System, content)
    教学点：角色只有三种 —— system（系统设定）/ user（用户）/ assistant（助手回复）。
    """
    return {"role": "system", "content": content}


# ============================================================
# 非流式调用：一次请求，等完整回复
# ============================================================

def non_stream_reply(
    client: OpenAI,
    messages: List[dict],
    model: str,
    temperature: float,
) -> ReplyResult:
    """非流式回复：阻塞等待完整内容后返回。

    C#: var resp = await client.Chat.Completions.CreateAsync(new ChatCompletionCreateOptions {
            Model = model, Messages = messages, Temperature = temperature });
        var content = resp.Choices[0].Message.Content;
        var usage = resp.Usage;   // PromptTokens / CompletionTokens
    对比：流式是一次请求边收边显示；非流式是"转圈等结果" —— 体验差别明显。
    """
    resp = client.chat.completions.create(  # C#: 同步版：client.Chat.Completions.Create(...)
        model=model,  # C#: Model = model
        messages=messages,  # C#: Messages = messages（消息数组原样上传 —— 角色就是上下文）
        temperature=temperature,  # C#: Temperature = temperature（越高越随机）
    )
    content = resp.choices[0].message.content  # C#: resp.Choices[0].Message.Content
    usage = resp.usage  # C#: resp.Usage（token 统计，费用统计的依据）
    return ReplyResult(
        content=content or "",  # 有些模型可能返回空内容 —— C#: content ?? string.Empty
        prompt_tokens=usage.prompt_tokens,  # C#: usage.PromptTokens
        completion_tokens=usage.completion_tokens,  # C#: usage.CompletionTokens
    )


# ============================================================
# 流式调用：返回生成器，边收边 yield（Week 3 知识的实战应用！）
# ============================================================

def stream_reply(
    client: OpenAI,
    messages: List[dict],
    model: str,
    temperature: float,
) -> Iterator[str]:
    """流式回复生成器：逐块 yield 文本片段。

    C# 对照：
      var stream = client.Chat.Completions.CreateStreamingAsync(options);
      await foreach (var update in stream)
          Console.Write(update.ContentUpdate[0].Text);

    教学点（Week 3 生成器的实战应用）：
      - API 返回的 stream 本身就是可迭代对象 —— for 循环逐块消费（惰性！）
      - 本函数把"消费块 → 提取文本"包成自己的生成器 —— 上层只要 for piece 打印
      - 和 Week 3 的 iter_lines 一模一样的思想：管道逐级传递，数据流式经过

    用法（注意取统计结果的技巧）：
      用 chat.consume_stream(gen, on_piece=...) 消费 —— 它会负责把
      生成器的 return 值（token 统计）取出来，见 consume_stream 的说明。
    """
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True,  # C#: Stream = true —— 返回流而不是完整响应
        # 流式默认不返回 token 统计！必须显式要求 —— 最后一块 chunk 会带上 usage
        # C#: StreamOptions = new() { IncludeUsage = true }
        stream_options={"include_usage": True},
    )

    content_parts: List[str] = []  # C#: var builder = new StringBuilder();  —— 拼完整回复
    usage = None  # C#: Usage usage = null;
    for chunk in stream:  # C#: await foreach (var chunk in stream) —— 逐块到达，无需等待全部
        # 流式块结构：choices[0].delta.content 是"增量"文本（可能为 None/空）
        piece = chunk.choices[0].delta.content  # C#: update.ContentUpdate[0].Text
        if piece:  # 有内容才 yield —— 跳过空块
            content_parts.append(piece)
            yield piece  # C#: yield return 文本块 —— 调用方边收边显示
        # 统计信息：include_usage 开启时，最后一个块带 usage 字段
        if chunk.usage:  # C#: if (update.Usage != null)
            usage = chunk.usage

    # 生成器 return 值 —— Python 特色：既能 yield 数据流，最后还能 return 一个汇总值。
    # 注意：这个值不在生成器对象上，而是藏在迭代结束时抛出的 StopIteration 里，
    # 取法见 consume_stream（C# 无直接等价，一般用 out 参数或结果对象）。
    return ReplyResult(
        content="".join(content_parts),  # C#: builder.ToString()
        prompt_tokens=usage.prompt_tokens if usage else 0,  # C#: usage?.PromptTokens ?? 0
        completion_tokens=usage.completion_tokens if usage else 0,
    )


def consume_stream(gen: Iterator[str], on_piece=None) -> ReplyResult:
    """消费完流式生成器，并取出它 return 的汇总结果（token 统计）。

    教学点 —— 为什么不能直接 for 循环？
      for piece in gen 消费完就结束了，生成器 return 的值会被 for 循环吞掉，
      再也拿不到。要用底层协议手动取：
        1. next(gen) 取下一个块 —— 对应 C#: enumerator.MoveNext() + Current
        2. 迭代结束时会抛 StopIteration —— 对应 C#: MoveNext() 返回 false
        3. 生成器 return 的值 = StopIteration 异常的 e.value
      这正是 Week 3 学的迭代协议（__next__ / StopIteration）在实际中的收尾用法。

    C#: 无直接等价 —— .NET 里通常用一个结果对象/out 参数代替。
    on_piece 是逐块回调 —— C#: Action<string>（CLI 用来边收边打印）。
    """
    reply: Optional[ReplyResult] = None
    try:
        while True:  # C#: while (enumerator.MoveNext())
            piece = next(gen)  # C#: enumerator.Current —— 取下一个文本块
            if on_piece:  # 回调：CLI 传入 print 实现实时显示
                on_piece(piece)
    except StopIteration as e:  # C#: while 循环正常结束（MoveNext 返回 false）
        reply = e.value  # ← 生成器 return 的值在这里（e.value ≈ StopIteration.Value）
    return reply  # type: ignore[return-value]  # reply 必然非 None（生成器必有 return）


# ============================================================
# 消息历史：保存 / 加载 / 裁剪（上下文窗口管理）
# ============================================================

def save_history(messages: List[dict], path: str) -> None:
    """把消息历史保存为 JSON 文件（下一次继续聊用）。

    C#: File.WriteAllText(path, JsonSerializer.Serialize(messages));
    messages 本身就是 {"role", "content"} 字典列表 —— 和 JSON 格式天然对应，
    不需要任何转换（对比 C# 需要把 List<ChatMessage> 序列化成 DTO）。
    """
    with open(path, "w", encoding="utf-8") as f:  # C#: using var f = File.CreateText(path);
        json.dump(messages, f, ensure_ascii=False, indent=2)  # ensure_ascii=False 保留中文


def load_history(path: str) -> List[dict]:
    """从 JSON 加载历史；文件不存在时返回空列表（首次使用不报错）。

    C#: if (!File.Exists(path)) return new List<ChatMessage>();
    教学点：过滤脏数据 —— 只保留 role 合法的消息（防止手改文件搞坏对话）。
    """
    if not os.path.exists(path):  # C#: File.Exists(path)
        return []
    with open(path, "r", encoding="utf-8") as f:  # C#: JsonSerializer.Deserialize<List<ChatMessage>>(...)
        data = json.load(f)
    # 推导式过滤 + set 成员判断 —— C#: data.Where(m => validRoles.Contains(m.Role)).ToList()
    return [
        m for m in data
        if isinstance(m, dict) and m.get("role") in {"system", "user", "assistant"}
    ]


def trim_history(messages: List[dict], max_messages: int) -> List[dict]:
    """上下文窗口管理：保留 system + 最近 N 条消息，防止 token 越聊越长。

    C#: 没有标准库等价 —— 概念上对应"滑动窗口"：
        var system = messages.Where(m => m.Role == System).ToList();
        var recent = messages.Where(m => m.Role != System).TakeLast(N).ToList();
        return system.Concat(recent).ToList();
    教学点：context window 是有限的 —— 控制台演示时把历史裁剪到最近 N 条，
    真实产品还会用"摘要压缩"更精细地管理。
    """
    if max_messages <= 0:  # 0 = 不限 —— C#: if (maxMessages <= 0) return messages;
        return messages
    system_msgs = [m for m in messages if m["role"] == "system"]  # C#: .Where(...)
    recent = [m for m in messages if m["role"] != "system"][-max_messages:]  # C#: .TakeLast(N)
    return system_msgs + recent  # C#: system.Concat(recent).ToList() —— system 永远在最前
