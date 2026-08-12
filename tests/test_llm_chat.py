"""llm_chat 测试 —— Week 5（全程 mock API，不真实调用模型，不花钱）。

C# 对照主线：
  FakeCompletions.create + SimpleNamespace  ≈ Moq 的 It.IsAny / Returns（mock 外部依赖）
  monkeypatch                                 ≈ xUnit 的替换依赖（这里把 client 直接传入）
  fake client 对象                            ≈ 实现 IChatClient 接口的测试替身

为什么要 mock？
  - 真实调用会花钱 + 依赖网络 + 结果不确定 —— 测试永远不该依赖外部服务
  - 这就是 C# 里"mock HttpClient / IOpenAIClient"的同一思想：
    依赖边界（函数签名）确定后，测试端可以替换成假的实现
"""

import json  # C#: using System.Text.Json;
from pathlib import Path  # C#: System.IO.Path
from types import SimpleNamespace  # C#: 匿名对象（new { ... }）—— 快速构造假响应

import pytest  # C#: using Xunit;

from src.llm_chat import chat  # 与 call_streamer 相同的 pytest 导入方式
from src.llm_chat.cost import usage_cost


# ============================================================
# 假客户端工具（对应 C# 的 mock 替身）
# ============================================================

def make_fake_completions(create_fn):
    """构造一个假的 completions 接口，create() 由测试控制返回什么。

    C#: var fake = new Mock<IOpenAIClient>(); fake.Setup(c => c.CreateAsync(...)).Returns(fakeResp);
    结构模仿真实 SDK：client.chat.completions.create(...)
    """
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_fn)))


def make_chunk(content=None, usage=None):
    """构造一个流式 chunk（对应 SDK 的 ChatCompletionChunk）。"""
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content))],
        usage=usage,
    )


# ============================================================
# 测试 1-2: 非流式 / 流式回复（重点：生成器 + return 值）
# ============================================================

def test_non_stream_reply():
    """非流式：从假响应里取出内容 + token 用量。"""
    def fake_create(**kwargs):
        # 校验参数传对了 —— C#: Moq 的 Verify（传参断言）
        assert kwargs["model"] == "deepseek-chat"
        # 非流式调用不传 stream 参数（默认就是非流式）
        assert "stream" not in kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="你好！"))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=8, total_tokens=20),
        )

    client = make_fake_completions(fake_create)
    reply = chat.non_stream_reply(
        client, [{"role": "user", "content": "嗨"}], "deepseek-chat", 1.0
    )
    assert reply.content == "你好！"
    assert reply.prompt_tokens == 12
    assert reply.completion_tokens == 8


def test_stream_reply_yields_pieces_and_returns_usage():
    """流式：逐块 yield 文本，consume_stream 取出汇总结果。

    流式 chunk 序列（真实 API 的形状）：
      块1: content="你", usage=None
      块2: content="好", usage=None
      块3: content=None（空的角色块）, usage=None
      块4: content=None, usage=Usage(12, 8)   ← include_usage 的最后一块
    """
    final_usage = SimpleNamespace(prompt_tokens=12, completion_tokens=8, total_tokens=20)
    fake_chunks = [
        make_chunk(content="你"),
        make_chunk(content="好"),
        make_chunk(content=None),  # 空块：delta.content 为 None —— 必须跳过
        make_chunk(content=None, usage=final_usage),  # 统计在最后一块
    ]

    def fake_create(**kwargs):
        assert kwargs["stream"] is True  # 流式开关传对了
        assert kwargs["stream_options"] == {"include_usage": True}  # 显式要求返回 usage
        return iter(fake_chunks)  # 返回可迭代对象 —— SDK 返回的流就是一个迭代器

    client = make_fake_completions(fake_create)
    gen = chat.stream_reply(client, [{"role": "user", "content": "嗨"}], "deepseek-chat", 1.0)

    # 消费生成器并收集逐块文本（等价于 CLI 里 on_piece=print 实时显示）
    pieces = []
    reply = chat.consume_stream(gen, on_piece=pieces.append)
    assert pieces == ["你", "好"]  # 空块被跳过，不会 yield None
    # 生成器 return 的值通过 StopIteration.value 取出 —— CLI 靠它拿 token 统计
    assert reply.content == "你好"
    assert reply.prompt_tokens == 12
    assert reply.completion_tokens == 8


def test_stream_reply_handles_missing_usage():
    """极端情况：include_usage 没生效（没有 usage 块）—— token 记 0，不崩溃。"""
    fake_chunks = [make_chunk(content="回复")]

    def fake_create(**kwargs):
        return iter(fake_chunks)

    gen = chat.stream_reply(make_fake_completions(fake_create), [], "deepseek-chat", 1.0)
    pieces = []
    reply = chat.consume_stream(gen, on_piece=pieces.append)
    assert pieces == ["回复"]
    assert reply.prompt_tokens == 0  # 没有 usage 时的兜底值
    assert reply.content == "回复"


# ============================================================
# 测试 3: 客户端工厂
# ============================================================

def test_build_client_base_url():
    """客户端 base_url 指向 DeepSeek（OpenAI 兼容端点）。"""
    client = chat.build_client("sk-test", "https://api.deepseek.com")
    assert "api.deepseek.com" in str(client.base_url)  # base_url 属性是 URL 字符串


# ============================================================
# 测试 4-6: 消息历史（保存 / 加载 / 过滤 / 裁剪）
# ============================================================

def test_save_load_history_roundtrip(tmp_path: Path):
    """保存 → 加载，内容逐条一致（中文不转义）。"""
    messages = [
        {"role": "system", "content": "你是助手"},
        {"role": "user", "content": "你好"},
        {"role": "assistant", "content": "你好！"},
    ]
    path = str(tmp_path / "history.json")
    chat.save_history(messages, path)
    assert chat.load_history(path) == messages  # 往返一致


def test_load_history_missing_file_returns_empty():
    """文件不存在 → 返回空列表（首次使用不报错）。"""
    assert chat.load_history("not_exist.json") == []


def test_load_history_filters_invalid_roles():
    """脏数据过滤：非法角色 / 非字典条目被丢弃。"""
    tmp = Path(__file__).parent / "bad_history.json"
    tmp.write_text(
        json.dumps([
            {"role": "user", "content": "ok"},
            {"role": "hacker", "content": "恶意注入"},  # 非法角色 → 丢弃
            "not a dict",  # 非字典 → 丢弃
        ]),
        encoding="utf-8",
    )
    try:
        assert chat.load_history(str(tmp)) == [{"role": "user", "content": "ok"}]
    finally:
        tmp.unlink(missing_ok=True)  # C#: finally 里清理


def test_trim_history_keeps_system_and_recent():
    """裁剪：system 永远保留，对话只留最近 N 条。"""
    messages = [
        {"role": "system", "content": "人设"},
        {"role": "user", "content": "1"},
        {"role": "assistant", "content": "2"},
        {"role": "user", "content": "3"},
        {"role": "assistant", "content": "4"},
    ]
    trimmed = chat.trim_history(messages, 2)  # 只留最近 2 条对话
    assert [m["content"] for m in trimmed] == ["人设", "3", "4"]
    # 0 = 不限 —— 原样返回
    assert chat.trim_history(messages, 0) == messages


# ============================================================
# 测试 7-8: 费用换算（复用 Week 1 计费公式）
# ============================================================

def test_usage_cost_known_model(tmp_path: Path):
    """配置里有该模型 → 按 Week 1 公式算出费用。

    gpt-4o: in 1000/1e6*2.5 + out 500/1e6*10 = 0.0025 + 0.005 = 0.0075 元
    """
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "models": [
            {"name": "gpt-4o", "input_price_per_1m": 2.5, "output_price_per_1m": 10.0},
        ],
        "calls": [],
    }), encoding="utf-8")
    cost = usage_cost("gpt-4o", 1000, 500, str(config))
    assert cost == pytest.approx(0.0075)


def test_usage_cost_unknown_model(tmp_path: Path):
    """配置里没有该模型 → 返回 None（费用未知，不影响对话）。"""
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "models": [{"name": "gpt-4o", "input_price_per_1m": 2.5, "output_price_per_1m": 10.0}],
        "calls": [],
    }), encoding="utf-8")
    assert usage_cost("deepseek-chat", 100, 50, str(config)) is None
