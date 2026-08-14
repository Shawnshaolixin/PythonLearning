"""切片策略 —— 3 种把长文档切成检索单元（chunk）的算法 + 注册表。

C# 对照主线：
  本模块 ≈ C# 里的字符串分割服务 + 策略注册表（依赖注入）：
    IReadOnlyList<Chunk> ChunkFixed(string text, int size, int overlap)
    IReadOnlyList<Chunk> ChunkRecursive(...)   // LangChain RecursiveCharacterTextSplitter 同款思路
    IReadOnlyList<Chunk> ChunkSemantic(...)    // 句向量相似度贪心合并
  STRATEGIES 字典 ≈ C# 的 Dictionary<string, Func<...>> 注册表（运行时按名取策略）。

教学点（面试高频题「Chunk Size 怎么选？调大调小各有什么影响？」）：
  - 小切片：检索精确但上下文贫（回答时没有前后文）
  - 大切片：上下文完整但噪声多（相关段落混进不相关内容）
  - 语义切片：用句向量把「主题边界」翻译成切片边界，代价是 O(句子数) 的 Embedding
  - 切片粒度 = 检索粒度 —— 本周的 chunk_compare 实验就是量化验证
"""

import math  # C#: System.Math
import re  # C#: System.Text.RegularExpressions
from dataclasses import dataclass  # C#: record
from typing import Callable  # C#: Func<>

# C#: 依赖注入 —— 与 BgeSmallZh 同签名（List[str] -> List[List[float]]）
EmbeddingFn = Callable[[list[str]], list[list[float]]]


@dataclass
class Chunk:
    """一个切片。C#: public record Chunk(string Text, string Source, int Index, int CharStart, int CharEnd);"""

    text: str  # 切片内容
    source: str  # 来源标识（如 "game_interview_guide (pdf)"）
    index: int  # 文档内序号（C#: 0-based）
    char_start: int  # 在源文档全文中的字符偏移
    char_end: int  # 开区间终点；不变量：char_end - char_start == len(text)


@dataclass
class ChunkStats:
    """切片统计。C#: public record ChunkStats(int Count, float AvgLen, int MinLen, int MaxLen);"""

    count: int  # 切片数
    avg_len: float  # 平均字符长度
    min_len: int  # 最短
    max_len: int  # 最长


# 递归切分的分隔符优先级：从粗到细逐级降级（C#: string[] Separators）
DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n\n",  # 段落级（最高优先：语义最完整的分隔）
    "\n",  # 行级
    "。", "！", "？",  # 中文句子
    "；", "，", "、", ",",  # 中文短语
)
_SENTENCE_RE = re.compile(r"(?<=[。！？!?])")  # C#: 零宽后行断言 —— 句末标点后切分


def chunk_fixed(text: str, *, size: int = 300, overlap: int = 50, source: str = "") -> list[Chunk]:
    """固定大小切片：滑动窗口，窗口重叠 overlap 字符，末块截断到文尾。

    C#: for (int i = 0; i < text.Length; i += size - overlap) text.Substring(i, Math.Min(size, text.Length - i))
    教学点：最朴素的策略 —— 实现简单、边界完全可控（同一窗口边界可复现），
    但会把语义完整的段落拦腰切断（长答案可能被切碎，Q05 实验里见真章）。
    """
    if not text:  # C#: string.IsNullOrEmpty
        return []

    step = max(1, size - overlap)  # C#: Math.Max —— 防 overlap >= size 时死循环
    chunks: list[Chunk] = []
    n = len(text)
    i = 0  # C#: 滑动窗口起点
    while i < n:
        end = min(i + size, n)  # C#: Math.Min —— 末块截断
        chunks.append(Chunk(text=text[i:end], source=source, index=len(chunks), char_start=i, char_end=end))
        i += step
    return chunks


def _split_by(sep: str, piece: str) -> list[str]:
    """按分隔符切分并**保留分隔符**（挂在每段末尾）。

    C#: Regex.Split + 手工把捕获组拼回段尾
    为什么保留：切分后每段仍可独立成句/段（"你好。" 而非 "你好"），
    拼接回原文时也严格还原（Σ 段 == 原文，测试里有这个不变量）。
    """
    parts = re.split(f"({re.escape(sep)})", piece)  # C#: 捕获组保留分隔符
    merged: list[str] = []
    for k in range(0, len(parts) - 1, 2):  # C#: 文本与分隔符成对出现（末尾可能多一个空串）
        merged.append(parts[k] + parts[k + 1])
    if len(parts) % 2 == 1:  # 奇数个元素 = 末段后面没有分隔符（C#: parts[^1]）
        merged.append(parts[-1])
    # 过滤空串：片段以分隔符结尾时 re.split 会多出一个 ""（C#: Where(p => p.Length > 0)）
    # 必须过滤 —— 否则「xxx\n\n」永远切不出更短的片段 → 无限递归（踩过的坑）
    return [m for m in merged if m]


def _recursive_split(text: str, max_size: int, sep_index: int, separators: tuple[str, ...]) -> list[str]:
    """递归分割核心：超长片段按当前级分隔符切，切不开就降级，全用尽硬切。

    C#: 递归方法 —— if (text.Length <= maxSize) return leaf; 逐级降级
    教学点：递归字符分割（LangChain RecursiveCharacterTextSplitter 同款思路）
    —— 优先在语义最完整的分隔符处切（段落 > 行 > 句 > 短语），
    分隔符越细，切出来的碎片语义越碎。
    """
    if len(text) <= max_size:  # C#: 叶子 —— 已满足大小约束
        return [text]

    if sep_index >= len(separators):  # C#: 全部分隔符用尽
        return [text[i : i + max_size] for i in range(0, len(text), max_size)]  # C#: 硬切兜底

    sep = separators[sep_index]
    parts = _split_by(sep, text)
    if len(parts) <= 1:  # 当前级没有可用的分隔符 → 降级到下一级（C#: 递归下降）
        return _recursive_split(text, max_size, sep_index + 1, separators)

    leaves: list[str] = []
    for part in parts:  # C#: foreach —— 同级递归（每段可能仍超长）
        if part:
            leaves.extend(_recursive_split(part, max_size, sep_index, separators))
    return leaves


def chunk_recursive(
    text: str,
    *,
    max_size: int = 300,
    min_size: int = 50,
    separators: tuple[str, ...] = DEFAULT_SEPARATORS,
    source: str = "",
) -> list[Chunk]:
    """递归字符切片：按「段落 → 行 → 句 → 短语」逐级降级分割 + 小片合并。

    参数：
      max_size — 切片目标长度上限（超过才继续切）
      min_size — 低于此长度的碎片与前一叶子合并（防大量小碎片）
    教学点：真实工程里这是默认首选 —— 边界贴着语义结构（段落/句子），
    但句内长答案若超过 max_size 仍会被「，」级切碎（实验里 Q05 专门测它）。
    """
    if not text:
        return []

    leaves = _recursive_split(text, max_size, 0, separators)
    if len(leaves) <= 1:
        leaves_merged = leaves
    else:
        # 小片合并：叶子 < min_size 且与前一叶子和不超过 max_size → 并进去（C#: 防碎片）
        leaves_merged: list[str] = []
        for leaf in leaves:
            if leaves_merged and len(leaf) < min_size and len(leaves_merged[-1]) + len(leaf) <= max_size:
                leaves_merged[-1] += leaf  # C#: 追加到上一段末尾
            else:
                leaves_merged.append(leaf)

    # 生成 Chunk 并推算字符偏移：Σ 前段长度 = 本段起点（C#: 前缀和）
    chunks: list[Chunk] = []
    offset = 0  # C#: int cursor
    for i, leaf in enumerate(leaves_merged):
        chunks.append(Chunk(text=leaf, source=source, index=i, char_start=offset, char_end=offset + len(leaf)))
        offset += len(leaf)
    return chunks


def split_sentences(text: str) -> list[tuple[str, int]]:
    """中文句子切分：先按行分，再按句末标点（。！？!?）切，标点保留在句尾。

    返回 (句子, 起始字符偏移) 列表 —— 偏移指向原文，供「引用片段定位」使用
    （周 4 的引用回答需要知道句子在原文的哪里）。

    C#: Regex.Split(text, @"(?<=[。！？!?])") + 行级预处理
    教学点：
      1. 中文没有空格分词，句号/问号/感叹号是天然句子边界
         （逗号、顿号**不是** —— 语义切分依赖「句子」粒度）
      2. 空白结构（\n\n 段落分隔）在句子粒度上**被归一化丢弃** ——
         语义切分对原文是「内容无损、空白有损」，面试可主动讲这一点
    """
    sentences: list[tuple[str, int]] = []
    cursor = 0  # C#: 字符扫描游标（Python 无指针，用偏移量模拟）
    for line in text.split("\n"):  # C#: foreach (var line in text.Split('\n'))
        start = cursor  # C#: 行起始（含行首空白）
        cursor += len(line) + 1  # +1 = 换行符本身
        stripped = line.strip()
        if not stripped:
            continue
        # 行内句切分：句首偏移 = 行起始 + 前导空白长度（C#: line.Length - line.TrimStart().Length）
        inner = start + (len(line) - len(line.lstrip()))
        parts = _SENTENCE_RE.split(stripped)  # C#: 零宽后行断言切分，标点留在段尾
        for part in parts:  # C#: foreach —— 逐句带偏移返回
            if part:
                sentences.append((part, inner))
            inner += len(part)
    return sentences


def chunk_semantic(
    text: str,
    *,
    embedding_fn: EmbeddingFn | None,
    threshold: float = 0.45,
    min_size: int = 50,
    max_size: int = 400,
    source: str = "",
) -> list[Chunk]:
    """语义切片：句子向量相邻相似度 >= threshold 就合并，否则断块；碎片再兜底合并。

    教学点（本周核心算法）：
      1. 句子切分 → 一次批量句向量（embedding_fn 注入，C#: IEmbeddingFunction）
      2. bge 输出已 L2 归一化 → 余弦相似度 = 点积（省一次归一化）
      3. 贪心合并：当前块与下一句相似且不超 max_size → 追加；否则开新块
      4. 防碎片合并（与 recursive 的 min_size 合并同思路）：块 < min_size
         且并入邻居后 <= max_size → 无论相似度都合并。
         **必须做**：bge 模型下相邻句相似度整体偏低（本语料中位数 ≈ 0.43），
         纯阈值切分会产生大量 1-2 句的碎块（16~28 字），检索信号碎片化，
         长答案的块排不进 top-3（实验实测命中率 10% vs 合并后明显回升）。
      5. threshold 是实验变量不是魔法常数：0.45 是按本语料相邻句相似度
         P50~P60 校准的起点（0.75 实测过度切碎）—— 换语料必须重新校准，
         中位数/分位数就是调参信号（README 有完整记录）。
      6. max_size=400：中文 ≈ 400 token，压在 bge 512 token 上限内 ——
         超过会被 Embedding 静默截断（向量只反映前缀），必须防。
    代价：每句一次向量推理（38K 字符 ≈ 1100 句 ≈ 首跑 6~8s）—— 语义最贵。
    """
    if embedding_fn is None:
        # C#: throw new ArgumentNullException(nameof(embedding_fn)) —— fail-fast，而非 AttributeError
        raise ValueError("chunk_semantic 需要 embedding_fn（句向量来源），请传入 BgeSmallZh() 实例")

    sentences = split_sentences(text)
    if not sentences:
        return []

    # 句子列表 → 向量列表（C#: embedder.Embed(sentences.Select(s => s.Text))）
    vectors = embedding_fn([s for s, _ in sentences])

    groups: list[list[tuple[str, int]]] = [[sentences[0]]]  # C#: List<List<(string, int)>> —— 当前块
    for i in range(1, len(sentences)):
        # 余弦相似度 = 点积（两向量都已 L2 归一化）（C#: MathNet.Numerics dot）
        sim = math.fsum(a * b for a, b in zip(vectors[i - 1], vectors[i]))
        cur_len = sum(len(s) for s, _ in groups[-1])  # C#: 当前块累计长度
        if sim >= threshold and cur_len + len(sentences[i][0]) <= max_size:
            groups[-1].append(sentences[i])  # C#: 相似 → 并入当前块
        else:
            groups.append([sentences[i]])  # C#: 不相似 → 开新块

    # 防碎片合并：块 < min_size 且并入前一邻居后 <= max_size → 合并（C#: 贪心向后并）
    merged: list[list[tuple[str, int]]] = []
    for group in groups:
        if merged:
            prev_len = sum(len(s) for s, _ in merged[-1])  # C#: 前一块累计长度
            cur_len = sum(len(s) for s, _ in group)
            if cur_len < min_size and prev_len + cur_len <= max_size:
                merged[-1].extend(group)  # C#: 并入前块（保持顺序稳定）
                continue
        merged.append(group)

    # 生成 Chunk：char_start 取块内第一句的原文偏移（引用定位用），
    # char_end 按「起点 + 内容长度」推算 —— 空白被归一化丢弃，所以 char_end
    # 不是原文的精确终点（语义切分对原文有损，README 有记录）
    chunks: list[Chunk] = []
    for i, group in enumerate(merged):
        piece = "".join(s for s, _ in group)  # C#: string.Concat(group.Select(g => g.Text))
        first_start = group[0][1]
        chunks.append(Chunk(text=piece, source=source, index=i, char_start=first_start, char_end=first_start + len(piece)))
    return chunks


def summarize(chunks: list[Chunk]) -> ChunkStats:
    """切片统计聚合。C#: 聚合查询（count / avg / min / max）。"""

    if not chunks:
        return ChunkStats(count=0, avg_len=0.0, min_len=0, max_len=0)
    lengths = [len(c.text) for c in chunks]  # C#: chunks.Select(c => c.Text.Length)
    return ChunkStats(
        count=len(chunks),
        avg_len=sum(lengths) / len(lengths),  # C#: lengths.Average()
        min_len=min(lengths),
        max_len=max(lengths),
    )


# 策略注册表：名字 → 策略函数（C#: Dictionary<string, Func<...>> + 按名反射调用）
STRATEGIES: dict[str, Callable] = {
    "fixed": chunk_fixed,
    "recursive": chunk_recursive,
    "semantic": chunk_semantic,
}
