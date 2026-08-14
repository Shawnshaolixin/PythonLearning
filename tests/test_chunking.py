"""chunking 测试 —— Week 2 三种切片策略（纯逻辑测试，不碰 ChromaDB）。

C# 对照主线：
  TopicEmbedder（fake embedding）        ≈ Moq 模拟 IEmbeddingFunction（只实现 __call__）
  不变量断言（Σ 切片 == 原文）           ≈ xUnit 的属性级测试（Theory）
  pytest.raises(ValueError)              ≈ Assert.Throws<ArgumentException>

重点不变量：所有策略都必须满足 ——
  Σ chunk.text == 原文（不丢字、不增字）
  char_end - char_start == len(text)（偏移自洽）
  chunk[i].char_end == chunk[i+1].char_start（连续无缝隙）
"""

import pytest  # C#: using Xunit;

from src.rag_core.chunking import (  # C#: using rag_core.chunking;
    STRATEGIES,
    Chunk,
    chunk_fixed,
    chunk_recursive,
    chunk_semantic,
    split_sentences,
    summarize,
)
from src.rag_core.golden_qa import normalize  # C#: 空白归一化（语义切片有损比较用）


def assert_tiles(chunks: list[Chunk], original: str) -> None:
    """校验「切片无缝拼回原文」不变量（C#: 自定义断言方法）。"""
    assert "".join(c.text for c in chunks) == original  # C#: string.Concat
    for i, c in enumerate(chunks):
        assert c.char_end - c.char_start == len(c.text)  # 偏移自洽
        if i > 0:
            assert c.char_start == chunks[i - 1].char_end  # 连续无缝隙


# ============================================================
# fixed：固定大小切片
# ============================================================

def test_fixed_exact_boundaries():
    """20 字符 / size=10 / overlap=0 → 恰好 2 块，边界精确。"""
    text = "01234567890123456789"

    chunks = chunk_fixed(text, size=10, overlap=0)

    assert len(chunks) == 2
    assert chunks[0].text == "0123456789"
    assert chunks[1].text == "0123456789"
    assert (chunks[0].char_start, chunks[0].char_end) == (0, 10)
    assert (chunks[1].char_start, chunks[1].char_end) == (10, 20)
    assert_tiles(chunks, text)


def test_fixed_overlap_and_clamp():
    """size=10 / overlap=2 → 相邻块重叠 2 字符，末块截断到文尾。"""
    text = "01234567890123456789"

    chunks = chunk_fixed(text, size=10, overlap=2)

    assert len(chunks) == 3  # 0-10, 8-18, 16-20（步长 8）
    assert chunks[0].text == "0123456789"
    assert chunks[1].text == "8901234567"  # 与块 0 重叠 "89"
    assert chunks[2].text == "6789"  # 末块：text[16:20] 截断到文尾
    assert chunks[2].char_end == len(text)  # C#: 末块贴文尾
    assert chunks[0].text[8:] == chunks[1].text[:2]  # 重叠 2 字符
    # 注意：带重叠的窗口 Σ 拼接必然 ≠ 原文（重叠区重复），不调用 assert_tiles


def test_fixed_empty_text():
    """空文本 → 空切片列表（不是空块）。"""
    assert chunk_fixed("", size=10, overlap=0) == []


# ============================================================
# recursive：递归字符切片
# ============================================================

def test_recursive_paragraph_boundary():
    """两段 \n\n 分隔、各 < max_size → 恰 2 块，边界在段落处。"""
    text = "第一段内容。\n\n第二段内容。"

    chunks = chunk_recursive(text, max_size=10, min_size=3)

    assert len(chunks) == 2
    assert "第一段内容。" in chunks[0].text  # 分隔符挂在上一段末尾
    assert chunks[1].text == "第二段内容。"
    assert_tiles(chunks, text)


def test_recursive_splits_long_paragraph_by_sentence():
    """单段 > max_size → 按「。」句级拆分，每块 <= max_size。"""
    text = "你好世界。这是第二句。这是第三句。"
    max_size = 15

    chunks = chunk_recursive(text, max_size=max_size, min_size=3)

    assert len(chunks) == 3  # 三句各 5-7 字，均 <= 15
    assert all(len(c.text) <= max_size for c in chunks)  # C#: chunks.All(...)
    assert_tiles(chunks, text)


def test_recursive_min_size_merge():
    """尾部碎片 < min_size → 与前一叶子合并（防碎片）。"""
    text = "第一句好。第二句好。短。"

    chunks = chunk_recursive(text, max_size=10, min_size=5)

    assert len(chunks) == 2  # "短。"(2字) 并入前块 → 7 字
    assert chunks[1].text == "第二句好。短。"
    assert_tiles(chunks, text)


def test_recursive_tiles_text_exactly():
    """混合长文本：Σ 切片 == 原文，偏移连续无缝隙。"""
    text = (
        "第一段。这一段的句子很长，超过最大长度之后，需要在逗号这一级切开，"
        "这样切出来的碎片语义相对完整。\n\n"
        "第二段只有一行但也很长，没有句号，只有逗号，那么它最终会在逗号级被切分。"
    )

    chunks = chunk_recursive(text, max_size=30, min_size=5)

    assert len(chunks) >= 3
    assert_tiles(chunks, text)


def test_recursive_empty_text():
    """空文本 → 空列表。"""
    assert chunk_recursive("") == []


# ============================================================
# semantic：语义切片（fake embedder）
# ============================================================

class TopicEmbedder:
    """按句子是否含「甲」返回主题向量（C#: 测试替身实现 IEmbeddingFunction）。

    「甲」句 → [1,0]；其他句 → [0,1]。同主题点积 = 1，异主题 = 0。
    """

    def __call__(self, texts: list[str]) -> list[list[float]]:
        # C#: return texts.Select(t => t.Contains("甲") ? new[]{1.0,0.0} : new[]{0.0,1.0})
        return [[1.0, 0.0] if "甲" in t else [0.0, 1.0] for t in texts]


def test_semantic_merges_similar_adjacent():
    """阈值逻辑：相邻同主题句合并成一块，异主题句断块（min_size=0 隔离防碎片）。"""
    text = "甲话题第一句。甲话题第二句。乙话题第一句。甲话题第三句。"

    chunks = chunk_semantic(text, embedding_fn=TopicEmbedder(), threshold=0.5, min_size=0, max_size=800)

    assert len(chunks) == 3  # [甲+甲], [乙], [甲]
    assert chunks[0].text == "甲话题第一句。甲话题第二句。"
    assert chunks[1].text == "乙话题第一句。"
    assert chunks[2].text == "甲话题第三句。"
    assert_tiles(chunks, text)


def test_semantic_min_size_merge():
    """防碎片：碎块（< min_size）无论相似度并入前块，除非超 max_size。"""
    text = "甲话题第一句。乙话题第一句。甲话题第二句。"
    # 相似度全为 0（异主题相邻）→ 阈值切出 3 个 5 字碎块

    chunks = chunk_semantic(text, embedding_fn=TopicEmbedder(), threshold=0.5, min_size=10, max_size=800)

    assert len(chunks) == 1  # 5 + 5 + 5 全部并入（每次并入后仍 <= max_size）
    assert chunks[0].text == text

    # max_size 挡住合并：第二块并入后 14 字，第三块再并 7 字 = 21 > 16 → 独立
    chunks_capped = chunk_semantic(text, embedding_fn=TopicEmbedder(), threshold=0.5, min_size=10, max_size=16)
    assert len(chunks_capped) == 2


def test_semantic_embedder_interface():
    """任何只实现 __call__(List[str]) -> List[List[float]] 的对象都能用。"""
    text = "句子一。句子二。"

    class ConstantEmbedder:
        """全部返回同一向量 → 相似度恒 1 → 全部合并（C#: 简单替身）。"""

        def __call__(self, texts):
            return [[0.5, 0.5] for _ in texts]

    chunks = chunk_semantic(text, embedding_fn=ConstantEmbedder(), threshold=0.5)

    assert len(chunks) == 1
    assert_tiles(chunks, text)


def test_semantic_requires_embedding_fn():
    """不传 embedding_fn → 明确 ValueError（fail-fast，而非 AttributeError）。"""
    with pytest.raises(ValueError, match="embedding_fn"):
        chunk_semantic("句子一。句子二。", embedding_fn=None)


def test_semantic_max_size_stops_merge():
    """max_size 上限：相似句也要受块大小约束。"""
    text = "甲甲甲甲甲甲甲甲甲甲。甲甲甲甲甲甲甲甲甲甲。"

    chunks = chunk_semantic(text, embedding_fn=TopicEmbedder(), threshold=0.5, max_size=12)

    assert len(chunks) == 2  # 每句 11 字 > 12/2 → 第二句塞不下，必须开新块
    assert_tiles(chunks, text)


def test_semantic_empty_text():
    """空文本 → 空列表（不调 embedding）。"""
    assert chunk_semantic("", embedding_fn=TopicEmbedder()) == []


# ============================================================
# 句子切分 + 注册表 + 汇总
# ============================================================

def test_split_sentences_chinese():
    """中文句切分：。！？都是句末标点（保留在句尾），逗号顿号不切，偏移指向原文。"""
    text = "第一句。第二句！第三句？半句，加顿号、不切。\n\n新行第四句。"

    sentences = split_sentences(text)

    # 「第三句？」单独成句 —— ？也是句末标点；「半句，加顿号、不切。」里逗号顿号不切分
    assert [s for s, _ in sentences] == ["第一句。", "第二句！", "第三句？", "半句，加顿号、不切。", "新行第四句。"]
    # 偏移指向原文：text[offset:offset+len] == 句子（C#: 引用定位的准确性）
    for s, offset in sentences:
        assert text[offset : offset + len(s)] == s
    assert sentences[0][1] == 0


def test_registry_keys():
    """注册表含全部三种策略。"""
    assert set(STRATEGIES.keys()) == {"fixed", "recursive", "semantic"}


def test_all_strategies_tile_text():
    """同一中文输入过三策略（semantic 用 fake）：内容无损拼回原文，统计字段齐全。"""
    text = "第一段。这一段比较长，用来验证三种策略都能完整拼回原文。\n\n第二段！结尾。"

    # 注意：fixed 的 overlap=0 —— 带重叠的窗口 Σ 拼接必然 ≠ 原文（重叠区重复），
    # 无缝拼回原文的不变量只在无重叠时成立（overlap 的正确性由
    # test_fixed_overlap_and_clamp 单独验证）
    fixed = chunk_fixed(text, size=8, overlap=0)
    recursive = chunk_recursive(text, max_size=12, min_size=3)
    semantic = chunk_semantic(text, embedding_fn=TopicEmbedder(), threshold=0.5)

    assert_tiles(fixed, text)
    assert_tiles(recursive, text)
    # semantic 对含空白的原文是「内容无损、空白有损」：\n\n 段落分隔被归一化丢弃
    # （split_sentences 按行切分），所以放宽为空白归一化后相等（C#: 归一化比较）
    assert normalize("".join(c.text for c in semantic)) == normalize(text)
    assert semantic[0].char_start == 0

    for chunks in (fixed, recursive, semantic):
        stats = summarize(chunks)
        assert stats.count == len(chunks)
        assert stats.avg_len > 0
        assert stats.min_len <= stats.max_len
